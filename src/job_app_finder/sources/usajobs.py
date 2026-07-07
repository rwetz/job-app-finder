"""USAJobs API adapter — free federal-jobs aggregator with geo radius search.
Docs: https://developer.usajobs.gov/api-reference/get-api-search
"""

from datetime import datetime, timezone

import httpx

from job_app_finder.config import get_env
from job_app_finder.models import Anchor, Posting
from job_app_finder.sources.base import AdapterMeta, SourceAdapter, register
from job_app_finder.sources.http import new_client

BASE_URL = "https://data.usajobs.gov/api/search"
SEARCH_RADIUS_MILES = 150


def _normalize(raw: dict, fetched_at: str) -> Posting | None:
    descriptor = raw.get("MatchedObjectDescriptor", {})
    external_id = descriptor.get("PositionID")
    url = descriptor.get("PositionURI")
    title = descriptor.get("PositionTitle")
    company = descriptor.get("OrganizationName")
    if not (external_id and url and title and company):
        return None

    locations = descriptor.get("PositionLocation") or []
    lat = locations[0].get("Latitude") if locations else None
    lon = locations[0].get("Longitude") if locations else None
    location_raw = descriptor.get("PositionLocationDisplay")
    description = ((descriptor.get("UserArea") or {}).get("Details") or {}).get("JobSummary")

    return Posting(
        source="usajobs",
        external_id=str(external_id),
        title=title,
        company=company,
        location_raw=location_raw,
        lat=lat,
        lon=lon,
        is_remote="remote" in (location_raw or "").lower(),
        url=url,
        description=description,
        posted_at=descriptor.get("PublicationStartDate"),
        fetched_at=fetched_at,
    )


class UsaJobsAdapter(SourceAdapter):
    meta = AdapterMeta(name="usajobs", kind="aggregator", priority=8)

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, queries: list[str], anchors: list[Anchor]) -> list[Posting]:
        api_key = get_env("USAJOBS_API_KEY")
        user_agent = get_env("USAJOBS_USER_AGENT")
        if not (api_key and user_agent):
            return []

        fetched_at = datetime.now(timezone.utc).isoformat()
        headers = {
            "Host": "data.usajobs.gov",
            "User-Agent": user_agent,
            "Authorization-Key": api_key,
        }
        postings: list[Posting] = []
        client = self._client or new_client(headers=headers)
        owns_client = self._client is None
        try:
            for anchor in anchors:
                for query in queries:
                    params = {
                        "Keyword": query,
                        "LocationName": anchor.name,
                        "Radius": SEARCH_RADIUS_MILES,
                        "ResultsPerPage": 500,
                    }
                    resp = await client.get(BASE_URL, params=params, headers=headers)
                    resp.raise_for_status()
                    items = resp.json().get("SearchResult", {}).get("SearchResultItems", [])
                    for raw in items:
                        posting = _normalize(raw, fetched_at)
                        if posting:
                            postings.append(posting)
        finally:
            if owns_client:
                await client.aclose()
        return postings


register(UsaJobsAdapter())
