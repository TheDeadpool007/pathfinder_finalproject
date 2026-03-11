# src/tools/currency.py
"""
Currency conversion using frankfurter.app — completely free, no API key.
https://www.frankfurter.app/
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

import requests

from src.tools.cache import TTLCache, make_key

logger = logging.getLogger(__name__)

_cache: TTLCache[Dict[str, float]] = TTLCache(default_ttl_s=3600, max_items=64)

BASE_URL = "https://api.frankfurter.app"

# Destination city → ISO currency code
DESTINATION_CURRENCY: Dict[str, str] = {
    "paris, france": "EUR",
    "london, uk": "GBP",
    "new york, usa": "USD",
    "tokyo, japan": "JPY",
    "rome, italy": "EUR",
    "barcelona, spain": "EUR",
    "amsterdam, netherlands": "EUR",
    "berlin, germany": "EUR",
    "dubai, uae": "AED",
    "singapore": "SGD",
    "sydney, australia": "AUD",
    "los angeles, usa": "USD",
    "chicago, usa": "USD",
    "toronto, canada": "CAD",
    "mumbai, india": "INR",
    "bangkok, thailand": "THB",
    "istanbul, turkey": "TRY",
    "prague, czech republic": "CZK",
    "vienna, austria": "EUR",
    "lisbon, portugal": "EUR",
    "athens, greece": "EUR",
    "budapest, hungary": "HUF",
    "cairo, egypt": "EGP",
    "cape town, south africa": "ZAR",
    "mexico city, mexico": "MXN",
    "buenos aires, argentina": "ARS",
    "seoul, south korea": "KRW",
    "kyoto, japan": "JPY",
    "bali, indonesia": "IDR",
    "marrakech, morocco": "MAD",
}


def get_local_currency(destination: str) -> str:
    """Return the ISO currency code for a destination, defaulting to USD."""
    return DESTINATION_CURRENCY.get(destination.lower(), "USD")


def convert(amount_usd: float, to_currency: str) -> Optional[float]:
    """
    Convert an amount from USD to to_currency.
    Returns None if conversion fails or currency is already USD.
    """
    if to_currency == "USD" or amount_usd <= 0:
        return None

    key = make_key("fx", f"USD_{to_currency}")
    rates = _cache.get(key)

    if rates is None:
        try:
            resp = requests.get(
                f"{BASE_URL}/latest",
                params={"from": "USD", "to": to_currency},
                timeout=8,
                headers={"User-Agent": "agentic-travel-planner/1.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get("rates", {})
                _cache.set(key, rates)
            else:
                return None
        except Exception as e:
            logger.debug(f"Currency fetch failed: {e}")
            return None

    rate = rates.get(to_currency)
    if rate is None:
        return None
    return round(amount_usd * rate, 2)
