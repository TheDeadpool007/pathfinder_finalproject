# src/tools/geoapify_routing.py
from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

from src.tools.cache import TTLCache, make_key

logger = logging.getLogger(__name__)


class GeoapifyRoutingError(RuntimeError):
    pass


@dataclass
class RouteSummary:
    distance_m: float
    time_s: float
    mode: str
    instructions: List[str]


class GeoapifyRoutingClient:
    """
    Geoapify Routing API client.
    - Uses the same GEOAPIFY_API_KEY as geocoding/places
    - Caches routing responses to avoid repeated calls on Streamlit reruns
    - Returns RouteSummary with distance/time + human-readable instructions (best effort)
    """

    BASE_URL = "https://api.geoapify.com/v1/routing"

    def __init__(
        self,
        timeout: int = 25,
        max_retries: int = 3,
        backoff_s: float = 1.2,
        cache_ttl_s: int = 1800,  # 30 min (routes don't change quickly)
        user_agent: str = "agentic-travel-planner/1.0",
    ) -> None:
        self.api_key = os.getenv("GEOAPIFY_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GEOAPIFY_API_KEY not found. "
                "Make sure load_dotenv() is called before importing/creating routing client."
            )

        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_s = backoff_s

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

        self.cache = TTLCache[Dict[str, Any]](default_ttl_s=cache_ttl_s, max_items=512)

    def route(
        self,
        *,
        waypoints: Sequence[Tuple[float, float]],  # [(lat, lon), ...]
        mode: str = "walk",
        units: str = "metric",
        lang: str = "en",
        include_instructions: bool = True,
    ) -> RouteSummary:
        if len(waypoints) < 2:
            raise ValueError("Routing requires at least 2 waypoints.")

        # Geoapify expects: waypoints=lat,lon|lat,lon
        wp_str = "|".join([f"{lat},{lon}" for lat, lon in waypoints])

        params: Dict[str, Any] = {
            "apiKey": self.api_key,
            "waypoints": wp_str,
            "mode": mode,
            "format": "json",
            "units": units,
            "lang": lang,
        }

        if include_instructions:
            params["details"] = "instruction_details"

        data = self._get_json(self.BASE_URL, params=params)
        return self._parse(data, mode=mode)

    # ---------------- internals ----------------

    def _get_json(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cached GET with retries.
        """
        key = make_key("GET", url, sorted(params.items()))

        cached = self.cache.get(key)
        if cached is not None:
            logger.debug("Geoapify Routing cache hit")
            return cached

        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)

                # retryable
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < self.max_retries:
                        sleep_s = self.backoff_s * (attempt + 1)
                        logger.warning(
                            f"Routing retry {attempt+1}/{self.max_retries} "
                            f"(HTTP {resp.status_code}), sleeping {sleep_s:.1f}s"
                        )
                        time.sleep(sleep_s)
                        continue

                if resp.status_code >= 400:
                    raise GeoapifyRoutingError(f"Geoapify Routing error {resp.status_code}: {resp.text}")

                data = resp.json()
                self.cache.set(key, data)
                return data

            except (requests.RequestException, ValueError, GeoapifyRoutingError) as e:
                last_err = e
                if attempt < self.max_retries:
                    sleep_s = self.backoff_s * (attempt + 1)
                    logger.warning(f"Routing exception retry {attempt+1}/{self.max_retries}: {e} (sleep {sleep_s:.1f}s)")
                    time.sleep(sleep_s)
                    continue
                break

        raise GeoapifyRoutingError(f"Geoapify Routing request failed after retries: {last_err}")

    def _parse(self, data: Dict[str, Any], *, mode: str) -> RouteSummary:
        # Defensive parsing (Geoapify response shape can vary)
        results = data.get("results")
        r0 = results[0] if isinstance(results, list) and results else data

        distance_m = float(r0.get("distance", 0.0) or 0.0)
        time_s = float(r0.get("time", 0.0) or 0.0)

        instructions: List[str] = []
        for leg in (r0.get("legs") or []):
            for step in (leg.get("steps") or []):
                instr = step.get("instruction") or {}
                text = instr.get("text")
                if text:
                    instructions.append(str(text))

        return RouteSummary(
            distance_m=distance_m,
            time_s=time_s,
            mode=mode,
            instructions=instructions,
        )
