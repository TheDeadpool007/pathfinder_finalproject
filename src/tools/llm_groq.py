# src/tools/llm_groq.py
"""
Groq LLM wrapper — completely free tier, no credit card required.

HOW TO GET YOUR FREE KEY:
  1. Go to https://console.groq.com
  2. Sign up (free, no card)
  3. Click "API Keys" → "Create API Key"
  4. Copy the key into your .env as: GROQ_API_KEY=your_key_here

Free tier limits (more than enough for a grad project):
  - 30 requests / minute
  - 6,000 requests / day
  - Model: llama3-8b-8192 (fast, smart, always free)

This file is used by:
  - NLRequirementsAgent  → parse natural language prompts
  - ExplainerAgent       → generate rich trip summaries
  - Orchestrator         → generate per-POI descriptions
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from src.tools.cache import TTLCache, make_key

logger = logging.getLogger(__name__)

# Cache responses — Streamlit reruns won't burn your daily quota
_cache: TTLCache[str] = TTLCache(default_ttl_s=600, max_items=128)


class GroqLLM:
    """Groq cloud LLM — free tier, works locally AND on Hugging Face Spaces."""

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    DEFAULT_MODEL = "llama-3.1-8b-instant"

    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.model = os.getenv("GROQ_MODEL", self.DEFAULT_MODEL)
        self._available: Optional[bool] = None
        logger.info(f"GroqLLM initialized — model: {self.model}")

    def is_available(self) -> bool:
        """Return True if GROQ_API_KEY is set and the API responds."""
        if self._available is not None:
            return self._available

        if not self.api_key:
            logger.info("GROQ_API_KEY not set — Groq unavailable")
            self._available = False
            return False

        try:
            resp = requests.post(
                self.BASE_URL,
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
                timeout=8,
            )
            self._available = resp.status_code == 200
            if self._available:
                logger.info("Groq LLM available ✓")
            else:
                logger.warning(
                    f"Groq check failed: HTTP {resp.status_code} — {resp.text[:200]}"
                )
        except Exception as e:
            logger.info(f"Groq not reachable: {e}")
            self._available = False

        return self._available

    def generate(
        self,
        prompt: str,
        system: str = "You are a helpful travel planning assistant.",
        max_tokens: int = 400,
        temperature: float = 0.3,
    ) -> Optional[str]:
        """
        Call Groq and return generated text, or None on failure.
        Responses are cached so Streamlit reruns don't burn daily quota.
        """
        if not self.is_available():
            return None

        cache_key = make_key("groq", self.model, system[:60], prompt[:200])
        cached = _cache.get(cache_key)
        if cached is not None:
            logger.debug("Groq cache hit")
            return cached

        try:
            resp = requests.post(
                self.BASE_URL,
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=30,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            _cache.set(cache_key, text)
            logger.info(f"Groq generated {len(text)} chars")
            return text

        except Exception as e:
            logger.error(f"Groq generation failed: {e}")
            return None

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }