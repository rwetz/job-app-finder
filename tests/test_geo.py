import asyncio
from pathlib import Path

import httpx

from job_app_finder.db.database import init_db
from job_app_finder.geo import geocode, haversine_miles, location_tier, nearest_anchor_distance
from job_app_finder.models import Anchor

FARGO = Anchor(name="Fargo, ND", zip="58102", lat=46.8772, lon=-96.7898)
ROCHESTER = Anchor(name="Rochester, MN", zip="55901", lat=44.0234, lon=-92.4630)
ANCHORS = [FARGO, ROCHESTER]
TIERS = {"tier_0_max_miles": 60, "tier_1_max_miles": 150}


def test_haversine_fargo_to_rochester_is_roughly_right():
    dist = haversine_miles(FARGO.lat, FARGO.lon, ROCHESTER.lat, ROCHESTER.lon)
    assert 250 < dist < 320


def test_nearest_anchor_distance_picks_closer_anchor():
    # A point essentially on top of Fargo.
    dist = nearest_anchor_distance(46.88, -96.79, ANCHORS)
    assert dist < 5


def test_location_tier_0_for_on_site_near_anchor():
    assert location_tier(is_remote=False, distance_miles=10, tiers=TIERS) == 0


def test_location_tier_1_for_regional_band():
    assert location_tier(is_remote=False, distance_miles=100, tiers=TIERS) == 1


def test_location_tier_2_for_remote_far_away():
    assert location_tier(is_remote=True, distance_miles=900, tiers=TIERS) == 2


def test_location_tier_3_for_far_on_site():
    assert location_tier(is_remote=False, distance_miles=900, tiers=TIERS) == 3


def test_location_tier_unknown_location_remote_is_tier_2():
    assert location_tier(is_remote=True, distance_miles=None, tiers=TIERS) == 2


def test_location_tier_unknown_location_on_site_is_tier_3():
    assert location_tier(is_remote=False, distance_miles=None, tiers=TIERS) == 3


def test_geocode_falls_back_to_nominatim_and_caches(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=[{"lat": "44.02", "lon": "-92.46"}])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        coords = asyncio.run(geocode("Rochester, MN", conn, client))
        assert coords == (44.02, -92.46)
        assert len(calls) == 1

        # Second call should hit the cache, not the network.
        coords_again = asyncio.run(geocode("Rochester, MN", conn, client))
        assert coords_again == (44.02, -92.46)
        assert len(calls) == 1
    finally:
        asyncio.run(client.aclose())


def test_geocode_returns_none_for_empty_location(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    try:
        assert asyncio.run(geocode(None, conn, client)) is None
        assert asyncio.run(geocode("", conn, client)) is None
    finally:
        asyncio.run(client.aclose())
