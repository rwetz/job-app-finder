import sqlite3
from datetime import datetime, timezone

from job_app_finder.dedup import canonicalize_url, fuzzy_key
from job_app_finder.models import Posting


def upsert_postings(conn: sqlite3.Connection, postings: list[Posting]) -> tuple[int, int]:
    """Insert new postings, merge duplicates into existing rows. Returns (new, updated)."""
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0
    updated_count = 0

    for p in postings:
        canon_url = canonicalize_url(p.url)
        key = fuzzy_key(p.company, p.title, p.location_raw)
        row = conn.execute(
            "SELECT id, merged_sources, posted_at FROM postings WHERE url = ? OR dedup_key = ?",
            (canon_url, key),
        ).fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO postings (
                    source, external_id, title, company, location_raw, lat, lon,
                    is_remote, url, description, posted_at, fetched_at,
                    dedup_key, merged_sources, last_seen_at, is_stale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    p.source, p.external_id, p.title, p.company, p.location_raw, p.lat, p.lon,
                    int(p.is_remote), canon_url, p.description, p.posted_at, p.fetched_at,
                    key, p.source, now,
                ),
            )
            new_count += 1
        else:
            merged = set(filter(None, (row["merged_sources"] or "").split(",")))
            merged.add(p.source)
            earliest_posted = min(filter(None, [row["posted_at"], p.posted_at]), default=None)
            conn.execute(
                """
                UPDATE postings
                SET merged_sources = ?, posted_at = ?, fetched_at = ?, last_seen_at = ?, is_stale = 0
                WHERE id = ?
                """,
                (",".join(sorted(merged)), earliest_posted, p.fetched_at, now, row["id"]),
            )
            updated_count += 1

    conn.commit()
    return new_count, updated_count


def mark_stale_not_seen_since(conn: sqlite3.Connection, cutoff_iso: str) -> int:
    cursor = conn.execute(
        "UPDATE postings SET is_stale = 1 WHERE last_seen_at < ? AND is_stale = 0",
        (cutoff_iso,),
    )
    conn.commit()
    return cursor.rowcount
