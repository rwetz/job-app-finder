import asyncio
import sqlite3
from datetime import datetime, timezone

from job_app_finder.config import Config
from job_app_finder.db.postings_repo import mark_stale_not_seen_since, upsert_postings
from job_app_finder.geo import geocode_and_tier_postings
from job_app_finder.match import claude_rationale_shortlist, score_all_postings
from job_app_finder.models import Posting
from job_app_finder.sources import get_registry  # noqa: F401 (triggers adapter registration)


async def _run_source(name: str, adapter, queries: list[str], anchors) -> tuple[str, list[Posting], str | None]:
    try:
        postings = await adapter.fetch(queries, anchors)
        return name, postings, None
    except Exception as exc:  # adapters are best-effort; one failure shouldn't sink the run
        return name, [], str(exc)


async def ingest_all(config: Config, conn: sqlite3.Connection) -> dict[str, dict]:
    run_started_at = datetime.now(timezone.utc).isoformat()

    registry = get_registry()
    active_names = set(config.enabled_sources) | set(config.besteffort_enabled)
    active = {name: adapter for name, adapter in registry.items() if name in active_names}

    results = await asyncio.gather(
        *(_run_source(name, adapter, config.seed_queries, config.anchors) for name, adapter in active.items())
    )

    summary: dict[str, dict] = {}
    for name, postings, error in results:
        started_at = datetime.now(timezone.utc).isoformat()
        new_count, updated_count = (0, 0) if error else upsert_postings(conn, postings)
        finished_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO fetch_runs (source, started_at, finished_at, count_fetched, count_new, count_updated, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, started_at, finished_at, len(postings), new_count, updated_count, error),
        )
        summary[name] = {
            "fetched": len(postings),
            "new": new_count,
            "updated": updated_count,
            "error": error,
        }
    conn.commit()

    tiered = await geocode_and_tier_postings(conn, config.anchors, config.location_tiers)
    stale = mark_stale_not_seen_since(conn, run_started_at)

    scored = 0
    rationales = 0
    if config.resume_path.exists():
        resume_text = config.resume_path.read_text().strip()
        if resume_text:
            scored = score_all_postings(conn, resume_text)
            rationales = claude_rationale_shortlist(
                conn, resume_text, config.claude_model, config.shortlist_size
            )

    summary["_meta"] = {
        "tiered": tiered,
        "marked_stale": stale,
        "scored": scored,
        "rationales": rationales,
    }

    return summary


def run_ingest_sync(config: Config, conn: sqlite3.Connection) -> dict[str, dict]:
    return asyncio.run(ingest_all(config, conn))
