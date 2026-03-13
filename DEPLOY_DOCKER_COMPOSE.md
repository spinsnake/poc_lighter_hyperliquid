# Deploy With Docker Compose

This repo now ships with a single Docker Compose service for the Tardis export:

- `tardis`
  Runs `src.collectors.non_live.collect_tardis_monthly_csv`.

## Files

- [Dockerfile](/d:/git/poc_lighter_hyperliquid/Dockerfile)
- [compose.yaml](/d:/git/poc_lighter_hyperliquid/compose.yaml)
- [docker/tardis-monthly-entrypoint.sh](/d:/git/poc_lighter_hyperliquid/docker/tardis-monthly-entrypoint.sh)
- [.dockerignore](/d:/git/poc_lighter_hyperliquid/.dockerignore)

## Default Tardis Run

`docker compose up --build` now runs the Tardis export with these defaults:

- `--data-types trades`
- `--from-date 2025-10-01`
- `--to-date 2026-02-28`
- `--exchange-symbols bitget-futures=PERPETUALS;hyperliquid=PERPETUALS`

The container mounts:

- `./data` to `/app/data`
- `./logs` to `/app/logs`
- `./config.yaml` to `/app/config.yaml`

`config.yaml` is mounted at runtime and is not copied into the Docker image.

`config.yaml` must contain both:

- `tardis`
- `r2`

## Commands

Build and run the default monthly Tardis job:

```bash
docker compose up --build
```

Run in detached mode:

```bash
docker compose up -d --build
```

View logs for the Tardis job:

```bash
docker compose logs -f tardis
```

Stop and remove containers:

```bash
docker compose down
```

## Customizing The Tardis Job

Edit the `tardis` environment block in [compose.yaml](/d:/git/poc_lighter_hyperliquid/compose.yaml).

Main variables:

- `TARDIS_DATA_TYPES`
- `TARDIS_MONTH`
- `TARDIS_YEAR`
- `TARDIS_MONTH_NUMBER`
- `TARDIS_FROM_DATE`
- `TARDIS_TO_DATE`
- `TARDIS_EXCHANGE_SYMBOLS`
- `TARDIS_BITGET_SYMBOLS`
- `TARDIS_HYPERLIQUID_SYMBOLS`
- `TARDIS_CONCURRENCY`
- `TARDIS_TEMP_DIR`
- `TARDIS_SHOW_RETRY_ERRORS`
- `TARDIS_EXTRA_ARGS`

`TARDIS_EXCHANGE_SYMBOLS` takes precedence over the legacy `TARDIS_BITGET_SYMBOLS` and `TARDIS_HYPERLIQUID_SYMBOLS` variables.

Examples:

Run a different month:

```yaml
environment:
  TARDIS_YEAR: "2025"
  TARDIS_MONTH_NUMBER: "10"
```

Use `--month YYYY-MM` instead of separate year/month:

```yaml
environment:
  TARDIS_MONTH: "2025-10"
```

Use an arbitrary inclusive date range instead of month mode:

```yaml
environment:
  TARDIS_MONTH: ""
  TARDIS_FROM_DATE: "2025-02-11"
  TARDIS_TO_DATE: "2026-02-28"
```

Pick exchanges explicitly:

```yaml
environment:
  TARDIS_EXCHANGE_SYMBOLS: "bybit=PERPETUALS;hyperliquid=PERPETUALS"
```

Limit symbols with explicit exchange names:

```yaml
environment:
  TARDIS_EXCHANGE_SYMBOLS: "bybit=BTCUSDT;bitget-futures=BTCUSDT;hyperliquid=BTC"
```

Pass extra flags through to the Python module:

```yaml
environment:
  TARDIS_EXTRA_ARGS: --show-retry-errors
```

## Plain Docker

Build the image:

```bash
docker build -t poc-lighter-hyperliquid .
```

Run the same monthly Tardis job without compose:

```bash
docker run --rm \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/config.yaml:/app/config.yaml:ro" \
  poc-lighter-hyperliquid
```
