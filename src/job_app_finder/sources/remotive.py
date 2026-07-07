"""Remotive remote-jobs API adapter. Docs: https://remotive.com/api-documentation

Free, no auth. Feeds tier 2 (remote). Remotive's own `search=` scoping still
lets non-tech roles through (loose full-text match), so results also pass
through the shared tech/CS/AI-ML relevance filter.
"""

from datetime import datetime, timezone

import httpx

from job_app_finder.models import Anchor, Posting
from job_app_finder.sources.base import AdapterMeta, SourceAdapter, register
from job_app_finder.sources.http import new_client
from job_app_finder.sources.relevance import is_tech_relevant

BASE_URL = "https://remotive.com/api/remote-jobs"


def _normalize(raw: dict, fetched_at: str) -> Posting | None:
    external_id = raw.get("id")
    title = raw.get("title")
    url = raw.get("url")
    company = raw.get("company_name")
    if not (external_id and title and url and company):
        return None

    return Posting(
        source="remotive",
        external_id=str(external_id),
        title=title,
        company=company,
        location_raw=raw.get("candidate_required_location"),
        lat=None,
        lon=None,
        is_remote=True,
        url=url,
        description=raw.get("description"),
        posted_at=raw.get("publication_date"),
        fetched_at=fetched_at,
    )


class RemotiveAdapter(SourceAdapter):
    meta = AdapterMeta(name="remotive", kind="board", priority=5)

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, queries: list[str], anchors: list[Anchor]) -> list[Posting]:
        fetched_at = datetime.now(timezone.utc).isoformat()
        postings: list[Posting] = []
        client = self._client or new_client()
        owns_client = self._client is None
        try:
            for query in queries:
                resp = await client.get(BASE_URL, params={"search": query})
                resp.raise_for_status()
                for raw in resp.json().get("jobs", []):
                    if not is_tech_relevant(raw.get("title")):
                        continue
                    posting = _normalize(raw, fetched_at)
                    if posting:
                        postings.append(posting)
        finally:
            if owns_client:
                await client.aclose()
        return postings


register(RemotiveAdapter())
