# backend/providers.py
"""Provider interfaces — the boundary between deterministic business logic and where the
data actually comes from. Today every provider is a Fixture implementation backed by the
JSON files in backend/data/. A real deployment swaps in a PlacesShopProvider (Google
Places + certification filter), a FleetWarrantyProvider (OEM claims API), a
TMSDispatchProvider (McLeod/TMW/Samsara Dispatch webhook), etc. — the agents that call
these interfaces don't change.

This is what turns "it's a JSON file" into "it's an interface, here's the adapter."
"""
from typing import Optional, Protocol

from backend.tools import shop_db, warranty_db


class ShopProvider(Protocol):
    async def search(self, needs_def_pump: bool, max_distance: float) -> list[dict]: ...

    async def best(
        self, shops: list[dict], needs_def_pump: bool, hos_hours_remaining: Optional[float]
    ) -> Optional[dict]: ...


class WarrantyProvider(Protocol):
    async def lookup(self, warranty_code: str) -> Optional[dict]: ...


class DispatchProvider(Protocol):
    async def notify(self, load_number: str, delay_hours: int, reason: str) -> dict: ...
    simulated: bool


class FixtureShopProvider:
    async def search(self, needs_def_pump: bool, max_distance: float = 25) -> list[dict]:
        return shop_db.search_shops(needs_def_pump=needs_def_pump, max_distance=max_distance)

    async def best(
        self, shops: list[dict], needs_def_pump: bool, hos_hours_remaining: Optional[float] = None
    ) -> Optional[dict]:
        return shop_db.get_best_shop(shops, needs_def_pump=needs_def_pump, hos_hours_remaining=hos_hours_remaining)

    async def search_ranked(
        self, needs_def_pump: bool, max_distance: float = 25,
        geo_key: str = "unknown", hos_hours_remaining: Optional[float] = None,
    ) -> tuple[list[dict], Optional[dict]]:
        """Geo-hash-cached search+rank in one call (hot path). Falls back to
        plain search+best when the cache misses or errors."""
        return shop_db.search_shops_cached(
            needs_def_pump=needs_def_pump, max_distance=max_distance,
            geo_key=geo_key, hos_hours_remaining=hos_hours_remaining,
        )


class FixtureWarrantyProvider:
    async def lookup(self, warranty_code: str) -> Optional[dict]:
        return warranty_db.lookup_warranty_cached(warranty_code)


class FixtureDispatchProvider:
    """No real TMS integration exists yet — this provider is explicitly simulated and
    says so in every result, so the SSE audit trail never asserts an action that didn't
    happen (see P2-1 in the audit)."""

    simulated = True

    async def notify(self, load_number: str, delay_hours: int, reason: str) -> dict:
        return {
            "load_number": load_number,
            "status": "DELAYED",
            "delay_estimate_hours": delay_hours,
            "reason": reason,
            "notified": True,
            "simulated": True,
        }


def get_shop_provider() -> ShopProvider:
    return FixtureShopProvider()


def get_warranty_provider() -> WarrantyProvider:
    return FixtureWarrantyProvider()


def get_dispatch_provider() -> DispatchProvider:
    return FixtureDispatchProvider()
