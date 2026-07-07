import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DEFAULT_DB_PATH = Path("data/job_app_finder.db")


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_PATH.read_text())
    _migrate(conn)
    conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a table's original CREATE TABLE IF NOT EXISTS.

    executescript's CREATE TABLE IF NOT EXISTS is a no-op on a DB file that
    already has the table, so new columns need an explicit ALTER TABLE here.
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(postings)")}
    if "stale_reason" not in columns:
        conn.execute("ALTER TABLE postings ADD COLUMN stale_reason TEXT")
    if "last_checked_at" not in columns:
        conn.execute("ALTER TABLE postings ADD COLUMN last_checked_at TEXT")
