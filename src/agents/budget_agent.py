# src/agents/budget_agent.py
"""
BudgetAgent
- Estimates daily travel costs based on itinerary structure
- Uses simple, explainable heuristics (no external APIs)
- Attaches BudgetEstimate to each DayItinerary
"""

import logging
from typing import List

from src.core.models import DayItinerary, BudgetEstimate

logger = logging.getLogger(__name__)


class BudgetAgent:
    """
    BudgetAgent estimates per-day costs for a travel itinerary.

    Cost model (simple & explainable):
    - Accommodation: fixed per day (based on assumed mid-range hotel)
    - Food: per-POI estimate
    - Transport: proportional to distance traveled
    - Activities: per-POI estimate
    """

    def __init__(
        self,
        accommodation_per_day: float = 70.0,
        food_per_place: float = 12.0,
        activity_per_place: float = 10.0,
        transport_per_km: float = 1.5,
    ):
        self.accommodation_per_day = accommodation_per_day
        self.food_per_place = food_per_place
        self.activity_per_place = activity_per_place
        self.transport_per_km = transport_per_km

        logger.info("BudgetAgent initialized")

    def execute(self, itineraries: List[DayItinerary]) -> List[DayItinerary]:
        """
        Estimate budget for each day and attach BudgetEstimate.

        Args:
            itineraries: List of DayItinerary objects

        Returns:
            Same list with budget estimates filled in
        """
        for day in itineraries:
            num_places = len(day.pois)
            distance_km = day.total_distance_km or 0.0

            accommodation = self.accommodation_per_day
            food = num_places * self.food_per_place
            activities = num_places * self.activity_per_place
            transport = distance_km * self.transport_per_km

            estimate = BudgetEstimate(
                day=day.day,
                accommodation=round(accommodation, 2),
                food=round(food, 2),
                activities=round(activities, 2),
                transport=round(transport, 2),
            )

            estimate.calculate_total()
            day.estimate = estimate

            logger.info(
                f"Day {day.day} budget: ${estimate.total} "
                f"(acc={estimate.accommodation}, food={estimate.food}, "
                f"act={estimate.activities}, trans={estimate.transport})"
            )

        return itineraries
