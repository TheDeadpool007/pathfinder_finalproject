---
title: Pathfinder
emoji: ✈️
colorFrom: blue
colorTo: indigo
sdk: streamlit
app_file: streamlit_app.py
pinned: false
---

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

## 🚀 Installation

### Prerequisites
- Python 3.10 or higher
- (Optional) Ollama installed locally for LLM features

### Step 1: Clone Repository
```bash
cd /Users/deekshagandhip/StudioProjects/Pathfinder_AI
```

### Step 2: Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
```bash
cp .env.example .env
# Edit .env and add your API keys
```

Get free API keys:
- **Geoapify**: https://www.geoapify.com/get-started-with-maps-api
- **Groq** (optional for cloud LLM): https://console.groq.com

### Step 5 (Optional): Install Ollama
For enhanced LLM explanations:
```bash
# Install Ollama from https://ollama.ai
ollama pull qwen2.5:0.5b  # Lightweight 0.5B model
```

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

## 🔬 How It Works (Technical Details)

### 1. Agent Communication
Agents communicate through **typed dataclass models**:
- Each agent has a clearly defined input/output contract
- Data flows sequentially through the pipeline
- No shared state between agents (functional approach)

### 2. API Integration
- **Fallback mechanisms**: All APIs have deterministic fallbacks if unavailable
- **Error handling**: Graceful degradation without crashes
- **Rate limiting**: Reasonable request limits to avoid API throttling

### 3. LLM Usage
- **Optional enhancement**: System works fully without LLM
- **Lightweight model**: Uses Qwen2.5 0.5B (fits in 8GB RAM)
- **Limited scope**: LLM only used for natural language generation
- **Local inference**: No cloud API calls, privacy-preserved

### 4. Resource Optimization
- **Sequential execution**: One agent at a time (low memory)
- **Lazy loading**: APIs initialized only when needed
- **Minimal context**: Small prompts to LLM (<500 tokens)

---

## 🧪 Example Output

**Input:**
- Destination: Paris
- Days: 3
- Budget: $150/day
- Interests: Museums, History

**Output:**
```
Day 1: Louvre Museum, Notre-Dame, Sainte-Chapelle, Latin Quarter
Day 2: Eiffel Tower, Arc de Triomphe, Champs-Élysées, Sacré-Cœur
Day 3: Versailles Palace, Musée d'Orsay, Luxembourg Gardens

Total Budget: $465
Weather: Sunny, 18-24°C
```

---

## 🎓 Academic Context

### Agentic AI Requirement
This project satisfies "agentic AI" criteria through:

1. **Autonomy**: Each agent makes independent decisions within its domain
2. **Specialization**: Agents have distinct, non-overlapping responsibilities
3. **Collaboration**: Agents work together through structured data exchange
4. **Goal-directed**: System pursues the overarching goal (create travel plan)

### Multi-Agent vs Monolithic
| Aspect | Multi-Agent (This Project) | Monolithic |
|--------|----------------------------|------------|
| Modularity | ✅ Each agent is independent | ❌ Tightly coupled |
| Testing | ✅ Test agents individually | ❌ Integration tests only |
| Scalability | ✅ Add/remove agents easily | ❌ Refactor entire system |
| Clarity | ✅ Clear responsibilities | ❌ Complex interdependencies |

---

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Geoapify API Key (required for geocoding, places, routing)
GEOAPIFY_API_KEY=your_key_here

# Groq API key (optional, for cloud LLM enhancement)
GROQ_API_KEY=your_key_here

# Groq model (optional)
GROQ_MODEL=llama-3.1-8b-instant

# Ollama Model (optional, defaults to qwen2.5:0.5b)
OLLAMA_MODEL=qwen2.5:0.5b
```

### Recommended Models for Ollama
For 8GB RAM systems:
- `qwen2.5:0.5b` - Fastest, lowest memory (500MB)
- `qwen2.5:1.5b` - Balanced quality (1.5GB)
- `phi3:mini` - Good for summaries (2GB)

---

## 🐛 Troubleshooting

### "API key not found"
- Copy `.env.example` to `.env`
- Add at least `GEOAPIFY_API_KEY`
- Restart the application

### "Ollama not available"
- This is optional - system will work without it
- To use LLM features: Install Ollama and run `ollama pull qwen2.5:0.5b`

### "No POIs found"
- Check API keys are valid
- Verify destination spelling
- Check Geoapify account quota and key restrictions

### "Budget exceeded"
- Adjust budget_per_day or num_days
- System will still generate plan with warning

---

## 📝 Future Enhancements

- [ ] Add user preferences learning
- [ ] Implement POI clustering for better routes
- [ ] Support multiple cities in one trip
- [ ] Add collaborative filtering for recommendations
- [ ] Export itinerary to PDF/Google Maps

---

## 👨‍💻 Development

### Running Tests
```bash
# Install dev dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/

# With coverage
pytest --cov=src tests/
```

### Code Style
```bash
# Install formatters
pip install black isort flake8

# Format code
black src/ app.py
isort src/ app.py

# Lint
flake8 src/ app.py
```

---

## 📄 License

This is an academic project for educational purposes.

---

## 🙏 Acknowledgments

- **OpenTripMap** - POI data
- **OpenRouteService** - Routing algorithms
- **Open-Meteo** - Weather forecasts
- **Ollama** - Local LLM inference
- **Streamlit** - Rapid UI development

---

## 📧 Contact

**Project:** Final Year Engineering - Agentic AI Travel Planner  
**Student:** Deeksha Gandhip  
**Institution:** [Your Institution Name]

---

**Built with ❤️ using Multi-Agent Architecture**
