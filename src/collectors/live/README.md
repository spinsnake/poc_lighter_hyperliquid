# Live Data Collectors

This folder contains the first live collector for the POC.

Current live coverage:

- Lighter websocket `market_stats/all`
- Lighter websocket `order_book/{market_id}`
- Lighter websocket `trade/{market_id}`
- Hyperliquid websocket `l2Book`
- Hyperliquid websocket `trades`
- Hyperliquid polling for `metaAndAssetCtxs`
- Hyperliquid polling for `predictedFundings`

The current live collector is focused on:

- 1-second funding snapshots
- 1-second mark / index / mid style prices
- 1-second top-of-book and depth summaries
- 1-second trade aggregates
- recent raw trades in `latest.csv` for inspection only

It does not yet collect:

- orders / fills / balances / positions
- risk / recovery / venue-health logs

## Main command

Foreground, defaulting to all shared symbols in summary-first mode:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.live.collect_all_live --all-shared --duration-sec 300
```

Background launcher, defaulting to all shared symbols with:

- `flush-sec = 1`
- `hyperliquid-poll-sec = 1`
- `parquet-batch-sec = 60`
- raw writes disabled by default

```powershell
.\start_live_collect.ps1
```

Run a fixed symbol subset instead:

```powershell
.\start_live_collect.ps1 -Symbols BTC,ETH,SOL -DurationSec 1800
```

Enable raw JSONL writes only when needed for debugging:

```powershell
.\start_live_collect.ps1 -Symbols BTC,ETH,SOL -DurationSec 1800 -WriteRaw
```

## Output

Raw, only when `-WriteRaw` is used:

- `data/raw/lighter/ws/market_stats/date=YYYY-MM-DD/...jsonl`
- `data/raw/lighter/ws/orderbook/date=YYYY-MM-DD/session=.../symbol=...jsonl`
- `data/raw/lighter/ws/trades/date=YYYY-MM-DD/session=.../symbol=...jsonl`
- `data/raw/hyperliquid/ws/l2_book/date=YYYY-MM-DD/session=.../symbol=...jsonl`
- `data/raw/hyperliquid/ws/trades/date=YYYY-MM-DD/session=.../symbol=...jsonl`
- `data/raw/hyperliquid/rest/live_info/date=YYYY-MM-DD/...jsonl`

Processed:

- `data/processed/live_funding_snapshots_latest.csv`
- `data/processed/live_book_snapshots_latest.csv`
- `data/processed/live_trade_tape_latest.csv`
- `data/processed/live_trade_aggregates_latest.csv`
- `data/processed/live/funding_snapshots/date=YYYY-MM-DD/...parquet`
- `data/processed/live/book_snapshots/date=YYYY-MM-DD/...parquet`
- `data/processed/live/trade_aggregates/date=YYYY-MM-DD/...parquet`

## Notes

- `.\start_live_collect.ps1` now starts with `all shared symbols` by default.
- The default mode is summary-first and is intended for the threshold/formula POC.
- If a previous live collector is already running, the launcher stops it before starting a new one.
- Orders / fills / balances / positions still need separate authenticated collectors.
