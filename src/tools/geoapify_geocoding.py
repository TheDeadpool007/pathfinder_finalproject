# src/tools/geoapify_geocoding.py
"""
Geoapify Geocoding tool (NO fallbacks).
- Forward geocoding: place name/address -> (lat, lon)
Docs: https://apidocs.geoapify.com/docs/geocoding/
"""

import os
from typing import Optional, Tuple, Dict, Any
import requests


class GeoapifyGeocoder:
    BASE_URL = "https://api.geoapify.com/v1/geocode/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEOAPIFY_API_KEY")
        if not self.api_key:
            raise ValueError("GEOAPIFY_API_KEY is not set in environment (.env).")

    def geocode(self, query: str) -> Tuple[float, float, Dict[str, Any]]:
        """
        Returns (lat, lon, raw_feature_properties).
        Raises ValueError if not found.
        """
        q = (query or "").strip()
        if not q:
            raise ValueError("Destination query is empty.")

        params = {
            "text": q,
            "format": "json",
            "limit": 1,
            "apiKey": self.api_key,
        }

        r = requests.get(self.BASE_URL, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()

        results = data.get("results") or []
        if not results:
            raise ValueError(f"No geocoding results for: {query}")

        top = results[0]
        lat = float(top["lat"])
        lon = float(top["lon"])
        return lat, lon, top
