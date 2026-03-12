#!/usr/bin/env bash
set -euo pipefail

cd /app

mkdir -p /app/data /app/logs

if [[ ! -f /app/config.yaml ]]; then
  echo "config.yaml not found at /app/config.yaml"
  echo "Copy config.example.yaml to config.yaml and fill in R2 credentials first."
  exit 1
fi

if [[ "${RUN_REFERENCE_ON_START:-1}" == "1" ]]; then
  echo "[entrypoint] collecting reference data"
  python -m src.collectors.non_live.collect_reference_data
fi

collector_args=()

if [[ -n "${SYMBOLS:-}" ]]; then
  collector_args+=(--symbols "${SYMBOLS}")
else
  if [[ "${ALL_SHARED:-1}" == "1" ]]; then
    collector_args+=(--all-shared)
  fi
fi

if [[ "${WRITE_R2:-1}" == "1" ]]; then
  collector_args+=(--write-r2)
fi

if [[ "${WRITE_RAW:-0}" == "1" ]]; then
  collector_args+=(--write-raw)
fi

if [[ -n "${DURATION_SEC:-}" && "${DURATION_SEC:-0}" != "0" ]]; then
  collector_args+=(--duration-sec "${DURATION_SEC}")
fi

if [[ -n "${FLUSH_SEC:-}" ]]; then
  collector_args+=(--flush-sec "${FLUSH_SEC}")
fi

if [[ -n "${HYPERLIQUID_POLL_SEC:-}" ]]; then
  collector_args+=(--hyperliquid-poll-sec "${HYPERLIQUID_POLL_SEC}")
fi

if [[ -n "${PARQUET_BATCH_SEC:-}" ]]; then
  collector_args+=(--parquet-batch-sec "${PARQUET_BATCH_SEC}")
fi

if [[ -n "${TRADE_AGGREGATE_SEC:-}" ]]; then
  collector_args+=(--trade-aggregate-sec "${TRADE_AGGREGATE_SEC}")
fi

if [[ -n "${PARQUET_COMPRESSION:-}" ]]; then
  collector_args+=(--parquet-compression "${PARQUET_COMPRESSION}")
fi

if [[ -n "${EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_args=( ${EXTRA_ARGS} )
  collector_args+=("${extra_args[@]}")
fi

echo "[entrypoint] starting live collector"
echo "[entrypoint] args: ${collector_args[*]}"
exec python -u -m src.collectors.live.collect_all_live "${collector_args[@]}"
