# app.py
from dotenv import load_dotenv
load_dotenv()  # MUST be first so GEOAPIFY_API_KEY is available to imported modules

import os
import traceback
from typing import List

import streamlit as st

from src.core.orchestrator import Orchestrator
from src.core.models import POI, DayItinerary  # for typing / safety checks

st.set_page_config(page_title="Agentic AI Travel Planner", layout="wide")

# ------ Helpers ------

def safe_getattr(obj, attr, default=None):
    return getattr(obj, attr, default)

def display_poi(poi: POI):
    # robust display that won't crash if fields missing
    name = safe_getattr(poi, "name", "Unknown")
    address = safe_getattr(poi, "address", "")
    desc = safe_getattr(poi, "description", "")
    cats = safe_getattr(poi, "categories", [])
    st.write(f"**{name}**")
    if address:
        st.caption(address)
    if desc:
        st.caption(desc)
    if cats:
        st.caption("Categories: " + ", ".join(cats))

def format_km(x):
    try:
        return f"{float(x):.2f} km"
    except Exception:
        return "N/A"

def format_min(x):
    try:
        return f"{float(x):.1f} min"
    except Exception:
        return "N/A"

def format_c(x):
    try:
        return f"{float(x):.1f}°C"
    except Exception:
        return "N/A"

def format_mm(x):
    try:
        return f"{float(x):.1f} mm"
    except Exception:
        return "N/A"

# ------ App UI ------

st.title("✈️ Agentic AI Travel Planner")
st.write("Multi-Agent System for Intelligent Travel Itinerary Generation")

# Sidebar inputs
with st.sidebar:
    st.header("🎯 Trip Preferences")

    destination = st.text_input("Destination", value="Paris")
    num_days = st.slider("Number of Days", 1, 14, 3)
    daily_budget = st.number_input("Daily Budget (USD)", min_value=10, value=150, step=10)

    # Provide the same normalized options the SearcherAgent understands
    interest_options = [
        "Museums", "History", "Culture", "Art", "Attractions",
        "Food", "Restaurants", "Cafe", "Nightlife",
        "Parks", "Nature", "Shopping", "Transport", "Essentials"
    ]
    interests = st.multiselect("Interests", interest_options, default=["Museums", "History"])

    if "GEOAPIFY_API_KEY" not in os.environ or not os.environ.get("GEOAPIFY_API_KEY"):
        st.error(
            "GEOAPIFY_API_KEY not loaded. Make sure you have a .env with GEOAPIFY_API_KEY and "
            "`from dotenv import load_dotenv; load_dotenv()` at top of app.py."
        )
    st.markdown("---")
    generate = st.button("🚀 Generate Itinerary")

orch = Orchestrator()

# Only run pipeline on button click
if generate:
    st.info("Running planner — this may take a few seconds (Geoapify calls)...")

    try:
        # Orchestrator will geocode if coords invalid (0,0)
        lat = 0.0
        lon = 0.0

        result = orch.run(destination=destination, lat=lat, lon=lon, num_days=num_days, interests=interests)

        st.success("Planner finished")
        itineraries = result.get("itineraries", [])

        # high-level summary
        st.subheader("📋 Summary")
        st.write(f"Destination: **{result.get('destination')}**")
        st.write(f"Days: **{result.get('days')}**")

        coords = result.get("coords") or {}
        if coords:
            st.caption(f"Coordinates used: lat={coords.get('lat')}, lon={coords.get('lon')}")

        explanation = result.get("explanation") or ""
        if explanation:
            st.markdown("**Explanation:**")
            st.write(explanation)

        st.markdown("---")
        st.subheader("🗓 Day-wise Itinerary")

        # Expanders per day
        for day in itineraries:
            # day may be dataclass DayItinerary or a dict; handle both
            if hasattr(day, "day"):
                title = f"Day {safe_getattr(day, 'day', '?')}: {safe_getattr(day, 'theme', '')}"
            else:
                title = f"Day {day.get('day', '?')}: {day.get('theme', '')}"

            with st.expander(title, expanded=False):

                # -------------------------
                # Weather (NEW)
                # -------------------------
                weather = safe_getattr(day, "weather", None)
                if weather:
                    w_date = safe_getattr(weather, "date", "")
                    w_min = safe_getattr(weather, "temp_min_c", None)
                    w_max = safe_getattr(weather, "temp_max_c", None)
                    w_precip = safe_getattr(weather, "precip_mm", None)
                    w_text = safe_getattr(weather, "weather_text", "")
                    st.markdown("**Weather (Open-Meteo)**")
                    if w_date:
                        st.write(f"- Date: {w_date}")
                    st.write(f"- Condition: {w_text or 'N/A'}")
                    st.write(f"- Temp: {format_c(w_min)} to {format_c(w_max)}")
                    st.write(f"- Precipitation: {format_mm(w_precip)}")
                    st.markdown("---")

                # -------------------------
                # POIs list (use pois or items)
                # -------------------------
                places = safe_getattr(day, "pois", None)
                if places is None:
                    places = safe_getattr(day, "items", [])

                if not places:
                    st.write("_No POIs for this day._")
                else:
                    for poi in places:
                        display_poi(poi)

                # -------------------------
                # Routing summary (safe)
                # -------------------------
                route = safe_getattr(day, "route", None) or {}
                if route:
                    dist_km = safe_getattr(day, "total_distance_km", None) or route.get("distance_m")
                    # route.distance_m might be meters — convert if necessary
                    if isinstance(dist_km, (int, float)):
                        if route.get("distance_m") is not None and dist_km > 1000:
                            dist_display = format_km(dist_km / 1000.0)
                        else:
                            dist_display = format_km(dist_km)
                    else:
                        dist_display = "N/A"

                    time_s = route.get("time_s") or safe_getattr(day, "total_time_min", None)
                    time_display = format_min(time_s / 60.0) if isinstance(time_s, (int, float)) else "N/A"

                    st.markdown("**Route summary**")
                    st.write(f"- Distance: {dist_display}")
                    st.write(f"- Time: {time_display}")

                    # show first few instructions if any
                    instr = route.get("instructions") or []
                    if instr:
                        st.markdown("**Directions (sample)**")
                        for i, step in enumerate(instr[:8]):
                            st.write(f"{i+1}. {step}")

                # -------------------------
                # Budget / estimate
                # -------------------------
                estimate = safe_getattr(day, "estimate", None) or safe_getattr(day, "budget", None)
                if estimate:
                    # estimate may be BudgetEstimate dataclass or dict
                    if hasattr(estimate, "total"):
                        st.markdown(f"**Daily budget:** ${getattr(estimate, 'total', 'N/A')}")
                    elif isinstance(estimate, dict):
                        st.markdown(f"**Daily budget:** ${estimate.get('total', 'N/A')}")
                else:
                    # Fallback: show any per-day scalar
                    est_cost = safe_getattr(day, "estimated_cost", None)
                    if est_cost:
                        st.markdown(f"**Estimated daily cost:** ${est_cost}")

    except Exception as e:
        st.error("Planner failed — see traceback below.")
        tb = traceback.format_exc()
        st.code(tb)
        print(tb)
