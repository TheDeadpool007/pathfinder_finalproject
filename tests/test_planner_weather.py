from src.agents.planner_agent import PlannerAgent
from src.core.models import DayWeather, POI


class DummyRoutingClient:
    def route(self, **kwargs):
        return type("Route", (), {"distance_m": 1000.0, "time_s": 600.0, "mode": kwargs.get("mode", "walk"), "instructions": []})()


def test_rainy_day_prefers_indoor_pois(monkeypatch):
    monkeypatch.setattr("src.agents.planner_agent.GeoapifyRoutingClient", lambda: DummyRoutingClient())
    agent = PlannerAgent()

    indoor = POI(name="City Museum", lat=48.85, lon=2.35, categories=["entertainment.museum"], rating=4.2)
    outdoor = POI(name="Central Park", lat=48.86, lon=2.36, categories=["leisure.park"], rating=4.8)

    rainy = DayWeather(
        date="2026-06-01",
        temp_min_c=12.0,
        temp_max_c=18.0,
        precip_mm=12.0,
        weather_code=65,
        weather_text="Heavy rain",
    )

    itineraries = agent.execute(
        pois=[outdoor, indoor],
        num_days=1,
        weather_by_day=[rainy],
        budget_per_day=120.0,
        constraints=[],
    )

    assert itineraries
    assert itineraries[0].pois[0].name == "City Museum"
