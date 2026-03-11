# src/tools/pdf_export.py
"""
PDF export for the travel itinerary using reportlab.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_pdf(result: Dict[str, Any], start_date: Any, end_date: Any) -> bytes:
    """
    Generate a PDF itinerary and return as bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=20, spaceAfter=6)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=14, spaceAfter=4)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceAfter=4)
    body = styles["Normal"]
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=9, textColor=colors.grey)

    story = []

    destination = result.get("destination", "")
    days = result.get("days", 0)
    story.append(Paragraph(f"✈ Travel Itinerary: {destination}", title_style))
    story.append(Paragraph(
        f"{start_date.strftime('%B %d, %Y')} → {end_date.strftime('%B %d, %Y')}  |  {days} day{'s' if days != 1 else ''}",
        small
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 0.3*cm))

    # Summary / explanation
    explanation = result.get("explanation", "")
    if explanation:
        story.append(Paragraph("Summary", h1))
        for line in explanation.split("\n"):
            line = line.strip()
            if line:
                story.append(Paragraph(line, body))
        story.append(Spacer(1, 0.4*cm))

    # Day-by-day
    import datetime
    itineraries = result.get("itineraries", [])
    for day in itineraries:
        day_num = getattr(day, "day", 1)
        theme = getattr(day, "theme", "")
        day_date = start_date + datetime.timedelta(days=day_num - 1)
        story.append(Paragraph(
            f"Day {day_num} — {day_date.strftime('%A, %B %d')}: {theme}", h1
        ))

        # Weather
        weather = getattr(day, "weather", None)
        if weather:
            w_min = getattr(weather, "temp_min_c", "")
            w_max = getattr(weather, "temp_max_c", "")
            w_text = getattr(weather, "weather_text", "")
            story.append(Paragraph(
                f"<b>Weather:</b> {w_text}  |  {w_min:.1f}°C – {w_max:.1f}°C",
                small
            ))
            story.append(Spacer(1, 0.2*cm))

        # POIs
        pois = getattr(day, "pois", [])
        if pois:
            story.append(Paragraph("Places to visit:", h2))
            for poi in pois:
                name = getattr(poi, "name", "")
                address = getattr(poi, "address", "")
                opening = getattr(poi, "opening_hours", "")
                rating = getattr(poi, "rating", None)
                website = getattr(poi, "website", "")
                desc = getattr(poi, "description", "")

                line = f"<b>{name}</b>"
                if address:
                    line += f"<br/><font size='9' color='grey'>{address}</font>"
                if desc:
                    line += f"<br/><font size='9'>{desc}</font>"
                extras = []
                if opening:
                    extras.append(f"Hours: {opening}")
                if rating:
                    extras.append(f"Rating: {rating:.1f}")
                if website:
                    extras.append(f"Web: {website}")
                if extras:
                    line += f"<br/><font size='9' color='grey'>{' | '.join(extras)}</font>"
                story.append(Paragraph(line, body))
                story.append(Spacer(1, 0.15*cm))

        # Route
        dist = getattr(day, "total_distance_km", 0.0) or 0.0
        time_m = getattr(day, "total_time_min", 0.0) or 0.0
        route = getattr(day, "route", {}) or {}
        mode = route.get("mode", "")
        if dist > 0:
            story.append(Paragraph(
                f"<b>Route:</b> {dist:.2f} km · {time_m:.0f} min · {mode}",
                small
            ))

        # Budget
        estimate = getattr(day, "estimate", None)
        if estimate:
            total = getattr(estimate, "total", 0.0)
            acc = getattr(estimate, "accommodation", 0.0)
            food = getattr(estimate, "food", 0.0)
            act = getattr(estimate, "activities", 0.0)
            trans = getattr(estimate, "transport", 0.0)
            data = [
                ["Category", "Cost (USD)"],
                ["Accommodation", f"${acc:.2f}"],
                ["Food", f"${food:.2f}"],
                ["Activities", f"${act:.2f}"],
                ["Transport", f"${trans:.2f}"],
                ["Total", f"${total:.2f}"],
            ]
            t = Table(data, colWidths=[9*cm, 4*cm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a86c8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8f0fe")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f5f5f5")]),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(Spacer(1, 0.2*cm))
            story.append(t)

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#eeeeee")))
        story.append(Spacer(1, 0.4*cm))

    doc.build(story)
    return buf.getvalue()
