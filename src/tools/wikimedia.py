# src/tools/wikimedia.py
"""
Wikimedia Commons / Wikipedia thumbnail fetcher.
No API key required. Uses the Wikipedia REST summary API.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

from src.tools.cache import TTLCache, make_key

logger = logging.getLogger(__name__)

_cache: TTLCache[Optional[str]] = TTLCache(default_ttl_s=3600, max_items=512)


def fetch_photo_url(place_name: str, timeout: int = 6) -> Optional[str]:
    """
    Return a thumbnail URL for a place name using the Wikipedia REST API.
    Returns None if nothing is found or the request fails.
    """
    if not place_name or not place_name.strip():
        return None

    key = make_key("wiki_photo", place_name.strip().lower())
    cached = _cache.get(key)
    if cached is not None:
        return cached if cached != "__NONE__" else None

    # Wikipedia page summary endpoint
    title = place_name.strip().replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}"

    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "agentic-travel-planner/1.0 (educational project)"},
        )
        if resp.status_code == 200:
            data = resp.json()
            thumb = data.get("thumbnail") or data.get("originalimage")
            if thumb and thumb.get("source"):
                photo_url = thumb["source"]
                _cache.set(key, photo_url)
                return photo_url
    except Exception as e:
        logger.debug(f"Wikimedia fetch failed for '{place_name}': {e}")

    _cache.set(key, "__NONE__")
    return None
