"""Background refresh so the dashboard stays warm between opens.

Uses APScheduler (`schedule` extra) — raises ImportError if not installed,
which callers should treat as "background refresh unavailable" rather than
a hard failure (the app still works with live-fetch-on-open + manual refresh).
"""

import asyncio

from job_app_finder.config import load_config
from job_app_finder.db.database import get_connection
from job_app_finder.ingest import ingest_all


def _run_ingest_job() -> None:
    config = load_config()
    conn = get_connection(config.db_path)
    try:
        asyncio.run(ingest_all(config, conn))
    finally:
        conn.close()


def start_background_scheduler(interval_minutes: int):
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_ingest_job, "interval", minutes=interval_minutes, id="refresh", replace_existing=True
    )
    scheduler.start()
    return scheduler
