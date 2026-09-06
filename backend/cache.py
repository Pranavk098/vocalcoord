# backend/cache.py
"""Tiny TTL caches for the webhook hot path (2nd-cycle revamp).

What is cached and why:
  - fault_decode: fault_code string -> (spn, fmi, fault_record). The regex +
    dict lookup is already ~microseconds, but caching skips re-parse on
    ElevenLabs re-triggers and gives re-trigger storms a single shared entry.
  - shop_rank: (geo_hash, needs_def_pump, hos_bucket) -> ranked shop list +
    best. Fixture scoring is microseconds today, but the same key shape fronts
    a future Places API call without changing callers.

Geo-hash: city string or lat/lon rounded to 0.1 deg (~11 km) — coarse enough
to share across drivers in the same metro, fine enough not to mix metros.
HOS is bucketed to 0.5 hr so nearby clocks share entries without changing
tier outcomes (tier edges sit on 0.5 hr boundaries: 1.0/2.0/3.5/6.0).

All caches are process-local, bounded, TTL'd. Thread-safe for the
asyncio.to_thread audit path via a single lock.
"""
import threading
from time import monotonic

FAULT_DECODE_TTL_S = 600.0
SHOP_RANK_TTL_S = 300.0
_MAX_ENTRIES = 2048


class TTLCache:
    def __init__(self, ttl_s: float, max_entries: int = _MAX_ENTRIES):
        self._ttl = ttl_s
        self._max = max_entries
        self._lock = threading.Lock()
        self._store: dict[str, tuple[object, float]] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str):
        now = monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            value, expires = entry
            if now > expires:
                self._store.pop(key, None)
                self.misses += 1
                return None
            self.hits += 1
            return value

    def set(self, key: str, value: object) -> None:
        with self._lock:
            if len(self._store) >= self._max:
                # Evict the single oldest entry (cheap, no full scan ordering).
                oldest = min(self._store.items(), key=lambda kv: kv[1][1])[0]
                self._store.pop(oldest, None)
            self._store[key] = (value, monotonic() + self._ttl)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self._store),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else 0.0,
            }


fault_decode_cache = TTLCache(FAULT_DECODE_TTL_S)
shop_rank_cache = TTLCache(SHOP_RANK_TTL_S)


def geo_hash(location: object) -> str:
    """Coarse geo key: 'city:<lower>' for strings, 'll:<lat>,<lon>' rounded
    to 0.1 deg for dicts, 'unknown' otherwise."""
    if isinstance(location, str):
        s = location.strip().lower()
        return f"city:{s}" if s else "unknown"
    if isinstance(location, dict):
        city = str(location.get("city") or "").strip().lower()
        lat, lon = location.get("lat"), location.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return f"ll:{round(lat, 1)},{round(lon, 1)}"
        if city:
            return f"city:{city}"
        return "unknown"
    return "unknown"


def hos_bucket(hos: float | None) -> str:
    if hos is None:
        return "none"
    try:
        return f"{round(float(hos) * 2) / 2:.1f}"
    except (TypeError, ValueError):
        return "none"


def shop_cache_key(geo: str, needs_def_pump: bool, hos: float | None) -> str:
    return f"{geo}|def={int(bool(needs_def_pump))}|hos={hos_bucket(hos)}"
