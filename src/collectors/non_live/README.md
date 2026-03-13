# Non-Live Data Collectors

This folder contains collectors for data that can be pulled without live streams or websockets.

Current coverage:

- Lighter public reference data
- Lighter funding snapshot inside the reference bundle
- Lighter funding history
- Hyperliquid public reference data
- Hyperliquid funding history
- Hyperliquid user funding ledger
- Tardis daily CSV upload to Cloudflare R2 for Bitget Futures and Hyperliquid
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

Collect Tardis daily CSV files for October of last year using aggregate perpetual symbols on both exchanges and upload them directly to R2:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_tardis_monthly_csv
```

Collect Tardis CSV by passing year and month as separate arguments:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_tardis_monthly_csv --year 2025 --month-number 10
```

Collect a smaller Tardis export for one symbol per exchange using `derivative_ticker`:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_tardis_monthly_csv --data-types derivative_ticker --bitget-symbols BTCUSDT --hyperliquid-symbols BTC
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
- `tardis/{data_type}/{exchange}/YYYY-MM-DD/{exchange}_{data_type}_YYYY-MM-DD_{symbol}.csv`

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
- `tardis/summary/month=YYYY-MM/summary.json`
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
- You can choose the target period with either `--month YYYY-MM` or `--year YYYY --month-number MM`.
- `collect_tardis_monthly_csv` now uses only temporary local `.csv.gz` files during the run, then uploads decompressed `.csv` files straight to R2 and removes the temp files.
- Duplicate checks now happen against the destination R2 object key before each daily download. If the CSV object already exists, that day is skipped.
- The per-run summary is uploaded to `tardis/summary/month=YYYY-MM/summary.json` and includes both successful and failed daily uploads.
- `PERPETUALS` with `trades` produces large files. Use `derivative_ticker` or narrower symbols when you want a smaller export.
