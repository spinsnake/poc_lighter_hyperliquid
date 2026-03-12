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
from src.collectors.non_live.hyperliquid_public import fetch_funding_history


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Hyperliquid funding history without websockets.")
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
        "--out-root",
        type=Path,
        default=DATA_ROOT,
        help="Base output directory. Defaults to <repo>/data.",
    )
    return parser.parse_args()


def resolve_coins(args: argparse.Namespace) -> list[str]:
    explicit = [item.strip().upper() for item in args.coins.split(",") if item.strip()]
    if explicit:
        return explicit
    if args.all_shared:
        shared_csv = args.out_root / "reference" / "shared_markets_latest.csv"
        return sorted({row["symbol_canonical"] for row in load_csv_rows(shared_csv) if row.get("symbol_canonical")})
    raise SystemExit("Provide --coins BTC,ETH or run with --all-shared after collecting reference data first.")


def collect_hyperliquid_funding_history(coins: list[str], days: int, out_root: Path = DATA_ROOT) -> dict[str, object]:
    start_time = datetime.now(timezone.utc) - timedelta(days=days)
    start_time_ms = int(start_time.timestamp() * 1000)
    stamp = timestamp_slug()
    day = date_slug()
    collected_at = iso_utc()

    flattened_rows: list[dict[str, object]] = []
    for coin in coins:
        history = fetch_funding_history(coin, start_time_ms)
        raw_path = (
            out_root
            / "raw"
            / "hyperliquid"
            / "rest"
            / "funding_history"
            / f"date={day}"
            / f"coin={coin}_{stamp}.json"
        )
        write_json(raw_path, history)

        for item in history:
            flattened_rows.append(
                {
                    "coin": coin,
                    "time": item.get("time"),
                    "funding_rate": item.get("fundingRate"),
                    "premium": item.get("premium"),
                    "collected_at_utc": collected_at,
                }
            )

    latest_csv = out_root / "processed" / "hyperliquid_funding_history_latest.csv"
    latest_json = out_root / "processed" / "hyperliquid_funding_history_latest.json"
    fieldnames = ["coin", "time", "funding_rate", "premium", "collected_at_utc"]
    write_csv(latest_csv, fieldnames, flattened_rows)
    write_json(latest_json, flattened_rows)

    return {
        "row_count": len(flattened_rows),
        "latest_csv": str(latest_csv),
        "coins": coins,
    }


def main() -> int:
    args = parse_args()
    coins = resolve_coins(args)
    summary = collect_hyperliquid_funding_history(coins, args.days, args.out_root)

    print(f"Saved Hyperliquid funding history rows -> {summary['row_count']}")
    print(f"Saved latest CSV -> {summary['latest_csv']}")
    print(f"Coins processed -> {', '.join(summary['coins'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
