from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from src.collectors.non_live.common import DATA_ROOT, iso_utc, load_csv_rows, write_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check funding-rate and contract-size units from collected non-live data.")
    parser.add_argument(
        "--out-root",
        type=Path,
        default=DATA_ROOT,
        help="Base data directory. Defaults to <repo>/data.",
    )
    return parser.parse_args()


def load_json(path: Path) -> object | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def safe_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def abs_median(values: list[float | None]) -> float | None:
    return median([abs(value) for value in values if value is not None])


def log_gap(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return abs(math.log10(a / b))


def build_lighter_current_funding_map(lighter_reference: dict | None) -> dict[str, float | None]:
    if not isinstance(lighter_reference, dict):
        return {}
    return {
        item["symbol"]: safe_float(item.get("rate"))
        for item in lighter_reference.get("fundingRates", {}).get("funding_rates", [])
        if item.get("exchange") == "lighter" and item.get("symbol")
    }


def build_hyperliquid_current_funding_map(hyper_reference: dict | None) -> dict[str, float | None]:
    if not isinstance(hyper_reference, dict):
        return {}
    meta_and_asset_ctxs = hyper_reference.get("metaAndAssetCtxs", [])
    if not isinstance(meta_and_asset_ctxs, list) or len(meta_and_asset_ctxs) != 2:
        return {}

    meta = meta_and_asset_ctxs[0] or {}
    asset_ctxs = meta_and_asset_ctxs[1] or []
    universe = meta.get("universe", [])
    return {
        universe_item["name"]: safe_float(asset_ctx.get("funding"))
        for universe_item, asset_ctx in zip(universe, asset_ctxs)
        if universe_item.get("name")
    }


def latest_rows_by_symbol(
    rows: list[dict[str, str]],
    symbol_field: str,
    time_field: str,
) -> dict[str, dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        symbol = row.get(symbol_field, "")
        if not symbol:
            continue
        current_time = int(row.get(time_field) or 0)
        previous = latest.get(symbol)
        previous_time = int(previous.get(time_field) or 0) if previous else -1
        if current_time >= previous_time:
            latest[symbol] = row
    return latest


def build_funding_rows(out_root: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    shared_rows = load_csv_rows(out_root / "reference" / "shared_markets_latest.csv")
    lighter_reference = load_json(out_root / "reference" / "lighter_reference_latest.json")
    hyper_reference = load_json(out_root / "reference" / "hyperliquid_reference_latest.json")
    lighter_history_rows = load_csv_rows(out_root / "processed" / "lighter_funding_history_latest.csv")
    hyper_history_rows = load_csv_rows(out_root / "processed" / "hyperliquid_funding_history_latest.csv")

    lighter_current_map = build_lighter_current_funding_map(lighter_reference if isinstance(lighter_reference, dict) else None)
    hyper_current_map = build_hyperliquid_current_funding_map(hyper_reference if isinstance(hyper_reference, dict) else None)
    lighter_history_latest = latest_rows_by_symbol(lighter_history_rows, "symbol", "timestamp")
    hyper_history_latest = latest_rows_by_symbol(hyper_history_rows, "coin", "time")

    rows: list[dict[str, object]] = []
    lighter_history_values: list[float | None] = []
    lighter_history_raw_rates: list[float | None] = []
    lighter_current_rates: list[float | None] = []
    hyper_current_rates: list[float | None] = []
    hyper_history_rates: list[float | None] = []

    for shared_row in shared_rows:
        symbol = shared_row.get("symbol_canonical", "")
        if not symbol:
            continue

        lighter_current = lighter_current_map.get(symbol)
        hyper_current = hyper_current_map.get(symbol)
        lighter_history = lighter_history_latest.get(symbol, {})
        hyper_history = hyper_history_latest.get(symbol, {})

        lighter_history_value = safe_float(
            lighter_history.get("funding_value_signed_assuming_direction_is_payer")
            or lighter_history.get("funding_value")
        )
        lighter_history_raw_rate = safe_float(lighter_history.get("lighter_raw_rate"))
        hyper_history_rate = safe_float(hyper_history.get("funding_rate"))

        lighter_current_rates.append(lighter_current)
        hyper_current_rates.append(hyper_current)
        lighter_history_values.append(lighter_history_value)
        lighter_history_raw_rates.append(lighter_history_raw_rate)
        hyper_history_rates.append(hyper_history_rate)

        rows.append(
            {
                "symbol": symbol,
                "lighter_current_rate": lighter_current,
                "hyperliquid_current_rate": hyper_current,
                "lighter_history_value_signed": lighter_history_value,
                "lighter_history_raw_rate": lighter_history_raw_rate,
                "lighter_history_direction": lighter_history.get("funding_direction"),
                "lighter_history_timestamp_utc": lighter_history.get("timestamp_utc"),
                "hyperliquid_history_rate": hyper_history_rate,
                "hyperliquid_history_time": hyper_history.get("time"),
                "funding_unit_note": (
                    "Compare Lighter current rate or signed funding_value against Hyperliquid funding_rate. "
                    "Do not use Lighter lighter_raw_rate for cross-venue spread."
                ),
            }
        )

    summary = {
        "shared_symbol_count": len(rows),
        "lighter_current_symbol_count": sum(1 for value in lighter_current_rates if value is not None),
        "hyperliquid_current_symbol_count": sum(1 for value in hyper_current_rates if value is not None),
        "lighter_history_symbol_count": sum(1 for value in lighter_history_values if value is not None),
        "hyperliquid_history_symbol_count": sum(1 for value in hyper_history_rates if value is not None),
        "lighter_current_abs_median": abs_median(lighter_current_rates),
        "lighter_history_value_abs_median": abs_median(lighter_history_values),
        "lighter_history_raw_rate_abs_median": abs_median(lighter_history_raw_rates),
        "hyperliquid_current_abs_median": abs_median(hyper_current_rates),
        "hyperliquid_history_abs_median": abs_median(hyper_history_rates),
    }
    summary["lighter_value_vs_current_log_gap"] = log_gap(
        summary["lighter_history_value_abs_median"],
        summary["lighter_current_abs_median"],
    )
    summary["lighter_raw_rate_vs_current_log_gap"] = log_gap(
        summary["lighter_history_raw_rate_abs_median"],
        summary["lighter_current_abs_median"],
    )
    summary["hyperliquid_history_vs_current_log_gap"] = log_gap(
        summary["hyperliquid_history_abs_median"],
        summary["hyperliquid_current_abs_median"],
    )

    value_gap = summary["lighter_value_vs_current_log_gap"]
    raw_gap = summary["lighter_raw_rate_vs_current_log_gap"]
    if value_gap is not None and raw_gap is not None and value_gap < raw_gap:
        funding_status = "likely_same_hourly_decimal_rate"
        funding_assessment = (
            "Lighter funding-rates.rate and signed fundings.value are on the same scale as "
            "Hyperliquid funding/fundingHistory. Lighter lighter_raw_rate appears to be a different field."
        )
    else:
        funding_status = "needs_more_data"
        funding_assessment = (
            "Current local data is not strong enough to separate Lighter comparable funding field from "
            "its raw rate field. Collect fresher Lighter funding history and reference snapshots."
        )

    summary["status"] = funding_status
    summary["assessment"] = funding_assessment
    return rows, summary


def build_contract_rows(out_root: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    shared_rows = load_csv_rows(out_root / "reference" / "shared_markets_latest.csv")
    rows: list[dict[str, object]] = []
    lighter_decimals: list[float] = []
    hyperliquid_decimals: list[float] = []

    for shared_row in shared_rows:
        lighter_size_decimals = safe_float(shared_row.get("lighter_size_decimals"))
        hyperliquid_sz_decimals = safe_float(shared_row.get("hyperliquid_sz_decimals"))
        lighter_decimals.append(lighter_size_decimals)
        hyperliquid_decimals.append(hyperliquid_sz_decimals)
        rows.append(
            {
                "symbol": shared_row.get("symbol_canonical"),
                "lighter_size_decimals": lighter_size_decimals,
                "lighter_min_base_amount": safe_float(shared_row.get("lighter_min_base_amount")),
                "hyperliquid_sz_decimals": hyperliquid_sz_decimals,
                "contract_size_assessment": (
                    "Likely same base/underlying asset unit. Validate with fills or position_value before production."
                ),
            }
        )

    summary = {
        "shared_symbol_count": len(rows),
        "lighter_size_decimals_median": median([value for value in lighter_decimals if value is not None]),
        "hyperliquid_sz_decimals_median": median([value for value in hyperliquid_decimals if value is not None]),
        "status": "docs_likely_same_base_asset_unit_pending_fill_confirmation",
        "assessment": (
            "Treat both venue sizes as base/underlying asset units for POC. "
            "Still hedge by notional and confirm with fills/position_value once account data is available."
        ),
    }
    return rows, summary


def write_markdown_report(
    report_path: Path,
    funding_summary: dict[str, object],
    contract_summary: dict[str, object],
) -> None:
    lines = [
        "# Unit Check Report",
        "",
        f"Generated at: {iso_utc()}",
        "",
        "## Funding Rate Unit Check",
        "",
        f"- Status: `{funding_summary['status']}`",
        f"- Assessment: {funding_summary['assessment']}",
        f"- Shared symbols in check: `{funding_summary['shared_symbol_count']}`",
        f"- Lighter current funding median abs rate: `{funding_summary['lighter_current_abs_median']}`",
        f"- Lighter history signed funding_value median abs rate: `{funding_summary['lighter_history_value_abs_median']}`",
        f"- Lighter history raw rate median abs value: `{funding_summary['lighter_history_raw_rate_abs_median']}`",
        f"- Hyperliquid current funding median abs rate: `{funding_summary['hyperliquid_current_abs_median']}`",
        f"- Hyperliquid history median abs rate: `{funding_summary['hyperliquid_history_abs_median']}`",
        f"- Lighter signed-value vs current log gap: `{funding_summary['lighter_value_vs_current_log_gap']}`",
        f"- Lighter raw-rate vs current log gap: `{funding_summary['lighter_raw_rate_vs_current_log_gap']}`",
        f"- Hyperliquid history vs current log gap: `{funding_summary['hyperliquid_history_vs_current_log_gap']}`",
        "",
        "Interpretation:",
        "- Compare `Lighter funding-rates.rate` or `Lighter fundings.value` signed by `direction` against `Hyperliquid funding` / `fundingHistory.fundingRate`.",
        "- Do not use `Lighter fundings.rate` as the cross-venue funding spread field.",
        "",
        "## Contract Size Unit Check",
        "",
        f"- Status: `{contract_summary['status']}`",
        f"- Assessment: {contract_summary['assessment']}",
        f"- Shared symbols in check: `{contract_summary['shared_symbol_count']}`",
        f"- Lighter size decimals median: `{contract_summary['lighter_size_decimals_median']}`",
        f"- Hyperliquid size decimals median: `{contract_summary['hyperliquid_sz_decimals_median']}`",
        "",
        "Interpretation:",
        "- For POC, treat both venues as using base/underlying asset units.",
        "- For real sizing, hedge by notional and confirm with fills or position value.",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    reports_root = args.out_root / "reports"
    reports_root.mkdir(parents=True, exist_ok=True)

    funding_rows, funding_summary = build_funding_rows(args.out_root)
    contract_rows, contract_summary = build_contract_rows(args.out_root)

    funding_csv = reports_root / "funding_unit_check_latest.csv"
    contract_csv = reports_root / "contract_size_check_latest.csv"
    report_md = reports_root / "unit_check_report_latest.md"
    report_json = reports_root / "unit_check_report_latest.json"

    funding_fieldnames = list(funding_rows[0].keys()) if funding_rows else [
        "symbol",
        "lighter_current_rate",
        "hyperliquid_current_rate",
        "lighter_history_value_signed",
        "lighter_history_raw_rate",
        "lighter_history_direction",
        "lighter_history_timestamp_utc",
        "hyperliquid_history_rate",
        "hyperliquid_history_time",
        "funding_unit_note",
    ]
    contract_fieldnames = list(contract_rows[0].keys()) if contract_rows else [
        "symbol",
        "lighter_size_decimals",
        "lighter_min_base_amount",
        "hyperliquid_sz_decimals",
        "contract_size_assessment",
    ]

    write_csv(funding_csv, funding_fieldnames, funding_rows)
    write_csv(contract_csv, contract_fieldnames, contract_rows)
    write_markdown_report(report_md, funding_summary, contract_summary)
    report_json.write_text(
        json.dumps(
            {
                "generated_at_utc": iso_utc(),
                "funding_rate_unit_check": funding_summary,
                "contract_size_unit_check": contract_summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Saved funding unit check CSV -> {funding_csv}")
    print(f"Saved contract size check CSV -> {contract_csv}")
    print(f"Saved report -> {report_md}")
    print(f"Funding status -> {funding_summary['status']}")
    print(f"Contract size status -> {contract_summary['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
