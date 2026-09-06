# backend/geocode.py
"""Static city -> coordinates lookup for the fixture data layer.

Replaces the old hardcoded "always Columbus, OH" behavior. This is still a fixture
(no live geocoding API call), but it at least reflects what the driver actually said
instead of silently attaching Ohio coordinates to every city name. A real deployment
swaps this for the vehicle's own telematics GPS fix or a geocoding provider — see
backend/providers.py for the same fixture-vs-real-provider pattern applied elsewhere.
"""
from typing import Optional

_CITY_COORDS: dict[str, tuple[float, float]] = {
    "columbus, oh": (39.96, -82.99),
    "columbus": (39.96, -82.99),
    "phoenix": (33.45, -112.07),
    "phoenix, az": (33.45, -112.07),
    "dallas": (32.78, -96.80),
    "dallas, tx": (32.78, -96.80),
    "atlanta": (33.75, -84.39),
    "atlanta, ga": (33.75, -84.39),
    "chicago": (41.88, -87.63),
    "chicago, il": (41.88, -87.63),
    "denver": (39.74, -104.99),
    "denver, co": (39.74, -104.99),
    "los angeles": (34.05, -118.24),
    "los angeles, ca": (34.05, -118.24),
    "indianapolis": (39.77, -86.16),
    "indianapolis, in": (39.77, -86.16),
    "memphis": (35.15, -90.05),
    "memphis, tn": (35.15, -90.05),
    "nashville": (36.16, -86.78),
    "nashville, tn": (36.16, -86.78),
    "kansas city": (39.10, -94.58),
    "kansas city, mo": (39.10, -94.58),
    "st. louis": (38.63, -90.20),
    "st louis": (38.63, -90.20),
    "louisville": (38.25, -85.76),
    "louisville, ky": (38.25, -85.76),
    "cincinnati": (39.10, -84.51),
    "cincinnati, oh": (39.10, -84.51),
    "cleveland": (41.50, -81.69),
    "cleveland, oh": (41.50, -81.69),
    "pittsburgh": (40.44, -79.99),
    "pittsburgh, pa": (40.44, -79.99),
}

_DEFAULT_CITY = "Columbus, OH"
_DEFAULT_COORDS = _CITY_COORDS["columbus, oh"]


def geocode_city(city: str) -> Optional[dict]:
    """Look up known coordinates for a city string. Returns None if unrecognized —
    callers decide whether that's a clarifying question (non-demo) or a labeled
    fallback (demo)."""
    coords = _CITY_COORDS.get(city.strip().lower())
    if coords is None:
        return None
    lat, lon = coords
    return {"lat": lat, "lon": lon, "city": city}


def default_location() -> dict:
    lat, lon = _DEFAULT_COORDS
    return {"lat": lat, "lon": lon, "city": _DEFAULT_CITY}
