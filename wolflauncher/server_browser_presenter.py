from dataclasses import dataclass
from typing import Any

from .models import DiscoveredServer


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


def browser_row(server: DiscoveredServer) -> BrowserRow:
    flags = []
    if server.password:
        flags.append("Password")
    if server.modded:
        flags.append("Mods")
    flags_text = ", ".join(flags) if flags else "Vanilla/unknown"
    live_name = live_name_text(server)
    tooltips = {}
    if live_name:
        tooltips[0] = f"Live name: {server.server_name}"
    else:
        tooltips[1] = "Same as display name, or not reported yet."
    if not server.last_checked:
        tooltips[11] = "This row has not been live-checked yet."
    if not server.last_seen:
        tooltips[12] = "This row has not been seen online yet."

    return BrowserRow(
        values=[
            server.name,
            live_name,
            server.host,
            str(server.game_port),
            str(server.query_port),
            "ONLINE" if server.online else "OFFLINE",
            server.map_name,
            players_text(server.players_current, server.players_max),
            f"{server.ping_ms}ms" if server.ping_ms is not None else "",
            server.version,
            flags_text,
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
            server.last_checked,
            server.last_seen,
            server.source,
        ],
        tooltips=tooltips,
        status_colour="#6ee16e" if server.online else "#ff6b6b",
    )


def browser_summary_text(summary: dict[str, int], shown: int, match_count: int, limit: int) -> str:
    total = summary["total"]
    if total == 0:
        return "Cached discovered servers: empty"

    parts = [
        f"Showing {shown} of {match_count} matching",
        f"{total} cached",
        f"{summary['online']} online",
        f"{summary['checked']} checked",
        f"{summary['seen']} seen online",
    ]
    if shown == limit and match_count > shown:
        parts[0] = f"Showing first {shown} of {match_count} matching"
    elif shown == 0:
        parts[0] = f"No matches from {total} cached"
    return "Cached discovered servers: " + " | ".join(parts)
