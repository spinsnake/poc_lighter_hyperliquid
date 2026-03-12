from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.collectors.non_live.common import (
    DATA_ROOT,
    date_slug,
    iso_utc,
    load_csv_rows,
    timestamp_slug,
    write_csv,
    write_json,
)
from src.collectors.non_live.lighter_public import fetch_fundings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Lighter funding history without websockets.")
    parser.add_argument(
        "--coins",
        default="",
        help="Comma-separated coin list, e.g. BTC,ETH,SOL.",
    )
    parser.add_argument(
        "--all-shared",
        action="store_true",
        help="Load all symbols from data/reference/shared_markets_latest.csv.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="How many days of history to request.",
    )
    parser.add_argument(
        "--resolution",
        choices=["1h", "1d"],
        default="1h",
        help="Funding resolution to request from Lighter.",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=DATA_ROOT,
        help="Base output directory. Defaults to <repo>/data.",
    )
    return parser.parse_args()


def resolve_symbol_market_pairs(args: argparse.Namespace) -> list[tuple[str, int]]:
    shared_csv = args.out_root / "reference" / "shared_markets_latest.csv"
    shared_rows = load_csv_rows(shared_csv)
    market_map = {
        row["symbol_canonical"]: int(row["lighter_market_id"])
        for row in shared_rows
        if row.get("symbol_canonical") and row.get("lighter_market_id")
    }

    explicit = [item.strip().upper() for item in args.coins.split(",") if item.strip()]
    if explicit:
        missing = [symbol for symbol in explicit if symbol not in market_map]
        if missing:
            raise SystemExit(
                "Missing Lighter market_id for symbol(s): "
                + ", ".join(missing)
                + ". Collect reference data first and use shared symbols."
            )
        return [(symbol, market_map[symbol]) for symbol in explicit]

    if args.all_shared:
        return [(symbol, market_map[symbol]) for symbol in sorted(market_map)]

    raise SystemExit("Provide --coins BTC,ETH or run with --all-shared after collecting reference data first.")


def build_count_back(days: int, resolution: str) -> int:
    if resolution == "1d":
        return max(days + 7, 14)
    return max(days * 24 + 24, 48)


def build_signed_value(value: str | float | int | None, direction: str | None) -> float | None:
    if value in (None, ""):
        return None
    numeric_value = float(value)
    if direction == "short":
        return -numeric_value
    if direction == "long":
        return numeric_value
    return None


def collect_lighter_funding_history(
    symbol_market_pairs: list[tuple[str, int]],
    days: int,
    resolution: str,
    out_root: Path = DATA_ROOT,
) -> dict[str, object]:
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)
    start_timestamp = int(start_time.timestamp())
    end_timestamp = int(end_time.timestamp())
    count_back = build_count_back(days, resolution)
    stamp = timestamp_slug()
    day = date_slug()
    collected_at = iso_utc()

    flattened_rows: list[dict[str, object]] = []
    for symbol, market_id in symbol_market_pairs:
        history = fetch_fundings(
            market_id=market_id,
            resolution=resolution,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            count_back=count_back,
        )
        raw_path = (
            out_root
            / "raw"
            / "lighter"
            / "rest"
            / "fundings"
            / f"date={day}"
            / f"market_id={market_id}_{stamp}.json"
        )
        write_json(raw_path, history)

        for item in history.get("fundings", []):
            timestamp = item.get("timestamp")
            timestamp_utc = (
                iso_utc(datetime.fromtimestamp(int(timestamp), tz=timezone.utc))
                if timestamp not in (None, "")
                else None
            )
            flattened_rows.append(
                {
                    "symbol": symbol,
                    "market_id": market_id,
                    "resolution": resolution,
                    "timestamp": timestamp,
                    "timestamp_utc": timestamp_utc,
                    "funding_value": item.get("value"),
                    "funding_direction": item.get("direction"),
                    "funding_value_signed_assuming_direction_is_payer": build_signed_value(
                        item.get("value"),
                        item.get("direction"),
                    ),
                    "lighter_raw_rate": item.get("rate"),
                    "collected_at_utc": collected_at,
                }
            )

    latest_csv = out_root / "processed" / "lighter_funding_history_latest.csv"
    latest_json = out_root / "processed" / "lighter_funding_history_latest.json"
    fieldnames = [
        "symbol",
        "market_id",
        "resolution",
        "timestamp",
        "timestamp_utc",
        "funding_value",
        "funding_direction",
        "funding_value_signed_assuming_direction_is_payer",
        "lighter_raw_rate",
        "collected_at_utc",
    ]
    write_csv(latest_csv, fieldnames, flattened_rows)
    write_json(latest_json, flattened_rows)

    return {
        "row_count": len(flattened_rows),
        "latest_csv": str(latest_csv),
        "symbols": [symbol for symbol, _ in symbol_market_pairs],
    }


def main() -> int:
    args = parse_args()
    symbol_market_pairs = resolve_symbol_market_pairs(args)
    summary = collect_lighter_funding_history(symbol_market_pairs, args.days, args.resolution, args.out_root)

    print(f"Saved Lighter funding history rows -> {summary['row_count']}")
    print(f"Saved latest CSV -> {summary['latest_csv']}")
    print(f"Symbols processed -> {', '.join(summary['symbols'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
