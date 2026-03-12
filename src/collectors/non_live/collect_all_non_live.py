from __future__ import annotations

import argparse
from pathlib import Path

from src.collectors.non_live.collect_lighter_funding_history import collect_lighter_funding_history
from src.collectors.non_live.collect_hyperliquid_funding_history import collect_hyperliquid_funding_history
from src.collectors.non_live.collect_hyperliquid_user_funding import collect_hyperliquid_user_funding
from src.collectors.non_live.collect_reference_data import collect_reference_data
from src.collectors.non_live.common import DATA_ROOT, load_csv_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all non-live collectors in one command.")
    parser.add_argument(
        "--coins",
        default="",
        help="Comma-separated coin list, e.g. BTC,ETH,SOL. If omitted, uses shared markets from reference data.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="How many days of Hyperliquid funding history to request.",
    )
    parser.add_argument(
        "--user",
        default="",
        help="Optional Hyperliquid user address for user funding ledger collection.",
    )
    parser.add_argument(
        "--reference-only",
        action="store_true",
        help="Only collect non-live reference data and stop.",
    )
    parser.add_argument(
        "--max-coins",
        type=int,
        default=0,
        help="Optional limit when using all shared symbols. 0 means no limit.",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=DATA_ROOT,
        help="Base output directory. Defaults to <repo>/data.",
    )
    return parser.parse_args()


def resolve_coins(out_root: Path, coins_arg: str, max_coins: int) -> list[str]:
    explicit = [item.strip().upper() for item in coins_arg.split(",") if item.strip()]
    if explicit:
        return explicit[:max_coins] if max_coins > 0 else explicit

    shared_csv = out_root / "reference" / "shared_markets_latest.csv"
    shared = sorted({row["symbol_canonical"] for row in load_csv_rows(shared_csv) if row.get("symbol_canonical")})
    return shared[:max_coins] if max_coins > 0 else shared


def resolve_symbol_market_pairs(out_root: Path, coins: list[str]) -> list[tuple[str, int]]:
    shared_csv = out_root / "reference" / "shared_markets_latest.csv"
    shared_rows = load_csv_rows(shared_csv)
    market_map = {
        row["symbol_canonical"]: int(row["lighter_market_id"])
        for row in shared_rows
        if row.get("symbol_canonical") and row.get("lighter_market_id")
    }
    return [(coin, market_map[coin]) for coin in coins if coin in market_map]


def main() -> int:
    args = parse_args()

    print("[1/4] Collecting reference data...")
    reference_summary = collect_reference_data(args.out_root)
    print(f"  Shared symbols: {reference_summary['shared_symbol_count']}")

    if args.reference_only:
        print("Reference-only mode enabled. Done.")
        return 0

    coins = resolve_coins(args.out_root, args.coins, args.max_coins)
    lighter_pairs = resolve_symbol_market_pairs(args.out_root, coins)
    print(f"[2/4] Collecting Lighter funding history for {len(lighter_pairs)} coin(s)...")
    lighter_summary = collect_lighter_funding_history(lighter_pairs, args.days, "1h", args.out_root)
    print(f"  Funding rows: {lighter_summary['row_count']}")

    print(f"[3/4] Collecting Hyperliquid funding history for {len(coins)} coin(s)...")
    funding_summary = collect_hyperliquid_funding_history(coins, args.days, args.out_root)
    print(f"  Funding rows: {funding_summary['row_count']}")

    if args.user:
        print("[4/4] Collecting Hyperliquid user funding ledger...")
        user_summary = collect_hyperliquid_user_funding(args.user, args.days, args.out_root)
        print(f"  User funding rows: {user_summary['row_count']}")
    else:
        print("[4/4] Skipped user funding ledger. Use --user 0x... to enable.")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
