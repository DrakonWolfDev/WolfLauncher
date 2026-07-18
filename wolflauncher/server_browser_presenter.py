from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from .models import DiscoveredServer
from .server_display import display_map_name, display_required_mod_count, display_server_flags
from .theme import STATUS_COLOURS


@dataclass(frozen=True)
class BrowserRow:
    values: list[str]
    sort_values: list[Any]
    tooltips: dict[int, str]
    status_colour: str


@dataclass(frozen=True)
class BrowserInspector:
    title: str
    status: str
    status_kind: str
    endpoint: str
    map_name: str
    region: str
    game_time: str
    players: str
    ping: str
    truth: str
    features: str
    mods: str
    diagnostics: str


def browser_style_terms(style: str) -> list[str]:
    if style == "PvE":
        return ["pve", "p.v.e", "no pvp", "no kos", "no-kos", "no kill on sight"]
    if style == "PvP":
        return ["pvp", "p.v.p"]
    return []


def players_text(current: int | None, maximum: int | None) -> str:
    if current is None and maximum is None:
        return ""
    if maximum is None:
        return str(current)
    if current is None:
        return f"?/{maximum}"
    return f"{current}/{maximum}"


def game_time_text(server: DiscoveredServer, include_symbol: bool = True) -> str:
    """Format locally measured DayZ time with a broad day/night cue."""
    parsed = _game_time_parts(server.game_time)
    if parsed is None:
        return "—"
    hour, minute = parsed
    is_day = 6 <= hour < 18
    multiplier = server.day_acceleration
    if not is_day and multiplier is not None and server.night_acceleration is not None:
        multiplier *= server.night_acceleration
    suffix = f" · {_number_text(multiplier)}×" if multiplier is not None else ""
    symbol = f"{'☀' if is_day else '☾'} " if include_symbol else ""
    return f"{symbol}{hour:02d}:{minute:02d}{suffix}"


def game_time_is_day(server: DiscoveredServer) -> bool | None:
    parsed = _game_time_parts(server.game_time)
    return 6 <= parsed[0] < 18 if parsed is not None else None


def browser_mod_pill(mod_preview: str) -> tuple[str, str]:
    """Return conditional actionable mod status text and its semantic kind."""
    normalized = (mod_preview or "").strip().casefold()
    missing = re.search(r"(\d+)\s+missing", normalized)
    if missing:
        return f"{missing.group(1)} MODS MISSING", "offline"
    if normalized == "unavailable":
        return "MOD CHECK FAILED", "warning"
    if normalized.startswith("checking"):
        return "MODS CHECKING", "warning"
    return "", "warning"


def game_time_tooltip(server: DiscoveredServer) -> str:
    if _game_time_parts(server.game_time) is None:
        return "Game time is measured locally when you select this server."
    measured = f" at {server.last_checked}" if server.last_checked else ""
    parts = [
        "Locally measured in-game time"
        f"{measured}; the sun/moon cue uses 06:00 and 18:00 boundaries."
    ]
    if server.day_acceleration is not None:
        parts.append(f"Day acceleration: x{_number_text(server.day_acceleration)}.")
    if server.night_acceleration is not None:
        effective = (
            server.day_acceleration * server.night_acceleration
            if server.day_acceleration is not None
            else None
        )
        text = f"Night factor: x{_number_text(server.night_acceleration)}"
        if effective is not None:
            text += f" (effective night acceleration x{_number_text(effective)})"
        parts.append(text + ".")
    return " ".join(parts)


def _game_time_parts(value: str) -> tuple[int, int] | None:
    match = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", value or "")
    return (int(match.group(1)), int(match.group(2))) if match else None


def _game_time_sort_value(value: str) -> int | None:
    parsed = _game_time_parts(value)
    return parsed[0] * 60 + parsed[1] if parsed else None


def _number_text(value: float) -> str:
    return f"{value:g}"


def live_name_text(server: DiscoveredServer) -> str:
    live_name = (server.server_name or "").strip()
    display_name = (server.name or "").strip()
    if not live_name or live_name.casefold() == display_name.casefold():
        return ""
    return live_name


def display_server_name(server: DiscoveredServer) -> str:
    live_name = live_name_text(server)
    if server.status_source == "local" and live_name:
        return live_name
    return (server.name or "").strip() or server.connect_target


def api_freshness_text(
    server: DiscoveredServer,
    now: datetime | None = None,
) -> str:
    freshness = server.freshness.strip()
    if not freshness:
        return ""
    label = freshness.replace("_", " ").title()
    expires_at = server.freshness_expires_at.strip()
    if not expires_at:
        return label
    try:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return label
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if current >= expires:
        return f"{label} (expired; refresh pending)"
    return label


def api_status_tooltip(server: DiscoveredServer) -> str:
    lines = []
    freshness = api_freshness_text(server)
    if freshness:
        lines.append(f"WolfAPI freshness: {freshness}")
    if server.validation_status:
        lines.append(
            "WolfAPI validation: "
            + server.validation_status.replace("_", " ").title()
        )
    if server.validation_checked_at:
        lines.append(f"Validated at: {server.validation_checked_at}")
    if server.provider_last_seen:
        lines.append(f"Provider last saw server: {server.provider_last_seen}")
    if lines:
        lines.append("Local ping and launch-time checks remain separate.")
    return "\n".join(lines)


def browser_status(server: DiscoveredServer) -> tuple[str, str]:
    """Return a human-facing status and colour without exposing provider jargon."""
    if server.status_source == "local":
        return (
            ("ONLINE", STATUS_COLOURS["positive"])
            if server.online
            else ("OFFLINE", STATUS_COLOURS["negative"])
        )
    freshness = server.freshness.strip().lower()
    if freshness == "live":
        return "LIVE", STATUS_COLOURS["positive"]
    if freshness == "recent":
        return "RECENT", STATUS_COLOURS["warning"]
    if freshness == "stale":
        return "STALE", STATUS_COLOURS["warning"]
    if freshness == "offline" or server.validation_status.strip().lower() == "offline":
        return "OFFLINE", STATUS_COLOURS["negative"]
    if freshness == "unverified":
        return "UNVERIFIED", STATUS_COLOURS["warning"]
    return (
        ("RECENT", STATUS_COLOURS["warning"])
        if server.online
        else ("UNVERIFIED", STATUS_COLOURS["warning"])
    )


def browser_row(server: DiscoveredServer) -> BrowserRow:
    flags_text = display_server_flags(
        server.password,
        server.modded,
        quality_warning=bool(server.quality_flags),
    )
    live_name = live_name_text(server)
    tooltips = {}
    if server.status_source == "local" and live_name:
        tooltips[0] = (
            "Locally validated live name."
            + (f" Provider/cache name: {server.name}" if server.name else "")
        )
    else:
        tooltips[0] = "Provider/cache name; local enrichment can supply a fresher live name."
    locally_checked = server.status_source == "local"
    status_text, status_colour = browser_status(server)
    if not server.last_checked:
        tooltips[12] = "This row has not been checked yet."
    elif locally_checked:
        tooltips[5] = f"Locally validated at {server.last_checked}."
    else:
        tooltips[5] = (
            f"Reported by {server.source}; not yet validated from this computer. "
            "Use Enrich visible for a fresh local check."
        )
    if not server.last_seen:
        tooltips[13] = "This row has not been seen online yet."
    if server.ping_ms is None:
        tooltips[8] = "Ping is measured locally when you select this server."
    if server.required_mod_count is None:
        if server.mod_metadata_status == "failed":
            tooltips[11] = (
                "WolfAPI's required-mod lookup failed"
                + (f" ({server.mod_metadata_error_code})" if server.mod_metadata_error_code else "")
                + ". Use Inspect mods to query this server directly."
            )
        else:
            tooltips[11] = (
                "Required-mod count is unknown. "
                "Use Inspect mods to query this server directly."
            )
    elif server.mod_metadata_status == "stale":
        tooltips[11] = (
            f"WolfAPI last found {server.required_mod_count} required mod(s), but that "
            "metadata is stale. Inspect mods before joining."
        )
    elif server.mod_metadata_status == "ready":
        tooltips[11] = (
            f"WolfAPI found {server.required_mod_count} required mod(s)"
            + (f" at {server.mod_metadata_checked_at}" if server.mod_metadata_checked_at else "")
            + ". This is browsing evidence; Inspect mods remains final truth."
        )
    status_tooltip = api_status_tooltip(server)
    if status_tooltip:
        existing_status = tooltips.get(5, "")
        tooltips[5] = "\n".join(
            part for part in (existing_status, status_tooltip) if part
        )
    if server.quality_flags:
        tooltips[10] = (
            "WolfAPI quality warning: "
            + ", ".join(flag.replace("_", " ") for flag in server.quality_flags)
            + ". This is advisory provider-data screening, not proof the server is unsafe."
        )
    if server.country_code:
        tooltips[15] = (
            f"Country reported by {server.country_source or 'the discovery provider'}; "
            "this is provider metadata, not an IP-based guess."
        )
    else:
        tooltips[15] = "Country is not available from a trusted discovery source."
    tooltips[16] = game_time_tooltip(server)

    return BrowserRow(
        values=[
            display_server_name(server),
            live_name,
            server.host,
            str(server.game_port),
            str(server.query_port),
            status_text,
            display_map_name(server.map_name),
            players_text(server.players_current, server.players_max),
            f"{server.ping_ms}ms" if server.ping_ms is not None else "",
            server.version,
            flags_text,
            display_required_mod_count(server.required_mod_count),
            server.last_checked,
            server.last_seen,
            server.source,
            server.country_code or "—",
            game_time_text(server, include_symbol=False),
        ],
        sort_values=[
            display_server_name(server),
            live_name or server.name,
            server.host,
            server.game_port,
            server.query_port,
            0 if server.online else 1,
            server.map_name,
            server.players_current,
            server.ping_ms,
            server.version,
            flags_text,
            server.required_mod_count,
            server.last_checked,
            server.last_seen,
            server.source,
            server.country_code or None,
            _game_time_sort_value(server.game_time),
        ],
        tooltips=tooltips,
        status_colour=status_colour,
    )


def browser_inspector(
    server: DiscoveredServer,
    mod_preview: str = "",
) -> BrowserInspector:
    """Build the calm selected-server summary without hiding support detail."""
    status, colour = browser_status(server)
    status_kind = (
        "ready" if colour == STATUS_COLOURS["positive"] else
        "offline" if colour == STATUS_COLOURS["negative"] else
        "warning"
    )
    players = players_text(server.players_current, server.players_max) or "Unknown"
    ping = f"{server.ping_ms} ms" if server.ping_ms is not None else "Unknown"
    features = display_server_flags(
        server.password,
        server.modded,
        quality_warning=bool(server.quality_flags),
    )
    freshness = api_freshness_text(server) or "Unverified"
    truth = (
        f"Locally validated · {server.last_checked or 'time unavailable'}"
        if server.status_source == "local"
        else f"Provider reported · {freshness}"
    )
    mods = mod_preview or display_required_mod_count(server.required_mod_count)
    if mods == "–":
        mods = "Unknown until checked"
    return BrowserInspector(
        title=display_server_name(server),
        status=status.title(),
        status_kind=status_kind,
        endpoint=server.connect_target,
        map_name=display_map_name(server.map_name),
        region=server.country_code or "Not available",
        game_time=(
            game_time_text(server)
            if game_time_text(server) != "—"
            else "Unknown until locally checked"
        ),
        players=players,
        ping=ping,
        truth=truth,
        features=features,
        mods=mods,
        diagnostics=(
            f"Host  {server.host}\n"
            f"Game port  {server.game_port}    Query port  {server.query_port}\n"
            f"Source  {server.source or 'Unknown'}    Version  {server.version or 'Unknown'}\n"
            f"Last seen  {server.last_seen or 'Never'}"
        ),
    )


def discovered_server_details(server: DiscoveredServer) -> str:
    flags_text = display_server_flags(
        server.password,
        server.modded,
        quality_warning=bool(server.quality_flags),
    )
    lines = [server.name]
    if live_name_text(server):
        lines.append(f"Live name: {server.server_name}")
    lines.extend([
        server.connect_target,
        f"Query port: {server.query_port}",
        f"Map: {display_map_name(server.map_name)}",
        f"Game time: {game_time_text(server)}",
        f"Players: {players_text(server.players_current, server.players_max)}",
        f"Version: {server.version}",
        f"Features: {flags_text}",
        f"Mods: {display_required_mod_count(server.required_mod_count)}",
        f"Status basis: {'Locally validated' if server.status_source == 'local' else 'Provider reported'}",
        f"Last checked: {server.last_checked or 'Never'}",
        f"Last seen: {server.last_seen or 'Never'}",
    ])
    if server.mod_metadata_status:
        lines.append(
            "API mod metadata: "
            + server.mod_metadata_status.replace("_", " ").title()
        )
    if server.quality_flags:
        lines.append(
            "API quality warnings: "
            + ", ".join(flag.replace("_", " ") for flag in server.quality_flags)
        )
    if server.mod_metadata_checked_at:
        lines.append(f"Mod metadata checked: {server.mod_metadata_checked_at}")
    if server.mod_metadata_expires_at:
        lines.append(f"Mod metadata expires: {server.mod_metadata_expires_at}")
    if server.mod_metadata_error_code:
        lines.append(f"Mod metadata error: {server.mod_metadata_error_code}")
    freshness = api_freshness_text(server)
    if freshness:
        lines.append(f"API freshness: {freshness}")
    if server.freshness_expires_at:
        lines.append(f"Freshness expires: {server.freshness_expires_at}")
    if server.validation_status:
        lines.append(
            "API validation: "
            + server.validation_status.replace("_", " ").title()
        )
    if server.validation_checked_at:
        lines.append(f"Validation checked: {server.validation_checked_at}")
    if server.provider_last_checked:
        lines.append(f"Provider checked: {server.provider_last_checked}")
    if server.provider_last_seen:
        lines.append(f"Provider last seen: {server.provider_last_seen}")
    lines.append(f"Source: {server.source}")
    return "\n".join(lines).strip()


def browser_summary_text(summary: dict[str, int], shown: int, match_count: int, limit: int) -> str:
    total = summary["total"]
    if total == 0:
        return "No discovered servers cached"

    parts = [f"Showing {shown} of {match_count} matching", f"{summary['online']} online"]
    if shown == limit and match_count > shown:
        parts[0] = f"Showing first {shown} of {match_count} matching"
    elif shown == 0:
        parts[0] = f"No matches from {total} cached"
    return " · ".join(parts)


def browser_summary_tooltip(summary: dict[str, int]) -> str:
    return (
        f"{summary['total']} cached · {summary['online']} provider/local online · "
        f"{summary['checked']} checked · {summary['seen']} seen online"
    )
