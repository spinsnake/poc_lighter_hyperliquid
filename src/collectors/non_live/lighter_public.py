from __future__ import annotations

import requests


BASE_URL = "https://mainnet.zklighter.elliot.ai/api/v1"
TIMEOUT_SECONDS = 30


def _get(path: str) -> dict:
    response = requests.get(f"{BASE_URL}/{path}", timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def fetch_order_book_details() -> dict:
    return _get("orderBookDetails")


def fetch_exchange_stats() -> dict:
    return _get("exchangeStats")


def fetch_funding_rates() -> dict:
    return _get("funding-rates")


def fetch_fundings(
    market_id: int,
    resolution: str,
    start_timestamp: int,
    end_timestamp: int,
    count_back: int,
) -> dict:
    response = requests.get(
        f"{BASE_URL}/fundings",
        params={
            "market_id": market_id,
            "resolution": resolution,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "count_back": count_back,
        },
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def fetch_reference_bundle() -> dict:
    return {
        "orderBookDetails": fetch_order_book_details(),
        "exchangeStats": fetch_exchange_stats(),
        "fundingRates": fetch_funding_rates(),
    }
