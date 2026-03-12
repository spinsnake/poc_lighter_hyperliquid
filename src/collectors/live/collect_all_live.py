from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import websockets

from src.collectors.non_live.common import (
    DATA_ROOT,
    append_jsonl,
    date_slug,
    ensure_dir,
    iso_utc,
    load_csv_rows,
    timestamp_slug,
    write_csv,
)
from src.collectors.non_live.hyperliquid_public import fetch_meta_and_asset_ctxs, fetch_predicted_fundings
from src.storage.r2_config import load_config
from src.storage.r2_uploader import R2Uploader


LIGHTER_WS_URL = "wss://mainnet.zklighter.elliot.ai/stream"
HYPERLIQUID_WS_URL = "wss://api.hyperliquid.xyz/ws"
MAX_RECENT_TRADES = 5000
MAX_RECENT_TRADE_AGGREGATES = 5000


@dataclass
class LiveState:
    lighter_market_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    lighter_books: dict[str, dict[str, Any]] = field(default_factory=dict)
    lighter_book_levels: dict[str, dict[str, dict[float, float]]] = field(default_factory=dict)
    hyperliquid_ctx: dict[str, dict[str, Any]] = field(default_factory=dict)
    hyperliquid_predicted: dict[str, dict[str, Any]] = field(default_factory=dict)
    hyperliquid_books: dict[str, dict[str, Any]] = field(default_factory=dict)
    recent_trades: list[dict[str, object]] = field(default_factory=list)
    recent_trade_aggregates: list[dict[str, object]] = field(default_factory=list)
    trade_aggregate_buckets: dict[tuple[str, str, str], dict[str, object]] = field(default_factory=dict)
    pending_funding_rows: list[dict[str, object]] = field(default_factory=list)
    pending_book_rows: list[dict[str, object]] = field(default_factory=list)
    pending_trade_aggregate_rows: list[dict[str, object]] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect live funding, price, BBO/depth summaries, and 1-second trade aggregates "
            "from Lighter and Hyperliquid."
        )
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated shared symbols to track. If omitted, defaults to all shared symbols.",
    )
    parser.add_argument(
        "--all-shared",
        action="store_true",
        help="Track all shared symbols from data/reference/shared_markets_latest.csv.",
    )
    parser.add_argument(
        "--duration-sec",
        type=int,
        default=0,
        help="How long to run. 0 means run until stopped.",
    )
    parser.add_argument(
        "--flush-sec",
        type=int,
        default=1,
        help="How often to build 1-second funding/book summaries and latest CSVs.",
    )
    parser.add_argument(
        "--hyperliquid-poll-sec",
        type=int,
        default=1,
        help="Polling interval for Hyperliquid funding/context snapshots.",
    )
    parser.add_argument(
        "--parquet-batch-sec",
        type=int,
        default=60,
        help="How often to write summary batches to Parquet.",
    )
    parser.add_argument(
        "--trade-aggregate-sec",
        type=int,
        default=1,
        help="Trade aggregation window in seconds. Use 1 for the current POC mode.",
    )
    parser.add_argument(
        "--write-raw",
        action="store_true",
        help="Also write raw websocket and REST payloads to JSONL for debugging.",
    )
    parser.add_argument(
        "--write-r2",
        action="store_true",
        help="Upload processed outputs to Cloudflare R2 using config.yaml.",
    )
    parser.add_argument(
        "--r2-config",
        default="config.yaml",
        help="Path to R2 YAML config file. Used with --write-r2.",
    )
    parser.add_argument(
        "--parquet-compression",
        default="zstd",
        help="Compression codec for Parquet output. Defaults to zstd.",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=DATA_ROOT,
        help="Base output directory. Defaults to <repo>/data.",
    )
    return parser.parse_args()


def safe_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def iso_utc_precise(ts: datetime | None = None) -> str:
    value = ts or datetime.now(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def ms_to_datetime_utc(timestamp_ms: object) -> datetime | None:
    if timestamp_ms in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(timestamp_ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def ms_to_iso_utc(timestamp_ms: object) -> str | None:
    timestamp = ms_to_datetime_utc(timestamp_ms)
    return iso_utc_precise(timestamp) if timestamp else None


def precise_timestamp_slug(ts: datetime | None = None) -> str:
    value = ts or datetime.now(timezone.utc)
    return value.strftime("%Y%m%dT%H%M%S%fZ")


def bucket_start_utc(dt: datetime, bucket_sec: int) -> datetime:
    epoch_sec = int(dt.timestamp())
    bucket_epoch = epoch_sec - (epoch_sec % bucket_sec)
    return datetime.fromtimestamp(bucket_epoch, tz=timezone.utc)


def append_recent_trade(state: LiveState, trade_row: dict[str, object]) -> None:
    state.recent_trades.append(trade_row)
    overflow = len(state.recent_trades) - MAX_RECENT_TRADES
    if overflow > 0:
        del state.recent_trades[:overflow]


def append_recent_trade_aggregate(state: LiveState, aggregate_row: dict[str, object]) -> None:
    state.recent_trade_aggregates.append(aggregate_row)
    overflow = len(state.recent_trade_aggregates) - MAX_RECENT_TRADE_AGGREGATES
    if overflow > 0:
        del state.recent_trade_aggregates[:overflow]


def resolve_symbol_market_map(args: argparse.Namespace) -> dict[str, int]:
    shared_csv = args.out_root / "reference" / "shared_markets_latest.csv"
    shared_rows = load_csv_rows(shared_csv)
    market_map = {
        row["symbol_canonical"]: int(row["lighter_market_id"])
        for row in shared_rows
        if row.get("symbol_canonical") and row.get("lighter_market_id")
    }

    requested = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    if args.all_shared or not requested:
        return {symbol: market_map[symbol] for symbol in sorted(market_map)}

    missing = [symbol for symbol in requested if symbol not in market_map]
    if missing:
        raise SystemExit(
            "Missing shared symbol(s): "
            + ", ".join(missing)
            + ". Collect reference data first or use symbols that exist in shared_markets_latest.csv."
        )
    return {symbol: market_map[symbol] for symbol in requested}


def best_book_metrics(
    bids: list[dict[str, Any]],
    asks: list[dict[str, Any]],
    bid_price_key: str,
    ask_price_key: str,
    size_key: str,
) -> dict[str, float | None]:
    parsed_bids = [(safe_float(item.get(bid_price_key)), safe_float(item.get(size_key))) for item in bids]
    parsed_asks = [(safe_float(item.get(ask_price_key)), safe_float(item.get(size_key))) for item in asks]
    parsed_bids = [(px, sz) for px, sz in parsed_bids if px is not None and sz is not None]
    parsed_asks = [(px, sz) for px, sz in parsed_asks if px is not None and sz is not None]

    best_bid = max((px for px, _ in parsed_bids), default=None)
    best_ask = min((px for px, _ in parsed_asks), default=None)
    if best_bid is None or best_ask is None or best_bid <= 0 or best_ask <= 0:
        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid_price": None,
            "top_spread_bps": None,
            "bid_depth_5bps_usd": None,
            "ask_depth_5bps_usd": None,
            "bid_depth_10bps_usd": None,
            "ask_depth_10bps_usd": None,
            "bid_depth_20bps_usd": None,
            "ask_depth_20bps_usd": None,
        }

    mid_price = (best_bid + best_ask) / 2
    top_spread_bps = ((best_ask - best_bid) / mid_price) * 10000

    def depth_usd(levels: list[tuple[float, float]], bps: int) -> float:
        total = 0.0
        for price, size in levels:
            if abs(price - mid_price) / mid_price * 10000 <= bps:
                total += price * size
        return total

    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid_price,
        "top_spread_bps": top_spread_bps,
        "bid_depth_5bps_usd": depth_usd(parsed_bids, 5),
        "ask_depth_5bps_usd": depth_usd(parsed_asks, 5),
        "bid_depth_10bps_usd": depth_usd(parsed_bids, 10),
        "ask_depth_10bps_usd": depth_usd(parsed_asks, 10),
        "bid_depth_20bps_usd": depth_usd(parsed_bids, 20),
        "ask_depth_20bps_usd": depth_usd(parsed_asks, 20),
    }


def flatten_hyperliquid_predicted(predicted_rows: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in predicted_rows:
        if not isinstance(item, list) or len(item) != 2:
            continue
        symbol, venues = item
        if not isinstance(symbol, str) or not isinstance(venues, list):
            continue
        for venue_name, payload in venues:
            if venue_name == "HlPerp" and isinstance(payload, dict):
                result[symbol] = payload
                break
    return result


def apply_lighter_book_update(
    state: LiveState,
    symbol: str,
    order_book: dict[str, Any],
    message_type: str | None,
) -> None:
    is_snapshot = message_type == "subscribed/order_book" or order_book.get("begin_nonce") == 0
    levels = state.lighter_book_levels.setdefault(symbol, {"bids": {}, "asks": {}})
    if is_snapshot:
        levels["bids"] = {}
        levels["asks"] = {}

    for side_name in ("bids", "asks"):
        side_levels = levels[side_name]
        for item in order_book.get(side_name, []):
            price = safe_float(item.get("price"))
            size = safe_float(item.get("size"))
            if price is None or size is None:
                continue
            if size <= 0:
                side_levels.pop(price, None)
            else:
                side_levels[price] = size

    bids = [{"price": price, "size": size} for price, size in sorted(levels["bids"].items(), reverse=True)]
    asks = [{"price": price, "size": size} for price, size in sorted(levels["asks"].items())]
    state.lighter_books[symbol] = best_book_metrics(
        bids=bids,
        asks=asks,
        bid_price_key="price",
        ask_price_key="price",
        size_key="size",
    )


def extract_lighter_trade_rows(payload: dict[str, Any], market_id_to_symbol: dict[int, str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for trades_key in ("trades", "liquidation_trades"):
        items = payload.get(trades_key, [])
        if not isinstance(items, list):
            continue
        for item in items:
            market_id_value = item.get("market_id")
            if market_id_value is None:
                continue
            try:
                market_id = int(market_id_value)
            except (TypeError, ValueError):
                continue
            symbol = market_id_to_symbol.get(market_id)
            if not symbol:
                continue
            price = safe_float(item.get("price"))
            size = safe_float(item.get("size"))
            usd_amount = safe_float(item.get("usd_amount"))
            timestamp_ms = item.get("timestamp")
            rows.append(
                {
                    "event_time_utc": ms_to_iso_utc(timestamp_ms),
                    "event_time_ms": timestamp_ms,
                    "symbol": symbol,
                    "venue": "lighter",
                    "trade_type": item.get("type") or trades_key.rstrip("s"),
                    "side": None,
                    "price": price,
                    "size": size,
                    "notional_usd": usd_amount if usd_amount is not None else (price * size if price and size else None),
                    "trade_id": item.get("trade_id"),
                    "tx_hash": item.get("tx_hash"),
                    "is_liquidation": item.get("type") == "liquidation",
                }
            )
    return rows


def extract_hyperliquid_trade_rows(payload: dict[str, Any]) -> list[dict[str, object]]:
    items = payload.get("data", [])
    if not isinstance(items, list):
        return []

    rows: list[dict[str, object]] = []
    for item in items:
        symbol = item.get("coin")
        price = safe_float(item.get("px"))
        size = safe_float(item.get("sz"))
        timestamp_ms = item.get("time")
        rows.append(
            {
                "event_time_utc": ms_to_iso_utc(timestamp_ms),
                "event_time_ms": timestamp_ms,
                "symbol": symbol,
                "venue": "hyperliquid",
                "trade_type": "trade",
                "side": item.get("side"),
                "price": price,
                "size": size,
                "notional_usd": price * size if price is not None and size is not None else None,
                "trade_id": item.get("tid"),
                "tx_hash": item.get("hash"),
                "is_liquidation": False,
            }
        )
    return rows


def update_trade_aggregate_bucket(state: LiveState, trade_row: dict[str, object], bucket_sec: int) -> None:
    trade_time = ms_to_datetime_utc(trade_row.get("event_time_ms")) or parse_iso_utc(trade_row.get("event_time_utc"))
    if trade_time is None:
        trade_time = datetime.now(timezone.utc)
    bucket_time = bucket_start_utc(trade_time, bucket_sec)
    bucket_time_utc = iso_utc(bucket_time)
    key = (bucket_time_utc, str(trade_row.get("symbol")), str(trade_row.get("venue")))

    price = safe_float(trade_row.get("price"))
    size = safe_float(trade_row.get("size"))
    notional_usd = safe_float(trade_row.get("notional_usd"))

    aggregate = state.trade_aggregate_buckets.setdefault(
        key,
        {
            "bucket_time_utc": bucket_time_utc,
            "symbol": trade_row.get("symbol"),
            "venue": trade_row.get("venue"),
            "trade_count": 0,
            "liquidation_count": 0,
            "total_size": 0.0,
            "total_notional_usd": 0.0,
            "open_price": price,
            "high_price": price,
            "low_price": price,
            "close_price": price,
            "vwap_numerator": 0.0,
            "vwap_denominator": 0.0,
        },
    )

    aggregate["trade_count"] += 1
    aggregate["liquidation_count"] += 1 if trade_row.get("is_liquidation") else 0

    if price is not None:
        if aggregate["open_price"] is None:
            aggregate["open_price"] = price
        aggregate["close_price"] = price
        aggregate["high_price"] = price if aggregate["high_price"] is None else max(aggregate["high_price"], price)
        aggregate["low_price"] = price if aggregate["low_price"] is None else min(aggregate["low_price"], price)

    if size is not None:
        aggregate["total_size"] += size
    if notional_usd is not None:
        aggregate["total_notional_usd"] += notional_usd
        if price is not None and size is not None:
            aggregate["vwap_numerator"] += price * size
            aggregate["vwap_denominator"] += size


def drain_closed_trade_aggregates(state: LiveState, bucket_sec: int) -> list[dict[str, object]]:
    if not state.trade_aggregate_buckets:
        return []

    current_bucket = bucket_start_utc(datetime.now(timezone.utc), bucket_sec)
    ready_keys = [
        key
        for key, aggregate in state.trade_aggregate_buckets.items()
        if parse_iso_utc(str(aggregate.get("bucket_time_utc"))) and parse_iso_utc(str(aggregate.get("bucket_time_utc"))) < current_bucket
    ]
    drained_rows: list[dict[str, object]] = []
    for key in sorted(ready_keys):
        aggregate = state.trade_aggregate_buckets.pop(key)
        vwap_denominator = safe_float(aggregate.get("vwap_denominator")) or 0.0
        drained_rows.append(
            {
                "bucket_time_utc": aggregate.get("bucket_time_utc"),
                "symbol": aggregate.get("symbol"),
                "venue": aggregate.get("venue"),
                "trade_count": aggregate.get("trade_count"),
                "liquidation_count": aggregate.get("liquidation_count"),
                "total_size": round(safe_float(aggregate.get("total_size")) or 0.0, 12),
                "total_notional_usd": round(safe_float(aggregate.get("total_notional_usd")) or 0.0, 12),
                "vwap_price": (
                    round((safe_float(aggregate.get("vwap_numerator")) or 0.0) / vwap_denominator, 12)
                    if vwap_denominator > 0
                    else None
                ),
                "open_price": aggregate.get("open_price"),
                "high_price": aggregate.get("high_price"),
                "low_price": aggregate.get("low_price"),
                "close_price": aggregate.get("close_price"),
            }
        )
    return drained_rows


def build_funding_rows(symbols: list[str], state: LiveState) -> list[dict[str, object]]:
    snapshot_at = iso_utc()
    rows: list[dict[str, object]] = []
    for symbol in symbols:
        lighter = state.lighter_market_stats.get(symbol, {})
        lighter_book = state.lighter_books.get(symbol, {})
        hyper_ctx = state.hyperliquid_ctx.get(symbol, {})
        hyper_pred = state.hyperliquid_predicted.get(symbol, {})
        hyper_book = state.hyperliquid_books.get(symbol, {})

        rows.append(
            {
                "snapshot_at_utc": snapshot_at,
                "symbol": symbol,
                "venue": "lighter",
                "current_funding_rate": lighter.get("current_funding_rate"),
                "predicted_or_reference_funding_rate": lighter.get("funding_rate"),
                "next_funding_time": lighter.get("funding_timestamp"),
                "index_price": lighter.get("index_price"),
                "mark_price": lighter.get("mark_price"),
                "mid_price": lighter_book.get("mid_price"),
                "last_trade_price": lighter.get("last_trade_price"),
                "open_interest": lighter.get("open_interest"),
            }
        )
        rows.append(
            {
                "snapshot_at_utc": snapshot_at,
                "symbol": symbol,
                "venue": "hyperliquid",
                "current_funding_rate": hyper_ctx.get("funding"),
                "predicted_or_reference_funding_rate": hyper_pred.get("fundingRate"),
                "next_funding_time": hyper_pred.get("nextFundingTime"),
                "index_price": hyper_ctx.get("oraclePx"),
                "mark_price": hyper_ctx.get("markPx"),
                "mid_price": hyper_ctx.get("midPx") or hyper_book.get("mid_price"),
                "last_trade_price": None,
                "open_interest": hyper_ctx.get("openInterest"),
            }
        )
    return rows


def build_book_rows(symbols: list[str], state: LiveState) -> list[dict[str, object]]:
    snapshot_at = iso_utc()
    rows: list[dict[str, object]] = []
    for symbol in symbols:
        rows.append(
            {
                "snapshot_at_utc": snapshot_at,
                "symbol": symbol,
                "venue": "lighter",
                **state.lighter_books.get(symbol, {}),
            }
        )
        rows.append(
            {
                "snapshot_at_utc": snapshot_at,
                "symbol": symbol,
                "venue": "hyperliquid",
                **state.hyperliquid_books.get(symbol, {}),
            }
        )
    return rows


def maybe_append_jsonl(path: Path | None, payload: object) -> None:
    if path is not None:
        append_jsonl(path, payload)


def write_parquet_batch(
    base_dir: Path,
    prefix: str,
    rows: list[dict[str, object]],
    timestamp_field: str,
    compression: str,
) -> list[Path]:
    if not rows:
        return []

    grouped_rows: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        timestamp_value = str(row.get(timestamp_field) or "")
        day = timestamp_value[:10] if len(timestamp_value) >= 10 else date_slug()
        grouped_rows.setdefault(day, []).append(row)

    written_paths: list[Path] = []
    for day, day_rows in grouped_rows.items():
        out_dir = base_dir / f"date={day}"
        ensure_dir(out_dir)
        out_path = out_dir / f"{prefix}_{precise_timestamp_slug()}.parquet"
        frame = pd.DataFrame(day_rows)
        for column in frame.columns:
            non_null = frame[column].dropna()
            if non_null.empty:
                continue
            numeric = pd.to_numeric(frame[column], errors="coerce")
            if int(numeric.notna().sum()) == int(non_null.shape[0]):
                frame[column] = numeric
                continue
            if not non_null.map(lambda value: isinstance(value, str)).all():
                frame[column] = frame[column].map(
                    lambda value: None if value is None or pd.isna(value) else str(value)
                )
        frame.to_parquet(out_path, index=False, compression=compression)
        written_paths.append(out_path)
    return written_paths


async def maybe_upload_to_r2(
    uploader: R2Uploader | None,
    paths: list[Path],
) -> None:
    if uploader is None or not paths:
        return
    try:
        uploaded_keys = await asyncio.to_thread(uploader.upload_files, paths)
        if uploaded_keys:
            print(f"[r2] uploaded {len(uploaded_keys)} object(s)")
    except Exception as exc:
        print(f"[r2] upload error: {exc!r}")


def trade_row_is_after_start(trade_row: dict[str, object], collection_started_at: datetime) -> bool:
    trade_time = ms_to_datetime_utc(trade_row.get("event_time_ms")) or parse_iso_utc(trade_row.get("event_time_utc"))
    if trade_time is None:
        return True
    return trade_time >= collection_started_at


async def lighter_market_stats_task(
    state: LiveState,
    symbols: set[str],
    raw_path: Path | None,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            async with websockets.connect(LIGHTER_WS_URL, max_size=None) as ws:
                await ws.send(json.dumps({"type": "subscribe", "channel": "market_stats/all"}))
                while not stop_event.is_set():
                    payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                    maybe_append_jsonl(raw_path, payload)
                    if payload.get("channel") != "market_stats:all":
                        continue
                    market_stats = payload.get("market_stats", {})
                    for item in market_stats.values():
                        symbol = item.get("symbol")
                        if symbol in symbols:
                            state.lighter_market_stats[symbol] = item
        except Exception as exc:
            print(f"[lighter_market_stats] reconnect after error: {exc!r}")
            await asyncio.sleep(2)


async def lighter_order_books_task(
    state: LiveState,
    symbol_market_map: dict[str, int],
    raw_dir: Path | None,
    stop_event: asyncio.Event,
) -> None:
    channel_to_symbol = {f"order_book:{market_id}": symbol for symbol, market_id in symbol_market_map.items()}
    raw_paths = {symbol: raw_dir / f"symbol={symbol}.jsonl" for symbol in symbol_market_map} if raw_dir else {}

    while not stop_event.is_set():
        try:
            async with websockets.connect(LIGHTER_WS_URL, max_size=None) as ws:
                for symbol, market_id in symbol_market_map.items():
                    await ws.send(json.dumps({"type": "subscribe", "channel": f"order_book/{market_id}"}))
                while not stop_event.is_set():
                    payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                    channel = payload.get("channel")
                    symbol = channel_to_symbol.get(channel)
                    if not symbol:
                        continue
                    maybe_append_jsonl(raw_paths.get(symbol), payload)
                    order_book = payload.get("order_book")
                    if isinstance(order_book, dict):
                        apply_lighter_book_update(state, symbol, order_book, payload.get("type"))
        except Exception as exc:
            print(f"[lighter_order_books] reconnect after error: {exc!r}")
            await asyncio.sleep(2)


async def lighter_trades_task(
    state: LiveState,
    symbol_market_map: dict[str, int],
    raw_dir: Path | None,
    bucket_sec: int,
    collection_started_at: datetime,
    stop_event: asyncio.Event,
) -> None:
    channel_to_symbol = {f"trade:{market_id}": symbol for symbol, market_id in symbol_market_map.items()}
    market_id_to_symbol = {market_id: symbol for symbol, market_id in symbol_market_map.items()}
    raw_paths = {symbol: raw_dir / f"symbol={symbol}.jsonl" for symbol in symbol_market_map} if raw_dir else {}

    while not stop_event.is_set():
        try:
            async with websockets.connect(LIGHTER_WS_URL, max_size=None) as ws:
                for symbol, market_id in symbol_market_map.items():
                    await ws.send(json.dumps({"type": "subscribe", "channel": f"trade/{market_id}"}))
                while not stop_event.is_set():
                    payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                    channel = payload.get("channel")
                    symbol = channel_to_symbol.get(channel)
                    if symbol:
                        maybe_append_jsonl(raw_paths.get(symbol), payload)
                    for row in extract_lighter_trade_rows(payload, market_id_to_symbol):
                        if not trade_row_is_after_start(row, collection_started_at):
                            continue
                        append_recent_trade(state, row)
                        update_trade_aggregate_bucket(state, row, bucket_sec)
        except Exception as exc:
            print(f"[lighter_trades] reconnect after error: {exc!r}")
            await asyncio.sleep(2)


async def hyperliquid_context_poll_task(
    state: LiveState,
    symbols: set[str],
    meta_raw_path: Path | None,
    predicted_raw_path: Path | None,
    poll_sec: int,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            meta_and_asset_ctxs = await asyncio.to_thread(fetch_meta_and_asset_ctxs)
            predicted = await asyncio.to_thread(fetch_predicted_fundings)

            maybe_append_jsonl(meta_raw_path, {"collected_at_utc": iso_utc(), "payload": meta_and_asset_ctxs})
            maybe_append_jsonl(predicted_raw_path, {"collected_at_utc": iso_utc(), "payload": predicted})

            if isinstance(meta_and_asset_ctxs, list) and len(meta_and_asset_ctxs) == 2:
                meta = meta_and_asset_ctxs[0] or {}
                asset_ctxs = meta_and_asset_ctxs[1] or []
                universe = meta.get("universe", [])
                for universe_item, asset_ctx in zip(universe, asset_ctxs):
                    symbol = universe_item.get("name")
                    if symbol in symbols:
                        state.hyperliquid_ctx[symbol] = asset_ctx

            predicted_map = flatten_hyperliquid_predicted(predicted if isinstance(predicted, list) else [])
            for symbol, payload in predicted_map.items():
                if symbol in symbols:
                    state.hyperliquid_predicted[symbol] = payload
        except Exception as exc:
            print(f"[hyperliquid_context_poll] retry after error: {exc!r}")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_sec)
        except asyncio.TimeoutError:
            pass


async def hyperliquid_l2_books_task(
    state: LiveState,
    symbols: list[str],
    raw_dir: Path | None,
    stop_event: asyncio.Event,
) -> None:
    raw_paths = {symbol: raw_dir / f"symbol={symbol}.jsonl" for symbol in symbols} if raw_dir else {}

    while not stop_event.is_set():
        try:
            async with websockets.connect(HYPERLIQUID_WS_URL, max_size=None) as ws:
                for symbol in symbols:
                    await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "l2Book", "coin": symbol}}))
                while not stop_event.is_set():
                    payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                    if payload.get("channel") != "l2Book":
                        continue
                    data = payload.get("data", {})
                    symbol = data.get("coin")
                    if symbol not in symbols:
                        continue
                    maybe_append_jsonl(raw_paths.get(symbol), payload)
                    levels = data.get("levels")
                    if isinstance(levels, list) and len(levels) == 2:
                        state.hyperliquid_books[symbol] = best_book_metrics(
                            bids=levels[0] or [],
                            asks=levels[1] or [],
                            bid_price_key="px",
                            ask_price_key="px",
                            size_key="sz",
                        )
        except Exception as exc:
            print(f"[hyperliquid_l2_books] reconnect after error: {exc!r}")
            await asyncio.sleep(2)


async def hyperliquid_trades_task(
    state: LiveState,
    symbols: list[str],
    raw_dir: Path | None,
    bucket_sec: int,
    collection_started_at: datetime,
    stop_event: asyncio.Event,
) -> None:
    raw_paths = {symbol: raw_dir / f"symbol={symbol}.jsonl" for symbol in symbols} if raw_dir else {}

    while not stop_event.is_set():
        try:
            async with websockets.connect(HYPERLIQUID_WS_URL, max_size=None) as ws:
                for symbol in symbols:
                    await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "trades", "coin": symbol}}))
                while not stop_event.is_set():
                    payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                    if payload.get("channel") != "trades":
                        continue
                    rows = extract_hyperliquid_trade_rows(payload)
                    if rows:
                        symbol = str(rows[0]["symbol"])
                        maybe_append_jsonl(raw_paths.get(symbol), payload)
                    for row in rows:
                        if not trade_row_is_after_start(row, collection_started_at):
                            continue
                        append_recent_trade(state, row)
                        update_trade_aggregate_bucket(state, row, bucket_sec)
        except Exception as exc:
            print(f"[hyperliquid_trades] reconnect after error: {exc!r}")
            await asyncio.sleep(2)


async def flush_processed_outputs(
    state: LiveState,
    symbols: list[str],
    out_root: Path,
    flush_sec: int,
    parquet_batch_sec: int,
    bucket_sec: int,
    compression: str,
    r2_uploader: R2Uploader | None,
    stop_event: asyncio.Event,
) -> None:
    latest_funding_csv = out_root / "processed" / "live_funding_snapshots_latest.csv"
    latest_book_csv = out_root / "processed" / "live_book_snapshots_latest.csv"
    latest_trade_csv = out_root / "processed" / "live_trade_tape_latest.csv"
    latest_trade_aggregate_csv = out_root / "processed" / "live_trade_aggregates_latest.csv"

    funding_base_dir = out_root / "processed" / "live" / "funding_snapshots"
    book_base_dir = out_root / "processed" / "live" / "book_snapshots"
    trade_aggregate_base_dir = out_root / "processed" / "live" / "trade_aggregates"

    funding_fieldnames = [
        "snapshot_at_utc",
        "symbol",
        "venue",
        "current_funding_rate",
        "predicted_or_reference_funding_rate",
        "next_funding_time",
        "index_price",
        "mark_price",
        "mid_price",
        "last_trade_price",
        "open_interest",
    ]
    book_fieldnames = [
        "snapshot_at_utc",
        "symbol",
        "venue",
        "best_bid",
        "best_ask",
        "mid_price",
        "top_spread_bps",
        "bid_depth_5bps_usd",
        "ask_depth_5bps_usd",
        "bid_depth_10bps_usd",
        "ask_depth_10bps_usd",
        "bid_depth_20bps_usd",
        "ask_depth_20bps_usd",
    ]
    trade_fieldnames = [
        "event_time_utc",
        "event_time_ms",
        "symbol",
        "venue",
        "trade_type",
        "side",
        "price",
        "size",
        "notional_usd",
        "trade_id",
        "tx_hash",
        "is_liquidation",
    ]
    trade_aggregate_fieldnames = [
        "bucket_time_utc",
        "symbol",
        "venue",
        "trade_count",
        "liquidation_count",
        "total_size",
        "total_notional_usd",
        "vwap_price",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
    ]

    last_parquet_flush = datetime.now(timezone.utc)

    while not stop_event.is_set():
        funding_rows = build_funding_rows(symbols, state)
        book_rows = build_book_rows(symbols, state)
        closed_trade_aggregates = drain_closed_trade_aggregates(state, bucket_sec)

        if funding_rows:
            state.pending_funding_rows.extend(funding_rows)
            write_csv(latest_funding_csv, funding_fieldnames, funding_rows)
        if book_rows:
            state.pending_book_rows.extend(book_rows)
            write_csv(latest_book_csv, book_fieldnames, book_rows)

        if closed_trade_aggregates:
            state.pending_trade_aggregate_rows.extend(closed_trade_aggregates)
            for row in closed_trade_aggregates:
                append_recent_trade_aggregate(state, row)

        if state.recent_trades:
            write_csv(latest_trade_csv, trade_fieldnames, state.recent_trades)
        if state.recent_trade_aggregates:
            write_csv(latest_trade_aggregate_csv, trade_aggregate_fieldnames, state.recent_trade_aggregates)

        now = datetime.now(timezone.utc)
        if (now - last_parquet_flush).total_seconds() >= parquet_batch_sec:
            written_paths = []
            written_paths.extend(
                write_parquet_batch(
                    funding_base_dir,
                    "funding_snapshots",
                    state.pending_funding_rows,
                    "snapshot_at_utc",
                    compression,
                )
            )
            written_paths.extend(
                write_parquet_batch(
                    book_base_dir,
                    "book_snapshots",
                    state.pending_book_rows,
                    "snapshot_at_utc",
                    compression,
                )
            )
            written_paths.extend(
                write_parquet_batch(
                    trade_aggregate_base_dir,
                    "trade_aggregates",
                    state.pending_trade_aggregate_rows,
                    "bucket_time_utc",
                    compression,
                )
            )
            await maybe_upload_to_r2(
                r2_uploader,
                written_paths + [latest_funding_csv, latest_book_csv, latest_trade_csv, latest_trade_aggregate_csv],
            )
            state.pending_funding_rows.clear()
            state.pending_book_rows.clear()
            state.pending_trade_aggregate_rows.clear()
            last_parquet_flush = now

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=flush_sec)
        except asyncio.TimeoutError:
            pass

    for row in drain_closed_trade_aggregates(state, bucket_sec):
        state.pending_trade_aggregate_rows.append(row)
        append_recent_trade_aggregate(state, row)

    written_paths = []
    written_paths.extend(
        write_parquet_batch(
            funding_base_dir,
            "funding_snapshots",
            state.pending_funding_rows,
            "snapshot_at_utc",
            compression,
        )
    )
    written_paths.extend(
        write_parquet_batch(
            book_base_dir,
            "book_snapshots",
            state.pending_book_rows,
            "snapshot_at_utc",
            compression,
        )
    )
    written_paths.extend(
        write_parquet_batch(
            trade_aggregate_base_dir,
            "trade_aggregates",
            state.pending_trade_aggregate_rows,
            "bucket_time_utc",
            compression,
        )
    )
    await maybe_upload_to_r2(
        r2_uploader,
        written_paths + [latest_funding_csv, latest_book_csv, latest_trade_csv, latest_trade_aggregate_csv],
    )


async def run_live_collect(args: argparse.Namespace) -> None:
    symbol_market_map = resolve_symbol_market_map(args)
    symbols = list(symbol_market_map)
    symbols_set = set(symbols)
    state = LiveState()
    collection_started_at = datetime.now(timezone.utc)
    session_stamp = timestamp_slug()
    day = date_slug()
    out_root = args.out_root
    r2_uploader = None
    if args.write_r2:
        app_config = load_config(args.r2_config)
        r2_uploader = R2Uploader(app_config.r2, out_root)

    lighter_market_stats_raw = (
        out_root / "raw" / "lighter" / "ws" / "market_stats" / f"date={day}" / f"market_stats_all_{session_stamp}.jsonl"
        if args.write_raw
        else None
    )
    lighter_orderbook_raw_dir = (
        out_root / "raw" / "lighter" / "ws" / "orderbook" / f"date={day}" / f"session={session_stamp}"
        if args.write_raw
        else None
    )
    lighter_trades_raw_dir = (
        out_root / "raw" / "lighter" / "ws" / "trades" / f"date={day}" / f"session={session_stamp}"
        if args.write_raw
        else None
    )
    hyperliquid_meta_raw = (
        out_root / "raw" / "hyperliquid" / "rest" / "live_info" / f"date={day}" / f"meta_and_asset_ctxs_{session_stamp}.jsonl"
        if args.write_raw
        else None
    )
    hyperliquid_predicted_raw = (
        out_root / "raw" / "hyperliquid" / "rest" / "live_info" / f"date={day}" / f"predicted_fundings_{session_stamp}.jsonl"
        if args.write_raw
        else None
    )
    hyperliquid_l2_raw_dir = (
        out_root / "raw" / "hyperliquid" / "ws" / "l2_book" / f"date={day}" / f"session={session_stamp}"
        if args.write_raw
        else None
    )
    hyperliquid_trades_raw_dir = (
        out_root / "raw" / "hyperliquid" / "ws" / "trades" / f"date={day}" / f"session={session_stamp}"
        if args.write_raw
        else None
    )

    if lighter_orderbook_raw_dir is not None:
        ensure_dir(lighter_orderbook_raw_dir)
    if lighter_trades_raw_dir is not None:
        ensure_dir(lighter_trades_raw_dir)
    if hyperliquid_l2_raw_dir is not None:
        ensure_dir(hyperliquid_l2_raw_dir)
    if hyperliquid_trades_raw_dir is not None:
        ensure_dir(hyperliquid_trades_raw_dir)

    stop_event = asyncio.Event()
    stream_tasks = [
        asyncio.create_task(lighter_market_stats_task(state, symbols_set, lighter_market_stats_raw, stop_event)),
        asyncio.create_task(lighter_order_books_task(state, symbol_market_map, lighter_orderbook_raw_dir, stop_event)),
        asyncio.create_task(
            lighter_trades_task(
                state,
                symbol_market_map,
                lighter_trades_raw_dir,
                args.trade_aggregate_sec,
                collection_started_at,
                stop_event,
            )
        ),
        asyncio.create_task(
            hyperliquid_context_poll_task(
                state,
                symbols_set,
                hyperliquid_meta_raw,
                hyperliquid_predicted_raw,
                args.hyperliquid_poll_sec,
                stop_event,
            )
        ),
        asyncio.create_task(hyperliquid_l2_books_task(state, symbols, hyperliquid_l2_raw_dir, stop_event)),
        asyncio.create_task(
            hyperliquid_trades_task(
                state,
                symbols,
                hyperliquid_trades_raw_dir,
                args.trade_aggregate_sec,
                collection_started_at,
                stop_event,
            )
        ),
    ]
    flush_task = asyncio.create_task(
        flush_processed_outputs(
            state,
            symbols,
            out_root,
            args.flush_sec,
            args.parquet_batch_sec,
            args.trade_aggregate_sec,
            args.parquet_compression,
            r2_uploader,
            stop_event,
        )
    )

    print(f"Live collector session -> {session_stamp}")
    print(f"Symbols -> {', '.join(symbols)}")
    print(f"Flush sec -> {args.flush_sec}")
    print(f"Trade aggregate sec -> {args.trade_aggregate_sec}")
    print(f"Parquet batch sec -> {args.parquet_batch_sec}")
    print(f"Write raw -> {args.write_raw}")
    print(f"Write R2 -> {args.write_r2}")
    print(f"Processed funding latest -> {out_root / 'processed' / 'live_funding_snapshots_latest.csv'}")
    print(f"Processed book latest -> {out_root / 'processed' / 'live_book_snapshots_latest.csv'}")
    print(f"Processed trades latest -> {out_root / 'processed' / 'live_trade_tape_latest.csv'}")
    print(f"Processed trade aggregates latest -> {out_root / 'processed' / 'live_trade_aggregates_latest.csv'}")

    try:
        if args.duration_sec > 0:
            await asyncio.sleep(args.duration_sec)
            stop_event.set()
        else:
            await asyncio.Future()
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        stop_event.set()
        flush_results = await asyncio.gather(flush_task, return_exceptions=True)
        if flush_results and isinstance(flush_results[0], Exception):
            print(f"[flush_processed_outputs] error: {flush_results[0]!r}")
        for task in stream_tasks:
            task.cancel()
        await asyncio.gather(*stream_tasks, return_exceptions=True)


def main() -> int:
    args = parse_args()
    asyncio.run(run_live_collect(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
