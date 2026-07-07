import asyncio

import httpx
import pytest

from job_app_finder.models import Anchor
from job_app_finder.sources.greenhouse import GreenhouseAdapter
from job_app_finder.sources.lever import LeverAdapter
from job_app_finder.sources.remoteok import RemoteOkAdapter
from job_app_finder.sources.remotive import RemotiveAdapter
from job_app_finder.sources.workday import WorkdayAdapter

FARGO = Anchor(name="Fargo, ND", zip="58102", lat=46.8772, lon=-96.7898)


@pytest.fixture
def anchors():
    return [FARGO]


@pytest.fixture
def queries():
    return ["software engineering intern"]


def _write_companies_yaml(tmp_path, content):
    path = tmp_path / "companies.yaml"
    path.write_text(content)
    return path


def test_greenhouse_normalizes_and_skips_companies_without_entries(anchors, queries, tmp_path, monkeypatch):
    path = _write_companies_yaml(tmp_path, "greenhouse:\n  - token: acme\n    name: Acme Co\n")
    monkeypatch.setattr("job_app_finder.sources.greenhouse.load_companies", lambda: __import__("yaml").safe_load(path.read_text()))

    def handler(request: httpx.Request) -> httpx.Response:
        assert "boards-api.greenhouse.io/v1/boards/acme/jobs" in str(request.url)
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 1,
                        "title": "Intern",
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                        "location": {"name": "Fargo, ND"},
                        "content": "desc",
                        "updated_at": "2026-07-01T00:00:00Z",
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GreenhouseAdapter(client=client)
    postings = asyncio.run(adapter.fetch(queries, anchors))
    assert len(postings) == 1
    assert postings[0].company == "Acme Co"
    asyncio.run(client.aclose())


def test_greenhouse_returns_empty_with_no_companies(anchors, queries, tmp_path, monkeypatch):
    path = _write_companies_yaml(tmp_path, "greenhouse: []\n")
    monkeypatch.setattr("job_app_finder.sources.greenhouse.load_companies", lambda: __import__("yaml").safe_load(path.read_text()))
    adapter = GreenhouseAdapter()
    assert asyncio.run(adapter.fetch(queries, anchors)) == []


def test_lever_normalizes(anchors, queries, tmp_path, monkeypatch):
    path = _write_companies_yaml(tmp_path, "lever:\n  - handle: beta\n    name: Beta Inc\n")
    monkeypatch.setattr("job_app_finder.sources.lever.load_companies", lambda: __import__("yaml").safe_load(path.read_text()))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": "abc",
                    "text": "Backend Intern",
                    "categories": {"location": "Remote"},
                    "hostedUrl": "https://jobs.lever.co/beta/abc",
                    "createdAt": 1751328000000,
                    "descriptionPlain": "desc",
                }
            ],
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = LeverAdapter(client=client)
    postings = asyncio.run(adapter.fetch(queries, anchors))
    assert len(postings) == 1
    assert postings[0].is_remote is True
    asyncio.run(client.aclose())


def test_workday_normalizes(anchors, queries, tmp_path, monkeypatch):
    path = _write_companies_yaml(
        tmp_path, "workday:\n  - tenant: gamma\n    site: gamma_careers\n    name: Gamma LLC\n"
    )
    monkeypatch.setattr("job_app_finder.sources.workday.load_companies", lambda: __import__("yaml").safe_load(path.read_text()))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={
                "jobPostings": [
                    {
                        "title": "QA Intern",
                        "externalPath": "/job/QA-Intern_R-001",
                        "locationsText": "Fargo, ND",
                        "postedOn": "Posted 3 Days Ago",
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = WorkdayAdapter(client=client)
    postings = asyncio.run(adapter.fetch(queries, anchors))
    assert len(postings) == 1
    assert postings[0].url == "https://gamma.wd1.myworkdayjobs.com/gamma_careers/job/QA-Intern_R-001"
    asyncio.run(client.aclose())


def test_remotive_normalizes(anchors, queries):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 5,
                        "title": "Remote Software Engineer Intern",
                        "company_name": "Delta",
                        "url": "https://remotive.com/jobs/5",
                        "candidate_required_location": "USA",
                        "publication_date": "2026-07-01T00:00:00",
                        "description": "Build backend services in Python",
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RemotiveAdapter(client=client)
    postings = asyncio.run(adapter.fetch(queries, anchors))
    assert len(postings) == 1
    assert postings[0].is_remote is True
    asyncio.run(client.aclose())


def test_remotive_filters_out_non_tech_postings(anchors, queries):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 5,
                        "title": "Remote Software Engineer Intern",
                        "company_name": "Delta",
                        "url": "https://remotive.com/jobs/5",
                        "candidate_required_location": "USA",
                        "publication_date": "2026-07-01T00:00:00",
                        "description": "Build backend services in Python",
                    },
                    {
                        "id": 6,
                        "title": "Senior Product Manager",
                        "company_name": "Epsilon",
                        "url": "https://remotive.com/jobs/6",
                        "candidate_required_location": "USA",
                        "publication_date": "2026-07-01T00:00:00",
                        "description": "Own the product roadmap and stakeholder communication",
                    },
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RemotiveAdapter(client=client)
    postings = asyncio.run(adapter.fetch(queries, anchors))
    assert [p.title for p in postings] == ["Remote Software Engineer Intern"]
    asyncio.run(client.aclose())


def test_remoteok_skips_leading_legal_notice(anchors, queries):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"legal": "some notice"},
                {
                    "id": "9",
                    "position": "Remote Dev Intern",
                    "company": "Epsilon",
                    "url": "https://remoteok.com/remote-jobs/9",
                    "location": "Worldwide",
                    "date": "2026-07-01T00:00:00",
                    "description": "desc",
                },
            ],
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RemoteOkAdapter(client=client)
    postings = asyncio.run(adapter.fetch(queries, anchors))
    assert len(postings) == 1
    assert postings[0].company == "Epsilon"
    asyncio.run(client.aclose())


def test_remoteok_filters_out_non_tech_postings(anchors, queries):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"legal": "some notice"},
                {
                    "id": "1",
                    "position": "Software Engineer",
                    "company": "Acme",
                    "url": "https://remoteok.com/remote-jobs/1",
                    "location": "Worldwide",
                    "date": "2026-07-01T00:00:00",
                    "description": "Build backend systems in Python",
                    "tags": ["python", "backend"],
                },
                {
                    "id": "2",
                    "position": "Social Media Coordinator",
                    "company": "Beta",
                    "url": "https://remoteok.com/remote-jobs/2",
                    "location": "Worldwide",
                    "date": "2026-07-01T00:00:00",
                    "description": "Manage our Instagram and TikTok presence",
                    "tags": ["marketing", "social"],
                },
            ],
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = RemoteOkAdapter(client=client)
    postings = asyncio.run(adapter.fetch(queries, anchors))
    assert [p.title for p in postings] == ["Software Engineer"]
    asyncio.run(client.aclose())
