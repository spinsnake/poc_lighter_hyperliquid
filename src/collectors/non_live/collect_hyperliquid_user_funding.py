from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.collectors.non_live.common import DATA_ROOT, date_slug, iso_utc, timestamp_slug, write_csv, write_json
from src.collectors.non_live.hyperliquid_public import fetch_user_funding


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Hyperliquid user funding ledger without websockets.")
    parser.add_argument("--user", required=True, help="Hyperliquid user address, e.g. 0xabc...")
    parser.add_argument("--days", type=int, default=30, help="How many days of history to request.")
    parser.add_argument(
        "--out-root",
        type=Path,
        default=DATA_ROOT,
        help="Base output directory. Defaults to <repo>/data.",
    )
    return parser.parse_args()


def collect_hyperliquid_user_funding(user: str, days: int, out_root: Path = DATA_ROOT) -> dict[str, object]:
    start_time = datetime.now(timezone.utc) - timedelta(days=days)
    start_time_ms = int(start_time.timestamp() * 1000)
    stamp = timestamp_slug()
    day = date_slug()
    collected_at = iso_utc()

    history = fetch_user_funding(user, start_time_ms)
    raw_path = (
        out_root
        / "raw"
        / "hyperliquid"
        / "rest"
        / "user_funding"
        / f"date={day}"
        / f"user={user}_{stamp}.json"
    )
    write_json(raw_path, history)

    rows: list[dict[str, object]] = []
    for item in history:
        delta = item.get("delta", {})
        rows.append(
            {
                "user": user,
                "time": item.get("time"),
                "coin": delta.get("coin"),
                "funding_rate": delta.get("fundingRate"),
                "position_size": delta.get("szi"),
                "funding_usdc": delta.get("usdc"),
                "collected_at_utc": collected_at,
            }
        )

    latest_csv = out_root / "processed" / "hyperliquid_user_funding_latest.csv"
    latest_json = out_root / "processed" / "hyperliquid_user_funding_latest.json"
    fieldnames = ["user", "time", "coin", "funding_rate", "position_size", "funding_usdc", "collected_at_utc"]
    write_csv(latest_csv, fieldnames, rows)
    write_json(latest_json, rows)

    return {
        "row_count": len(rows),
        "latest_csv": str(latest_csv),
        "user": user,
    }


def main() -> int:
    args = parse_args()
    summary = collect_hyperliquid_user_funding(args.user, args.days, args.out_root)

    print(f"Saved Hyperliquid user funding rows -> {summary['row_count']}")
    print(f"Saved latest CSV -> {summary['latest_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
