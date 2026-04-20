# backend/tools/shop_db.py
import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "shops.json"
_shops: list[dict] = []


def _load() -> None:
    global _shops
    if _shops:
        return
    _shops = json.loads(_DATA_PATH.read_text())


def search_shops(needs_def_pump: bool = False, max_distance: float = 50) -> list[dict]:
    _load()
    results = [s for s in _shops if s["distance_miles"] <= max_distance]
    if needs_def_pump:
        results = [s for s in results if s.get("has_def_pump")]
    return sorted(results, key=lambda x: x["distance_miles"])


def get_best_shop(shops: list[dict], needs_def_pump: bool = False) -> Optional[dict]:
    if not shops:
        return None
    if needs_def_pump:
        with_part = [s for s in shops if s.get("has_def_pump")]
        if with_part:
            return sorted(with_part, key=lambda x: x["distance_miles"])[0]
    return shops[0]
