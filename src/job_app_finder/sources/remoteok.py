"""RemoteOK API adapter. Docs: https://remoteok.com/api

Free, no auth, but requires a real User-Agent or requests get blocked. The
first array element is a legal/metadata notice, not a job — skip it. Feeds
tier 2 (remote). RemoteOK's tag-based search doesn't map cleanly onto free-text
seed queries, so we pull the full feed once per run and filter client-side by
title against a tech/CS/AI-ML signal list — otherwise every non-tech RemoteOK
posting (marketing, sales, support, ...) lands in the DB unfiltered.
"""

from datetime import datetime, timezone

import httpx

from job_app_finder.models import Anchor, Posting
from job_app_finder.sources.base import AdapterMeta, SourceAdapter, register
from job_app_finder.sources.http import new_client
from job_app_finder.sources.relevance import is_tech_relevant


BASE_URL = "https://remoteok.com/api"
USER_AGENT = "job-app-finder/0.1 (personal use; single-user local app)"


def _normalize(raw: dict, fetched_at: str) -> Posting | None:
    external_id = raw.get("id")
    title = raw.get("position")
    url = raw.get("url")
    company = raw.get("company")
    if not (external_id and title and url and company):
        return None

    return Posting(
        source="remoteok",
        external_id=str(external_id),
        title=title,
        company=company,
        location_raw=raw.get("location"),
        lat=None,
        lon=None,
        is_remote=True,
        url=url,
        description=raw.get("description"),
        posted_at=raw.get("date"),
        fetched_at=fetched_at,
    )


class RemoteOkAdapter(SourceAdapter):
    meta = AdapterMeta(name="remoteok", kind="board", priority=5)

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def fetch(self, queries: list[str], anchors: list[Anchor]) -> list[Posting]:
        fetched_at = datetime.now(timezone.utc).isoformat()
        postings: list[Posting] = []
        client = self._client or new_client(headers={"User-Agent": USER_AGENT})
        owns_client = self._client is None
        try:
            resp = await client.get(BASE_URL, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            for raw in resp.json()[1:]:  # skip the leading legal-notice object
                if not is_tech_relevant(raw.get("position")):
                    continue
                posting = _normalize(raw, fetched_at)
                if posting:
                    postings.append(posting)
        finally:
            if owns_client:
                await client.aclose()
        return postings


register(RemoteOkAdapter())
