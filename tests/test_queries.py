from pathlib import Path

from job_app_finder.db.database import init_db
from job_app_finder.db.postings_repo import upsert_postings
from job_app_finder.db.queries import distinct_sources, list_postings, set_application_status
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
        url="https://example.com/1",
        description="build things",
        posted_at="2026-07-01T00:00:00Z",
        fetched_at="2026-07-07T00:00:00Z",
    )
    base.update(overrides)
    return Posting(**base)


def _seed(conn):
    upsert_postings(
        conn,
        [
            _posting(external_id="1", url="https://example.com/1", title="Local Intern", is_remote=False),
            _posting(
                external_id="2",
                url="https://example.com/2",
                title="Remote Intern",
                is_remote=True,
                source="jsearch",
            ),
        ],
    )
    conn.execute("UPDATE postings SET location_tier = 0 WHERE external_id = '1'")
    conn.execute("UPDATE postings SET location_tier = 2 WHERE external_id = '2'")
    conn.commit()


def test_list_postings_orders_by_tier_then_match(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    _seed(conn)
    rows = list_postings(conn)
    assert [r["title"] for r in rows] == ["Local Intern", "Remote Intern"]


def test_list_postings_filters_by_tier(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    _seed(conn)
    rows = list_postings(conn, tiers=[2])
    assert [r["title"] for r in rows] == ["Remote Intern"]


def test_list_postings_filters_by_keyword(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    _seed(conn)
    rows = list_postings(conn, keyword="Remote")
    assert [r["title"] for r in rows] == ["Remote Intern"]


def test_list_postings_filters_by_source(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    _seed(conn)
    rows = list_postings(conn, sources=["jsearch"])
    assert [r["title"] for r in rows] == ["Remote Intern"]


def test_set_application_status_upserts_and_joins(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    _seed(conn)
    posting_id = conn.execute("SELECT id FROM postings WHERE external_id = '1'").fetchone()["id"]

    set_application_status(conn, posting_id, "interested")
    rows = list_postings(conn)
    row = next(r for r in rows if r["id"] == posting_id)
    assert row["application_status"] == "interested"

    set_application_status(conn, posting_id, "applied")
    rows = list_postings(conn)
    row = next(r for r in rows if r["id"] == posting_id)
    assert row["application_status"] == "applied"


def test_distinct_sources(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    _seed(conn)
    assert distinct_sources(conn) == ["adzuna", "jsearch"]
