import time
import threading
from typing import Any, Optional


class SimpleTTLCache:
    """Thread-safe, self-expiring in-memory cache for high-throughput quantitative endpoints."""

    def __init__(self, ttl_seconds: float = 120.0, max_items: int = 150):
        self._ttl = ttl_seconds
        self._max = max_items
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        with self._lock:
            if key in self._data:
                timestamp, val = self._data[key]
                if now - timestamp < self._ttl:
                    return val
                del self._data[key]
        return None

    def set(self, key: str, val: Any) -> None:
        now = time.time()
        with self._lock:
            if len(self._data) >= self._max:
                try:
                    oldest_key = min(self._data, key=lambda k: self._data[k][0])
                    del self._data[oldest_key]
                except (ValueError, KeyError):
                    pass
            self._data[key] = (now, val)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


# Pre-configured global caches for hot endpoints
opportunity_cache = SimpleTTLCache(ttl_seconds=120.0, max_items=80)
watchlist_cache = SimpleTTLCache(ttl_seconds=60.0, max_items=50)
ai_answer_cache = SimpleTTLCache(ttl_seconds=300.0, max_items=50)

