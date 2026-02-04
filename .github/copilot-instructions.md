# Agentic AI Travel Planner - Project Instructions

This is a final year engineering project demonstrating multi-agent architecture for travel planning.

## Project Overview
- Multi-agent travel itinerary planner
- Uses local LLM (Ollama) with lightweight models
- Optimized for 8GB RAM systems
- Sequential agent execution pipeline

## Architecture
Five specialized agents working in sequence:
1. RequirementsAgent - Parses user input
2. SearcherAgent - Retrieves POIs
3. PlannerAgent - Creates itinerary
4. BudgetAgent - Estimates costs
5. ExplainerAgent - Generates explanations

## Tech Stack
- Python 3.10+
- Streamlit for UI
- Ollama (local LLM)
- OpenTripMap, OpenRouteService, Open-Meteo APIs
- Pydantic for validation
