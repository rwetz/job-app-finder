import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from job_app_finder.db.database import init_db
from job_app_finder.db.postings_repo import get_link_check_candidates, upsert_postings
from job_app_finder.link_check import check_posting_links
from job_app_finder.models import Posting


def _posting(**overrides) -> Posting:
    base = dict(
        source="adzuna",
        external_id="1",
        title="Software Engineering Intern",
        company="Acme",
        location_raw="Fargo, ND",
        lat=46.8772,
        lon=-96.7898,
        is_remote=False,
        url="https://example.com/jobs/1",
        description="desc",
        posted_at="2026-07-01T00:00:00Z",
        fetched_at="2026-07-07T00:00:00Z",
    )
    base.update(overrides)
    return Posting(**base)


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "gone-404" in url:
        return httpx.Response(404)
    if "closed-text" in url:
        return httpx.Response(200, text="Sorry, this position has been filled.")
    if "network-error" in url:
        raise httpx.ConnectError("boom", request=request)
    return httpx.Response(200, text="<html>Great opportunity, apply now!</html>")


def _mock_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(_handler))


def test_confirms_offline_on_404(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    upsert_postings(conn, [_posting(url="https://example.com/gone-404")])
    candidates = conn.execute("SELECT id, url FROM postings").fetchall()

    offline_count = asyncio.run(check_posting_links(conn, candidates, client=_mock_client()))

    assert offline_count == 1
    row = conn.execute("SELECT is_stale, stale_reason, last_checked_at FROM postings").fetchone()
    assert row["is_stale"] == 1
    assert row["stale_reason"] == "link_check"
    assert row["last_checked_at"] is not None


def test_confirms_offline_on_closed_page_text(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    upsert_postings(conn, [_posting(url="https://example.com/closed-text")])
    candidates = conn.execute("SELECT id, url FROM postings").fetchall()

    offline_count = asyncio.run(check_posting_links(conn, candidates, client=_mock_client()))

    assert offline_count == 1
    row = conn.execute("SELECT is_stale, stale_reason FROM postings").fetchone()
    assert (row["is_stale"], row["stale_reason"]) == (1, "link_check")


def test_leaves_live_posting_alone_but_records_check_time(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    upsert_postings(conn, [_posting(url="https://example.com/still-open")])
    candidates = conn.execute("SELECT id, url FROM postings").fetchall()

    offline_count = asyncio.run(check_posting_links(conn, candidates, client=_mock_client()))

    assert offline_count == 0
    row = conn.execute("SELECT is_stale, stale_reason, last_checked_at FROM postings").fetchone()
    assert row["is_stale"] == 0
    assert row["stale_reason"] is None
    assert row["last_checked_at"] is not None


def test_network_error_does_not_mark_offline(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    upsert_postings(conn, [_posting(url="https://example.com/network-error")])
    candidates = conn.execute("SELECT id, url FROM postings").fetchall()

    offline_count = asyncio.run(check_posting_links(conn, candidates, client=_mock_client()))

    assert offline_count == 0
    row = conn.execute("SELECT is_stale FROM postings").fetchone()
    assert row["is_stale"] == 0


def test_no_candidates_is_a_no_op(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    offline_count = asyncio.run(check_posting_links(conn, [], client=_mock_client()))
    assert offline_count == 0


def test_get_link_check_candidates_skips_already_stale_and_recently_checked(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    upsert_postings(
        conn,
        [
            _posting(external_id="1", company="Acme", url="https://example.com/a"),
            _posting(external_id="2", company="Globex", url="https://example.com/b"),
            _posting(external_id="3", company="Initech", url="https://example.com/c"),
        ],
    )
    now = datetime.now(timezone.utc)
    conn.execute("UPDATE postings SET is_stale = 1 WHERE url = 'https://example.com/a'")
    conn.execute(
        "UPDATE postings SET last_checked_at = ? WHERE url = 'https://example.com/b'",
        (now.isoformat(),),
    )
    conn.commit()

    cutoff = (now - timedelta(hours=6)).isoformat()
    candidates = get_link_check_candidates(conn, cutoff)

    assert [row["url"] for row in candidates] == ["https://example.com/c"]
