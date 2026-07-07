from pathlib import Path

from job_app_finder.db.database import init_db


def test_init_db_creates_expected_tables(tmp_path: Path):
    conn = init_db(tmp_path / "test.db")
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"postings", "applications", "sources", "fetch_runs"} <= tables
