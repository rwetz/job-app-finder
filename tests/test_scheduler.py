import pytest

apscheduler = pytest.importorskip("apscheduler")

from job_app_finder.scheduler import start_background_scheduler  # noqa: E402


def test_start_background_scheduler_registers_interval_job():
    scheduler = start_background_scheduler(interval_minutes=30)
    try:
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "refresh"
    finally:
        scheduler.shutdown(wait=False)
