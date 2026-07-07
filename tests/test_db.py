import sqlite3
from pathlib import Path

from job_app_finder.db.database import get_connection, init_db


def test_init_db_creates_expected_tables(tmp_path: Path):
    conn = init_db(tmp_path / "test.db")
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"postings", "applications", "sources", "fetch_runs"} <= tables


def test_init_db_adds_link_check_columns_to_a_pre_existing_db(tmp_path: Path):
    db_path = tmp_path / "old.db"
    # Simulate a DB created before stale_reason/last_checked_at existed.
    legacy_conn = sqlite3.connect(db_path)
    legacy_conn.execute(
        """
        CREATE TABLE postings (
            id               INTEGER PRIMARY KEY,
            source           TEXT NOT NULL,
            external_id      TEXT NOT NULL,
            title            TEXT NOT NULL,
            company          TEXT NOT NULL,
            location_raw     TEXT,
            lat              REAL,
            lon              REAL,
            is_remote        INTEGER NOT NULL DEFAULT 0,
            url              TEXT NOT NULL UNIQUE,
            description      TEXT,
            posted_at        TEXT,
            fetched_at       TEXT NOT NULL,
            dedup_key        TEXT,
            merged_sources   TEXT,
            last_seen_at     TEXT,
            location_tier    INTEGER,
            match_score      REAL,
            match_rationale  TEXT,
            is_stale         INTEGER NOT NULL DEFAULT 0,
            UNIQUE (source, external_id)
        )
        """
    )
    legacy_conn.commit()
    legacy_conn.close()

    conn = init_db(db_path)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(postings)")}
    assert {"stale_reason", "last_checked_at"} <= columns

    # Migration must be idempotent — re-running init_db shouldn't error.
    init_db(db_path)
    get_connection(db_path).execute("SELECT stale_reason, last_checked_at FROM postings")
