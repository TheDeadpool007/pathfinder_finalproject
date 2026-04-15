# src/core/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ======================================================
# TRIP REQUIREMENTS MODEL
# ======================================================

@dataclass
class TripRequirements:
    """
    Structured travel request used by the legacy requirements agent.

    Keeps the current project compatible with both form input and
    natural-language parsing workflows.
    """

    destination: str
    num_days: int = 3
    budget_per_day: float = 100.0
    interests: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    start_location: str = ""


# ======================================================
# POI MODEL
# ======================================================

@dataclass
class POI:
    """
    Point of Interest used across the system.

    This model is UI-safe and backward compatible with:
    - Wikipedia/OpenTripMap era fields
    - Geoapify real-time data
    """
    name: str
    lat: float
    lon: float

    address: str = ""
    description: str = ""        # UI expects this
    categories: List[str] = field(default_factory=list)
    source: str = "geoapify"

    # Extended fields from Geoapify / enrichment
    website: str = ""
    phone: str = ""
    opening_hours: str = ""
    rating: Optional[float] = None
    photo_url: str = ""          # Wikimedia Commons thumbnail
    fee: Optional[bool] = None   # True = paid entry, False = free


# ======================================================
# BUDGET MODEL (matches BudgetAgent exactly)
# ======================================================

@dataclass
class BudgetEstimate:
    """
    Budget estimate for a single day.
    BudgetAgent EXPECTS this exact structure.
    """
    day: int
    accommodation: float
    food: float
    activities: float
    transport: float
    total: float = 0.0

    def calculate_total(self) -> float:
        self.total = round(
            self.accommodation
            + self.food
            + self.activities
            + self.transport,
            2,
        )
        return self.total


# ======================================================
# WEATHER MODEL
# ======================================================

@dataclass
class DayWeather:
    """
    Daily weather summary attached to each DayItinerary.
    Sourced from Open-Meteo (no API key).
    """
    date: str  # YYYY-MM-DD
    temp_min_c: float
    temp_max_c: float
    precip_mm: float
    weather_code: int
    weather_text: str


# ======================================================
# DAY ITINERARY MODEL (core glue object)
# ======================================================

@dataclass
class DayItinerary:
    """
    Central data object passed between all agents.
    """

    day: int
    theme: str

    # ---- POIs ----
    # Old code uses .pois
    # New planner uses .items
    pois: List[POI] = field(default_factory=list)
    items: List[POI] = field(default_factory=list)

    # ---- Routing ----
    route: Optional[Dict[str, Any]] = None

    # BudgetAgent expects these scalar fields
    total_distance_km: float = 0.0
    total_time_min: float = 0.0

    # BudgetAgent writes this
    estimate: Optional[BudgetEstimate] = None

    # ---- Weather ----
    weather: Optional[DayWeather] = None

    # ---- Nearby restaurants (enriched by orchestrator) ----
    restaurants: List[POI] = field(default_factory=list)

    # UI / future extensions
    currency: str = "USD"
    estimated_cost: Optional[float] = None

    # --------------------------------------------------
    # Post-init sync for migration safety
    # --------------------------------------------------
    def __post_init__(self) -> None:
        # Keep pois/items in sync
        if self.items and not self.pois:
            self.pois = self.items
        elif self.pois and not self.items:
            self.items = self.pois

        # Populate legacy distance/time fields from route
        if self.route:
            dist_m = self.route.get("distance_m")
            time_s = self.route.get("time_s")

            if isinstance(dist_m, (int, float)):
                self.total_distance_km = round(dist_m / 1000.0, 3)

            if isinstance(time_s, (int, float)):
                self.total_time_min = round(time_s / 60.0, 1)
