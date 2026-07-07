import httpx
import pytest

from job_app_finder.models import Anchor
from job_app_finder.sources.adzuna import AdzunaAdapter
from job_app_finder.sources.jsearch import JSearchAdapter
from job_app_finder.sources.usajobs import UsaJobsAdapter

FARGO = Anchor(name="Fargo, ND", zip="58102", lat=46.8772, lon=-96.7898)


@pytest.fixture
def anchors():
    return [FARGO]


@pytest.fixture
def queries():
    return ["software engineering intern"]


async def _drain(coro):
    return await coro


def test_adzuna_normalizes_and_dedupes_across_anchors(anchors, queries, monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "123",
                        "title": "Software Engineering Intern",
                        "company": {"display_name": "Acme"},
                        "location": {"display_name": "Fargo, ND"},
                        "redirect_url": "https://jobs.adzuna.com/123",
                        "created": "2026-07-01T00:00:00Z",
                        "description": "desc",
                        "latitude": 46.87,
                        "longitude": -96.78,
                    },
                    {"id": "missing-fields"},
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = AdzunaAdapter(client=client)
    import asyncio

    postings = asyncio.run(adapter.fetch(queries, anchors))
    assert len(postings) == 1
    assert postings[0].source == "adzuna"
    assert postings[0].company == "Acme"
    asyncio.run(client.aclose())


def test_adzuna_returns_empty_without_credentials(anchors, queries, monkeypatch):
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    import asyncio

    adapter = AdzunaAdapter()
    assert asyncio.run(adapter.fetch(queries, anchors)) == []


def test_jsearch_normalizes(anchors, queries, monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "jobs": [
                        {
                            "job_id": "abc",
                            "job_title": "Data Science Intern",
                            "employer_name": "Beta Corp",
                            "job_city": "Rochester",
                            "job_state": "MN",
                            "job_is_remote": False,
                            "job_apply_link": "https://jobs.example.com/abc",
                            "job_posted_at_datetime_utc": "2026-07-02T00:00:00Z",
                            "job_description": "desc",
                        }
                    ]
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = JSearchAdapter(client=client)
    import asyncio

    postings = asyncio.run(adapter.fetch(queries, anchors))
    assert len(postings) > 0
    assert postings[0].location_raw == "Rochester, MN"
    asyncio.run(client.aclose())


def test_usajobs_normalizes(anchors, queries, monkeypatch):
    monkeypatch.setenv("USAJOBS_API_KEY", "key")
    monkeypatch.setenv("USAJOBS_USER_AGENT", "me@example.com")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "SearchResult": {
                    "SearchResultItems": [
                        {
                            "MatchedObjectDescriptor": {
                                "PositionID": "XYZ",
                                "PositionTitle": "IT Intern",
                                "OrganizationName": "USDA",
                                "PositionLocationDisplay": "Fargo, North Dakota",
                                "PositionURI": "https://usajobs.gov/XYZ",
                                "PublicationStartDate": "2026-07-01",
                                "PositionLocation": [{"Latitude": 46.87, "Longitude": -96.78}],
                                "UserArea": {"Details": {"JobSummary": "summary"}},
                            }
                        }
                    ]
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = UsaJobsAdapter(client=client)
    import asyncio

    postings = asyncio.run(adapter.fetch(queries, anchors))
    assert len(postings) == 1
    assert postings[0].lat == 46.87
    asyncio.run(client.aclose())
