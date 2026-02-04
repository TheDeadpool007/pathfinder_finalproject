# src/tools/cache.py
from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, Optional, Tuple, TypeVar

T = TypeVar("T")


@dataclass
class _CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    """
    Tiny in-memory TTL cache.
    - Thread-safe
    - Pure Python (works in Streamlit + CLI)
    - Good enough for academic demos + reliability

    Notes:
    - Cache is per-process (Streamlit reruns in same process, so it helps a lot).
    - Not persistent across app restarts.
    """

    def __init__(self, default_ttl_s: int = 600, max_items: int = 512) -> None:
        self.default_ttl_s = int(default_ttl_s)
        self.max_items = int(max_items)
        self._lock = threading.Lock()
        self._store: Dict[str, _CacheEntry[T]] = {}

    def get(self, key: str) -> Optional[T]:
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if entry.expires_at <= now:
                # expired
                self._store.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: T, ttl_s: Optional[int] = None) -> None:
        ttl = self.default_ttl_s if ttl_s is None else int(ttl_s)
        expires_at = time.time() + ttl

        with self._lock:
            # simple eviction if over capacity
            if len(self._store) >= self.max_items:
                self._evict_some(now=time.time())

            self._store[key] = _CacheEntry(value=value, expires_at=expires_at)

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl_s: Optional[int] = None,
    ) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value, ttl_s=ttl_s)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _evict_some(self, now: float) -> None:
        """
        Evict expired entries first, otherwise evict a few oldest-ish (by earliest expiry).
        """
        # remove expired
        expired_keys = [k for k, v in self._store.items() if v.expires_at <= now]
        for k in expired_keys:
            self._store.pop(k, None)

        if len(self._store) < self.max_items:
            return

        # if still too big, evict ~10% by soonest expiry
        items = sorted(self._store.items(), key=lambda kv: kv[1].expires_at)
        remove_n = max(1, int(self.max_items * 0.1))
        for i in range(min(remove_n, len(items))):
            self._store.pop(items[i][0], None)


def make_key(*parts: Any) -> str:
    """
    Stable cache key helper.
    Converts arguments to a string key; good enough for our API param caching.
    """
    safe_parts = []
    for p in parts:
        if isinstance(p, (dict, list, tuple)):
            safe_parts.append(repr(p))
        else:
            safe_parts.append(str(p))
    return "||".join(safe_parts)
