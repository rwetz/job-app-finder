from pathlib import Path

from job_app_finder.db.database import init_db
from job_app_finder.db.postings_repo import upsert_postings
from job_app_finder.models import Posting


def _posting(**overrides):
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


def test_upsert_inserts_new_posting(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    new, updated = upsert_postings(conn, [_posting()])
    assert (new, updated) == (1, 0)
    row = conn.execute("SELECT * FROM postings").fetchone()
    assert row["title"] == "Software Engineering Intern"
    assert row["merged_sources"] == "adzuna"


def test_upsert_merges_duplicate_by_url(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    upsert_postings(conn, [_posting()])
    new, updated = upsert_postings(
        conn, [_posting(source="jsearch", external_id="99", url="https://example.com/jobs/1")]
    )
    assert (new, updated) == (0, 1)
    row = conn.execute("SELECT * FROM postings").fetchone()
    assert set(row["merged_sources"].split(",")) == {"adzuna", "jsearch"}


def test_upsert_merges_duplicate_by_fuzzy_key_across_different_urls(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    upsert_postings(conn, [_posting()])
    new, updated = upsert_postings(
        conn,
        [_posting(source="jsearch", external_id="99", url="https://boards.example.com/1", posted_at="2026-06-28T00:00:00Z")],
    )
    assert (new, updated) == (0, 1)
    row = conn.execute("SELECT * FROM postings").fetchone()
    assert row["posted_at"] == "2026-06-28T00:00:00Z"  # earliest posted_at kept
