# Proposal Alignment and Execution Plan

This document maps the seminar proposal goals to the current codebase and defines concrete implementation steps to close remaining gaps.

## 1. Current Status vs Proposal

### 1.1 Implemented and Working
- Multi-agent sequential flow is implemented in `src/core/orchestrator.py`.
- Agents implemented: requirements (form/NL), searcher, planner, budget, explainer.
- Natural-language trip parsing exists in `src/agents/nl_requirements_agent.py`.
- API integration is active for:
  - Geoapify (geocoding, POIs, routing)
  - Open-Meteo (weather)
- Streamlit UI supports:
  - Form mode and natural-language mode
  - Day-wise itinerary
  - Maps, weather, and budget display
  - PDF export
- LLM strategy supports:
  - Groq cloud inference
  - Ollama local fallback

### 1.2 Partially Implemented
- Explainability exists, but reasoning can be made more explicit per decision (why this POI, why this route order).
- Budget validation exists, but strict budget-violation alerts and alternative plan generation are limited.
- Constraint handling (dietary/accessibility) is parsed but not deeply enforced in planning logic.

### 1.3 Missing from Proposal Scope
- Automated tests are not present yet (`tests/` folder missing).
- Formal metrics pipeline (latency, relevance, coherence scoring) is not yet packaged.
- LangChain/LangGraph orchestration is not currently used; orchestration is custom Python.

## 2. Chosen Architecture Decision

Selected approach: **Option A**.

The implementation remains on **Geoapify + Open-Meteo** with Groq/Ollama for LLM features, and the proposal/report wording is updated to match the running code.

Why this was selected:
- Lowest risk for final demo readiness
- Avoids late-stage API migration regressions
- Keeps documentation, code, and deployment behavior consistent

## 3. Implementation Roadmap (4 Weeks)

### Week 1: Reliability and Contract Cleanup
- Remove or fix stale `TripRequirements` dependency path in `src/agents/requirements_agent.py`.
- Add strict error handling for missing keys and empty POI returns in UI.
- Add deterministic fallback itinerary messaging to avoid demo-time failures.

Deliverable: stable end-to-end run for at least 5 sample destinations.

### Week 2: Explainability and Constraint Enforcement
- Add explicit rationale per day:
  - match between interests and selected POIs
  - route compactness explanation
  - weather-aware notes
- Enforce constraints from NL parser in planner/search filtering (e.g., accessibility, vegetarian preference signals where data exists).

Deliverable: improved explanation panel and visible constraint-aware behavior.

### Week 3: Testing and Metrics
- Add unit tests:
  - searcher normalization and fallback
  - planner routing fallback and ordering
  - budget estimation consistency
  - NL parsing validation and clamp behavior
- Add integration test for orchestrator run with mocked API clients.
- Add benchmark script for average response latency and API success rate.

Deliverable: `tests/` suite and measurable performance table for report.

### Week 4: Deployment and Demo Packaging
- Finalize Hugging Face Spaces setup and env-secret documentation.
- Add reproducible demo prompts and expected outputs.
- Prepare final architecture and workflow diagrams to match implementation.

Deliverable: deployment URL + demo script + final report evidence pack.

## 4. Suggested Metrics for Section 6 (Project Results)

- End-to-end latency (mean, p95)
- POI retrieval success rate
- Routing success rate
- Budget adherence ratio
- User-rated relevance (1-5)
- Explanation clarity score (1-5)

## 5. Demo-Day Checklist

- `.env` configured with `GEOAPIFY_API_KEY` and `GROQ_API_KEY` (or Ollama running).
- 3 backup prompts ready (short trip, budget trip, accessibility-focused trip).
- Network fallback message validated (no crash behavior).
- PDF export tested.
- One-slide architecture summary synced with actual modules.
