"""JSearch (RapidAPI) adapter — compliant aggregator covering LinkedIn/Indeed/
Glassdoor/ZipRecruiter listings. Docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch

Uses /search-v2 (not /search — that path returns a gateway 404 on this
listing as of 2026-07; the provider versioned the endpoint at some point).
Response shape is nested one level deeper than the old /search: jobs live at
`data.jobs[]`, not `data[]`.
"""

from datetime import datetime, timezone

import httpx

from job_app_finder.config import get_env
from job_app_finder.models import Anchor, Posting
from job_app_finder.sources.base import AdapterMeta, SourceAdapter, register
from job_app_finder.sources.http import new_client

BASE_URL = "https://jsearch.p.rapidapi.com/search-v2"
API_HOST = "jsearch.p.rapidapi.com"


def _normalize(raw: dict, fetched_at: str) -> Posting | None:
    external_id = raw.get("job_id")
    url = raw.get("job_apply_link") or raw.get("job_google_link")
    title = raw.get("job_title")
    company = raw.get("employer_name")
    if not (external_id and url and title and company):
        return None

    city = raw.get("job_city")
    state = raw.get("job_state")
    location_raw = ", ".join(part for part in (city, state) if part) or raw.get("job_country")

    return Posting(
        source="jsearch",
        external_id=str(external_id),
        title=title,
        company=company,
        location_raw=location_raw,
        lat=raw.get("job_latitude"),
        lon=raw.get("job_longitude"),
        is_remote=bool(raw.get("job_is_remote")),
        url=url,
        description=raw.get("job_description"),
        posted_at=raw.get("job_posted_at_datetime_utc"),
        fetched_at=fetched_at,
    )


class JSearchAdapter(SourceAdapter):
    meta = AdapterMeta(name="jsearch", kind="aggregator", priority=9)

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, queries: list[str], anchors: list[Anchor]) -> list[Posting]:
        api_key = get_env("RAPIDAPI_KEY")
        if not api_key:
            return []

        fetched_at = datetime.now(timezone.utc).isoformat()
        headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": API_HOST}
        postings: list[Posting] = []
        client = self._client or new_client(headers=headers)
        owns_client = self._client is None
        try:
            # One query per anchor (geo-scoped) plus one remote-scoped query per seed term.
            search_terms = [f"{query} in {anchor.name}" for anchor in anchors for query in queries]
            search_terms += [f"{query} remote" for query in queries]

            for term in search_terms:
                params = {"query": term, "num_pages": "1", "country": "us"}
                resp = await client.get(BASE_URL, params=params, headers=headers)
                resp.raise_for_status()
                jobs = resp.json().get("data", {}).get("jobs", [])
                for raw in jobs:
                    posting = _normalize(raw, fetched_at)
                    if posting:
                        postings.append(posting)
        finally:
            if owns_client:
                await client.aclose()
        return postings


register(JSearchAdapter())
