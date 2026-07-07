"""Lever Postings API adapter. Docs: https://github.com/lever/postings-api

Public per-company JSON, no auth. Company handles come from `companies.yaml`.
"""

from datetime import datetime, timezone

import httpx

from job_app_finder.config import load_companies
from job_app_finder.models import Anchor, Posting
from job_app_finder.sources.base import AdapterMeta, SourceAdapter, register
from job_app_finder.sources.http import new_client

BASE_URL = "https://api.lever.co/v0/postings/{handle}"


def _normalize(raw: dict, company_name: str, fetched_at: str) -> Posting | None:
    external_id = raw.get("id")
    title = raw.get("text")
    url = raw.get("hostedUrl") or raw.get("applyUrl")
    if not (external_id and title and url):
        return None

    location = (raw.get("categories") or {}).get("location")
    created_ms = raw.get("createdAt")
    posted_at = (
        datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc).isoformat() if created_ms else None
    )

    return Posting(
        source="lever",
        external_id=str(external_id),
        title=title,
        company=company_name,
        location_raw=location,
        lat=None,
        lon=None,
        is_remote="remote" in (location or "").lower(),
        url=url,
        description=raw.get("descriptionPlain"),
        posted_at=posted_at,
        fetched_at=fetched_at,
    )


class LeverAdapter(SourceAdapter):
    meta = AdapterMeta(name="lever", kind="ats", priority=7)

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, queries: list[str], anchors: list[Anchor]) -> list[Posting]:
        companies = load_companies().get("lever") or []
        if not companies:
            return []

        fetched_at = datetime.now(timezone.utc).isoformat()
        postings: list[Posting] = []
        client = self._client or new_client()
        owns_client = self._client is None
        try:
            for entry in companies:
                handle = entry["handle"]
                company_name = entry.get("name", handle)
                resp = await client.get(BASE_URL.format(handle=handle), params={"mode": "json"})
                resp.raise_for_status()
                for raw in resp.json():
                    posting = _normalize(raw, company_name, fetched_at)
                    if posting:
                        postings.append(posting)
        finally:
            if owns_client:
                await client.aclose()
        return postings


register(LeverAdapter())
