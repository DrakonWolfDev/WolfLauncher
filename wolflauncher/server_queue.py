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
    # Keep uncertainty distinct from an explicitly measured empty queue. The
    # explanation belongs in the tooltip, rather than widening every row.
    observed = queue_text(count, checked_at)
    suffix = str(count) if observed == f"Queue: {count}" else "?"
    return f"{players or '—'}+{suffix}"


def players_queue_tooltip(count: int | None, checked_at: str) -> str:
    observed = queue_text(count, checked_at)
    if observed.endswith(" (stale)"):
        return "Players / server capacity + waiting to join. Queue reading has expired; recheck this server."
    if observed == "Queue: unknown":
        return "Players / server capacity + waiting to join. Queue size is not available yet."
    return f"Players / server capacity + waiting to join. {observed}."
