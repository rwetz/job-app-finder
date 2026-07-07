"""Greenhouse Job Board API adapter. Docs: https://developers.greenhouse.io/job-board.html

Public per-company JSON, no auth. Company tokens come from `companies.yaml`.
"""

from datetime import datetime, timezone

import httpx

from job_app_finder.config import load_companies
from job_app_finder.models import Anchor, Posting
from job_app_finder.sources.base import AdapterMeta, SourceAdapter, register
from job_app_finder.sources.http import new_client

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def _normalize(raw: dict, company_name: str, fetched_at: str) -> Posting | None:
    external_id = raw.get("id")
    title = raw.get("title")
    url = raw.get("absolute_url")
    if not (external_id and title and url):
        return None

    location = (raw.get("location") or {}).get("name")
    return Posting(
        source="greenhouse",
        external_id=str(external_id),
        title=title,
        company=company_name,
        location_raw=location,
        lat=None,
        lon=None,
        is_remote="remote" in (location or "").lower(),
        url=url,
        description=raw.get("content"),
        posted_at=raw.get("updated_at"),
        fetched_at=fetched_at,
    )


class GreenhouseAdapter(SourceAdapter):
    meta = AdapterMeta(name="greenhouse", kind="ats", priority=7)

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, queries: list[str], anchors: list[Anchor]) -> list[Posting]:
        companies = load_companies().get("greenhouse") or []
        if not companies:
            return []

        fetched_at = datetime.now(timezone.utc).isoformat()
        postings: list[Posting] = []
        client = self._client or new_client()
        owns_client = self._client is None
        try:
            for entry in companies:
                token = entry["token"]
                company_name = entry.get("name", token)
                resp = await client.get(BASE_URL.format(token=token), params={"content": "true"})
                resp.raise_for_status()
                for raw in resp.json().get("jobs", []):
                    posting = _normalize(raw, company_name, fetched_at)
                    if posting:
                        postings.append(posting)
        finally:
            if owns_client:
                await client.aclose()
        return postings


register(GreenhouseAdapter())
