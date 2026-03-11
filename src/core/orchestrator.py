# src/core/orchestrator.py
"""
Orchestrator
- Coordinates all agents in sequence
- Acts as the central controller for the agentic system
- Adds REAL geocoding fallback (Geoapify) when lat/lon are missing/0
- Adds REAL weather (Open-Meteo) per day
"""

from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Dict, Any, List, Optional, Tuple

import requests

from src.agents.searcher_agent import SearcherAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.budget_agent import BudgetAgent
from src.agents.explainer_agent import ExplainerAgent
from src.core.models import DayItinerary, DayWeather, POI
from src.tools.openmeteo import OpenMeteoClient
from src.tools.geoapify_geocoding import GeoapifyGeocoder
from src.tools.wikimedia import fetch_photo_url
from src.tools.geoapify_places import GeoapifyPlacesClient
from src.tools.llm_ollama import OllamaLLM

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Orchestrator coordinates the multi-agent travel planning pipeline.
    """

    def __init__(self):
        self.searcher = SearcherAgent()
        self.planner = PlannerAgent()
        self.budgeter = BudgetAgent()
        self.explainer = ExplainerAgent()
        self.weather = OpenMeteoClient()
        self.llm = OllamaLLM()
        self._session = requests.Session()
        logger.info("Orchestrator initialized")

    def run(
        self,
        destination: str,
        lat: float,
        lon: float,
        num_days: int,
        interests: List[str],
        start_date: Optional[datetime.date] = None,
        start_location: Optional[str] = None,
        end_location: Optional[str] = None,
        transport_mode: str = "auto",
    ) -> Dict[str, Any]:
        """
        Execute the full agent pipeline.
        """

        logger.info(f"Starting pipeline for destination={destination}")

        # 0) Ensure we have valid coordinates
        if not self._coords_look_valid(lat, lon):
            logger.info("Lat/lon missing or invalid -> geocoding destination using Geoapify")
            lat, lon = self._geocode_destination(destination)
            logger.info(f"Geocoded destination='{destination}' -> lat={lat}, lon={lon}")

        # 0.5) Weather (best-effort; do NOT fail whole pipeline if weather fails)
        weather_by_day: List[DayWeather] = []
        try:
            daily = self.weather.daily_forecast(
                lat=lat,
                lon=lon,
                days=max(num_days, 1),
                timezone="auto",
                start_date=start_date,
            )
            weather_by_day = [
                DayWeather(
                    date=w.date,
                    temp_min_c=w.temp_min_c,
                    temp_max_c=w.temp_max_c,
                    precip_mm=w.precip_mm,
                    weather_code=w.weather_code,
                    weather_text=w.weather_text,
                )
                for w in daily
            ]
        except Exception as e:
            logger.warning(f"Weather fetch failed (Open-Meteo): {e}")
            weather_by_day = []

        # 1) SearcherAgent (Geoapify Places)
        pois = self.searcher.execute(lat=lat, lon=lon, interests=interests)

        # 1.5) Geocode start/end locations if provided
        start_coords: Optional[Tuple[float, float]] = None
        end_coords: Optional[Tuple[float, float]] = None
        if start_location or end_location:
            geocoder = GeoapifyGeocoder()
            if start_location:
                try:
                    s_lat, s_lon, _ = geocoder.geocode(start_location)
                    start_coords = (s_lat, s_lon)
                    logger.info(f"Start location '{start_location}' -> {start_coords}")
                except Exception as e:
                    logger.warning(f"Could not geocode start location '{start_location}': {e}")
            if end_location:
                try:
                    e_lat, e_lon, _ = geocoder.geocode(end_location)
                    end_coords = (e_lat, e_lon)
                    logger.info(f"End location '{end_location}' -> {end_coords}")
                except Exception as e:
                    logger.warning(f"Could not geocode end location '{end_location}': {e}")

        # 2) Detect intercity travel: if start is >200 km from destination, fly there
        # and don't inject cross-country coords into day routing
        FLIGHT_THRESHOLD_KM = 200.0
        intercity_mode = "local"
        planner_start_coords = start_coords
        planner_end_coords = end_coords
        if start_coords:
            dist_to_dest_km = self._haversine_km(start_coords[0], start_coords[1], lat, lon)
            if dist_to_dest_km > FLIGHT_THRESHOLD_KM:
                intercity_mode = "flight"
                planner_start_coords = None
                planner_end_coords = None
                logger.info(
                    f"Start '{start_location}' is {dist_to_dest_km:.0f} km from destination "
                    f"-> intercity mode = flight, day routes will be within-city only"
                )

        # 2) PlannerAgent (Routing per day)
        itineraries: List[DayItinerary] = self.planner.execute(
            pois=pois,
            num_days=num_days,
            start_coords=planner_start_coords,
            end_coords=planner_end_coords,
            transport_mode=transport_mode,
        )

        # 2.5) Attach weather per day (Day 1 -> forecast[0], etc.)
        if weather_by_day:
            for it in itineraries:
                idx = it.day - 1
                if 0 <= idx < len(weather_by_day):
                    it.weather = weather_by_day[idx]

        # 3) BudgetAgent (uses day.pois + day.total_distance_km)
        itineraries = self.budgeter.execute(itineraries)

        # 3.5) Enrich POIs: Wikimedia photo + Ollama description (best-effort)
        ollama_ok = self.llm.is_available()
        places_client = GeoapifyPlacesClient()
        for it in itineraries:
            # Nearby restaurants for this day (centre of day's POIs)
            if it.pois:
                day_lat = sum(p.lat for p in it.pois) / len(it.pois)
                day_lon = sum(p.lon for p in it.pois) / len(it.pois)
                try:
                    raw_restaurants = places_client.search_by_interests(
                        center_lat=day_lat,
                        center_lon=day_lon,
                        interests=["restaurants"],
                        radius_m=1000,
                        per_interest_limit=5,
                    )
                    it.restaurants = [
                        POI(
                            name=r.name,
                            lat=r.lat,
                            lon=r.lon,
                            address=r.formatted or "",
                            categories=r.categories or [],
                            website=r.website or "",
                            phone=r.phone or "",
                            opening_hours=r.opening_hours or "",
                            rating=r.rating,
                            source="geoapify",
                        )
                        for r in raw_restaurants
                    ]
                except Exception as e:
                    logger.warning(f"Restaurant fetch failed for day {it.day}: {e}")
                    it.restaurants = []

            for poi in it.pois:
                # Photo from Wikimedia (best-effort)
                if not poi.photo_url:
                    try:
                        poi.photo_url = fetch_photo_url(poi.name) or ""
                    except Exception:
                        pass
                # Description from Ollama (best-effort, only if not already set)
                if ollama_ok and not poi.description:
                    try:
                        prompt = (
                            f"In 2 sentences, describe the attraction '{poi.name}' "
                            f"located at {poi.address or destination} for a tourist."
                        )
                        desc = self.llm.generate(prompt, max_tokens=80)
                        if desc:
                            poi.description = desc.strip()
                    except Exception:
                        pass

        # 4) ExplainerAgent (text summary)
        explanation = self.explainer.execute(itineraries=itineraries, destination=destination)

        logger.info("Pipeline completed successfully")

        return {
            "destination": destination,
            "days": num_days,
            "itineraries": itineraries,
            "explanation": explanation,
            "coords": {"lat": lat, "lon": lon},
            "start_location": start_location or "",
            "end_location": end_location or start_location or "",
            "transport_mode": transport_mode,
            "intercity_mode": intercity_mode,
        }

    # -------------------------
    # Helpers
    # -------------------------

    def _haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance in km between two lat/lon points."""
        import math
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _coords_look_valid(self, lat: float, lon: float) -> bool:
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except Exception:
            return False

        # Treat (0,0) as invalid for our use case
        if abs(lat_f) < 1e-9 and abs(lon_f) < 1e-9:
            return False

        return -90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0

    def _geocode_destination(self, destination: str) -> Tuple[float, float]:
        """
        Geoapify Geocoding API (real-time).
        Endpoint: /v1/geocode/search?text=...&apiKey=...
        """
        api_key = os.getenv("GEOAPIFY_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEOAPIFY_API_KEY not found. Make sure .env is loaded (load_dotenv at top of app.py)."
            )

        url = "https://api.geoapify.com/v1/geocode/search"
        params = {
            "text": destination,
            "limit": 1,
            "format": "json",
            "apiKey": api_key,
        }

        last_err: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = self._session.get(url, params=params, timeout=20)
                if resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(1.2 * (attempt + 1))
                    continue
                if resp.status_code >= 400:
                    raise RuntimeError(f"Geoapify geocoding error {resp.status_code}: {resp.text}")

                data = resp.json()
                results = data.get("results") or []
                if not results:
                    raise RuntimeError(f"Geoapify geocoding returned 0 results for '{destination}'")

                r0 = results[0]
                lat = r0.get("lat")
                lon = r0.get("lon")
                if lat is None or lon is None:
                    raise RuntimeError(f"Geoapify geocoding missing lat/lon for '{destination}'")

                return float(lat), float(lon)

            except Exception as e:
                last_err = e
                time.sleep(1.2 * (attempt + 1))

        raise RuntimeError(f"Geocoding failed after retries: {last_err}")
