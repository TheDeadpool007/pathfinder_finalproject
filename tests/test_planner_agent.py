from src.agents.planner_agent import PlannerAgent
from src.core.models import POI


class DummyRoutingClient:
    def route(self, **kwargs):
        return type("Route", (), {"distance_m": 1000.0, "time_s": 600.0, "mode": kwargs.get("mode", "walk"), "instructions": []})()


def test_planner_limits_day_items_when_budget_is_low(monkeypatch):
    monkeypatch.setattr("src.agents.planner_agent.GeoapifyRoutingClient", lambda: DummyRoutingClient())
    agent = PlannerAgent()

    pois = [
        POI(name=f"POI {i}", lat=float(i), lon=float(i), fee=(i % 2 == 0), rating=4.0)
        for i in range(8)
    ]

    itineraries = agent.execute(pois=pois, num_days=1, budget_per_day=60, constraints=["budget-friendly"])

    assert len(itineraries) == 1
    assert len(itineraries[0].pois) <= 5
    assert itineraries[0].pois[0].fee is False
