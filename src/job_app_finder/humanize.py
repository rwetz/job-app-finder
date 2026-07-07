from datetime import datetime, timezone


def minutes_ago(iso_ts: str | None) -> str:
    if not iso_ts:
        return "never"
    dt = datetime.fromisoformat(iso_ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    hours, rem_minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {rem_minutes}m ago"
    days = hours // 24
    return f"{days}d ago"


def is_stale(iso_ts: str | None, max_age_minutes: int) -> bool:
    """True if iso_ts is missing or older than max_age_minutes."""
    if not iso_ts:
        return True
    dt = datetime.fromisoformat(iso_ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_minutes = (datetime.now(timezone.utc) - dt).total_seconds() / 60
    return age_minutes >= max_age_minutes
