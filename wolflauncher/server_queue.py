"""Presentation of independently measured DayZ queue counts."""

from datetime import datetime, timezone

from .status import valid_queue_count

QUEUE_TTL_SECONDS = 120


def queue_text(count: int | None, checked_at: str, *, now: datetime | None = None) -> str:
    count = valid_queue_count(count)
    if count is None:
        return "Queue: unknown"
    try:
        checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        if checked.tzinfo is None:
            raise ValueError("Missing timezone")
        age = ((now or datetime.now(timezone.utc)) - checked).total_seconds()
        fresh = 0 <= age < QUEUE_TTL_SECONDS
    except (ValueError, TypeError):
        fresh = False
    return f"Queue: {count}" + ("" if fresh else " (stale)")


def players_with_queue(players: str, count: int | None, checked_at: str) -> str:
    return f"{players or 'Unknown'} · {queue_text(count, checked_at)}"
