# src/agents/planner_agent.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from src.core.models import DayItinerary, POI
from src.tools.geoapify_routing import GeoapifyRoutingClient

logger = logging.getLogger(__name__)


class PlannerAgent:
    """
    REAL-TIME PlannerAgent:
    - Takes POIs from SearcherAgent (Geoapify Places)
    - Splits across days
    - Orders stops using a nearest-neighbor heuristic (fast + reliable)
    - Calls Geoapify Routing per day and stores summary in DayItinerary.route
    - Reliability features:
        * waypoint cap (routing stability)
        * auto mode selection walk/drive
        * graceful routing failure (keeps itinerary)
    """

    # Keep routing stable (too many waypoints can fail or be slow)
    MAX_WAYPOINTS_PER_DAY = 8

    def __init__(self) -> None:
        self.routing = GeoapifyRoutingClient()

    def execute(self, *, pois: List[POI], num_days: int, start_coords: Optional[Tuple[float, float]] = None, end_coords: Optional[Tuple[float, float]] = None, transport_mode: str = "auto") -> List[DayItinerary]:
        if num_days < 1:
            raise ValueError("num_days must be >= 1")

        if not pois:
            # No dummy fallback allowed: fail loudly so UI shows real problem.
            raise ValueError("PlannerAgent received 0 POIs. Check Geoapify Places / interests / radius.")

        logger.info(f"PlannerAgent: building {num_days}-day itinerary from {len(pois)} POIs")

        pois_clean = self._dedupe_pois(pois)

        # Round-robin split across days
        buckets: List[List[POI]] = [[] for _ in range(num_days)]
        for idx, poi in enumerate(pois_clean):
            buckets[idx % num_days].append(poi)

        itineraries: List[DayItinerary] = []
        for d in range(num_days):
            day_num = d + 1

            # Cap POIs for UI sanity (you can tune this)
            day_items = buckets[d][:10]
            if not day_items:
                itineraries.append(DayItinerary(day=day_num, theme="Free Day", pois=[], items=[], route=None))
                continue

            # Order points (improves route realism)
            ordered = self._nearest_neighbor_order(day_items)

            # If too many points, cap for routing but still show all POIs in the itinerary
            routed_points = ordered[: self.MAX_WAYPOINTS_PER_DAY]

            # Auto choose walk vs drive based on approximate distance
            # Mode: honour user choice or auto-detect from distance
            if transport_mode in ("walk", "drive", "transit", "bicycle"):
                mode = transport_mode
            else:
                approx_items = []
                if start_coords:
                    approx_items.append(POI(name="_start", lat=start_coords[0], lon=start_coords[1]))
                approx_items.extend(routed_points)
                if end_coords:
                    approx_items.append(POI(name="_end", lat=end_coords[0], lon=end_coords[1]))
                approx_km = self._approx_path_km(approx_items)
                mode = "walk" if approx_km <= 4.0 else "drive"  # ~2.5 miles threshold

            route_summary = self._route_day(routed_points, mode=mode, lang="en", start_coords=start_coords, end_coords=end_coords)

            theme = self._infer_theme(ordered)
            dist_km = round((route_summary.get("distance_m") or 0.0) / 1000.0, 3)
            time_min = round((route_summary.get("time_s") or 0.0) / 60.0, 1)

            # Store all POIs (ordered), but route is built only for routed_points
            itineraries.append(
                DayItinerary(
                    day=day_num,
                    theme=theme,
                    pois=ordered,
                    items=ordered,
                    route=route_summary,
                    total_distance_km=dist_km,
                    total_time_min=time_min,
                )
            )

        logger.info("PlannerAgent: itinerary created")
        return itineraries

    # -------------------------
    # Routing
    # -------------------------

    def _route_day(self, ordered: List[POI], *, mode: str, lang: str, start_coords: Optional[Tuple[float, float]] = None, end_coords: Optional[Tuple[float, float]] = None) -> Dict[str, Any]:
        """
        Always returns a dict (never None) for UI stability.
        Builds route: optional start -> POIs -> optional end.
        """
        stops_meta = [{"name": p.name, "lat": p.lat, "lon": p.lon} for p in ordered]

        waypoints: List[Tuple[float, float]] = []
        if start_coords:
            waypoints.append(start_coords)
        waypoints.extend([(p.lat, p.lon) for p in ordered])
        if end_coords:
            waypoints.append(end_coords)

        if len(waypoints) < 2:
            return {
                "mode": mode,
                "distance_m": 0.0,
                "time_s": 0.0,
                "stops": stops_meta,
                "instructions": [],
                "note": "Not enough waypoints to compute a route",
            }

        try:
            r = self.routing.route(waypoints=waypoints, mode=mode, lang=lang, include_instructions=True)
            return {
                "mode": r.mode,
                "distance_m": float(r.distance_m),
                "time_s": float(r.time_s),
                "stops": stops_meta,
                "instructions": r.instructions[:50],
            }
        except Exception as e:
            logger.warning(f"PlannerAgent: routing failed for day (mode={mode}): {e}")
            return {
                "mode": mode,
                "distance_m": 0.0,
                "time_s": 0.0,
                "stops": stops_meta,
                "instructions": [],
                "error": str(e),
            }

    # -------------------------
    # Ordering + helpers
    # -------------------------

    def _dedupe_pois(self, pois: List[POI]) -> List[POI]:
        out: List[POI] = []
        for p in pois:
            duplicate = False
            for kept in out:
                if (p.name or "").strip().lower() == (kept.name or "").strip().lower():
                    duplicate = True
                    break
                if self._haversine_m(p.lat, p.lon, kept.lat, kept.lon) < 60:
                    duplicate = True
                    break
            if not duplicate:
                out.append(p)
        return out

    def _nearest_neighbor_order(self, pois: List[POI]) -> List[POI]:
        remaining = pois[:]
        ordered = [remaining.pop(0)]

        while remaining:
            last = ordered[-1]
            best_i = 0
            best_d = float("inf")
            for i, cand in enumerate(remaining):
                d = self._haversine_m(last.lat, last.lon, cand.lat, cand.lon)
                if d < best_d:
                    best_d = d
                    best_i = i
            ordered.append(remaining.pop(best_i))

        return ordered

    def _approx_path_km(self, pois: List[POI]) -> float:
        """
        Rough distance estimate by summing straight-line hops (fast, no API).
        Used only to decide walk vs drive.
        """
        if len(pois) < 2:
            return 0.0
        total_m = 0.0
        for i in range(len(pois) - 1):
            total_m += self._haversine_m(pois[i].lat, pois[i].lon, pois[i + 1].lat, pois[i + 1].lon)
        return total_m / 1000.0

    def _infer_theme(self, pois: List[POI]) -> str:
        cats_text = " ".join([" ".join(p.categories or []) for p in pois]).lower()
        parts: List[str] = []

        if any(x in cats_text for x in ["tourism", "heritage", "entertainment", "religion"]):
            parts.append("Highlights")
        if any(x in cats_text for x in ["leisure", "natural", "beach"]):
            parts.append("Outdoors")
        if any(x in cats_text for x in ["catering"]):
            parts.append("Food")
        if any(x in cats_text for x in ["commercial"]):
            parts.append("Shopping")
        if any(x in cats_text for x in ["transport", "airport"]):
            parts.append("Transit")

        return " + ".join(parts) if parts else "City Plan"

    def _haversine_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        import math

        R = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)

        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
