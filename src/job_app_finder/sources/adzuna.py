"""Adzuna Jobs API adapter. Docs: https://developer.adzuna.com/docs/search

Free app_id/app_key from https://developer.adzuna.com/. Geo radius search
(`where` + `distance`) is why this is the backbone breadth source.
"""

from datetime import datetime, timezone

import httpx

from job_app_finder.config import get_env
from job_app_finder.models import Anchor, Posting
from job_app_finder.sources.base import AdapterMeta, SourceAdapter, register
from job_app_finder.sources.http import new_client

BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search/1"
RESULTS_PER_PAGE = 50
SEARCH_RADIUS_MILES = 150  # covers tier 0 + tier 1; wider net = max coverage


def _normalize(raw: dict, fetched_at: str) -> Posting | None:
    external_id = str(raw.get("id", ""))
    url = raw.get("redirect_url")
    title = raw.get("title")
    company = (raw.get("company") or {}).get("display_name")
    if not (external_id and url and title and company):
        return None

    location = raw.get("location") or {}
    return Posting(
        source="adzuna",
        external_id=external_id,
        title=title,
        company=company,
        location_raw=location.get("display_name"),
        lat=raw.get("latitude"),
        lon=raw.get("longitude"),
        is_remote=False,  # Adzuna's radius search is inherently on-site/local
        url=url,
        description=raw.get("description"),
        posted_at=raw.get("created"),
        fetched_at=fetched_at,
    )


class AdzunaAdapter(SourceAdapter):
    meta = AdapterMeta(name="adzuna", kind="aggregator", priority=10)

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, queries: list[str], anchors: list[Anchor]) -> list[Posting]:
        app_id = get_env("ADZUNA_APP_ID")
        app_key = get_env("ADZUNA_APP_KEY")
        if not (app_id and app_key):
            return []

        fetched_at = datetime.now(timezone.utc).isoformat()
        postings: list[Posting] = []
        client = self._client or new_client()
        owns_client = self._client is None
        try:
            for anchor in anchors:
                for query in queries:
                    params = {
                        "app_id": app_id,
                        "app_key": app_key,
                        "what": query,
                        "where": anchor.name,
                        "distance": SEARCH_RADIUS_MILES,
                        "results_per_page": RESULTS_PER_PAGE,
                        "content-type": "application/json",
                    }
                    resp = await client.get(BASE_URL, params=params)
                    resp.raise_for_status()
                    for raw in resp.json().get("results", []):
                        posting = _normalize(raw, fetched_at)
                        if posting:
                            postings.append(posting)
        finally:
            if owns_client:
                await client.aclose()
        return postings


register(AdzunaAdapter())
