# Non-Live Data Collectors

This folder contains collectors for data that can be pulled without live streams or websockets.

Current coverage:

- Lighter public reference data
- Lighter funding snapshot inside the reference bundle
- Lighter funding history
- Hyperliquid public reference data
- Hyperliquid funding history
- Hyperliquid user funding ledger
- Tardis daily Parquet upload to Cloudflare R2 for selected exchanges
- Unit check report for funding-rate units and contract-size units

## Files

```text
src/collectors/non_live/
  common.py
  lighter_public.py
  hyperliquid_public.py
  collect_reference_data.py
  collect_lighter_funding_history.py
  collect_hyperliquid_funding_history.py
  collect_hyperliquid_user_funding.py
  collect_tardis_monthly_csv.py
  collect_all_non_live.py
  unit_check.py
  README.md
```

## Prerequisites

Use the Python environment inside this repo:

```powershell
.\.venv\Scripts\python.exe --version
```

If dependencies are missing:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Recommended Run Order

### 1. Run everything in one command

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_all_non_live --days 30
```

Examples:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_all_non_live --days 30 --max-coins 10
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_all_non_live --coins BTC,ETH,SOL --days 30
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_all_non_live --coins BTC,ETH --days 30 --user 0xYOURADDRESS
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_all_non_live --reference-only
```

### 2. Run collectors individually

Collect reference bundles:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_reference_data
```

Collect Lighter funding history:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_lighter_funding_history --coins BTC,ETH,SOL --days 30
```

Collect Lighter funding history for all shared symbols:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_lighter_funding_history --all-shared --days 30
```

Collect Hyperliquid funding history:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_hyperliquid_funding_history --coins BTC,ETH,SOL --days 30
```

Collect Hyperliquid funding history for all shared symbols:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_hyperliquid_funding_history --all-shared --days 30
```

Collect Hyperliquid user funding ledger:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_hyperliquid_user_funding --user 0xYOURADDRESS --days 30
```

Collect Tardis daily files for October of last year using aggregate perpetual symbols on both exchanges and upload Parquet output directly to R2:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_tardis_monthly_csv
```

Collect Tardis data by passing year and month as separate arguments:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_tardis_monthly_csv --year 2025 --month-number 10
```

Collect Tardis data across an arbitrary inclusive date range:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_tardis_monthly_csv --from-date 2025-02-11 --to-date 2026-02-28
```

Collect Tardis data by naming exchanges explicitly, for example `bybit` plus `hyperliquid`:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_tardis_monthly_csv --data-types derivative_ticker --exchange-symbols "bybit=PERPETUALS;hyperliquid=PERPETUALS" --from-date 2025-10-01 --to-date 2026-02-28
```

Collect Bitget symbols that intersect with Bybit for the requested data type:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_tardis_monthly_csv --data-types quotes --exchange-symbols "bitget-futures=@intersect:bybit" --from-date 2025-10-01 --to-date 2025-10-01
```

Store temporary download files under a custom directory before upload:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_tardis_monthly_csv --year 2025 --month-number 10 --temp-dir D:\git\poc_lighter_hyperliquid\data\raw\tardis
```

Collect a smaller Tardis export for one symbol per exchange using `derivative_ticker`:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_tardis_monthly_csv --data-types derivative_ticker --bitget-symbols BTCUSDT --hyperliquid-symbols BTC
```

Show retry stack traces from `tardis-dev` only when you are debugging download failures:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_tardis_monthly_csv --data-types derivative_ticker --year 2026 --month-number 2 --show-retry-errors
```

Run the same monthly Tardis job with Docker Compose:

```powershell
docker compose up --build
```

Generate unit-check report:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.unit_check
```

## Output Layout

Raw payloads:

- `data/raw/lighter/rest/date=YYYY-MM-DD/reference_bundle_*.json`
- `data/raw/lighter/rest/fundings/date=YYYY-MM-DD/market_id=..._*.json`
- `data/raw/hyperliquid/rest/date=YYYY-MM-DD/reference_bundle_*.json`
- `data/raw/hyperliquid/rest/funding_history/date=YYYY-MM-DD/coin=..._*.json`
- `data/raw/hyperliquid/rest/user_funding/date=YYYY-MM-DD/user=..._*.json`
- `{data_type}/{exchange}/YYYY-MM-DD/{exchange}_{data_type}_YYYY-MM-DD_{symbol}.parquet`

Latest processed outputs:

- `data/reference/lighter_reference_latest.json`
- `data/reference/hyperliquid_reference_latest.json`
- `data/reference/shared_markets_latest.csv`
- `data/reference/shared_markets_latest.json`
- `data/processed/lighter_funding_history_latest.csv`
- `data/processed/lighter_funding_history_latest.json`
- `data/processed/hyperliquid_funding_history_latest.csv`
- `data/processed/hyperliquid_funding_history_latest.json`
- `data/processed/hyperliquid_user_funding_latest.csv`
- `data/processed/hyperliquid_user_funding_latest.json`
- `summary/month=YYYY-MM/summary.json`
- `summary/range=YYYY-MM-DD_to_YYYY-MM-DD/summary.json`
- `data/reports/funding_unit_check_latest.csv`
- `data/reports/contract_size_check_latest.csv`
- `data/reports/unit_check_report_latest.md`
- `data/reports/unit_check_report_latest.json`

## Notes

- `collect_reference_data` now stores Lighter `funding-rates` inside `lighter_reference_latest.json`.
- For cross-venue funding spread checks, use Lighter current `funding-rates.rate` or historical `fundings.value` signed by `direction`.
- Do not use Lighter historical `fundings.rate` as the funding spread field until it is validated separately.
- Contract-size confirmation is still partial until fills or position-value data are collected.
- `collect_tardis_monthly_csv` reads the Tardis API key from `config.yaml` under the `tardis` field.
- The default Tardis target month is October of the previous calendar year. On March 13, 2026 that resolves to `2025-10`.
- You can choose the target period with either `--month YYYY-MM`, `--year YYYY --month-number MM`, or `--from-date YYYY-MM-DD --to-date YYYY-MM-DD`.
- `--to-date` is inclusive in date range mode.
- You can choose exchanges explicitly with `--exchange-symbols exchange=symbol1,symbol2;exchange=symbol1`, for example `bybit=PERPETUALS;hyperliquid=PERPETUALS`.
- `--exchange-symbols` also supports `@intersect:<exchange>`, for example `bitget-futures=@intersect:bybit`, which expands to the exact symbol ids shared by both exchanges and supported by the requested data type(s).
- Legacy `--bitget-symbols` and `--hyperliquid-symbols` flags still work when `--exchange-symbols` is not provided.
- `collect_tardis_monthly_csv` now uses only temporary local `.csv.gz` files during the run, converts them to `.parquet`, uploads the parquet files to R2, and removes the temp files.
- Temporary Tardis download files now default to `data/raw/tardis/tardis_csv_r2_*`. Use `--temp-dir` when you want another temp location.
- The script also deletes stale `tardis_csv_r2_*` temp workspaces from earlier runs when a new run starts.
- The script now prints byte-based progress for each day during download, conversion, and upload.
- Retry stack traces from `tardis-dev` are hidden by default. Use `--show-retry-errors` only when you need verbose retry diagnostics.
- Duplicate checks now happen against the destination R2 object key before each daily download. If the parquet object already exists, that day is skipped.
- The per-run summary is uploaded to `summary/month=YYYY-MM/summary.json` or `summary/range=YYYY-MM-DD_to_YYYY-MM-DD/summary.json` and includes both successful and failed daily uploads.
- `PERPETUALS` with `trades` produces large files. Use `derivative_ticker` or narrower symbols when you want a smaller export.
