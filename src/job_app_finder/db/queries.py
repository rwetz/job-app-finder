import sqlite3
from datetime import datetime, timezone


def list_postings(
    conn: sqlite3.Connection,
    *,
    tiers: list[int] | None = None,
    remote_only: bool = False,
    keyword: str | None = None,
    sources: list[str] | None = None,
    min_match: float | None = None,
    include_stale: bool = True,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    params: list = []

    if tiers:
        placeholders = ",".join("?" * len(tiers))
        clauses.append(f"p.location_tier IN ({placeholders})")
        params.extend(tiers)
    if remote_only:
        clauses.append("p.is_remote = 1")
    if keyword:
        like = f"%{keyword}%"
        clauses.append("(p.title LIKE ? OR p.company LIKE ? OR p.description LIKE ?)")
        params.extend([like, like, like])
    if sources:
        source_clauses = []
        for s in sources:
            source_clauses.append("(',' || p.merged_sources || ',') LIKE ?")
            params.append(f"%,{s},%")
        clauses.append("(" + " OR ".join(source_clauses) + ")")
    if min_match is not None:
        clauses.append("p.match_score >= ?")
        params.append(min_match)
    if not include_stale:
        clauses.append("p.is_stale = 0")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT p.*, a.status AS application_status
        FROM postings p
        LEFT JOIN applications a ON a.posting_id = p.id
        {where}
        ORDER BY
            COALESCE(p.location_tier, 3) ASC,
            COALESCE(p.match_score, -1) DESC,
            p.posted_at DESC
    """
    return conn.execute(query, params).fetchall()


def set_application_status(
    conn: sqlite3.Connection, posting_id: int, status: str, notes: str | None = None
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO applications (posting_id, status, notes, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(posting_id) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
        """,
        (posting_id, status, notes, now),
    )
    conn.commit()


def distinct_sources(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT merged_sources FROM postings WHERE merged_sources IS NOT NULL"
    ).fetchall()
    names: set[str] = set()
    for row in rows:
        names.update(filter(None, row["merged_sources"].split(",")))
    return sorted(names)


def last_refresh_at(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(finished_at) AS t FROM fetch_runs").fetchone()
    return row["t"] if row else None
