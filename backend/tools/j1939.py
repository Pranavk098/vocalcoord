import json
import re
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "fault_codes.json"
_fault_data: list[dict] = []
_by_spn: dict[int, dict] = {}

_PATTERN = re.compile(r"SPN\s*[:#-]?\s*(\d{1,6})(?:\D{1,12}?FMI\s*[:#-]?\s*(\d{1,2}))?", re.I)


def _load() -> None:
    global _fault_data, _by_spn
    if _fault_data:
        return
    _fault_data = json.loads(_DATA_PATH.read_text())
    _by_spn = {f["spn"]: f for f in _fault_data}


def parse_fault_code(code: Optional[str]) -> Optional[tuple[int, int]]:
    """Parse 'SPN 4334 FMI 18' -> (4334, 18). Total: returns None instead of raising
    for anything that isn't a recognizable SPN/FMI code (e.g. "check engine light",
    "DEF light is on") — callers treat None as a real product state (ask the driver
    to read the code off the dash), not a crash."""
    if not code:
        return None
    match = _PATTERN.search(code)
    if not match:
        return None
    spn = int(match.group(1))
    fmi = int(match.group(2)) if match.group(2) else 0
    return spn, fmi


def lookup_fault(spn: int) -> Optional[dict]:
    _load()
    return _by_spn.get(spn)


def lookup_fault_cached(raw_code: str) -> tuple[Optional[tuple[int, int]], Optional[dict]]:
    """Cached fault decode: raw string -> (parsed, record). TTL'd in
    backend/cache.py so re-triggers skip re-parse. Falls back to the
    uncached path on any cache error (cache must never break a turn)."""
    try:
        from backend import cache as _cache

        key = f"fault:{(raw_code or '').strip().lower()}"
        hit = _cache.fault_decode_cache.get(key)
        if hit is not None:
            return hit
        parsed = parse_fault_code(raw_code)
        fault = lookup_fault(parsed[0]) if parsed else None
        out = (parsed, fault)
        _cache.fault_decode_cache.set(key, out)
        return out
    except Exception:
        parsed = parse_fault_code(raw_code)
        return parsed, (lookup_fault(parsed[0]) if parsed else None)
