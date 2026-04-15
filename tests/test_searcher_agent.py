from src.agents.searcher_agent import SearcherAgent
from src.core.models import POI


class DummyPlacesClient:
    def search_by_interests(self, **kwargs):
        return [
            type("Place", (), {"name": "Paid Museum", "lat": 1.0, "lon": 1.0, "formatted": "", "categories": ["entertainment.museum"], "website": "", "phone": "", "opening_hours": "", "rating": 4.8, "fee": True})(),
            type("Place", (), {"name": "Free Park", "lat": 2.0, "lon": 2.0, "formatted": "", "categories": ["leisure.park"], "website": "", "phone": "", "opening_hours": "", "rating": 4.2, "fee": False})(),
        ]


def test_searcher_prefers_free_pois_for_low_budget(monkeypatch):
    monkeypatch.setattr("src.agents.searcher_agent.GeoapifyPlacesClient", lambda: DummyPlacesClient())
    agent = SearcherAgent()
    pois = agent.execute(lat=0.0, lon=0.0, interests=["Nature"], budget_per_day=60, constraints=["budget-friendly"])

    assert isinstance(pois[0], POI)
    assert pois[0].name == "Free Park"
    assert pois[0].fee is False
