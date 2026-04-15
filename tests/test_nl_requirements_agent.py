from src.agents.nl_requirements_agent import NLRequirementsAgent


class DummyLLM:
    def is_available(self):
        return False

    def generate(self, *args, **kwargs):
        return None


def test_nl_keyword_fallback_extracts_budget_and_interests(monkeypatch):
    agent = NLRequirementsAgent()
    agent.groq = DummyLLM()
    agent.ollama = DummyLLM()

    result = agent.parse("Plan 3 days in Tokyo on a cheap budget, I love museums and food")

    assert result["destination"] == "Tokyo, Japan"
    assert result["num_days"] == 3
    assert result["budget_per_day"] == 60.0
    assert "Museums" in result["interests"]
    assert "Food" in result["interests"]
