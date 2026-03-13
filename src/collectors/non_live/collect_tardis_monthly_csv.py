from __future__ import annotations

import argparse
import asyncio
import gzip
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml
from tardis_dev import datasets, get_exchange_details
from tardis_dev.datasets.download import default_file_name

from src.collectors.non_live.common import DATA_ROOT, ensure_dir, iso_utc, write_json
from src.storage.r2_config import load_config
from src.storage.r2_uploader import R2Uploader


def default_target_month() -> str:
    today = datetime.now(timezone.utc).date()
    return f"{today.year - 1:04d}-10"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download Tardis daily gzip CSVs for Bitget Futures and Hyperliquid, "
            "convert them to CSV, and upload them directly to Cloudflare R2."
        )
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML config file containing the Tardis API key under 'tardis'.",
    )
    parser.add_argument(
        "--month",
        default="",
        help="Target month in YYYY-MM. Optional if using --year with --month-number.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=0,
        help="Target year, for example 2025. Use together with --month-number.",
    )
    parser.add_argument(
        "--month-number",
        type=int,
        default=0,
        help="Target month number from 1 to 12. Use together with --year.",
    )
    parser.add_argument(
        "--data-types",
        default="trades",
        help="Comma-separated Tardis dataset types, e.g. trades or derivative_ticker.",
    )
    parser.add_argument(
        "--bitget-symbols",
        default="PERPETUALS",
        help="Comma-separated Bitget Futures symbols or aggregate symbols, e.g. BTCUSDT or PERPETUALS.",
    )
    parser.add_argument(
        "--hyperliquid-symbols",
        default="PERPETUALS",
        help="Comma-separated Hyperliquid symbols or aggregate symbols, e.g. BTC or PERPETUALS.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Tardis download concurrency. Daily CSV uploads are processed one day at a time.",
    )
    parser.add_argument(
        "--r2-config",
        default="config.yaml",
        help="Path to YAML config file containing R2 settings.",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=DATA_ROOT,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--clean-raw-after-merge",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--write-r2",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--write-r2-raw",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def parse_month(month: str) -> tuple[date, date]:
    try:
        month_start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise SystemExit("Month must use YYYY-MM format, for example 2025-10.") from exc

    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1)
    return month_start, month_end


def resolve_target_month(args: argparse.Namespace) -> str:
    month_value = str(args.month or "").strip()
    year = int(args.year or 0)
    month_number = int(args.month_number or 0)

    if month_value:
        if year or month_number:
            raise SystemExit("Use either --month YYYY-MM or --year with --month-number, not both.")
        return month_value

    if year or month_number:
        if not year or not month_number:
            raise SystemExit("When using separate values, provide both --year and --month-number.")
        if month_number < 1 or month_number > 12:
            raise SystemExit("--month-number must be between 1 and 12.")
        return f"{year:04d}-{month_number:02d}"

    return default_target_month()


def parse_csv_items(raw_value: str) -> list[str]:
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def load_tardis_api_key(config_path: str | Path) -> str:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    api_key = str(payload.get("tardis", "")).strip()
    if not api_key:
        raise ValueError(f"Missing Tardis API key in {path}. Set the 'tardis' field first.")
    return api_key


def normalize_symbol_token(symbol: str) -> str:
    return symbol.strip().upper().replace(":", "-").replace("/", "-")


def fetch_exchange_details(exchange: str) -> dict[str, object]:
    try:
        return get_exchange_details(exchange)
    except RuntimeError as exc:
        if "There is no current event loop" not in str(exc):
            raise

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return get_exchange_details(exchange)
        finally:
            asyncio.set_event_loop(None)
            loop.close()


def load_symbol_catalog(exchange: str) -> dict[str, dict[str, object]]:
    details = fetch_exchange_details(exchange)
    symbols = details.get("datasets", {}).get("symbols", [])
    return {
        normalize_symbol_token(str(item["id"])): item
        for item in symbols
        if item.get("id")
    }


def resolve_symbols(exchange: str, requested_symbols: list[str], catalog: dict[str, dict[str, object]]) -> list[str]:
    resolved: list[str] = []
    missing: list[str] = []

    for raw_symbol in requested_symbols:
        token = normalize_symbol_token(raw_symbol)
        item = catalog.get(token)
        if item is None:
            missing.append(raw_symbol)
            continue
        resolved.append(str(item["id"]))

    if missing:
        raise SystemExit(
            f"Unsupported symbol(s) for {exchange}: {', '.join(missing)}. "
            "Use exact Tardis symbol ids such as PERPETUALS, BTCUSDT, or BTC."
        )
    return resolved


def validate_data_types(
    exchange: str,
    symbols: list[str],
    data_types: list[str],
    catalog: dict[str, dict[str, object]],
) -> None:
    for symbol in symbols:
        item = catalog[normalize_symbol_token(symbol)]
        supported = {str(data_type) for data_type in item.get("dataTypes", [])}
        missing = [data_type for data_type in data_types if data_type not in supported]
        if missing:
            raise SystemExit(
                f"Unsupported data type(s) for {exchange} symbol {symbol}: {', '.join(missing)}. "
                f"Supported types: {', '.join(sorted(supported))}"
            )


def iter_days(start: date, end_exclusive: date):
    current = start
    while current < end_exclusive:
        yield current
        current += timedelta(days=1)


def build_temp_gzip_relative_path(
    exchange: str,
    data_type: str,
    day: date,
    symbol: str,
    format_name: str = "csv",
) -> Path:
    file_name = default_file_name(
        exchange=exchange,
        data_type=data_type,
        date=datetime.combine(day, datetime.min.time()),
        symbol=symbol,
        format=format_name,
    )
    return Path("tardis_tmp") / data_type / exchange / day.isoformat() / file_name


def build_r2_csv_object_key(exchange: str, data_type: str, day: date, symbol: str) -> str:
    symbol_token = normalize_symbol_token(symbol)
    file_name = f"{exchange}_{data_type}_{day.isoformat()}_{symbol_token}.csv"
    return f"tardis/{data_type}/{exchange}/{day.isoformat()}/{file_name}"


def build_summary_object_key(month: str) -> str:
    return f"tardis/summary/month={month}/summary.json"


def tardis_download_filename(exchange: str, data_type: str, day: datetime, symbol: str, format_name: str) -> str:
    return build_temp_gzip_relative_path(
        exchange=exchange,
        data_type=data_type,
        day=day.date(),
        symbol=symbol,
        format_name=format_name,
    ).as_posix()


def download_day_gzip(
    temp_root: Path,
    exchange: str,
    data_type: str,
    symbol: str,
    day: date,
    api_key: str,
    concurrency: int,
) -> Path:
    from_date = day.isoformat()
    to_date = (day + timedelta(days=1)).isoformat()
    expected = temp_root / build_temp_gzip_relative_path(exchange, data_type, day, symbol)
    ensure_dir(expected.parent)
    datasets.download(
        exchange=exchange,
        data_types=[data_type],
        symbols=[symbol],
        from_date=from_date,
        to_date=to_date,
        format="csv",
        api_key=api_key,
        download_dir=str(temp_root),
        get_filename=tardis_download_filename,
        concurrency=concurrency,
    )
    if not expected.exists():
        raise FileNotFoundError(
            f"Tardis download did not produce the expected gzip file for {exchange} "
            f"{data_type} {symbol} on {day.isoformat()}: {expected}"
        )
    return expected


def upload_daily_csv_from_gzip(
    uploader: R2Uploader,
    gzip_path: Path,
    object_key: str,
    label: str,
) -> str:
    full_key = uploader.prefixed_object_key(object_key)
    remote_size = uploader.remote_object_size(full_key)
    if remote_size is not None:
        print(f"[r2] {label}: skipped existing -> {full_key}")
        return full_key

    with gzip.open(gzip_path, "rb") as handle:
        uploaded_key = uploader.upload_fileobj_to_object_key(
            handle,
            object_key,
            content_type="text/csv",
        )
    print(f"[r2] {label}: uploaded -> {uploaded_key}")
    return uploaded_key


def format_exception_message(exc: Exception | None) -> str:
    if exc is None:
        return ""
    return f"{type(exc).__name__}: {exc}"


def build_failure_summary(
    exchange: str,
    symbol: str,
    data_type: str,
    day: date,
    stage: str,
    error: str,
    object_key: str,
) -> dict[str, object]:
    return {
        "exchange": exchange,
        "symbol": symbol,
        "data_type": data_type,
        "date": day.isoformat(),
        "stage": stage,
        "error": error,
        "object_key": object_key,
    }


def collect_exchange_month(
    exchange: str,
    symbols: list[str],
    data_types: list[str],
    month: str,
    month_start: date,
    month_end: date,
    api_key: str,
    temp_root: Path,
    concurrency: int,
    r2_uploader: R2Uploader,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    summaries: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for data_type in data_types:
        for symbol in symbols:
            print(
                f"Processing {exchange} {data_type} {symbol} for {month_start.isoformat()} "
                f"to {month_end.isoformat()}..."
            )
            for day in iter_days(month_start, month_end):
                object_key = build_r2_csv_object_key(exchange, data_type, day, symbol)
                label = f"{exchange} {data_type} {symbol} {day.isoformat()}"

                if r2_uploader.object_exists(object_key):
                    full_key = r2_uploader.prefixed_object_key(object_key)
                    print(f"[r2] {label}: skipped existing -> {full_key}")
                    summaries.append(
                        {
                            "exchange": exchange,
                            "symbol": symbol,
                            "data_type": data_type,
                            "month": month,
                            "date": day.isoformat(),
                            "object_key": full_key,
                            "uploaded": False,
                            "skipped_existing": True,
                        }
                    )
                    continue

                gzip_path: Path | None = None
                try:
                    print(f"Downloading {label}...")
                    gzip_path = download_day_gzip(
                        temp_root=temp_root,
                        exchange=exchange,
                        data_type=data_type,
                        symbol=symbol,
                        day=day,
                        api_key=api_key,
                        concurrency=concurrency,
                    )
                except Exception as exc:
                    error_message = format_exception_message(exc)
                    failures.append(
                        build_failure_summary(
                            exchange=exchange,
                            symbol=symbol,
                            data_type=data_type,
                            day=day,
                            stage="download",
                            error=error_message,
                            object_key=object_key,
                        )
                    )
                    print(f"FAILED download {label}: {error_message}")
                    continue

                try:
                    uploaded_key = upload_daily_csv_from_gzip(
                        r2_uploader,
                        gzip_path=gzip_path,
                        object_key=object_key,
                        label=label,
                    )
                except Exception as exc:
                    error_message = format_exception_message(exc)
                    failures.append(
                        build_failure_summary(
                            exchange=exchange,
                            symbol=symbol,
                            data_type=data_type,
                            day=day,
                            stage="upload",
                            error=error_message,
                            object_key=object_key,
                        )
                    )
                    print(f"FAILED upload {label}: {error_message}")
                    continue
                finally:
                    if gzip_path is not None:
                        gzip_path.unlink(missing_ok=True)

                summaries.append(
                    {
                        "exchange": exchange,
                        "symbol": symbol,
                        "data_type": data_type,
                        "month": month,
                        "date": day.isoformat(),
                        "object_key": uploaded_key,
                        "uploaded": True,
                        "skipped_existing": False,
                    }
                )

    return summaries, failures


def main() -> int:
    args = parse_args()
    target_month = resolve_target_month(args)
    month_start, month_end = parse_month(target_month)
    data_types = parse_csv_items(args.data_types)
    bitget_requested = parse_csv_items(args.bitget_symbols)
    hyperliquid_requested = parse_csv_items(args.hyperliquid_symbols)

    if not data_types:
        raise SystemExit("Provide at least one value in --data-types.")
    if not bitget_requested and not hyperliquid_requested:
        raise SystemExit("Provide at least one symbol for Bitget Futures or Hyperliquid.")

    if args.write_r2 or args.write_r2_raw or args.clean_raw_after_merge:
        print(
            "Note: collect_tardis_monthly_csv now uploads CSV files directly to R2 and "
            "does not retain local Tardis files. Legacy local/raw flags are ignored."
        )

    api_key = load_tardis_api_key(args.config)
    app_config = load_config(args.r2_config)
    r2_uploader = R2Uploader(app_config.r2, args.out_root)
    try:
        r2_uploader.verify_bucket_access()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    collected_at = iso_utc()
    summary_rows: list[dict[str, object]] = []
    failure_rows: list[dict[str, object]] = []
    bitget_catalog = load_symbol_catalog("bitget-futures") if bitget_requested else {}
    hyperliquid_catalog = load_symbol_catalog("hyperliquid") if hyperliquid_requested else {}
    bitget_symbols = (
        resolve_symbols("bitget-futures", bitget_requested, bitget_catalog) if bitget_requested else []
    )
    hyperliquid_symbols = (
        resolve_symbols("hyperliquid", hyperliquid_requested, hyperliquid_catalog) if hyperliquid_requested else []
    )

    if bitget_symbols:
        validate_data_types("bitget-futures", bitget_symbols, data_types, bitget_catalog)
    if hyperliquid_symbols:
        validate_data_types("hyperliquid", hyperliquid_symbols, data_types, hyperliquid_catalog)

    with tempfile.TemporaryDirectory(prefix="tardis_csv_r2_") as temp_dir_name:
        temp_root = Path(temp_dir_name)

        if bitget_symbols:
            print(
                f"Uploading bitget-futures {', '.join(data_types)} for {', '.join(bitget_symbols)} "
                f"from {month_start.isoformat()} to {month_end.isoformat()} into R2..."
            )
            exchange_summary_rows, exchange_failure_rows = collect_exchange_month(
                exchange="bitget-futures",
                symbols=bitget_symbols,
                data_types=data_types,
                month=target_month,
                month_start=month_start,
                month_end=month_end,
                api_key=api_key,
                temp_root=temp_root,
                concurrency=args.concurrency,
                r2_uploader=r2_uploader,
            )
            summary_rows.extend(exchange_summary_rows)
            failure_rows.extend(exchange_failure_rows)

        if hyperliquid_symbols:
            print(
                f"Uploading hyperliquid {', '.join(data_types)} for {', '.join(hyperliquid_symbols)} "
                f"from {month_start.isoformat()} to {month_end.isoformat()} into R2..."
            )
            exchange_summary_rows, exchange_failure_rows = collect_exchange_month(
                exchange="hyperliquid",
                symbols=hyperliquid_symbols,
                data_types=data_types,
                month=target_month,
                month_start=month_start,
                month_end=month_end,
                api_key=api_key,
                temp_root=temp_root,
                concurrency=args.concurrency,
                r2_uploader=r2_uploader,
            )
            summary_rows.extend(exchange_summary_rows)
            failure_rows.extend(exchange_failure_rows)

        summary_key = build_summary_object_key(target_month)
        summary_path = temp_root / "summary.json"
        summary_payload = {
            "collected_at_utc": collected_at,
            "month": target_month,
            "storage_mode": "r2_only",
            "summary": summary_rows,
            "failed": failure_rows,
            "success_count": len(summary_rows),
            "failure_count": len(failure_rows),
            "summary_object_key": r2_uploader.prefixed_object_key(summary_key),
        }
        write_json(summary_path, summary_payload)

        try:
            uploaded_summary_key = r2_uploader.upload_path_to_object_key(summary_path, summary_key)
        except Exception as exc:
            error_message = format_exception_message(exc)
            failure_rows.append(
                {
                    "exchange": "",
                    "symbol": "",
                    "data_type": "summary",
                    "date": "",
                    "stage": "upload_summary",
                    "error": error_message,
                    "object_key": summary_key,
                }
            )
            print(f"[r2] summary: FAILED -> {error_message}")
        else:
            print(f"[r2] summary: uploaded -> {uploaded_summary_key}")

    for row in summary_rows:
        action = "skipped existing" if row["skipped_existing"] else "uploaded"
        print(
            f"{action}: {row['exchange']} {row['data_type']} {row['symbol']} {row['date']} -> "
            f"{row['object_key']}"
        )

    for row in failure_rows:
        print(
            f"Failed {row['stage']} {row['exchange']} {row['data_type']} {row['symbol']} "
            f"{row['date']} -> {row['error']}"
        )

    print(f"Uploaded summary -> {r2_uploader.prefixed_object_key(build_summary_object_key(target_month))}")
    if failure_rows:
        print(f"Completed with {len(failure_rows)} failed dataset(s).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
