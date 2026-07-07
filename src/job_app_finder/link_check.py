"""Active liveness probe for posting URLs.

Supplements the passive "didn't reappear in a refresh" staleness signal
(db.postings_repo.mark_stale_not_seen_since) with a direct HTTP check. That
passive signal only works for sources that return a full current listing on
every fetch (Greenhouse/Lever/Workday, Remotive/RemoteOK) — a job pulled from
a search-based aggregator (Adzuna/JSearch/USAJobs) can vanish from results
just from ranking drift, not because it closed. Fetching the posting's own
URL and looking for a 404 or a "no longer accepting applications"-style page
works regardless of source.
"""

import asyncio
import re
import sqlite3
from datetime import datetime, timezone

import httpx

from job_app_finder.db.postings_repo import record_link_check_results
from job_app_finder.sources.http import new_client

DEFAULT_CONCURRENCY = 8

OFFLINE_STATUS_CODES = {404, 410}

# Phrases ATSes/boards show on a closed-job page, matched case-insensitively
# against the response body. Kept short and specific to avoid false
# positives on ordinary listing/search pages.
OFFLINE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"no longer (accepting applications|available)",
        r"position has (been filled|closed)",
        r"this job (posting )?has expired",
        r"job is closed",
        r"posting is no longer active",
        r"we('re| are) no longer accepting applications",
    ]
]


async def _check_one(client: httpx.AsyncClient, sem: asyncio.Semaphore, posting_id: int, url: str) -> tuple[int, bool]:
    async with sem:
        try:
            resp = await client.get(url, follow_redirects=True)
        except httpx.HTTPError:
            return posting_id, False  # a network hiccup isn't evidence the job is gone

    if resp.status_code in OFFLINE_STATUS_CODES:
        return posting_id, True
    if resp.status_code >= 400:
        return posting_id, False

    body = resp.text[:20000]  # closed-job banners render near the top
    return posting_id, any(pattern.search(body) for pattern in OFFLINE_PATTERNS)


async def check_posting_links(
    conn: sqlite3.Connection,
    candidates: list[sqlite3.Row],
    concurrency: int = DEFAULT_CONCURRENCY,
    client: httpx.AsyncClient | None = None,
) -> int:
    """Probe each candidate's URL and mark confirmed-offline postings stale.

    Returns how many postings were newly confirmed offline. `client` is
    exposed for tests to inject an httpx.MockTransport-backed client; the
    real ingest path always uses the default (a fresh new_client()).
    """
    if not candidates:
        return 0

    sem = asyncio.Semaphore(concurrency)
    owns_client = client is None
    client = client or new_client()
    try:
        results = await asyncio.gather(
            *(_check_one(client, sem, row["id"], row["url"]) for row in candidates)
        )
    finally:
        if owns_client:
            await client.aclose()

    checked_ids = [pid for pid, _ in results]
    offline_ids = [pid for pid, offline in results if offline]
    record_link_check_results(conn, checked_ids, offline_ids, datetime.now(timezone.utc).isoformat())
    return len(offline_ids)
