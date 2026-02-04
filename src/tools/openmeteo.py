# src/tools/openmeteo.py
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from src.tools.cache import TTLCache, make_key

logger = logging.getLogger(__name__)


class OpenMeteoError(RuntimeError):
    pass


@dataclass
class DailyWeather:
    date: str  # YYYY-MM-DD
    temp_min_c: float
    temp_max_c: float
    precip_mm: float
    weather_code: int
    weather_text: str


class OpenMeteoClient:
    """
    Open-Meteo daily forecast client (no API key).

    Caching:
    - Forecast is cached for a short TTL to prevent repeated calls on reruns.
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(
        self,
        timeout: int = 20,
        max_retries: int = 3,
        backoff_s: float = 1.2,
        cache_ttl_s: int = 900,   # 15 min
        user_agent: str = "agentic-travel-planner/1.0",
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_s = backoff_s

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

        self.cache = TTLCache[Dict[str, Any]](default_ttl_s=cache_ttl_s, max_items=256)

    def daily_forecast(
        self,
        *,
        lat: float,
        lon: float,
        days: int = 7,
        timezone: str = "auto",
    ) -> List[DailyWeather]:
        """
        Returns up to `days` entries of daily forecast.
        """
        if days < 1:
            raise ValueError("days must be >= 1")

        params: Dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
            "forecast_days": min(days, 16),
            "timezone": timezone,
        }

        data = self._get_json(self.BASE_URL, params=params)
        return self._parse_daily(data)

    # ---------------- internals ----------------

    def _get_json(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        key = make_key("GET", url, sorted(params.items()))

        cached = self.cache.get(key)
        if cached is not None:
            logger.debug("Open-Meteo cache hit")
            return cached

        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)

                if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    sleep_s = self.backoff_s * (attempt + 1)
                    logger.warning(
                        f"Open-Meteo retry {attempt+1}/{self.max_retries} "
                        f"(HTTP {resp.status_code}), sleeping {sleep_s:.1f}s"
                    )
                    time.sleep(sleep_s)
                    continue

                if resp.status_code >= 400:
                    raise OpenMeteoError(f"Open-Meteo HTTP {resp.status_code}: {resp.text[:1200]}")

                data = resp.json()
                self.cache.set(key, data)
                return data

            except (requests.RequestException, ValueError, OpenMeteoError) as e:
                last_err = e
                if attempt < self.max_retries:
                    sleep_s = self.backoff_s * (attempt + 1)
                    logger.warning(f"Open-Meteo exception retry {attempt+1}/{self.max_retries}: {e} (sleep {sleep_s:.1f}s)")
                    time.sleep(sleep_s)
                    continue
                break

        raise OpenMeteoError(f"Open-Meteo request failed after retries: {last_err}")

    def _parse_daily(self, data: Dict[str, Any]) -> List[DailyWeather]:
        daily = data.get("daily") or {}
        times = daily.get("time") or []
        tmax = daily.get("temperature_2m_max") or []
        tmin = daily.get("temperature_2m_min") or []
        precip = daily.get("precipitation_sum") or []
        wcode = daily.get("weather_code") or []

        n = min(len(times), len(tmax), len(tmin), len(precip), len(wcode))
        out: List[DailyWeather] = []

        for i in range(n):
            code = int(wcode[i]) if wcode[i] is not None else -1
            out.append(
                DailyWeather(
                    date=str(times[i]),
                    temp_min_c=float(tmin[i]) if tmin[i] is not None else 0.0,
                    temp_max_c=float(tmax[i]) if tmax[i] is not None else 0.0,
                    precip_mm=float(precip[i]) if precip[i] is not None else 0.0,
                    weather_code=code,
                    weather_text=self._weather_code_to_text(code),
                )
            )

        return out

    def _weather_code_to_text(self, code: int) -> str:
        mapping = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return mapping.get(code, "Unknown")
