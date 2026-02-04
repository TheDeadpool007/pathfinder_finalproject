# src/core/orchestrator.py
"""
Orchestrator
- Coordinates all agents in sequence
- Acts as the central controller for the agentic system
- Adds REAL geocoding fallback (Geoapify) when lat/lon are missing/0
- Adds REAL weather (Open-Meteo) per day
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, Any, List, Optional, Tuple

import requests

from src.agents.searcher_agent import SearcherAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.budget_agent import BudgetAgent
from src.agents.explainer_agent import ExplainerAgent
from src.core.models import DayItinerary, DayWeather
from src.tools.openmeteo import OpenMeteoClient

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

        self._session = requests.Session()

        logger.info("Orchestrator initialized")

    def run(
        self,
        destination: str,
        lat: float,
        lon: float,
        num_days: int,
        interests: List[str],
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
            daily = self.weather.daily_forecast(lat=lat, lon=lon, days=max(num_days, 1), timezone="auto")
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

        # 2) PlannerAgent (Routing per day)
        itineraries: List[DayItinerary] = self.planner.execute(pois=pois, num_days=num_days)

        # 2.5) Attach weather per day (Day 1 -> forecast[0], etc.)
        if weather_by_day:
            for it in itineraries:
                idx = it.day - 1
                if 0 <= idx < len(weather_by_day):
                    it.weather = weather_by_day[idx]

        # 3) BudgetAgent (uses day.pois + day.total_distance_km)
        itineraries = self.budgeter.execute(itineraries)

        # 4) ExplainerAgent (text summary)
        explanation = self.explainer.execute(itineraries=itineraries, destination=destination)

        logger.info("Pipeline completed successfully")

        return {
            "destination": destination,
            "days": num_days,
            "itineraries": itineraries,
            "explanation": explanation,
            "coords": {"lat": lat, "lon": lon},
        }

    # -------------------------
    # Helpers
    # -------------------------

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
