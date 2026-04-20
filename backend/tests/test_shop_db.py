# backend/tests/test_shop_db.py
from backend.tools.shop_db import search_shops, get_best_shop


def test_search_shops_returns_all_within_radius():
    results = search_shops(max_distance=50)
    assert len(results) == 4


def test_search_shops_filters_by_distance():
    results = search_shops(max_distance=10)
    assert all(s["distance_miles"] <= 10 for s in results)


def test_search_shops_filters_by_part_availability():
    results = search_shops(needs_def_pump=True)
    assert all(s["has_def_pump"] for s in results)
    assert len(results) == 2


def test_get_best_shop_prefers_shop_with_part():
    shops = search_shops(max_distance=50)
    best = get_best_shop(shops, needs_def_pump=True)
    assert best["has_def_pump"] is True


def test_get_best_shop_returns_none_for_empty_list():
    assert get_best_shop([], needs_def_pump=False) is None
