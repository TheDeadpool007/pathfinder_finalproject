# src/tools/geoapify_places.py
from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from src.tools.cache import TTLCache, make_key

logger = logging.getLogger(__name__)


class GeoapifyPlacesError(RuntimeError):
    pass


@dataclass
class GeoapifyPlace:
    name: str
    lat: float
    lon: float
    formatted: str = ""
    categories: List[str] = None
    website: str = ""
    phone: str = ""
    opening_hours: str = ""
    rating: Optional[float] = None
    fee: Optional[bool] = None

    def __post_init__(self) -> None:
        if self.categories is None:
            self.categories = []


class GeoapifyPlacesClient:
    """
    Geoapify Places API client (v2/places).
    - Reliability-first: retries + category auto-fallback on 400 invalid category
    - Caching: TTL cache for GET requests (reduces rate limits / speeds up reruns)
    """

    BASE_URL = "https://api.geoapify.com/v2/places"

    def __init__(
        self,
        timeout: int = 25,
        max_retries: int = 3,
        backoff_s: float = 1.2,
        cache_ttl_s: int = 600,  # 10 min
        user_agent: str = "agentic-travel-planner/1.0",
    ) -> None:
        self.api_key = os.getenv("GEOAPIFY_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GEOAPIFY_API_KEY not found. "
                "Make sure load_dotenv() is called before importing/creating GeoapifyPlacesClient."
            )

        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_s = backoff_s

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

        self.cache = TTLCache[Dict[str, Any]](default_ttl_s=cache_ttl_s, max_items=512)

    # -------------------------
    # Public API
    # -------------------------

    def search_by_interests(
        self,
        *,
        center_lat: float,
        center_lon: float,
        interests: List[str],
        radius_m: int = 6000,
        per_interest_limit: int = 12,
        lang: str = "en",
    ) -> List[GeoapifyPlace]:
        """
        For each interest, map -> category list, query Places, and merge results.
        Deduping is done lightly (by place_id if present, otherwise name+coords).
        """
        if not interests:
            raise ValueError("interests is empty")

        all_places: List[GeoapifyPlace] = []
        seen: set[str] = set()

        for interest in interests:
            cats = self._interest_to_categories(interest)
            places = self._search_nearby(
                lat=center_lat,
                lon=center_lon,
                radius_m=radius_m,
                categories=cats,
                limit=per_interest_limit,
                lang=lang,
            )

            for p in places:
                # best-effort dedupe key
                k = f"{p.name.strip().lower()}::{round(p.lat, 5)}::{round(p.lon, 5)}"
                if k in seen:
                    continue
                seen.add(k)
                all_places.append(p)

        return all_places

    # -------------------------
    # Internals
    # -------------------------

    def _interest_to_categories(self, interest: str) -> List[str]:
        """
        IMPORTANT: only use categories that are known to work reliably.
        We also auto-fallback on 400 invalid category later.

        Notes:
        - The earlier error was: tourism.museum is NOT supported.
        - Geoapify commonly uses entertainment.museum for museums.
        """
        s = (interest or "").strip().lower()

        # safest broad buckets (almost always supported)
        BROAD_TOURISM = "tourism"
        BROAD_ENTERTAINMENT = "entertainment"
        BROAD_CATERING = "catering"
        BROAD_LEISURE = "leisure"
        BROAD_COMMERCIAL = "commercial"

        mapping: Dict[str, List[str]] = {
            # ✅ museums: use entertainment.museum (NOT tourism.museum)
            "museums": ["entertainment.museum", BROAD_ENTERTAINMENT, BROAD_TOURISM],
            "museum": ["entertainment.museum", BROAD_ENTERTAINMENT, BROAD_TOURISM],

            # history/culture: keep broad tourism + heritage-ish via tourism/building if supported
            "history": [BROAD_TOURISM, "building.historic", "heritage", BROAD_ENTERTAINMENT],
            "culture": [BROAD_TOURISM, BROAD_ENTERTAINMENT],

            # art: galleries are sometimes available; keep broad fallback
            "art": ["entertainment.gallery", BROAD_ENTERTAINMENT, BROAD_TOURISM],

            # general sightseeing
            "attractions": [BROAD_TOURISM],
            "sights": [BROAD_TOURISM],
            "highlights": [BROAD_TOURISM],

            # food
            "food": [BROAD_CATERING],
            "restaurants": ["catering.restaurant", BROAD_CATERING],
            "cafe": ["catering.cafe", BROAD_CATERING],

            # outdoors
            "parks": ["leisure.park", BROAD_LEISURE],
            "nature": [BROAD_LEISURE],

            # shopping
            "shopping": [BROAD_COMMERCIAL],

            # nightlife (keep broad entertainment; adult categories exist but we avoid them)
            "nightlife": [BROAD_ENTERTAINMENT],

            # transport + essentials
            "transport": ["transport"],
            "essentials": ["service", "amenity"],
        }

        # default safe fallback
        return mapping.get(s, [BROAD_TOURISM, BROAD_ENTERTAINMENT])

    def _search_nearby(
        self,
        *,
        lat: float,
        lon: float,
        radius_m: int,
        categories: List[str],
        limit: int,
        lang: str,
    ) -> List[GeoapifyPlace]:
        """
        Call Geoapify Places.
        If a category is invalid (HTTP 400 + message), automatically retry with
        progressively broader categories instead of crashing your app.
        """
        cats = [c for c in (categories or []) if c]
        if not cats:
            cats = ["tourism", "entertainment"]

        # 1) attempt as requested
        try:
            data = self._get_places(lat=lat, lon=lon, radius_m=radius_m, categories=cats, limit=limit, lang=lang)
            return self._parse_places(data)
        except GeoapifyPlacesError as e:
            msg = str(e)
            # 2) If invalid category, remove it and retry
            bad_cat = self._extract_unsupported_category(msg)
            if bad_cat and bad_cat in cats and len(cats) > 1:
                logger.warning(f"Geoapify Places: category '{bad_cat}' unsupported. Retrying without it.")
                cats2 = [c for c in cats if c != bad_cat]
                data = self._get_places(lat=lat, lon=lon, radius_m=radius_m, categories=cats2, limit=limit, lang=lang)
                return self._parse_places(data)

            # 3) last-resort fallback: super broad
            logger.warning(f"Geoapify Places: retrying with broad categories due to error: {msg}")
            data = self._get_places(
                lat=lat,
                lon=lon,
                radius_m=radius_m,
                categories=["tourism", "entertainment"],
                limit=limit,
                lang=lang,
            )
            return self._parse_places(data)

    def _get_places(
        self,
        *,
        lat: float,
        lon: float,
        radius_m: int,
        categories: List[str],
        limit: int,
        lang: str,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "apiKey": self.api_key,
            "categories": ",".join(categories),
            # Geoapify uses filter circle: lon,lat,radius
            "filter": f"circle:{lon},{lat},{int(radius_m)}",
            "bias": f"proximity:{lon},{lat}",
            "limit": int(limit),
            "lang": lang,
        }
        return self._get(self.BASE_URL, params=params)

    def _get(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cached GET with retries. Cache key includes URL + params.
        """
        key = make_key("GET", url, sorted(params.items()))

        cached = self.cache.get(key)
        if cached is not None:
            logger.debug("Geoapify Places cache hit")
            return cached

        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)

                # retryable HTTPs
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < self.max_retries:
                        sleep_s = self.backoff_s * (attempt + 1)
                        logger.warning(
                            f"Geoapify Places retry {attempt+1}/{self.max_retries} "
                            f"(HTTP {resp.status_code}), sleeping {sleep_s:.1f}s"
                        )
                        time.sleep(sleep_s)
                        continue

                if resp.status_code >= 400:
                    msg = f"Geoapify Places HTTP {resp.status_code}: {resp.text} | params={params}"
                    raise GeoapifyPlacesError(msg)

                data = resp.json()

                # store in cache
                self.cache.set(key, data)
                return data

            except (requests.RequestException, ValueError, GeoapifyPlacesError) as e:
                last_err = e
                if attempt < self.max_retries:
                    sleep_s = self.backoff_s * (attempt + 1)
                    logger.warning(f"Geoapify Places exception retry {attempt+1}/{self.max_retries}: {e} (sleep {sleep_s:.1f}s)")
                    time.sleep(sleep_s)
                    continue
                break

        raise GeoapifyPlacesError(f"Geoapify Places request failed after retries: {last_err}")

    def _parse_places(self, data: Dict[str, Any]) -> List[GeoapifyPlace]:
        """
        Parse Geoapify Places GeoJSON:
        features[].properties.{name, formatted, lat, lon, categories}
        """
        features = data.get("features") or []
        out: List[GeoapifyPlace] = []

        for f in features:
            props = (f or {}).get("properties") or {}
            name = props.get("name") or props.get("address_line1") or "Unknown place"

            # Geoapify returns lat/lon in properties for places
            lat = props.get("lat")
            lon = props.get("lon")
            if lat is None or lon is None:
                # sometimes geometry exists
                geom = (f or {}).get("geometry") or {}
                coords = geom.get("coordinates")
                if isinstance(coords, list) and len(coords) >= 2:
                    lon, lat = coords[0], coords[1]

            if lat is None or lon is None:
                continue

            formatted = props.get("formatted") or props.get("address_line2") or ""
            categories = props.get("categories") or []

            # Extended fields
            website = props.get("website") or props.get("contact:website") or ""
            phone = props.get("phone") or props.get("contact:phone") or ""
            opening_hours = props.get("opening_hours") or ""
            raw_rating = props.get("rating")
            rating: Optional[float] = float(raw_rating) if raw_rating is not None else None
            raw_fee = props.get("fee")
            fee: Optional[bool] = None
            if isinstance(raw_fee, bool):
                fee = raw_fee
            elif isinstance(raw_fee, str):
                fee = raw_fee.lower() in ("yes", "true", "1")

            out.append(
                GeoapifyPlace(
                    name=str(name),
                    lat=float(lat),
                    lon=float(lon),
                    formatted=str(formatted) if formatted else "",
                    categories=[str(c) for c in categories] if isinstance(categories, list) else [],
                    website=str(website) if website else "",
                    phone=str(phone) if phone else "",
                    opening_hours=str(opening_hours) if opening_hours else "",
                    rating=rating,
                    fee=fee,
                )
            )

        return out

    def _extract_unsupported_category(self, error_msg: str) -> Optional[str]:
        """
        Extracts category from:
        'Category "tourism.museum" is not supported.'
        """
        if "Category" not in error_msg or "is not supported" not in error_msg:
            return None
        # crude but effective parsing
        try:
            left = error_msg.split('Category "', 1)[1]
            cat = left.split('"', 1)[0]
            return cat.strip() or None
        except Exception:
            return None
