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
    # Only a fresh, positive queue adds information to the visible player count.
    # Unknown, empty and expired observations stay distinct in the tooltip/data.
    players = " / ".join(part.strip() for part in players.split("/")) if players else "—"
    count = valid_queue_count(count)
    observed = queue_text(count, checked_at)
    return f"{players} +{count}" if count and observed == f"Queue: {count}" else players


def players_queue_tooltip(count: int | None, checked_at: str) -> str:
    observed = queue_text(count, checked_at)
    if observed.endswith(" (stale)"):
        return "Players / server capacity. Queue reading has expired; recheck this server."
    if observed == "Queue: unknown":
        return "Players / server capacity. Queue size is not available yet."
    return f"Players / server capacity. +N means N waiting to join. {observed}."
