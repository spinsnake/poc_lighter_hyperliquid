#!/usr/bin/env bash
set -euo pipefail

cd /app

mkdir -p /app/data/raw/tardis /app/logs

if [[ ! -f /app/config.yaml ]]; then
  echo "config.yaml not found at /app/config.yaml"
  echo "Copy config.example.yaml to config.yaml and fill in Tardis and R2 credentials first."
  exit 1
fi

python_args=(
  -u
  -m
  src.collectors.non_live.collect_tardis_monthly_csv
  --config
  "${TARDIS_CONFIG:-/app/config.yaml}"
  --r2-config
  "${TARDIS_R2_CONFIG:-/app/config.yaml}"
  --data-types
  "${TARDIS_DATA_TYPES:-derivative_ticker}"
  --bitget-symbols
  "${TARDIS_BITGET_SYMBOLS:-PERPETUALS}"
  --hyperliquid-symbols
  "${TARDIS_HYPERLIQUID_SYMBOLS:-PERPETUALS}"
  --concurrency
  "${TARDIS_CONCURRENCY:-5}"
  --temp-dir
  "${TARDIS_TEMP_DIR:-/app/data/raw/tardis}"
)

if [[ -n "${TARDIS_MONTH:-}" ]]; then
  python_args+=(
    --month
    "${TARDIS_MONTH}"
  )
else
  python_args+=(
    --year
    "${TARDIS_YEAR:-2026}"
    --month-number
    "${TARDIS_MONTH_NUMBER:-2}"
  )
fi

if [[ "${TARDIS_SHOW_RETRY_ERRORS:-0}" == "1" ]]; then
  python_args+=(--show-retry-errors)
fi

if [[ -n "${TARDIS_EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_args=( ${TARDIS_EXTRA_ARGS} )
  python_args+=("${extra_args[@]}")
fi

echo "[entrypoint] starting tardis monthly collector"
echo "[entrypoint] args: ${python_args[*]}"
exec python "${python_args[@]}"
