# src/agents/nl_requirements_agent.py
"""
NLRequirementsAgent — the upgrade that makes this project truly "agentic".

Instead of only accepting dropdowns, the user can now type:
  "Plan me 4 days in Tokyo under $100/day, I love street food and temples"
  "3 days in Paris, interested in art and history, budget around $150"
  "Week-long trip to Bali focused on nature and beaches, mid-range budget"

The LLM extracts all structured fields automatically.

LLM priority (all free):
  1. Groq  — free cloud API, works locally AND on Hugging Face Spaces
  2. Ollama — free local inference, works offline
  3. Keyword fallback — no LLM needed, extracts what it can from the text
     so the app NEVER crashes even without any LLM configured.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

KNOWN_DESTINATIONS = [
    "Paris, France", "London, UK", "New York, USA", "Tokyo, Japan",
    "Rome, Italy", "Barcelona, Spain", "Amsterdam, Netherlands",
    "Berlin, Germany", "Dubai, UAE", "Singapore", "Sydney, Australia",
    "Los Angeles, USA", "Chicago, USA", "Toronto, Canada", "Mumbai, India",
    "Bangkok, Thailand", "Istanbul, Turkey", "Prague, Czech Republic",
    "Vienna, Austria", "Lisbon, Portugal", "Athens, Greece",
    "Budapest, Hungary", "Cairo, Egypt", "Cape Town, South Africa",
    "Mexico City, Mexico", "Buenos Aires, Argentina", "Seoul, South Korea",
    "Kyoto, Japan", "Bali, Indonesia", "Marrakech, Morocco",
]

VALID_INTERESTS = [
    "Museums", "History", "Culture", "Art", "Attractions",
    "Food", "Restaurants", "Cafe", "Nightlife",
    "Parks", "Nature", "Shopping", "Transport", "Essentials",
]

_SYSTEM = (
    "You are a travel planning assistant. Extract structured information "
    "from natural language travel requests. Respond ONLY with valid JSON — "
    "no markdown fences, no explanation, just the raw JSON object."
)

_PROMPT_TEMPLATE = """Extract travel details from this request and return ONLY a JSON object.

User request: "{user_prompt}"

Known destinations (pick the closest match from this list only):
{destinations}

Valid interests (pick all that apply from this list only):
{interests}

Return EXACTLY this JSON structure:
{{
  "destination": "<one destination from the known list>",
  "num_days": <integer 1-14>,
  "budget_per_day": <number in USD>,
  "interests": ["<interest1>", "<interest2>"],
  "constraints": ["<constraint1>"],
  "start_location": "<starting point if mentioned, else empty string>",
  "confidence": <0.0-1.0>
}}

Rules:
- destination MUST come from the known destinations list (pick closest match)
- num_days: default 3 if not mentioned
- budget_per_day: default 100 if not mentioned; "cheap"=60, "mid-range"=120, "luxury"=250
- interests: only use values from the valid interests list
- constraints: dietary needs, accessibility needs, etc. Empty list [] if none mentioned
- confidence: how confident you are in the extraction (1.0 = very clear request)

Return ONLY the JSON object, nothing else."""


class NLRequirementsAgent:
    """
    Parses a free-text travel prompt into structured fields
    that the Orchestrator can use directly.
    """

    def __init__(self) -> None:
        from src.tools.llm_groq import GroqLLM
        from src.tools.llm_ollama import OllamaLLM

        self.groq = GroqLLM()
        self.ollama = OllamaLLM()
        logger.info("NLRequirementsAgent initialized")

    def parse(self, user_prompt: str) -> Dict[str, Any]:
        """
        Parse a natural language travel prompt into a structured dict.

        Returns dict with keys:
          destination, num_days, budget_per_day, interests,
          constraints, start_location, confidence, llm_used
        """
        if not user_prompt or not user_prompt.strip():
            return self._default_result()

        prompt = _PROMPT_TEMPLATE.format(
            user_prompt=user_prompt.strip(),
            destinations="\n".join(f"  - {d}" for d in KNOWN_DESTINATIONS),
            interests=", ".join(VALID_INTERESTS),
        )

        # 1) Try Groq (works locally + on Hugging Face Spaces)
        if self.groq.is_available():
            parsed_chain = self._langchain_groq_parse(user_prompt.strip())
            if parsed_chain:
                parsed_chain["llm_used"] = "groq_langchain"
                logger.info(f"NL parsed via LangChain+Groq — confidence: {parsed_chain.get('confidence', '?')}")
                return self._validate_and_fill(parsed_chain)

            raw = self.groq.generate(
                prompt, system=_SYSTEM, max_tokens=300, temperature=0.1
            )
            if raw:
                parsed = self._safe_parse_json(raw)
                if parsed:
                    parsed["llm_used"] = "groq"
                    logger.info(f"NL parsed via Groq — confidence: {parsed.get('confidence', '?')}")
                    return self._validate_and_fill(parsed)

        # 2) Try Ollama (local fallback)
        if self.ollama.is_available():
            raw = self.ollama.generate(prompt, max_tokens=300)
            if raw:
                parsed = self._safe_parse_json(raw)
                if parsed:
                    parsed["llm_used"] = "ollama"
                    logger.info(f"NL parsed via Ollama — confidence: {parsed.get('confidence', '?')}")
                    return self._validate_and_fill(parsed)

        # 3) Keyword fallback — no LLM needed
        logger.info("No LLM available — using keyword extraction fallback")
        return self._keyword_fallback(user_prompt)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _langchain_groq_parse(self, user_prompt: str) -> Optional[Dict[str, Any]]:
        """
        Try a LangChain chain with ChatGroq for structured extraction.

        If LangChain packages are unavailable or the invocation fails,
        return None and allow the existing fallback pipeline to continue.
        """
        try:
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_groq import ChatGroq
        except Exception:
            return None

        try:
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", _SYSTEM),
                    (
                        "human",
                        _PROMPT_TEMPLATE,
                    ),
                ]
            )
            llm = ChatGroq(
                model=self.groq.model,
                temperature=0.1,
                max_tokens=300,
            )
            chain = prompt | llm | StrOutputParser()
            raw = chain.invoke(
                {
                    "user_prompt": user_prompt,
                    "destinations": "\n".join(f"  - {d}" for d in KNOWN_DESTINATIONS),
                    "interests": ", ".join(VALID_INTERESTS),
                }
            )
            return self._safe_parse_json(raw)
        except Exception as e:
            logger.info(f"LangChain parse failed, fallback to direct Groq call: {e}")
            return None

    def _safe_parse_json(self, raw: str) -> Optional[Dict[str, Any]]:
        """Strip markdown fences and parse JSON safely."""
        text = raw.strip()
        # Remove ```json ... ``` or ``` ... ``` fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        # Find first { ... } block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e} — raw: {text[:200]}")
            return None

    def _validate_and_fill(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Clamp values into valid ranges and fix invalid entries."""
        result = self._default_result()
        result.update(parsed)

        # Destination: must be from known list
        dest = str(result.get("destination", "")).strip()
        result["destination"] = self._match_destination(dest)

        # num_days: 1-14
        try:
            result["num_days"] = max(1, min(14, int(result["num_days"])))
        except (TypeError, ValueError):
            result["num_days"] = 3

        # budget_per_day: positive number
        try:
            result["budget_per_day"] = max(10.0, float(result["budget_per_day"]))
        except (TypeError, ValueError):
            result["budget_per_day"] = 100.0

        # interests: only valid ones
        raw_interests = result.get("interests", [])
        valid_lower = {i.lower(): i for i in VALID_INTERESTS}
        clean = []
        for i in raw_interests:
            canonical = valid_lower.get(str(i).strip().lower())
            if canonical and canonical not in clean:
                clean.append(canonical)
        result["interests"] = clean if clean else ["Attractions", "Culture"]

        # constraints: list of strings
        if not isinstance(result.get("constraints"), list):
            result["constraints"] = []

        # start_location: string
        result["start_location"] = str(result.get("start_location", "")).strip()

        # confidence: 0-1
        try:
            result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.8))))
        except (TypeError, ValueError):
            result["confidence"] = 0.8

        return result

    def _match_destination(self, dest: str) -> str:
        """Find the closest known destination by substring match."""
        if not dest:
            return KNOWN_DESTINATIONS[0]

        dest_lower = dest.lower()

        # Exact match first
        for known in KNOWN_DESTINATIONS:
            if known.lower() == dest_lower:
                return known

        # City name match (e.g. "tokyo" matches "Tokyo, Japan")
        for known in KNOWN_DESTINATIONS:
            city = known.split(",")[0].lower()
            if city in dest_lower or dest_lower in city:
                return known

        # Partial match anywhere
        for known in KNOWN_DESTINATIONS:
            if dest_lower in known.lower() or known.lower() in dest_lower:
                return known

        logger.warning(f"Could not match destination '{dest}' — defaulting to Paris")
        return KNOWN_DESTINATIONS[0]

    def _keyword_fallback(self, text: str) -> Dict[str, Any]:
        """
        Best-effort extraction using simple keyword matching.
        Used when no LLM is available. Never crashes.
        """
        result = self._default_result()
        result["llm_used"] = "keyword_fallback"
        lower = text.lower()

        # Destination
        for known in KNOWN_DESTINATIONS:
            city = known.split(",")[0].lower()
            if city in lower:
                result["destination"] = known
                break

        # Number of days
        day_match = re.search(
            r"(\d+)\s*(?:-\s*day|day|days|night|nights)", lower
        )
        if day_match:
            result["num_days"] = max(1, min(14, int(day_match.group(1))))

        # Budget
        budget_match = re.search(
            r"\$\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:usd|dollars?)\s*(?:per|a|/)\s*day",
            lower,
        )
        if budget_match:
            val = budget_match.group(1) or budget_match.group(2)
            try:
                result["budget_per_day"] = float(val)
            except ValueError:
                pass
        elif "cheap" in lower or "budget" in lower:
            result["budget_per_day"] = 60.0
        elif "luxury" in lower or "splurge" in lower:
            result["budget_per_day"] = 250.0

        # Interests
        interest_keywords = {
            "museum": "Museums", "museums": "Museums",
            "history": "History", "historical": "History",
            "culture": "Culture", "cultural": "Culture",
            "art": "Art", "gallery": "Art",
            "food": "Food", "eat": "Food", "restaurant": "Restaurants",
            "cafe": "Cafe", "coffee": "Cafe",
            "park": "Parks", "garden": "Parks",
            "nature": "Nature", "hiking": "Nature", "beach": "Nature",
            "shop": "Shopping", "shopping": "Shopping", "market": "Shopping",
            "nightlife": "Nightlife", "bar": "Nightlife", "club": "Nightlife",
            "temple": "History", "monument": "History",
        }
        found = []
        for kw, interest in interest_keywords.items():
            if kw in lower and interest not in found:
                found.append(interest)
        result["interests"] = found if found else ["Attractions", "Culture"]

        result["confidence"] = 0.5  # lower confidence for keyword fallback
        return result

    def _default_result(self) -> Dict[str, Any]:
        return {
            "destination": "Paris, France",
            "num_days": 3,
            "budget_per_day": 100.0,
            "interests": ["Attractions", "Culture"],
            "constraints": [],
            "start_location": "",
            "confidence": 0.5,
            "llm_used": "none",
        }