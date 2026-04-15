# Deploy on Hugging Face Spaces

## 1. Create a Space
- Go to Hugging Face Spaces and create a new Space.
- Choose SDK: Streamlit.
- Set visibility (public or private).

## 2. Push this repository
- Connect your GitHub repository or push directly.
- Hugging Face will auto-build using requirements.txt.

## 3. Configure secrets
In Space Settings -> Variables and secrets, add:
- GEOAPIFY_API_KEY
- GROQ_API_KEY
- GROQ_MODEL (optional, default: llama3-8b-8192)
- OLLAMA_MODEL (optional, local fallback only)

## 4. Runtime behavior
- Entry point is app.py.
- Streamlit config is in .streamlit/config.toml.
- The app uses LangGraph orchestration and retries search automatically when POI count is too low.

## 5. Validate after deploy
- Open the Space URL.
- Try a natural-language prompt in AI mode.
- Confirm itinerary loads with day map, weather, and budget breakdown.
- Confirm retry note appears when sparse destinations are queried.

## 6. Suggested demo prompts
- Plan me 3 days in Paris under 120 dollars per day, I like museums and food.
- 4 days in Tokyo, budget-friendly, avoid nightlife, wheelchair accessible.
- 2 days in Reykjavik with nature focus and flexible budget.
