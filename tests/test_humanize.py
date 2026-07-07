from datetime import datetime, timedelta, timezone

from job_app_finder.humanize import is_stale


def test_is_stale_true_when_missing():
    assert is_stale(None, max_age_minutes=30) is True


def test_is_stale_false_when_recent():
    recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    assert is_stale(recent, max_age_minutes=30) is False


def test_is_stale_true_when_older_than_max_age():
    old = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    assert is_stale(old, max_age_minutes=30) is True


def test_is_stale_true_at_exact_boundary():
    boundary = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    assert is_stale(boundary, max_age_minutes=30) is True
