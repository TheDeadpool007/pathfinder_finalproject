from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple, TypedDict

import requests
from langgraph.graph import END, StateGraph

from src.agents.budget_agent import BudgetAgent
from src.agents.explainer_agent import ExplainerAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.searcher_agent import SearcherAgent
from src.core.models import DayItinerary, DayWeather, POI
from src.tools.geoapify_geocoding import GeoapifyGeocoder
from src.tools.geoapify_places import GeoapifyPlacesClient
from src.tools.llm_groq import GroqLLM
from src.tools.llm_ollama import OllamaLLM
from src.tools.openmeteo import OpenMeteoClient
from src.tools.wikimedia import fetch_photo_url

logger = logging.getLogger(__name__)


class OrchestratorState(TypedDict, total=False):
    destination: str
    lat: float
    lon: float
    num_days: int
    interests: List[str]
    budget_per_day: Optional[float]
    constraints: List[str]
    start_date: Optional[datetime.date]
    start_location: str
    end_location: str
    transport_mode: str

    # Search controls for autonomous retries
    search_interests: List[str]
    search_radius_m: int
    search_per_interest_limit: int
    relaxed_search_done: bool

    weather_by_day: List[DayWeather]
    pois: List[POI]

    start_coords: Optional[Tuple[float, float]]
    end_coords: Optional[Tuple[float, float]]
    planner_start_coords: Optional[Tuple[float, float]]
    planner_end_coords: Optional[Tuple[float, float]]
    intercity_mode: str

    itineraries: List[DayItinerary]
    explanation: str

    budget_status: str
    budget_warning: str


class Orchestrator:
    """Autonomous travel orchestrator implemented as a LangGraph state machine."""

    def __init__(self):
        self.searcher = SearcherAgent()
        self.planner = PlannerAgent()
        self.budgeter = BudgetAgent()
        self.explainer = ExplainerAgent()
        self.weather = OpenMeteoClient()
        self.ollama = OllamaLLM()
        self.groq = GroqLLM()
        self._session = requests.Session()
        self.graph = self._build_graph()
        logger.info("Orchestrator initialized (LangGraph)")

    def _build_graph(self):
        builder = StateGraph(OrchestratorState)

        builder.add_node("ensure_coords", self._node_ensure_coords)
        builder.add_node("fetch_weather", self._node_fetch_weather)
        builder.add_node("search_pois", self._node_search_pois)
        builder.add_node("relax_search", self._node_relax_search)
        builder.add_node("geocode_endpoints", self._node_geocode_endpoints)
        builder.add_node("plan_itinerary", self._node_plan_itinerary)
        builder.add_node("attach_weather", self._node_attach_weather)
        builder.add_node("budget_itinerary", self._node_budget_itinerary)
        builder.add_node("enrich_itinerary", self._node_enrich_itinerary)
        builder.add_node("explain", self._node_explain)

        builder.set_entry_point("ensure_coords")
        builder.add_edge("ensure_coords", "fetch_weather")
        builder.add_edge("fetch_weather", "search_pois")

        builder.add_conditional_edges(
            "search_pois",
            self._should_relax_search,
            {
                "relax": "relax_search",
                "continue": "geocode_endpoints",
            },
        )

        builder.add_edge("relax_search", "search_pois")
        builder.add_edge("geocode_endpoints", "plan_itinerary")
        builder.add_edge("plan_itinerary", "attach_weather")
        builder.add_edge("attach_weather", "budget_itinerary")
        builder.add_edge("budget_itinerary", "enrich_itinerary")
        builder.add_edge("enrich_itinerary", "explain")
        builder.add_edge("explain", END)

        return builder.compile()

    def run(
        self,
        destination: str,
        lat: float,
        lon: float,
        num_days: int,
        interests: List[str],
        budget_per_day: Optional[float] = None,
        constraints: Optional[List[str]] = None,
        start_date: Optional[datetime.date] = None,
        start_location: Optional[str] = None,
        end_location: Optional[str] = None,
        transport_mode: str = "auto",
    ) -> Dict[str, Any]:
        logger.info(f"Starting pipeline for destination={destination}")

        initial_state: OrchestratorState = {
            "destination": destination,
            "lat": lat,
            "lon": lon,
            "num_days": num_days,
            "interests": interests,
            "budget_per_day": budget_per_day,
            "constraints": constraints or [],
            "start_date": start_date,
            "start_location": start_location or "",
            "end_location": end_location or "",
            "transport_mode": transport_mode,
            "search_interests": interests,
            "search_radius_m": 6000,
            "search_per_interest_limit": 12,
            "relaxed_search_done": False,
            "intercity_mode": "local",
            "budget_status": "unknown",
            "budget_warning": "",
        }

        state = self.graph.invoke(initial_state)

        logger.info("Pipeline completed successfully")
        return {
            "destination": state.get("destination", destination),
            "days": state.get("num_days", num_days),
            "itineraries": state.get("itineraries", []),
            "explanation": state.get("explanation", ""),
            "coords": {"lat": state.get("lat", lat), "lon": state.get("lon", lon)},
            "start_location": state.get("start_location", ""),
            "end_location": state.get("end_location", "") or state.get("start_location", ""),
            "transport_mode": state.get("transport_mode", transport_mode),
            "intercity_mode": state.get("intercity_mode", "local"),
            "budget_per_day": state.get("budget_per_day"),
            "constraints": state.get("constraints", []),
            "budget_status": state.get("budget_status", "unknown"),
            "budget_warning": state.get("budget_warning", ""),
            "search_retried": bool(state.get("relaxed_search_done", False)),
        }

    def _node_ensure_coords(self, state: OrchestratorState) -> OrchestratorState:
        lat = state.get("lat", 0.0)
        lon = state.get("lon", 0.0)
        destination = state.get("destination", "")

        if not self._coords_look_valid(lat, lon):
            logger.info("Lat/lon missing — geocoding destination via Geoapify")
            lat, lon = self._geocode_destination(destination)
            logger.info(f"Geocoded '{destination}' -> lat={lat}, lon={lon}")

        return {"lat": lat, "lon": lon}

    def _node_fetch_weather(self, state: OrchestratorState) -> OrchestratorState:
        weather_by_day: List[DayWeather] = []
        try:
            lat = float(state.get("lat", 0.0))
            lon = float(state.get("lon", 0.0))
            daily = self.weather.daily_forecast(
                lat=lat,
                lon=lon,
                days=max(int(state.get("num_days", 1)), 1),
                timezone="auto",
                start_date=state.get("start_date"),
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

        return {"weather_by_day": weather_by_day}

    def _node_search_pois(self, state: OrchestratorState) -> OrchestratorState:
        lat = float(state.get("lat", 0.0))
        lon = float(state.get("lon", 0.0))
        pois = self.searcher.execute(
            lat=lat,
            lon=lon,
            interests=state.get("search_interests", state.get("interests", [])),
            budget_per_day=state.get("budget_per_day"),
            constraints=state.get("constraints", []),
            radius_m=int(state.get("search_radius_m", 6000)),
            per_interest_limit=int(state.get("search_per_interest_limit", 12)),
        )
        return {"pois": pois}

    def _should_relax_search(self, state: OrchestratorState) -> str:
        if len(state.get("pois", [])) >= 3:
            return "continue"
        if state.get("relaxed_search_done", False):
            return "continue"
        return "relax"

    def _node_relax_search(self, state: OrchestratorState) -> OrchestratorState:
        logger.info("Searcher found too few POIs; retrying with relaxed parameters")
        broadened = list(dict.fromkeys((state.get("interests", []) or []) + ["Attractions", "Culture", "Food", "Nature"]))
        return {
            "search_interests": broadened,
            "search_radius_m": 12000,
            "search_per_interest_limit": 20,
            "relaxed_search_done": True,
        }

    def _node_geocode_endpoints(self, state: OrchestratorState) -> OrchestratorState:
        start_coords: Optional[Tuple[float, float]] = None
        end_coords: Optional[Tuple[float, float]] = None
        planner_start_coords: Optional[Tuple[float, float]] = None
        planner_end_coords: Optional[Tuple[float, float]] = None
        intercity_mode = "local"

        start_location = state.get("start_location", "")
        end_location = state.get("end_location", "")

        if start_location or end_location:
            geocoder = GeoapifyGeocoder()
            if start_location:
                try:
                    s_lat, s_lon, _ = geocoder.geocode(start_location)
                    start_coords = (s_lat, s_lon)
                except Exception as e:
                    logger.warning(f"Could not geocode start '{start_location}': {e}")
            if end_location:
                try:
                    e_lat, e_lon, _ = geocoder.geocode(end_location)
                    end_coords = (e_lat, e_lon)
                except Exception as e:
                    logger.warning(f"Could not geocode end '{end_location}': {e}")

        planner_start_coords = start_coords
        planner_end_coords = end_coords
        lat = float(state.get("lat", 0.0))
        lon = float(state.get("lon", 0.0))

        if start_coords:
            dist_to_dest_km = self._haversine_km(start_coords[0], start_coords[1], lat, lon)
            if dist_to_dest_km > 200.0:
                intercity_mode = "flight"
                planner_start_coords = None
                planner_end_coords = None
                logger.info(f"Start is {dist_to_dest_km:.0f} km away -> intercity mode = flight")

        return {
            "start_coords": start_coords,
            "end_coords": end_coords,
            "planner_start_coords": planner_start_coords,
            "planner_end_coords": planner_end_coords,
            "intercity_mode": intercity_mode,
        }

    def _node_plan_itinerary(self, state: OrchestratorState) -> OrchestratorState:
        itineraries = self.planner.execute(
            pois=state.get("pois", []),
            num_days=int(state.get("num_days", 1)),
            start_coords=state.get("planner_start_coords"),
            end_coords=state.get("planner_end_coords"),
            transport_mode=state.get("transport_mode", "auto"),
            budget_per_day=state.get("budget_per_day"),
            constraints=state.get("constraints", []),
            weather_by_day=state.get("weather_by_day", []),
        )
        return {"itineraries": itineraries}

    def _node_attach_weather(self, state: OrchestratorState) -> OrchestratorState:
        itineraries = state.get("itineraries", [])
        weather_by_day = state.get("weather_by_day", [])

        if weather_by_day:
            for it in itineraries:
                idx = it.day - 1
                if 0 <= idx < len(weather_by_day):
                    it.weather = weather_by_day[idx]

        return {"itineraries": itineraries}

    def _node_budget_itinerary(self, state: OrchestratorState) -> OrchestratorState:
        itineraries = self.budgeter.execute(state.get("itineraries", []))

        budget_status = "unknown"
        budget_warning = ""
        budget_per_day = state.get("budget_per_day")
        if budget_per_day is not None:
            planned_budget_cap = float(budget_per_day) * max(int(state.get("num_days", 1)), 1)
            planned_total = sum((it.estimate.total if it.estimate else 0.0) for it in itineraries)
            if planned_total <= planned_budget_cap:
                budget_status = "within_budget"
            else:
                budget_status = "over_budget"
                budget_warning = (
                    f"Estimated total ${planned_total:.0f} exceeds budget cap ${planned_budget_cap:.0f}. "
                    "The planner reduced activity density, but you may still want to increase budget or reduce days."
                )

        return {
            "itineraries": itineraries,
            "budget_status": budget_status,
            "budget_warning": budget_warning,
        }

    def _node_enrich_itinerary(self, state: OrchestratorState) -> OrchestratorState:
        itineraries = state.get("itineraries", [])
        llm_ok = self._llm_available()
        destination = state.get("destination", "")
        places_client = GeoapifyPlacesClient()

        for it in itineraries:
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
                if not poi.photo_url:
                    try:
                        poi.photo_url = fetch_photo_url(poi.name) or ""
                    except Exception:
                        pass

                if llm_ok and not poi.description:
                    try:
                        prompt = (
                            f"In 2 sentences, describe the attraction '{poi.name}' "
                            f"in {destination} for a tourist. Be specific and enthusiastic."
                        )
                        desc = self._llm_generate(prompt, max_tokens=80)
                        if desc:
                            poi.description = desc.strip()
                    except Exception:
                        pass

        return {"itineraries": itineraries}

    def _node_explain(self, state: OrchestratorState) -> OrchestratorState:
        itineraries = state.get("itineraries", [])
        destination = state.get("destination", "")
        num_days = int(state.get("num_days", len(itineraries) or 1))

        if self._llm_available():
            explanation = self._llm_explanation(itineraries, destination, num_days)
        else:
            explanation = self.explainer.execute(itineraries=itineraries, destination=destination)

        return {"explanation": explanation}

    def _llm_generate(self, prompt: str, max_tokens: int = 100) -> Optional[str]:
        if self.groq.is_available():
            result = self.groq.generate(prompt, max_tokens=max_tokens, temperature=0.5)
            if result:
                return result

        if self.ollama.is_available():
            return self.ollama.generate(prompt, max_tokens=max_tokens)

        return None

    def _llm_available(self) -> bool:
        return self.groq.is_available() or self.ollama.is_available()

    def _llm_explanation(self, itineraries: List[DayItinerary], destination: str, num_days: int) -> str:
        total_cost = sum(it.estimate.total for it in itineraries if it.estimate)
        day_summaries = []
        for it in itineraries:
            names = [p.name for p in it.pois[:4]]
            weather_note = f" (weather: {it.weather.weather_text})" if it.weather else ""
            day_summaries.append(f"Day {it.day} ({it.theme}): {', '.join(names)}{weather_note}")

        prompt = (
            f"Write a friendly 3-paragraph travel summary for this {num_days}-day trip "
            f"to {destination}. Estimated total cost: ${total_cost:.0f}.\n\n"
            f"Itinerary:\n" + "\n".join(day_summaries) + "\n\n"
            f"Paragraph 1: Exciting overview of the trip.\n"
            f"Paragraph 2: Highlight the best attractions and why they were chosen.\n"
            f"Paragraph 3: Practical tips about budget and getting around."
        )

        result = self._llm_generate(prompt, max_tokens=350)
        if result:
            return result

        return self.explainer.execute(itineraries=itineraries, destination=destination)

    def _haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        import math

        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _coords_look_valid(self, lat: float, lon: float) -> bool:
        try:
            lat_f, lon_f = float(lat), float(lon)
        except Exception:
            return False
        if abs(lat_f) < 1e-9 and abs(lon_f) < 1e-9:
            return False
        return -90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0

    def _geocode_destination(self, destination: str) -> Tuple[float, float]:
        api_key = os.getenv("GEOAPIFY_API_KEY")
        if not api_key:
            raise RuntimeError("GEOAPIFY_API_KEY not found. Add it to your .env file.")

        url = "https://api.geoapify.com/v1/geocode/search"
        params = {"text": destination, "limit": 1, "format": "json", "apiKey": api_key}
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
                    raise RuntimeError(f"No geocoding results for '{destination}'")
                r0 = results[0]
                return float(r0["lat"]), float(r0["lon"])
            except Exception as e:
                last_err = e
                time.sleep(1.2 * (attempt + 1))

        raise RuntimeError(f"Geocoding failed after retries: {last_err}")
