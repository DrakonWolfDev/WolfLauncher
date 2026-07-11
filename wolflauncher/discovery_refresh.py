from datetime import datetime, timedelta, timezone


AUTO_REFRESH_INTERVAL = timedelta(hours=24)


def auto_refresh_due(value: object, now: datetime | None = None) -> bool:
    """Return whether a provider refresh timestamp is absent, invalid or expired."""
    timestamp = str(value or "")
    if not timestamp:
        return True
    try:
        last_refresh = datetime.fromisoformat(timestamp)
    except ValueError:
        return True
    if last_refresh.tzinfo is None:
        last_refresh = last_refresh.replace(tzinfo=timezone.utc)
    current_time = now or datetime.now(timezone.utc)
    return current_time - last_refresh >= AUTO_REFRESH_INTERVAL


def auto_refresh_timestamp(now: datetime | None = None) -> str:
    """Build the UTC timestamp persisted after an automatic provider refresh."""
    current_time = now or datetime.now(timezone.utc)
    return current_time.astimezone(timezone.utc).replace(microsecond=0).isoformat()
