# backend/tools/warranty_db.py
import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "warranty_parts.json"
_warranties: list[dict] = []
_by_code: dict[str, dict] = {}


def _load() -> None:
    global _warranties, _by_code
    if _warranties:
        return
    _warranties = json.loads(_DATA_PATH.read_text())
    _by_code = {w["warranty_code"]: w for w in _warranties}


def lookup_warranty(warranty_code: str) -> Optional[dict]:
    _load()
    return _by_code.get(warranty_code)


def lookup_warranty_cached(warranty_code: str) -> Optional[dict]:
    """TTL-cached warranty lookup. Sync dict hit today; same key fronts a
    future OEM claims API without changing callers."""
    try:
        from backend import cache as _cache

        key = f"wty:{(warranty_code or '').strip()}"
        hit = _cache.fault_decode_cache.get(key)
        if hit is not None:
            return hit
        out = lookup_warranty(warranty_code)
        _cache.fault_decode_cache.set(key, out)
        return out
    except Exception:
        return lookup_warranty(warranty_code)
