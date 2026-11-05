"""Shared, presentation-only labels for server data."""

import json
import re
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path

PING_WARNING_MS = 200
PING_CRITICAL_MS = 250


def is_displayable_server_name(value: str) -> bool:
    """Reject damaged text, punctuation-only names and address placeholders."""
    name = value.strip()
    if re.search(r"[\x00-\x1f\x7f\ufffd]", value) or not any(c.isalnum() for c in name):
        return False
    candidate = name
    # Bracketed IPv6 and IPv4 endpoints may include a port. A real title that
    # merely contains an address remains a usable name.
    endpoint = re.fullmatch(r"\[([^\]]+)\]:(\d+)|([^:]+):(\d+)", name)
    if endpoint:
        candidate = endpoint.group(1) or endpoint.group(3)
    try:
        ip_address(candidate.strip("[]"))
    except ValueError:
        return True
    return False


def has_browsable_server_name(name: str, live_name: str, status_source: str) -> bool:
    """Match the browser's locally verified name preference without guessing."""
    return is_displayable_server_name(name) or (
        status_source == "local" and is_displayable_server_name(live_name)
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
