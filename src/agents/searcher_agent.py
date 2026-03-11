# src/agents/searcher_agent.py
from __future__ import annotations

import logging
from typing import List

from src.core.models import POI
from src.tools.geoapify_places import GeoapifyPlacesClient

logger = logging.getLogger(__name__)


class SearcherAgent:
    """
    REAL-TIME POI fetcher using Geoapify Places.
    - Normalizes UI interests (e.g., "Museums" / "History") into safe keys
    - No Wikipedia / OpenTripMap / dummy data
    """

    # Map common UI labels -> canonical interest keys that GeoapifyPlacesClient supports
    INTEREST_ALIASES = {
        "museum": "museums",
        "museums": "museums",
        "history": "culture",      # history usually maps best to culture/museums/attractions
        "historical": "culture",
        "culture": "culture",
        "art": "culture",
        "attraction": "attractions",
        "attractions": "attractions",
        "sightseeing": "attractions",
        "food": "food",
        "restaurants": "food",
        "cafe": "cafes",
        "cafes": "cafes",
        "nightlife": "nightlife",
        "bars": "nightlife",
        "park": "parks",
        "parks": "parks",
        "nature": "nature",
        "shopping": "shopping",
        "transport": "transport",
        "essentials": "essentials",
    }

    def __init__(self) -> None:
        self.places = GeoapifyPlacesClient()

    def execute(self, *, lat: float, lon: float, interests: List[str]) -> List[POI]:
        logger.info("SearcherAgent: fetching POIs from Geoapify Places")

        normalized = self._normalize_interests(interests)
        logger.info(f"SearcherAgent: interests normalized from {interests} -> {normalized}")

        geo_places = self.places.search_by_interests(
            center_lat=lat,
            center_lon=lon,
            interests=normalized,
            radius_m=6000,
            per_interest_limit=12,
            lang="en",
        )

        pois: List[POI] = []
        for p in geo_places:
            # Provide a simple, non-LLM description for UI compatibility
            # (Geoapify doesn't reliably provide a narrative description)
            # Build readable description from categories only (address stored separately)
            if p.categories:
                nice = [c.split(".")[-1].replace("_", " ").title() for c in p.categories[:4]]
                description = " · ".join(nice)
            else:
                description = ""

            pois.append(
                POI(
                    name=p.name,
                    lat=p.lat,
                    lon=p.lon,
                    address=p.formatted or "",
                    description=description,
                    categories=p.categories or [],
                    source="geoapify",
                    website=p.website or "",
                    phone=p.phone or "",
                    opening_hours=p.opening_hours or "",
                    rating=p.rating,
                    fee=p.fee,
                )
            )

        logger.info(f"SearcherAgent: fetched {len(pois)} POIs")
        return pois

    def _normalize_interests(self, interests: List[str]) -> List[str]:
        """
        Normalize interests from UI input into canonical keys.

        - trims spaces
        - lowercases
        - maps common synonyms ("History" -> "culture")
        - de-dupes preserving order
        """
        out: List[str] = []
        seen = set()

        for raw in interests or []:
            key = (raw or "").strip().lower()
            if not key:
                continue

            key = self.INTEREST_ALIASES.get(key, key)

            if key not in seen:
                seen.add(key)
                out.append(key)

        # If user picks nothing / all unknown, keep system reliable by using safe defaults.
        if not out:
            out = ["attractions", "food", "parks"]

        return out
