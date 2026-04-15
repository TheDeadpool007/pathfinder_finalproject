# Proposal Revised Wording (Geoapify-Aligned)

Use this text to update your report so it matches the current implementation.

## Global Replace Rules

- Replace "OpenTripMap" with "Geoapify Places"
- Replace "OpenRouteService" or "ORS" with "Geoapify Routing"
- Replace "OpenTripMap, Open-Meteo, OpenRouteService" with "Geoapify (geocoding, places, routing) and Open-Meteo"
- Replace "Pydantic data models" with "typed dataclass models" where needed

## 1.1 Problem Domain and Background (Revised Paragraph)

With the emergence of Agentic Artificial Intelligence (AI) and Large Language Models (LLMs), the landscape of travel planning is poised for a fundamental transformation. Unlike traditional rule-based systems, agentic AI systems can reason, plan, act, and self-correct, enabling them to autonomously generate personalized and context-aware travel itineraries. In this project, agents integrate user preferences, budget, weather context, and real-time location constraints using free public APIs, specifically Geoapify services for geocoding, points of interest, and routing, along with Open-Meteo for weather forecasts.

## 1.3 Comparison with Proposed Solution (Revised Tool Stack Block)

Unlike proprietary commercial systems, this project uses free and open tools:
- Local LLM via Ollama (development and offline fallback)
- Groq-hosted LLM for fast cloud inference in deployment
- Geoapify APIs for geocoding, places search, and route estimation
- Open-Meteo for forecast-aware planning

## 1.4 Problem Solutions (Revised Feature List)

This project aims to build a fully functional Agentic AI Travel Planner Web App capable of:

1. Understanding User Intent:
Using an LLM-assisted requirements parser to convert natural-language prompts into structured trip constraints.

2. Retrieving Real-Time Travel Data:
Attractions and POIs via Geoapify Places, weather via Open-Meteo, and travel distance/time via Geoapify Routing.

3. Planning Optimized Itineraries:
A Planner Agent organizes attractions geographically, minimizes travel overhead, and adapts route mode based on day-level distance.

4. Ensuring Budget Feasibility:
A Budget Agent calculates estimated costs and checks recommendation feasibility against user budget targets.

5. Generating Explainable Output:
An Explainer Agent summarizes selection reasoning, daily themes, and practical travel guidance.

6. Deploying as a Web Application:
A Streamlit app deployable on Hugging Face Spaces using Groq inference, with local Ollama fallback for development.

## 3.1 Phases and Tasks (Revised API Bullets)

### Phase 2: Data Processing and Algorithm Implementation

Tasks:
- API Data Collection Setup
  - Retrieve attractions and POIs (Geoapify Places)
  - Fetch weather data (Open-Meteo)
  - Compute routes and travel distances (Geoapify Routing)
  - Geocode destination/start/end locations (Geoapify Geocoding)

## 4.1 Functional Requirements (Revised Data Handling Section)

### Data Handling Requirements (Revised)

- The system shall retrieve points-of-interest and place metadata from Geoapify Places.
- The system shall retrieve geocoding data from Geoapify Geocoding.
- The system shall retrieve routing distance and duration data from Geoapify Routing.
- The system shall retrieve weather forecast data from Open-Meteo.
- The system shall preprocess, filter, and normalize API responses before itinerary planning.
- API keys and secrets shall be stored securely in environment variables and never exposed in client-side code.

## 5.3 Machine Learning and Agent Libraries (Revised Tool Wording)

The system uses a lightweight multi-agent pipeline implemented in Python modules, with optional LLM enhancement for natural-language parsing and explanation generation. Agent orchestration is handled through a custom sequential orchestrator, prioritizing reliability and low-resource execution for student hardware.

## 5.5 API and Data Management Tools (Revised Section)

The system relies on free public APIs:

- Geoapify Geocoding:
  Converts destination and optional route endpoints into coordinates.

- Geoapify Places:
  Provides points of interest, categories, and place metadata.

- Geoapify Routing:
  Provides route distance, time, and navigation summaries for day plans.

- Open-Meteo:
  Provides weather forecast data for itinerary context.

- JSON/TTL Caching:
  Reduces redundant calls and improves responsiveness across reruns.

## 6.1 Trained and Integrated Agentic AI Models (Revised Expected Results)

Expected Results:
- A Requirements Agent that parses natural-language prompts into destination, duration, budget, interests, and constraints.
- A Searcher Agent that retrieves POIs from Geoapify Places.
- A Planner Agent that orders POIs and computes route summaries using Geoapify Routing.
- A Budget Agent that estimates day-wise costs.
- An Explainer Agent that produces concise, human-readable itinerary reasoning.

## 6.2 Evaluation Metrics and Performance Analysis (Revised Data Accuracy Bullet)

Data Integration Accuracy:
- Success rate of retrieving valid POI metadata from Geoapify Places.
- Success rate of route summary generation from Geoapify Routing.
- Consistency of weather-aware itinerary context from Open-Meteo.

## 7. Project Schedule (Revised API Task)

Update task 2.2 wording to:
"API integration setup (Geoapify Geocoding/Places/Routing, Open-Meteo)"

## Appendix: One-Paragraph Implementation Statement

The implemented system uses a sequential multi-agent architecture coordinated by a Python orchestrator. It currently integrates Geoapify APIs for geocoding, POI retrieval, and routing, Open-Meteo for weather context, and optional LLM enhancement through Groq (cloud) with Ollama (local fallback). This configuration was selected to maximize reliability, cost-efficiency, and deployability for an academic environment while preserving explainability and modularity.
