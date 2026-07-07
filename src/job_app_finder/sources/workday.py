"""Workday CxS adapter — public `/wday/cxs/{tenant}/{site}/jobs` JSON search
used by many large employers' careers sites. Per-tenant config in `companies.yaml`.

Note: the list endpoint doesn't include a full description (detail requires a
separate per-posting call, skipped for now) and `postedOn` is relative text
("Posted 3 Days Ago"), not an ISO date — best-effort only.
"""

from datetime import datetime, timezone

import httpx

from job_app_finder.config import load_companies
from job_app_finder.models import Anchor, Posting
from job_app_finder.sources.base import AdapterMeta, SourceAdapter, register
from job_app_finder.sources.http import new_client

PAGE_SIZE = 20


def _normalize(raw: dict, company_name: str, base_url: str, site: str, fetched_at: str) -> Posting | None:
    external_path = raw.get("externalPath")
    title = raw.get("title")
    if not (external_path and title):
        return None

    location = raw.get("locationsText")
    return Posting(
        source="workday",
        external_id=external_path,
        title=title,
        company=company_name,
        location_raw=location,
        lat=None,
        lon=None,
        is_remote="remote" in (location or "").lower(),
        url=f"{base_url}/{site}{external_path}",
        description=None,
        posted_at=raw.get("postedOn"),
        fetched_at=fetched_at,
    )


class WorkdayAdapter(SourceAdapter):
    meta = AdapterMeta(name="workday", kind="ats", priority=7)

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, queries: list[str], anchors: list[Anchor]) -> list[Posting]:
        companies = load_companies().get("workday") or []
        if not companies:
            return []

        fetched_at = datetime.now(timezone.utc).isoformat()
        postings: list[Posting] = []
        client = self._client or new_client()
        owns_client = self._client is None
        try:
            for entry in companies:
                tenant = entry["tenant"]
                site = entry["site"]
                host = entry.get("host", "wd1")
                company_name = entry.get("name", tenant)
                base_url = f"https://{tenant}.{host}.myworkdayjobs.com"
                jobs_url = f"{base_url}/wday/cxs/{tenant}/{site}/jobs"

                for query in queries or [""]:
                    body = {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": 0, "searchText": query}
                    resp = await client.post(jobs_url, json=body)
                    resp.raise_for_status()
                    for raw in resp.json().get("jobPostings", []):
                        posting = _normalize(raw, company_name, base_url, site, fetched_at)
                        if posting:
                            postings.append(posting)
        finally:
            if owns_client:
                await client.aclose()
        return postings


register(WorkdayAdapter())
