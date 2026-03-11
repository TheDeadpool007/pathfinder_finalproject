# app.py
from dotenv import load_dotenv
load_dotenv()  # MUST be first so GEOAPIFY_API_KEY is available to imported modules

import datetime
import os
import traceback
from typing import List

import streamlit as st
import pandas as pd

from src.core.orchestrator import Orchestrator
from src.core.models import POI, DayItinerary
from src.tools.currency import get_local_currency, convert
from src.tools.pdf_export import generate_pdf

st.set_page_config(page_title="Agentic AI Travel Planner", layout="wide", page_icon="✈️")

# ------ Helpers ------

def safe_getattr(obj, attr, default=None):
    return getattr(obj, attr, default)

def star_rating(rating):
    if rating is None:
        return ""
    full = int(rating)
    half = 1 if (rating - full) >= 0.5 else 0
    return "⭐" * full + ("½" if half else "")

def google_maps_url(stops, travelmode="driving"):
    coords_list = [(s["lat"], s["lon"]) for s in stops if "lat" in s and "lon" in s]
    if len(coords_list) >= 2:
        origin = f"{coords_list[0][0]},{coords_list[0][1]}"
        dest = f"{coords_list[-1][0]},{coords_list[-1][1]}"
        url = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={dest}&travelmode={travelmode}"
        mid = coords_list[1:-1]
        if mid:
            url += "&waypoints=" + "|".join(f"{c[0]},{c[1]}" for c in mid)
        return url
    elif len(coords_list) == 1:
        return f"https://www.google.com/maps/search/?api=1&query={coords_list[0][0]},{coords_list[0][1]}"
    return None

def display_poi_card(poi: POI, local_currency: str):
    name = safe_getattr(poi, "name", "Unknown")
    address = safe_getattr(poi, "address", "")
    desc = safe_getattr(poi, "description", "")
    website = safe_getattr(poi, "website", "")
    phone = safe_getattr(poi, "phone", "")
    hours = safe_getattr(poi, "opening_hours", "")
    rating = safe_getattr(poi, "rating", None)
    photo_url = safe_getattr(poi, "photo_url", "")
    fee = safe_getattr(poi, "fee", None)

    col_img, col_info = st.columns([1, 3])
    with col_img:
        if photo_url:
            st.image(photo_url, use_container_width=True)
        else:
            st.markdown("🏛️")
    with col_info:
        header = f"**{name}**"
        if rating is not None:
            header += f"  {star_rating(rating)} `{rating:.1f}`"
        if fee is not None:
            header += "  🎟️ Paid" if fee else "  ✅ Free entry"
        st.markdown(header)
        if address:
            st.caption(f"📍 {address}")
        if hours:
            st.caption(f"🕐 {hours}")
        if desc:
            st.write(desc)
        links = []
        if website:
            links.append(f"[🌐 Website]({website})")
        if phone:
            links.append(f"📞 {phone}")
        if links:
            st.markdown("  |  ".join(links))
    st.markdown("<hr style='margin:6px 0; border-color:#eee'>", unsafe_allow_html=True)


def km_to_miles(km):
    return float(km) * 0.621371

def c_to_f(c):
    return float(c) * 9 / 5 + 32

def mm_to_inches(mm):
    return float(mm) * 0.0393701

def format_dist(x):
    """km value → display in miles."""
    try:
        return f"{km_to_miles(x):.2f} mi"
    except Exception:
        return "N/A"

def format_min(x):
    try:
        mins = float(x)
        if mins >= 60:
            return f"{int(mins // 60)}h {int(mins % 60)}min"
        return f"{mins:.0f} min"
    except Exception:
        return "N/A"

def format_temp(x):
    """°C value → display in °F."""
    try:
        return f"{c_to_f(x):.1f}°F"
    except Exception:
        return "N/A"

def format_precip(x):
    """mm value → display in inches."""
    try:
        return f"{mm_to_inches(x):.2f} in"
    except Exception:
        return "N/A"

# ------ App UI ------

st.title("✈️ Agentic AI Travel Planner")
st.caption("Multi-Agent System for Intelligent Travel Itinerary Generation")

# Sidebar inputs
with st.sidebar:
    st.header("🎯 Trip Preferences")

    DESTINATIONS = [
        "Paris, France",
        "London, UK",
        "New York, USA",
        "Tokyo, Japan",
        "Rome, Italy",
        "Barcelona, Spain",
        "Amsterdam, Netherlands",
        "Berlin, Germany",
        "Dubai, UAE",
        "Singapore",
        "Sydney, Australia",
        "Los Angeles, USA",
        "Chicago, USA",
        "Toronto, Canada",
        "Mumbai, India",
        "Bangkok, Thailand",
        "Istanbul, Turkey",
        "Prague, Czech Republic",
        "Vienna, Austria",
        "Lisbon, Portugal",
        "Athens, Greece",
        "Budapest, Hungary",
        "Cairo, Egypt",
        "Cape Town, South Africa",
        "Mexico City, Mexico",
        "Buenos Aires, Argentina",
        "Seoul, South Korea",
        "Kyoto, Japan",
        "Bali, Indonesia",
        "Marrakech, Morocco",
    ]
    destination = st.selectbox("Destination", DESTINATIONS, index=0)

    today = datetime.date.today()
    default_start = today + datetime.timedelta(days=7)
    default_end = default_start + datetime.timedelta(days=2)

    date_range = st.date_input(
        "Trip Dates",
        value=(default_start, default_end),
        min_value=today,
        format="DD/MM/YYYY",
    )

    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range[0], date_range[1]
        num_days = (end_date - start_date).days + 1
        st.caption(f"{start_date.strftime('%b %d')} → {end_date.strftime('%b %d, %Y')} · {num_days} day{'s' if num_days != 1 else ''}")
    else:
        # User is mid-selection (only picked start so far)
        start_date = date_range[0] if isinstance(date_range, (list, tuple)) else date_range
        end_date = start_date
        num_days = 1
        st.caption("Select an end date to complete the range.")

    daily_budget = st.number_input("Daily Budget (USD)", min_value=10, value=150, step=10)

    # Provide the same normalized options the SearcherAgent understands
    interest_options = [
        "Museums", "History", "Culture", "Art", "Attractions",
        "Food", "Restaurants", "Cafe", "Nightlife",
        "Parks", "Nature", "Shopping", "Transport", "Essentials"
    ]
    interests = st.multiselect("Interests", interest_options, default=["Museums", "History"])

    st.markdown("---")
    st.markdown("**📍 Route**")
    start_location = st.text_input("Starting from", value="", placeholder="e.g. Eiffel Tower, Paris")
    end_location = st.text_input("Ending at (blank = same as start)", value="", placeholder="e.g. CDG Airport, Paris")

    if "GEOAPIFY_API_KEY" not in os.environ or not os.environ.get("GEOAPIFY_API_KEY"):
        st.error(
            "GEOAPIFY_API_KEY not loaded. Make sure you have a .env with GEOAPIFY_API_KEY and "
            "`from dotenv import load_dotenv; load_dotenv()` at top of app.py."
        )

    st.markdown("---")
    generate = st.button("🚀 Generate Itinerary", use_container_width=True)

orch = Orchestrator()

# Only run pipeline on button click
if generate:
    with st.spinner("Planning your trip — fetching places, routes and weather…"):
        try:
            result = orch.run(
                destination=destination,
                lat=0.0,
                lon=0.0,
                num_days=num_days,
                interests=interests,
                start_date=start_date,
                start_location=start_location or None,
                end_location=end_location or None,
                transport_mode="auto",
            )
        except Exception as e:
            st.error("Planner failed — see traceback below.")
            st.code(traceback.format_exc())
            st.stop()

    st.success("✅ Itinerary ready!")

    # ---- Currency setup ----
    local_currency = get_local_currency(destination)
    itineraries = result.get("itineraries", [])
    total_budget_usd = sum(
        (safe_getattr(d, "estimate", None) and safe_getattr(d.estimate, "total", 0) or 0)
        if hasattr(d, "estimate")
        else 0
        for d in itineraries
    )
    total_local = convert(total_budget_usd, local_currency)

    # ---- Flight / intercity travel banner ----
    intercity_mode = result.get("intercity_mode", "local")
    start_loc = result.get("start_location", "")
    if intercity_mode == "flight" and start_loc:
        st.info(
            f"✈️ **Getting there:** Fly from **{start_loc}** to **{destination}**  "
            f"— day routes below are within {destination.split(',')[0]}."
        )

    # ---- Summary banner ----
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    col1.markdown(
        f"<div style='font-size:0.75rem;color:gray;margin-bottom:4px'>Destination</div>"
        f"<div style='font-size:1rem;font-weight:600'>{destination.split(',')[0]}</div>",
        unsafe_allow_html=True,
    )
    col2.markdown(
        f"<div style='font-size:0.75rem;color:gray;margin-bottom:4px'>Dates</div>"
        f"<div style='font-size:1rem;font-weight:600'>{start_date.strftime('%b %d, %Y')} → {end_date.strftime('%b %d, %Y')}</div>",
        unsafe_allow_html=True,
    )
    if total_local and local_currency != "USD":
        cost_str = f"${total_budget_usd:.0f} USD (~{total_local:,.0f} {local_currency})"
    else:
        cost_str = f"${total_budget_usd:.0f} USD"
    col3.markdown(
        f"<div style='font-size:0.75rem;color:gray;margin-bottom:4px'>Est. Total Cost</div>"
        f"<div style='font-size:1rem;font-weight:600'>{cost_str}</div>",
        unsafe_allow_html=True,
    )
    col4.markdown(
        f"<div style='font-size:0.75rem;color:gray;margin-bottom:4px'>Days</div>"
        f"<div style='font-size:1rem;font-weight:600'>{num_days}</div>",
        unsafe_allow_html=True,
    )

    # ---- Explanation ----
    explanation = result.get("explanation") or ""
    if explanation:
        with st.expander("📋 Trip Summary", expanded=True):
            for line in explanation.split("\n"):
                if line.strip():
                    st.write(line)

    # ---- Full-trip map ----
    all_coords = []
    for day in itineraries:
        for poi in (safe_getattr(day, "pois", []) or []):
            all_coords.append({"lat": poi.lat, "lon": poi.lon, "name": poi.name})
    if all_coords:
        st.markdown("### 🗺️ Full Trip Map")
        st.map(pd.DataFrame(all_coords), latitude="lat", longitude="lon", size=80)

    st.markdown("---")
    st.subheader("🗓 Day-wise Itinerary")

    for day in itineraries:
        day_num = safe_getattr(day, "day", 1) if hasattr(day, "day") else day.get("day", 1)
        day_date = start_date + datetime.timedelta(days=day_num - 1)
        date_str = day_date.strftime("%a, %b %d")
        theme = safe_getattr(day, "theme", "") if hasattr(day, "theme") else day.get("theme", "")
        title = f"Day {day_num} — {date_str}: {theme}"

        with st.expander(title, expanded=False):

            # Weather
            weather = safe_getattr(day, "weather", None)
            if weather:
                wc1, wc2, wc3, wc4 = st.columns([2, 1, 1, 1])
                wc1.metric("Condition", safe_getattr(weather, "weather_text", "N/A"))
                wc2.metric("Min Temp", format_temp(safe_getattr(weather, "temp_min_c")))
                wc3.metric("Max Temp", format_temp(safe_getattr(weather, "temp_max_c")))
                wc4.metric("Precipitation", format_precip(safe_getattr(weather, "precip_mm")))
                st.markdown("---")

            # Day mini-map
            places = safe_getattr(day, "pois", []) or []
            if places:
                day_coords = [{"lat": p.lat, "lon": p.lon, "name": p.name} for p in places]
                st.markdown("**📍 Day Map**")
                st.map(pd.DataFrame(day_coords), latitude="lat", longitude="lon", size=120)
                st.markdown("---")

            # POI cards
            if not places:
                st.write("_No places for this day._")
            else:
                st.markdown("**🏛️ Places to Visit**")
                for poi in places:
                    display_poi_card(poi, local_currency)

            # Route summary
            route = safe_getattr(day, "route", None) or {}
            if route:
                dist_km = safe_getattr(day, "total_distance_km", 0.0) or 0.0
                time_min = safe_getattr(day, "total_time_min", 0.0) or 0.0
                mode = route.get("mode", "")
                mode_icon = {"walk": "🚶", "drive": "🚗", "bicycle": "🚲", "transit": "🚇"}.get(mode, "🗺️")

                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Distance", format_dist(dist_km))
                rc2.metric("Est. Travel Time", format_min(time_min))
                rc3.metric("Mode", f"{mode_icon} {mode.capitalize()}")

                r_start = result.get("start_location", "")
                r_end = result.get("end_location", "") or r_start
                # Only show start→end caption when it's a local (same-city) trip
                if r_start and intercity_mode != "flight":
                    st.caption(f"From **{r_start}** → **{r_end or destination}**")

                stops = route.get("stops") or []
                if stops:
                    travelmode = {"walk": "walking", "bicycle": "bicycling", "transit": "transit"}.get(mode, "driving")
                    url = google_maps_url(stops, travelmode)
                    if url:
                        st.link_button("🗺️ Open in Google Maps", url)
                st.markdown("---")

            # Restaurants
            restaurants = safe_getattr(day, "restaurants", []) or []
            if restaurants:
                with st.expander("🍽️ Nearby Restaurants", expanded=False):
                    for r in restaurants[:5]:
                        r_name = safe_getattr(r, "name", "")
                        r_addr = safe_getattr(r, "address", "")
                        r_hours = safe_getattr(r, "opening_hours", "")
                        r_rating = safe_getattr(r, "rating", None)
                        r_web = safe_getattr(r, "website", "")
                        label = f"🍴 **{r_name}**"
                        if r_rating is not None:
                            label += f"  {star_rating(r_rating)} `{r_rating:.1f}`"
                        st.markdown(label)
                        if r_addr:
                            st.caption(f"📍 {r_addr}")
                        if r_hours:
                            st.caption(f"🕐 {r_hours}")
                        if r_web:
                            st.markdown(f"[🌐 Website]({r_web})")
                st.markdown("---")

            # Budget breakdown
            estimate = safe_getattr(day, "estimate", None) or safe_getattr(day, "budget", None)
            if estimate:
                st.markdown("**💰 Daily Budget**")
                acc = safe_getattr(estimate, "accommodation", 0.0) or 0.0
                food = safe_getattr(estimate, "food", 0.0) or 0.0
                act = safe_getattr(estimate, "activities", 0.0) or 0.0
                trans = safe_getattr(estimate, "transport", 0.0) or 0.0
                total = safe_getattr(estimate, "total", 0.0) or 0.0
                bc1, bc2, bc3, bc4, bc5 = st.columns(5)
                bc1.metric("🏨 Stay", f"${acc:.0f}")
                bc2.metric("🍽️ Food", f"${food:.0f}")
                bc3.metric("🎡 Activities", f"${act:.0f}")
                bc4.metric("🚗 Transport", f"${trans:.0f}")
                bc5.metric("Total", f"${total:.0f}")
                if total_local is not None and local_currency != "USD":
                    day_local = convert(total, local_currency)
                    if day_local:
                        st.caption(f"≈ {day_local:,.0f} {local_currency}")
            else:
                est_cost = safe_getattr(day, "estimated_cost", None)
                if est_cost:
                    st.markdown(f"**Estimated daily cost:** ${est_cost}")

    # ---- PDF Download ----
    st.markdown("---")
    st.markdown("### 📄 Export")
    try:
        pdf_bytes = generate_pdf(result, start_date, end_date)
        dest_slug = destination.split(",")[0].replace(" ", "_").lower()
        st.download_button(
            label="⬇️ Download Itinerary as PDF",
            data=pdf_bytes,
            file_name=f"itinerary_{dest_slug}_{start_date}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as e:
        st.warning(f"PDF generation failed: {e}")
