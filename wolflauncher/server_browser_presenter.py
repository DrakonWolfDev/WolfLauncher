from dataclasses import dataclass
from datetime import datetime, timezone
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


def live_name_text(server: DiscoveredServer) -> str:
    live_name = (server.server_name or "").strip()
    display_name = (server.name or "").strip()
    if not live_name or live_name.casefold() == display_name.casefold():
        return ""
    return live_name


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


def browser_row(server: DiscoveredServer) -> BrowserRow:
    flags_text = display_server_flags(
        server.password,
        server.modded,
        quality_warning=bool(server.quality_flags),
    )
    live_name = live_name_text(server)
    tooltips = {}
    if live_name:
        tooltips[0] = f"Live name: {server.server_name}"
    else:
        tooltips[1] = "Same as display name, or not reported yet."
    locally_checked = server.status_source == "local"
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
        tooltips[8] = "Ping was not supplied by the discovery provider. Use Enrich visible to query it."
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

    return BrowserRow(
        values=[
            server.name,
            live_name,
            server.host,
            str(server.game_port),
            str(server.query_port),
            ("ONLINE" if server.online else "OFFLINE")
            if locally_checked else ("PROVIDER ONLINE" if server.online else "PROVIDER OFFLINE"),
            display_map_name(server.map_name),
            players_text(server.players_current, server.players_max),
            f"{server.ping_ms}ms" if server.ping_ms is not None else "",
            server.version,
            flags_text,
            display_required_mod_count(server.required_mod_count),
            server.last_checked,
            server.last_seen,
            server.source,
        ],
        sort_values=[
            server.name,
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
        ],
        tooltips=tooltips,
        status_colour=(
            STATUS_COLOURS["positive"] if server.online else STATUS_COLOURS["negative"]
        ) if locally_checked else STATUS_COLOURS["warning"],
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
        f"Players: {players_text(server.players_current, server.players_max)}",
        f"Version: {server.version}",
        f"Flags: {flags_text}",
        f"Required mods: {display_required_mod_count(server.required_mod_count)}",
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
