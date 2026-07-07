"""Geocoding and location-tier classification.

Geocoding tries, in order: DB cache -> offline uszipcode dataset (5-digit US
zips, `geo` extra) -> Nominatim (OpenStreetMap) as a network fallback for
freeform "City, State" strings. Results are cached in `geocode_cache` so a
refresh doesn't re-hit Nominatim for locations already seen.
"""

import asyncio
import functools
import math
import re
import sqlite3
import time
from datetime import datetime, timezone

import httpx

from job_app_finder.models import Anchor
from job_app_finder.sources.http import new_client

EARTH_RADIUS_MILES = 3958.8
_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_MIN_INTERVAL_SECONDS = 1.0  # OSM Nominatim usage policy: max 1 req/sec
_NOMINATIM_USER_AGENT = "job-app-finder/0.1 (personal use; single-user local app)"

_nominatim_lock = asyncio.Lock()
_last_nominatim_call = 0.0


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def nearest_anchor_distance(lat: float, lon: float, anchors: list[Anchor]) -> float:
    return min(haversine_miles(lat, lon, a.lat, a.lon) for a in anchors)


def location_tier(is_remote: bool, distance_miles: float | None, tiers: dict) -> int:
    """0/1 = on-site near an anchor, 2 = remote, 3 = far on-site or unknown location."""
    if distance_miles is not None:
        if distance_miles <= tiers["tier_0_max_miles"]:
            return 0
        if distance_miles <= tiers["tier_1_max_miles"]:
            return 1
    return 2 if is_remote else 3


@functools.lru_cache(maxsize=1)
def _search_engine():
    from uszipcode import SearchEngine  # optional `geo` extra

    return SearchEngine()


def _geocode_zip(zip_code: str) -> tuple[float, float] | None:
    try:
        engine = _search_engine()
    except ImportError:
        return None
    result = engine.by_zipcode(zip_code)
    if result and result.lat is not None and result.lng is not None:
        return float(result.lat), float(result.lng)
    return None


async def _geocode_nominatim(query: str, client: httpx.AsyncClient) -> tuple[float, float] | None:
    global _last_nominatim_call
    async with _nominatim_lock:
        elapsed = time.monotonic() - _last_nominatim_call
        if elapsed < _NOMINATIM_MIN_INTERVAL_SECONDS:
            await asyncio.sleep(_NOMINATIM_MIN_INTERVAL_SECONDS - elapsed)
        resp = await client.get(
            _NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": _NOMINATIM_USER_AGENT},
        )
        _last_nominatim_call = time.monotonic()
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


async def geocode(
    location_raw: str | None, conn: sqlite3.Connection, client: httpx.AsyncClient
) -> tuple[float, float] | None:
    if not location_raw:
        return None

    cached = conn.execute(
        "SELECT lat, lon FROM geocode_cache WHERE location_raw = ?", (location_raw,)
    ).fetchone()
    if cached:
        return (cached["lat"], cached["lon"]) if cached["lat"] is not None else None

    stripped = location_raw.strip()
    coords = _geocode_zip(stripped[:5]) if _ZIP_RE.match(stripped) else None
    if coords is None:
        coords = await _geocode_nominatim(location_raw, client)

    conn.execute(
        "INSERT OR REPLACE INTO geocode_cache (location_raw, lat, lon, resolved_at) VALUES (?, ?, ?, ?)",
        (
            location_raw,
            coords[0] if coords else None,
            coords[1] if coords else None,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return coords


async def geocode_and_tier_postings(
    conn: sqlite3.Connection, anchors: list[Anchor], tiers: dict
) -> int:
    """Backfill lat/lon (where missing) and location_tier for every posting missing a tier."""
    rows = conn.execute(
        "SELECT id, location_raw, lat, lon, is_remote FROM postings WHERE location_tier IS NULL"
    ).fetchall()
    updated = 0
    async with new_client() as client:
        for row in rows:
            lat, lon = row["lat"], row["lon"]
            if lat is None or lon is None:
                coords = await geocode(row["location_raw"], conn, client)
                if coords:
                    lat, lon = coords
            distance = (
                nearest_anchor_distance(lat, lon, anchors) if lat is not None and lon is not None else None
            )
            tier = location_tier(bool(row["is_remote"]), distance, tiers)
            conn.execute(
                "UPDATE postings SET lat = ?, lon = ?, location_tier = ? WHERE id = ?",
                (lat, lon, tier, row["id"]),
            )
            updated += 1
    conn.commit()
    return updated
