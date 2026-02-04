# src/agents/explainer_agent.py
"""
ExplainerAgent
- Generates a human-readable explanation of the travel plan
- Summarizes itinerary, budget, and highlights per day
- Deterministic (no LLM required)
"""

import logging
from typing import List

from src.core.models import DayItinerary

logger = logging.getLogger(__name__)


class ExplainerAgent:
    """
    ExplainerAgent produces a textual explanation of the itinerary
    suitable for UI display and report descriptions.
    """

    def __init__(self):
        logger.info("ExplainerAgent initialized")

    def execute(self, itineraries: List[DayItinerary], destination: str) -> str:
        if not itineraries:
            return "No itinerary could be generated for the given inputs."

        total_days = len(itineraries)
        total_places = sum(len(day.pois) for day in itineraries)
        total_budget = sum(
            (day.estimate.total if day.estimate else 0.0)
            for day in itineraries
        )

        lines = []
        lines.append(
            f"Your {total_days}-day trip to {destination} includes "
            f"{total_places} carefully selected attractions."
        )

        lines.append(f"Estimated total budget: ${round(total_budget, 2)}.")

        lines.append("")

        # Day-wise summary
        for day in itineraries:
            place_names = [p.name for p in day.pois[:3]]
            more_count = max(0, len(day.pois) - 3)

            summary = f"Day {day.day}: "
            if place_names:
                summary += "Visit " + ", ".join(place_names)
                if more_count > 0:
                    summary += f" and {more_count} more places"
            else:
                summary += "No planned activities"

            if day.total_distance_km > 0:
                summary += f" | Travel distance: {day.total_distance_km} km"

            if day.estimate:
                summary += f" | Daily budget: ${day.estimate.total}"

            lines.append(summary)

        explanation = "\n".join(lines)

        logger.info("ExplainerAgent generated explanation")
        return explanation
