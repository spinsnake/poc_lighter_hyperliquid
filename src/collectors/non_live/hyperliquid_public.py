from __future__ import annotations

import requests


BASE_URL = "https://api.hyperliquid.xyz/info"
TIMEOUT_SECONDS = 30


def _post(payload: dict) -> dict | list:
    response = requests.post(BASE_URL, json=payload, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def fetch_meta() -> dict:
    return _post({"type": "meta"})


def fetch_meta_and_asset_ctxs() -> list:
    return _post({"type": "metaAndAssetCtxs"})


def fetch_perp_dexs() -> list:
    return _post({"type": "perpDexs"})


def fetch_predicted_fundings() -> list:
    return _post({"type": "predictedFundings"})


def fetch_funding_history(coin: str, start_time_ms: int) -> list:
    return _post({"type": "fundingHistory", "coin": coin, "startTime": start_time_ms})


def fetch_user_funding(user: str, start_time_ms: int) -> list:
    return _post({"type": "userFunding", "user": user, "startTime": start_time_ms})


def fetch_reference_bundle() -> dict:
    return {
        "meta": fetch_meta(),
        "metaAndAssetCtxs": fetch_meta_and_asset_ctxs(),
        "perpDexs": fetch_perp_dexs(),
        "predictedFundings": fetch_predicted_fundings(),
    }

