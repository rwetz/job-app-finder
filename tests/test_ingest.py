import asyncio
from pathlib import Path

from job_app_finder.config import Config
from job_app_finder.db.database import init_db
from job_app_finder.ingest import ingest_all
from job_app_finder.models import Anchor, Posting
from job_app_finder.sources.base import AdapterMeta, SourceAdapter, register

FARGO = Anchor(name="Fargo, ND", zip="58102", lat=46.8772, lon=-96.7898)


class _FakeGoodAdapter(SourceAdapter):
    meta = AdapterMeta(name="fake-good", kind="aggregator", priority=1)

    async def fetch(self, queries, anchors):
        return [
            Posting(
                source="fake-good",
                external_id="1",
                title="Intern",
                company="Acme",
                location_raw="Fargo, ND",
                lat=46.8,
                lon=-96.8,
                is_remote=False,
                url="https://example.com/1",
                description="d",
                posted_at="2026-07-01T00:00:00Z",
                fetched_at="2026-07-07T00:00:00Z",
            )
        ]


class _FakeFailingAdapter(SourceAdapter):
    meta = AdapterMeta(name="fake-bad", kind="aggregator", priority=1)

    async def fetch(self, queries, anchors):
        raise RuntimeError("boom")


def _config(db_path: Path) -> Config:
    return Config(
        anchors=[FARGO],
        location_tiers={"tier_0_max_miles": 60, "tier_1_max_miles": 150},
        seed_queries=["intern"],
        enabled_sources=["fake-good", "fake-bad"],
        besteffort_enabled=[],
        refresh_interval_minutes=30,
        db_path=db_path,
    )


def test_ingest_all_upserts_and_logs_fetch_runs_including_failures(tmp_path: Path):
    register(_FakeGoodAdapter())
    register(_FakeFailingAdapter())
    conn = init_db(tmp_path / "t.db")
    config = _config(tmp_path / "t.db")

    summary = asyncio.run(ingest_all(config, conn))

    assert summary["fake-good"] == {"fetched": 1, "new": 1, "updated": 0, "error": None}
    assert summary["fake-bad"]["error"] == "boom"

    postings = conn.execute("SELECT * FROM postings").fetchall()
    assert len(postings) == 1

    runs = conn.execute("SELECT source, error FROM fetch_runs").fetchall()
    assert {(r["source"], r["error"]) for r in runs} == {("fake-good", None), ("fake-bad", "boom")}
