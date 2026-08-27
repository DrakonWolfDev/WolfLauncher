"""Shared, presentation-only labels for server data."""

import json
from functools import lru_cache
from pathlib import Path

PING_WARNING_MS = 200
PING_CRITICAL_MS = 250


def is_displayable_server_name(value: str) -> bool:
    """Reject names already damaged by upstream decoding or binary data."""
    return (
        bool(value.strip())
        and "\ufffd" not in value
        and not any(ord(character) < 32 for character in value)
    )


@lru_cache(maxsize=1)
def _known_maps() -> dict[str, tuple[str, str]]:
    """Return normalised input mapped to ``(technical key, display name)``."""
    path = Path(__file__).resolve().parent / "assets" / "known_maps.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    known: dict[str, tuple[str, str]] = {}
    for item in payload.get("maps", []):
        if not isinstance(item, dict):
            continue
        key = " ".join(str(item.get("key") or "").split())
        name = " ".join(str(item.get("name") or "").split())
        if not key or not name:
            continue
        entry = (key, name)
        for alias in [key, name, *item.get("aliases", [])]:
            alias = " ".join(str(alias or "").split()).casefold()
            if alias:
                known[alias] = entry
    return known


def map_filter_key(map_name: str) -> str:
    """Map a human label back to the stable technical key for WolfAPI."""
    value = " ".join(map_name.split())
    if not value:
        return ""
    return _known_maps().get(value.casefold(), (value.casefold(), ""))[0]


def display_map_name(map_name: str) -> str:
    """Render a stable known-map label; unknown case variants still collapse."""
    value = " ".join(map_name.split())
    if not value:
        return ""
    known = _known_maps().get(value.casefold())
    if known:
        return known[1]
    normalised = value.casefold()
    return normalised[:1].upper() + normalised[1:]


def display_server_flags(
    password: bool,
    modded: bool,
    quality_warning: bool = False,
) -> str:
    flags = []
    if password:
        flags.append("Password")
    flags.append("Modded" if modded else "Vanilla")
    if quality_warning:
        flags.append("Listing data warning")
    return ", ".join(flags)


def display_required_mod_count(count: int | None) -> str:
    return str(count) if count is not None and count > 0 else "–"


def ping_severity(ping_ms: int | None) -> str:
    """Classify latency using DayZ's documented warning thresholds."""
    if ping_ms is None:
        return "unknown"
    if ping_ms >= PING_CRITICAL_MS:
        return "critical"
    if ping_ms >= PING_WARNING_MS:
        return "warning"
    return "normal"
