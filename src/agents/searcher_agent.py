# src/agents/searcher_agent.py
from __future__ import annotations

import logging
from typing import List, Optional

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

    def execute(
        self,
        *,
        lat: float,
        lon: float,
        interests: List[str],
        budget_per_day: Optional[float] = None,
        constraints: Optional[List[str]] = None,
        radius_m: int = 6000,
        per_interest_limit: int = 12,
    ) -> List[POI]:
        logger.info("SearcherAgent: fetching POIs from Geoapify Places")

        normalized = self._normalize_interests(interests)
        logger.info(f"SearcherAgent: interests normalized from {interests} -> {normalized}")

        geo_places = self.places.search_by_interests(
            center_lat=lat,
            center_lon=lon,
            interests=normalized,
            radius_m=radius_m,
            per_interest_limit=per_interest_limit,
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

        pois = self._rank_pois(pois, budget_per_day=budget_per_day, constraints=constraints)

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

    def _rank_pois(
        self,
        pois: List[POI],
        *,
        budget_per_day: Optional[float] = None,
        constraints: Optional[List[str]] = None,
    ) -> List[POI]:
        """
        Rank POIs by practical travel fit.

        The goal is not strict optimization, but a visible quality gain:
        cheaper / more accessible options are promoted when the user asks for them.
        """
        normalized_constraints = {
            (c or "").strip().lower() for c in (constraints or []) if (c or "").strip()
        }
        low_budget = budget_per_day is not None and float(budget_per_day) <= 80.0

        def score(poi: POI) -> float:
            text = " ".join([poi.name, poi.description, " ".join(poi.categories or [])]).lower()
            value = float(poi.rating or 0.0)

            if poi.fee is False:
                value += 1.5
            elif poi.fee is True:
                value -= 1.0

            if low_budget:
                value += 1.5 if poi.fee is False else -1.5

            if any(k in normalized_constraints for k in {"cheap", "budget", "low budget", "tight budget"}):
                value += 1.25 if poi.fee is False else -1.25

            if any(k in normalized_constraints for k in {"accessibility", "accessible", "wheelchair", "mobility"}):
                if any(word in text for word in ["museum", "gallery", "park", "garden", "square", "promenade"]):
                    value += 1.0
                if any(word in text for word in ["stairs", "cliff", "mountain", "club", "bar", "nightlife"]):
                    value -= 1.0

            if any(k in normalized_constraints for k in {"family", "kids", "children"}):
                if any(word in text for word in ["park", "museum", "garden", "zoo", "aquarium"]):
                    value += 1.0
                if any(word in text for word in ["bar", "club", "nightlife"]):
                    value -= 1.0

            return value

        return sorted(pois, key=score, reverse=True)
