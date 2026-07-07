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
                SET merged_sources = ?, posted_at = ?, fetched_at = ?, last_seen_at = ?,
                    is_stale = 0, stale_reason = NULL
                WHERE id = ?
                """,
                (",".join(sorted(merged)), earliest_posted, p.fetched_at, now, row["id"]),
            )
            updated_count += 1

    conn.commit()
    return new_count, updated_count


def mark_stale_not_seen_since(conn: sqlite3.Connection, cutoff_iso: str) -> int:
    cursor = conn.execute(
        "UPDATE postings SET is_stale = 1, stale_reason = 'not_seen' WHERE last_seen_at < ? AND is_stale = 0",
        (cutoff_iso,),
    )
    conn.commit()
    return cursor.rowcount


def get_link_check_candidates(
    conn: sqlite3.Connection, cutoff_iso: str, limit: int = 150
) -> list[sqlite3.Row]:
    """Postings not already known-stale and not probed since cutoff_iso, oldest-checked first."""
    return conn.execute(
        """
        SELECT id, url FROM postings
        WHERE is_stale = 0 AND (last_checked_at IS NULL OR last_checked_at < ?)
        ORDER BY last_checked_at IS NOT NULL, last_checked_at ASC
        LIMIT ?
        """,
        (cutoff_iso, limit),
    ).fetchall()


def record_link_check_results(
    conn: sqlite3.Connection, checked_ids: list[int], offline_ids: list[int], now: str
) -> None:
    if checked_ids:
        placeholders = ",".join("?" * len(checked_ids))
        conn.execute(
            f"UPDATE postings SET last_checked_at = ? WHERE id IN ({placeholders})",
            (now, *checked_ids),
        )
    if offline_ids:
        placeholders = ",".join("?" * len(offline_ids))
        conn.execute(
            f"UPDATE postings SET is_stale = 1, stale_reason = 'link_check' WHERE id IN ({placeholders})",
            offline_ids,
        )
    conn.commit()
