from __future__ import annotations

import argparse
import asyncio
import gzip
import io
import logging
import os
import random
import secrets
import shutil
import tempfile
import time
import urllib.error
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
import yaml
from tardis_dev import get_exchange_details
from tardis_dev.datasets.download import default_file_name

from src.collectors.non_live.common import DATA_ROOT, ensure_dir, iso_utc, write_json
from src.storage.r2_config import load_config
from src.storage.r2_uploader import R2Uploader


def log(message: str) -> None:
    print(message, flush=True)


def configure_tardis_retry_logging(show_retry_errors: bool) -> None:
    retry_logger = logging.getLogger("tardis_dev.datasets.download")
    if show_retry_errors:
        retry_logger.disabled = False
        retry_logger.propagate = True
        return
    retry_logger.handlers.clear()
    retry_logger.propagate = False
    retry_logger.disabled = True


@dataclass
class ProgressTracker:
    total_items: int
    bar_width: int = 24
    current_item: int = 0
    current_label: str = ""
    _last_stage: str = ""
    _last_percent_bucket: int = -1
    _last_logged_at: float = 0.0
    _last_current_bytes: int = -1
    _last_total_bytes: int = -1

    def render_bar(self, ratio: float) -> str:
        filled = min(self.bar_width, int(self.bar_width * ratio))
        bar = "#" * filled + "-" * (self.bar_width - filled)
        return f"[{bar}] {ratio * 100:5.1f}%"

    def start(self) -> None:
        log(f"[progress] starting {self.total_items} item(s)")

    def start_item(self, label: str) -> None:
        self.current_item += 1
        self.current_label = label
        self._last_stage = ""
        self._last_percent_bucket = -1
        self._last_logged_at = 0.0
        self._last_current_bytes = -1
        self._last_total_bytes = -1

    def update_bytes(
        self,
        stage: str,
        current_bytes: int,
        total_bytes: int | None,
        *,
        force: bool = False,
    ) -> None:
        prefix = f"[progress {self.current_item}/{self.total_items}]"
        now = time.monotonic()
        normalized_total = total_bytes or 0
        if (
            stage == self._last_stage
            and current_bytes == self._last_current_bytes
            and normalized_total == self._last_total_bytes
        ):
            return
        if total_bytes and total_bytes > 0:
            ratio = min(1.0, current_bytes / total_bytes)
            percent_bucket = int((ratio * 100) // 5)
            should_log = (
                force
                or stage != self._last_stage
                or percent_bucket > self._last_percent_bucket
                or now - self._last_logged_at >= 15
                or current_bytes >= total_bytes
            )
            if not should_log:
                return
            bar = self.render_bar(ratio)
            log(
                f"{prefix} {stage:<11} {bar} {self.current_label} "
                f"({format_bytes(current_bytes)}/{format_bytes(total_bytes)})"
            )
            self._last_percent_bucket = percent_bucket
        else:
            should_log = force or stage != self._last_stage or now - self._last_logged_at >= 15
            if not should_log:
                return
            log(f"{prefix} {stage:<11} {self.current_label}")
            self._last_percent_bucket = -1
        self._last_stage = stage
        self._last_logged_at = now
        self._last_current_bytes = current_bytes
        self._last_total_bytes = normalized_total

    def finish_item(self, status: str) -> None:
        log(f"[progress {self.current_item}/{self.total_items}] {status}: {self.current_label}")


class CountingReader:
    def __init__(self, raw) -> None:
        self.raw = raw
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        data = self.raw.read(size)
        self.bytes_read += len(data)
        return data

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def close(self) -> None:
        self.raw.close()


def format_bytes(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0


def default_target_month() -> str:
    today = datetime.now(timezone.utc).date()
    return f"{today.year - 1:04d}-10"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download Tardis daily gzip CSVs for Bitget Futures and Hyperliquid, "
            "convert them to Parquet, and upload them directly to Cloudflare R2."
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
        help="HTTP connection pool size for Tardis requests. Daily files are still processed one at a time.",
    )
    parser.add_argument(
        "--r2-config",
        default="config.yaml",
        help="Path to YAML config file containing R2 settings.",
    )
    parser.add_argument(
        "--show-retry-errors",
        action="store_true",
        help="Show retry stack traces from tardis-dev downloads. Disabled by default.",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=DATA_ROOT,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--temp-dir",
        type=Path,
        default=None,
        help=(
            "Directory used for temporary Tardis downloads before upload. "
            "Defaults to <repo>/data/raw/tardis."
        ),
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


def build_temp_parquet_relative_path(exchange: str, data_type: str, day: date, symbol: str) -> Path:
    symbol_token = normalize_symbol_token(symbol)
    file_name = f"{exchange}_{data_type}_{day.isoformat()}_{symbol_token}.parquet"
    return Path("parquet_tmp") / data_type / exchange / day.isoformat() / file_name


def build_r2_parquet_object_key(exchange: str, data_type: str, day: date, symbol: str) -> str:
    symbol_token = normalize_symbol_token(symbol)
    file_name = f"{exchange}_{data_type}_{day.isoformat()}_{symbol_token}.parquet"
    return f"{data_type}/{exchange}/{day.isoformat()}/{file_name}"


def build_summary_object_key(month: str) -> str:
    return f"summary/month={month}/summary.json"


def resolve_temp_parent(args: argparse.Namespace) -> Path:
    if args.temp_dir is not None:
        return ensure_dir(args.temp_dir)
    return ensure_dir(args.out_root / "raw" / "tardis")


def iter_temp_workspaces(temp_parent: Path) -> list[Path]:
    return sorted(
        (path for path in temp_parent.glob("tardis_csv_r2_*") if path.is_dir()),
        key=lambda path: path.name,
    )


def cleanup_temp_workspace(path: Path) -> None:
    if not path.exists():
        return
    shutil.rmtree(path)
    log(f"Removed temp directory: {path}")


def cleanup_stale_temp_workspaces(temp_parent: Path) -> None:
    for path in iter_temp_workspaces(temp_parent):
        try:
            cleanup_temp_workspace(path)
        except OSError as exc:
            log(f"Temp cleanup warning for {path}: {format_exception_message(exc)}")


def build_dataset_url(exchange: str, data_type: str, day: date, symbol: str, format_name: str = "csv") -> str:
    symbol_token = normalize_symbol_token(symbol)
    return (
        f"https://datasets.tardis.dev/v1/{exchange}/{data_type}/"
        f"{day.strftime('%Y/%m/%d')}/{symbol_token}.{format_name}.gz"
    )


def get_retry_status_code(exc: Exception) -> int | None:
    if isinstance(exc, urllib.error.HTTPError):
        return int(exc.code)
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return int(exc.response.status_code)
    return None


def should_retry_download(exc: Exception) -> bool:
    if isinstance(exc, OSError):
        return False
    status_code = get_retry_status_code(exc)
    if status_code is not None:
        return status_code not in {400, 401}
    return isinstance(exc, requests.RequestException)


def next_retry_delay_seconds(exc: Exception, attempt: int) -> float:
    status_code = get_retry_status_code(exc)
    delay = random.random() + (2 ** attempt)
    if status_code == 429:
        delay += 3 * attempt
    return delay


def download_day_gzip(
    session: requests.Session,
    temp_root: Path,
    exchange: str,
    data_type: str,
    symbol: str,
    day: date,
    progress: ProgressTracker,
) -> Path:
    expected = temp_root / build_temp_gzip_relative_path(exchange, data_type, day, symbol)
    ensure_dir(expected.parent)
    url = build_dataset_url(exchange, data_type, day, symbol)
    max_attempts = 5

    if expected.exists():
        return expected

    for attempt in range(1, max_attempts + 1):
        temp_download_path = expected.with_name(f"{expected.name}{secrets.token_hex(8)}.unconfirmed")
        downloaded_bytes = 0
        try:
            request_url = url if attempt == 1 else f"{url}?retryAttempt={attempt - 1}"
            with session.get(request_url, stream=True, timeout=(30, 30 * 60)) as response:
                if response.status_code != 200:
                    raise urllib.error.HTTPError(
                        request_url,
                        code=response.status_code,
                        msg=response.text,
                        hdrs=None,
                        fp=None,
                    )
                total_bytes_header = response.headers.get("Content-Length")
                total_bytes = int(total_bytes_header) if total_bytes_header else None
                progress.update_bytes("downloading", 0, total_bytes, force=True)
                with temp_download_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded_bytes += len(chunk)
                        progress.update_bytes("downloading", downloaded_bytes, total_bytes)
            os.replace(temp_download_path, expected)
            progress.update_bytes("downloading", downloaded_bytes, total_bytes, force=True)
            return expected
        except Exception as exc:
            temp_download_path.unlink(missing_ok=True)
            if attempt == max_attempts or not should_retry_download(exc):
                raise
            time.sleep(next_retry_delay_seconds(exc, attempt))

    raise RuntimeError(f"Unexpected download retry state for {expected}")


def convert_gzip_csv_to_parquet(
    gzip_path: Path,
    parquet_path: Path,
    progress: ProgressTracker,
) -> Path:
    compressed_size = int(gzip_path.stat().st_size)
    ensure_dir(parquet_path.parent)
    writer: pq.ParquetWriter | None = None
    schema: pa.Schema | None = None

    with gzip_path.open("rb") as compressed_handle:
        counter = CountingReader(compressed_handle)
        gzip_stream = gzip.GzipFile(fileobj=counter, mode="rb")
        text_stream = io.TextIOWrapper(gzip_stream, encoding="utf-8", newline="")
        try:
            progress.update_bytes("converting", 0, compressed_size, force=True)
            for chunk in pd.read_csv(
                text_stream,
                chunksize=200_000,
                low_memory=False,
                dtype_backend="pyarrow",
            ):
                table = pa.Table.from_pandas(chunk, preserve_index=False, schema=schema)
                if writer is None:
                    schema = table.schema
                    writer = pq.ParquetWriter(parquet_path, schema, compression="snappy")
                writer.write_table(table)
                progress.update_bytes(
                    "converting",
                    min(counter.bytes_read, compressed_size),
                    compressed_size,
                )
        finally:
            text_stream.close()
            if writer is not None:
                writer.close()

    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet output was not created: {parquet_path}")

    progress.update_bytes("converting", compressed_size, compressed_size, force=True)
    return parquet_path


def upload_daily_parquet(
    uploader: R2Uploader,
    parquet_path: Path,
    object_key: str,
    label: str,
    progress: ProgressTracker,
) -> str:
    full_key = uploader.prefixed_object_key(object_key)
    remote_size = uploader.remote_object_size(full_key)
    if remote_size is not None:
        log(f"[r2] {label}: skipped existing -> {full_key}")
        return full_key

    parquet_size = int(parquet_path.stat().st_size)
    uploaded_bytes = 0

    def callback(bytes_transferred: int) -> None:
        nonlocal uploaded_bytes
        uploaded_bytes += int(bytes_transferred)
        progress.update_bytes("uploading", min(uploaded_bytes, parquet_size), parquet_size)

    progress.update_bytes("uploading", 0, parquet_size, force=True)
    uploaded_key = uploader.upload_path_to_object_key(
        parquet_path,
        object_key,
        callback=callback,
    )
    progress.update_bytes("uploading", parquet_size, parquet_size, force=True)
    log(f"[r2] {label}: uploaded -> {uploaded_key}")
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
    session: requests.Session,
    exchange: str,
    symbols: list[str],
    data_types: list[str],
    month: str,
    month_start: date,
    month_end: date,
    temp_root: Path,
    r2_uploader: R2Uploader,
    progress: ProgressTracker,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    summaries: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for data_type in data_types:
        for symbol in symbols:
            log(
                f"Processing {exchange} {data_type} {symbol} for {month_start.isoformat()} "
                f"to {month_end.isoformat()}..."
            )
            for day in iter_days(month_start, month_end):
                object_key = build_r2_parquet_object_key(exchange, data_type, day, symbol)
                label = f"{exchange} {data_type} {symbol} {day.isoformat()}"
                parquet_path = temp_root / build_temp_parquet_relative_path(exchange, data_type, day, symbol)
                progress.start_item(label)

                if r2_uploader.object_exists(object_key):
                    full_key = r2_uploader.prefixed_object_key(object_key)
                    progress.finish_item("skipped existing")
                    log(f"[r2] {label}: skipped existing -> {full_key}")
                    summaries.append(
                        {
                            "exchange": exchange,
                            "symbol": symbol,
                            "data_type": data_type,
                            "month": month,
                            "date": day.isoformat(),
                            "file_format": "parquet",
                            "object_key": full_key,
                            "uploaded": False,
                            "skipped_existing": True,
                        }
                    )
                    continue

                gzip_path: Path | None = None
                parquet_output: Path | None = None
                try:
                    gzip_path = download_day_gzip(
                        session=session,
                        temp_root=temp_root,
                        exchange=exchange,
                        data_type=data_type,
                        symbol=symbol,
                        day=day,
                        progress=progress,
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
                    progress.finish_item("failed download")
                    log(f"FAILED download {label}: {error_message}")
                    continue

                try:
                    parquet_output = convert_gzip_csv_to_parquet(
                        gzip_path=gzip_path,
                        parquet_path=parquet_path,
                        progress=progress,
                    )
                    uploaded_key = upload_daily_parquet(
                        r2_uploader,
                        parquet_path=parquet_output,
                        object_key=object_key,
                        label=label,
                        progress=progress,
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
                    progress.finish_item("failed processing")
                    log(f"FAILED processing {label}: {error_message}")
                    continue
                finally:
                    if gzip_path is not None:
                        gzip_path.unlink(missing_ok=True)
                    if parquet_output is not None:
                        parquet_output.unlink(missing_ok=True)

                summaries.append(
                    {
                        "exchange": exchange,
                        "symbol": symbol,
                        "data_type": data_type,
                        "month": month,
                        "date": day.isoformat(),
                        "file_format": "parquet",
                        "object_key": uploaded_key,
                        "uploaded": True,
                        "skipped_existing": False,
                    }
                )
                progress.finish_item("uploaded")

    return summaries, failures


def main() -> int:
    args = parse_args()
    configure_tardis_retry_logging(args.show_retry_errors)
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
        log(
            "Note: collect_tardis_monthly_csv now uploads Parquet files directly to R2 and "
            "does not retain local Tardis files. Legacy local/raw flags are ignored."
        )

    api_key = load_tardis_api_key(args.config)
    app_config = load_config(args.r2_config)
    r2_uploader = R2Uploader(app_config.r2, args.out_root)
    try:
        r2_uploader.verify_bucket_access()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    temp_parent = resolve_temp_parent(args)
    cleanup_stale_temp_workspaces(temp_parent)
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

    day_count = (month_end - month_start).days
    total_items = day_count * (
        len(bitget_symbols) * len(data_types) + len(hyperliquid_symbols) * len(data_types)
    )
    progress = ProgressTracker(total_items=total_items)
    progress.start()

    temp_workspace = tempfile.TemporaryDirectory(prefix="tardis_csv_r2_", dir=str(temp_parent))
    temp_root = Path(temp_workspace.name)
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=max(1, args.concurrency),
        pool_maxsize=max(1, args.concurrency),
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "poc_lighter_hyperliquid/tardis-collector",
        }
    )
    try:
        log(f"Using temp directory: {temp_root}")

        if bitget_symbols:
            log(
                f"Uploading bitget-futures {', '.join(data_types)} for {', '.join(bitget_symbols)} "
                f"from {month_start.isoformat()} to {month_end.isoformat()} into R2..."
            )
            exchange_summary_rows, exchange_failure_rows = collect_exchange_month(
                session=session,
                exchange="bitget-futures",
                symbols=bitget_symbols,
                data_types=data_types,
                month=target_month,
                month_start=month_start,
                month_end=month_end,
                temp_root=temp_root,
                r2_uploader=r2_uploader,
                progress=progress,
            )
            summary_rows.extend(exchange_summary_rows)
            failure_rows.extend(exchange_failure_rows)

        if hyperliquid_symbols:
            log(
                f"Uploading hyperliquid {', '.join(data_types)} for {', '.join(hyperliquid_symbols)} "
                f"from {month_start.isoformat()} to {month_end.isoformat()} into R2..."
            )
            exchange_summary_rows, exchange_failure_rows = collect_exchange_month(
                session=session,
                exchange="hyperliquid",
                symbols=hyperliquid_symbols,
                data_types=data_types,
                month=target_month,
                month_start=month_start,
                month_end=month_end,
                temp_root=temp_root,
                r2_uploader=r2_uploader,
                progress=progress,
            )
            summary_rows.extend(exchange_summary_rows)
            failure_rows.extend(exchange_failure_rows)

        summary_key = build_summary_object_key(target_month)
        summary_path = temp_root / "summary.json"
        summary_payload = {
            "collected_at_utc": collected_at,
            "month": target_month,
            "storage_mode": "r2_only_parquet",
            "file_format": "parquet",
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
            log(f"[r2] summary: FAILED -> {error_message}")
        else:
            log(f"[r2] summary: uploaded -> {uploaded_summary_key}")
    finally:
        session.close()
        temp_workspace.cleanup()
        try:
            cleanup_temp_workspace(temp_root)
        except OSError as exc:
            log(f"Temp cleanup warning for {temp_root}: {format_exception_message(exc)}")

    for row in summary_rows:
        action = "skipped existing" if row["skipped_existing"] else "uploaded"
        log(
            f"{action}: {row['exchange']} {row['data_type']} {row['symbol']} {row['date']} -> "
            f"{row['object_key']}"
        )

    for row in failure_rows:
        log(
            f"Failed {row['stage']} {row['exchange']} {row['data_type']} {row['symbol']} "
            f"{row['date']} -> {row['error']}"
        )

    log(f"Uploaded summary -> {r2_uploader.prefixed_object_key(build_summary_object_key(target_month))}")
    if failure_rows:
        log(f"Completed with {len(failure_rows)} failed dataset(s).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
