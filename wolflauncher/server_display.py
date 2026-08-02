"""Shared, presentation-only labels for server data."""

PING_WARNING_MS = 200
PING_CRITICAL_MS = 250


def is_displayable_server_name(value: str) -> bool:
    """Reject names already damaged by upstream decoding or binary data."""
    return bool(value.strip()) and "\ufffd" not in value and not any(
        ord(character) < 32 for character in value
    )


def display_map_name(map_name: str) -> str:
    value = map_name.strip()
    if not value:
        return ""
    if value.casefold() == "enoch":
        return "Livonia"
    return value[:1].upper() + value[1:]


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
