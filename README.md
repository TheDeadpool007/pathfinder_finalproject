# Agentic AI Travel Planner

**Final Year Engineering Project**  
A multi-agent travel itinerary planner using local LLM and REST APIs

---

## 🎯 Project Overview

This project demonstrates a **multi-agent architecture** where specialized AI agents collaborate to create personalized travel itineraries. The system runs entirely locally and is optimized for consumer hardware (8GB RAM).

### Key Features
- 🤖 **5 Specialized Agents** working in sequential pipeline
- 🧠 **LangGraph StateGraph Orchestration** with conditional retry on sparse POI search
- 🗺️ **Smart POI Selection** using Geoapify Places API
- 📊 **Route Optimization** with Geoapify Routing
- 🌧️ **Weather-Aware Planning** to prefer indoor POIs on heavy-rain days
- 📍 **Geographic Day Clustering** via k-means for tighter daily itineraries
- 💰 **Budget Estimation** with automatic warnings
- 🌤️ **Weather Integration** via Open-Meteo API
- 🧠 **Optional LLM Enhancement** with Groq + Ollama fallback

---

## 🏗️ Multi-Agent Architecture

The system uses a **LangGraph-coordinated multi-agent pipeline** with conditional edges and retry logic:

```
User Input
    ↓
[RequirementsAgent] → Parse & validate input
    ↓
[SearcherAgent] → Retrieve POIs from APIs
    ↓
[PlannerAgent] → Create day-wise itinerary
    ↓
[BudgetAgent] → Estimate costs
    ↓
[ExplainerAgent] → Generate summary
    ↓
Travel Plan Output
```

### Agent Responsibilities

| Agent | Input | Output | Purpose |
|-------|-------|--------|---------|
| **RequirementsAgent** | Raw user input | `TripRequirements` | Parse and validate preferences |
| **SearcherAgent** | destination coords + interests | `List[POI]` | Query Geoapify Places for attractions |
| **PlannerAgent** | Requirements + POIs | `List[DayItinerary]` | Group POIs, calculate routes |
| **BudgetAgent** | Itinerary | `List[BudgetEstimate]` | Estimate daily costs |
| **ExplainerAgent** | Complete plan | Natural language text | Generate human-readable summary |

---

## 📦 Tech Stack

- **Python 3.10+** - Core language
- **Streamlit** - Web UI framework
- **Dataclasses** - Typed data contracts between agents
- **Ollama** - Local LLM inference (optional)
- **Groq** - Free cloud LLM inference (optional)
- **REST APIs:**
    - Geoapify - Geocoding, points of interest, routing
  - Open-Meteo - Weather forecasts

---

## 🎮 Usage

### Run the Application
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

### Using the Interface
1. **Enter trip details** in the sidebar:
   - Destination city
   - Number of days (1-14)
   - Daily budget in USD
   - Interests (museums, nature, etc.)
   - Any constraints

2. **Click "Generate Itinerary"**

3. **View your plan** with:
   - Day-wise attraction list
   - Route distances
   - Weather forecasts
   - Budget breakdown

---

## 📁 Project Structure

```
agentic_travel_planner/
│
├── app.py                          # Streamlit UI entry point
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
├── README.md                       # This file
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py               # Shared dataclass models
│   │   └── orchestrator.py        # Agent coordinator
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── requirements_agent.py   # Agent 1: Parse input
│   │   ├── searcher_agent.py       # Agent 2: Search POIs
│   │   ├── planner_agent.py        # Agent 3: Create itinerary
│   │   ├── budget_agent.py         # Agent 4: Estimate costs
│   │   └── explainer_agent.py      # Agent 5: Generate summary
│   │
│   └── tools/
│       ├── __init__.py
│       ├── llm_groq.py             # Groq LLM wrapper
│       ├── llm_ollama.py           # Ollama LLM wrapper
│       ├── geoapify_geocoding.py   # Geocoding API
│       ├── geoapify_places.py      # Places API
│       ├── geoapify_routing.py     # Routing API
│       └── openmeteo.py            # Weather API
│
└── .github/
    └── copilot-instructions.md     # Project metadata
```

---

**Built with ❤️ using Multi-Agent Architecture**
