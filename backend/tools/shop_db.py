# backend/tools/shop_db.py
import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "shops.json"
_shops: list[dict] = []

# Fixture assumption: bay wait time is derived from a fixed estimate, not real scheduling
# data or wall-clock comparison against open_bay_time (which would make scoring
# nondeterministic across the day and across tests). A real ShopProvider replaces this
# with actual bay-availability data from the shop network's API.
_ESTIMATED_REPAIR_HOURS = 2.0
_BAY_WAIT_LATER_TODAY_HOURS = 2.0


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


def _bay_wait_hours(open_bay_time: str) -> float:
    return 0.0 if open_bay_time.strip().lower() == "now" else _BAY_WAIT_LATER_TODAY_HOURS


def score_shop(shop: dict, needs_def_pump: bool, hos_hours_remaining: Optional[float]) -> float:
    """Weighted score over distance, bay availability vs. HOS clock, part in stock,
    and labor rate — higher is better. Replaces pure nearest-shop ranking (which ignored
    open_bay_time and never consulted the HOS agent's output even though both were
    already computed in the same run)."""
    score = 0.0
    score += max(0.0, 30.0 - shop["distance_miles"])
    score += max(0.0, (200.0 - shop["labor_rate"]) / 10.0)

    wait = _bay_wait_hours(shop.get("open_bay_time", ""))
    if wait == 0.0:
        score += 15.0  # bay open now

    if needs_def_pump:
        score += 40.0 if shop.get("has_def_pump") else -60.0

    if hos_hours_remaining is not None:
        margin = hos_hours_remaining - wait - _ESTIMATED_REPAIR_HOURS
        if margin < 0:
            score -= 100.0  # driver would blow their HOS limit getting the repair done here
        else:
            score += min(margin, 5.0)

    return score


def get_best_shop(
    shops: list[dict],
    needs_def_pump: bool = False,
    hos_hours_remaining: Optional[float] = None,
) -> Optional[dict]:
    if not shops:
        return None
    return max(shops, key=lambda s: score_shop(s, needs_def_pump, hos_hours_remaining))


def score_shops_batch(
    shops: list[dict],
    needs_def_pump: bool = False,
    hos_hours_remaining: Optional[float] = None,
) -> list[tuple[dict, float]]:
    """Batch HOS computation: score every candidate in one pass and return
    (shop, score) sorted best-first. Same math as score_shop — one loop instead
    of max() re-walking — so a future Places-size list pays the HOS margin
    computation once per shop, not once per comparison."""
    scored = [(s, score_shop(s, needs_def_pump, hos_hours_remaining)) for s in shops]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


def search_shops_cached(
    needs_def_pump: bool = False,
    max_distance: float = 50,
    geo_key: str = "unknown",
    hos_hours_remaining: Optional[float] = None,
) -> tuple[list[dict], Optional[dict]]:
    """Geo-hash-keyed ranked-shop cache: (geo, part, HOS-bucket) -> (ranked, best).
    TTL'd (SHOP_RANK_TTL_S). Falls back to the uncached path on any error."""
    try:
        from backend import cache as _cache

        key = _cache.shop_cache_key(geo_key, needs_def_pump, hos_hours_remaining)
        hit = _cache.shop_rank_cache.get(key)
        if hit is not None:
            return hit
        shops = search_shops(needs_def_pump=needs_def_pump, max_distance=max_distance)
        best = get_best_shop(shops, needs_def_pump=needs_def_pump, hos_hours_remaining=hos_hours_remaining)
        out = (shops, best)
        _cache.shop_rank_cache.set(key, out)
        return out
    except Exception:
        shops = search_shops(needs_def_pump=needs_def_pump, max_distance=max_distance)
        return shops, get_best_shop(shops, needs_def_pump=needs_def_pump, hos_hours_remaining=hos_hours_remaining)
