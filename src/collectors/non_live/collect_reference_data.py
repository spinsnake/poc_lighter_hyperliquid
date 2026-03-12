from __future__ import annotations

import argparse
from pathlib import Path

from src.collectors.non_live.common import (
    DATA_ROOT,
    date_slug,
    iso_utc,
    timestamp_slug,
    write_csv,
    write_json,
)
from src.collectors.non_live.hyperliquid_public import fetch_reference_bundle as fetch_hyperliquid_reference
from src.collectors.non_live.lighter_public import fetch_reference_bundle as fetch_lighter_reference


def build_lighter_funding_map(lighter_bundle: dict) -> dict[str, dict[str, object]]:
    return {
        item["symbol"]: item
        for item in lighter_bundle.get("fundingRates", {}).get("funding_rates", [])
        if item.get("exchange") == "lighter" and item.get("symbol")
    }


def build_hyperliquid_funding_map(hyperliquid_bundle: dict) -> dict[str, dict[str, object]]:
    meta_and_asset_ctxs = hyperliquid_bundle.get("metaAndAssetCtxs", [])
    if not isinstance(meta_and_asset_ctxs, list) or len(meta_and_asset_ctxs) != 2:
        return {}

    meta = meta_and_asset_ctxs[0] or {}
    asset_ctxs = meta_and_asset_ctxs[1] or []
    universe = meta.get("universe", [])
    return {
        universe_item["name"]: asset_ctx
        for universe_item, asset_ctx in zip(universe, asset_ctxs)
        if universe_item.get("name")
    }


def build_shared_markets_rows(lighter_bundle: dict, hyperliquid_bundle: dict, collected_at: str) -> list[dict[str, object]]:
    lighter_markets = {
        item["symbol"]: item
        for item in lighter_bundle["orderBookDetails"].get("order_book_details", [])
        if item.get("market_type") == "perp" and item.get("status") == "active"
    }
    hyper_markets = {
        item["name"]: item
        for item in hyperliquid_bundle["meta"].get("universe", [])
    }
    lighter_funding = build_lighter_funding_map(lighter_bundle)
    hyper_funding = build_hyperliquid_funding_map(hyperliquid_bundle)

    rows: list[dict[str, object]] = []
    for symbol in sorted(set(lighter_markets) & set(hyper_markets)):
        lighter_item = lighter_markets[symbol]
        hyper_item = hyper_markets[symbol]
        lighter_funding_rate = lighter_funding.get(symbol, {}).get("rate")
        hyperliquid_funding_rate = hyper_funding.get(symbol, {}).get("funding")
        rows.append(
            {
                "symbol_canonical": symbol,
                "symbol_lighter": symbol,
                "symbol_hyperliquid": symbol,
                "lighter_market_id": lighter_item.get("market_id"),
                "lighter_status": lighter_item.get("status"),
                "lighter_size_decimals": lighter_item.get("size_decimals"),
                "lighter_price_decimals": lighter_item.get("price_decimals"),
                "lighter_min_base_amount": lighter_item.get("min_base_amount"),
                "lighter_maker_fee": lighter_item.get("maker_fee"),
                "lighter_taker_fee": lighter_item.get("taker_fee"),
                "lighter_current_funding_rate": lighter_funding_rate,
                "hyperliquid_sz_decimals": hyper_item.get("szDecimals"),
                "hyperliquid_max_leverage": hyper_item.get("maxLeverage"),
                "hyperliquid_margin_table_id": hyper_item.get("marginTableId"),
                "hyperliquid_current_funding_rate": hyperliquid_funding_rate,
                "collected_at_utc": collected_at,
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect non-live reference data from Lighter and Hyperliquid.")
    parser.add_argument(
        "--out-root",
        type=Path,
        default=DATA_ROOT,
        help="Base output directory. Defaults to <repo>/data.",
    )
    return parser.parse_args()


def collect_reference_data(out_root: Path = DATA_ROOT) -> dict[str, object]:
    stamp = timestamp_slug()
    day = date_slug()
    collected_at = iso_utc()

    lighter_bundle = fetch_lighter_reference()
    hyperliquid_bundle = fetch_hyperliquid_reference()

    lighter_raw_path = out_root / "raw" / "lighter" / "rest" / f"date={day}" / f"reference_bundle_{stamp}.json"
    hyperliquid_raw_path = (
        out_root / "raw" / "hyperliquid" / "rest" / f"date={day}" / f"reference_bundle_{stamp}.json"
    )
    lighter_latest_path = out_root / "reference" / "lighter_reference_latest.json"
    hyperliquid_latest_path = out_root / "reference" / "hyperliquid_reference_latest.json"
    shared_latest_json = out_root / "reference" / "shared_markets_latest.json"
    shared_latest_csv = out_root / "reference" / "shared_markets_latest.csv"

    shared_rows = build_shared_markets_rows(lighter_bundle, hyperliquid_bundle, collected_at)
    fieldnames = list(shared_rows[0].keys()) if shared_rows else [
        "symbol_canonical",
        "symbol_lighter",
        "symbol_hyperliquid",
        "lighter_market_id",
        "lighter_status",
        "lighter_size_decimals",
        "lighter_price_decimals",
        "lighter_min_base_amount",
        "lighter_maker_fee",
        "lighter_taker_fee",
        "lighter_current_funding_rate",
        "hyperliquid_sz_decimals",
        "hyperliquid_max_leverage",
        "hyperliquid_margin_table_id",
        "hyperliquid_current_funding_rate",
        "collected_at_utc",
    ]

    write_json(lighter_raw_path, lighter_bundle)
    write_json(hyperliquid_raw_path, hyperliquid_bundle)
    write_json(lighter_latest_path, lighter_bundle)
    write_json(hyperliquid_latest_path, hyperliquid_bundle)
    write_json(shared_latest_json, shared_rows)
    write_csv(shared_latest_csv, fieldnames, shared_rows)

    return {
        "lighter_raw_path": str(lighter_raw_path),
        "hyperliquid_raw_path": str(hyperliquid_raw_path),
        "shared_latest_csv": str(shared_latest_csv),
        "shared_symbol_count": len(shared_rows),
    }


def main() -> int:
    args = parse_args()
    summary = collect_reference_data(args.out_root)

    print(f"Saved Lighter reference bundle -> {summary['lighter_raw_path']}")
    print(f"Saved Hyperliquid reference bundle -> {summary['hyperliquid_raw_path']}")
    print(f"Saved shared markets CSV -> {summary['shared_latest_csv']}")
    print(f"Shared active perp symbols found -> {summary['shared_symbol_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
