from .models import Server
from .server_display import display_map_name, display_server_flags, is_displayable_server_name
from .server_queue import players_with_queue
from .status import ServerStatus


def curated_status_tooltip(server: Server, status: ServerStatus | None) -> str:
    """Keep connection roles and diagnostic detail available outside the card text."""
    lines = [
        f"Join in DayZ: {server.host}:{server.game_port}",
        f"Check server status: {server.host}:{server.query_port} (query port)",
    ]
    if status and not status.online:
        lines.append(status.user_message(include_details=True))
    return "\n".join(lines)


def curated_server_row(server: Server, status: ServerStatus | None = None) -> list[str]:
    """Build the fixed-column display values for a curated server row."""
    values = [
        "★" if server.favourite else "☆",
        server.group,
        server.name,
        server.name,
        server.host,
        "Checking...",
        str(server.game_port),
        str(server.query_port),
        "Checking...",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]
    if not status:
        return values

    values[5] = status.resolved_ip
    if not status.online:
        values[8] = status.display_state
        values[9] = status.user_message()
        return values

    configured_name = server.name if is_displayable_server_name(server.name) else server.host
    values[2] = configured_name
    values[3] = (
        status.server_name if is_displayable_server_name(status.server_name) else configured_name
    )
    values[8] = "ONLINE"
    values[9] = display_map_name(status.map_name)
    values[10] = players_with_queue(status.players, status.queue_count, status.query_started_at)
    values[11] = status.time
    values[12] = f"{status.ping}ms" if status.ping else ""
    values[13] = status.version
    values[14] = display_server_flags(status.password, status.modded)
    values[15] = status.connect
    return values


def curated_status_counts(statuses: list[str]) -> tuple[int, int, int]:
    return (
        statuses.count("ONLINE"),
        statuses.count("OFFLINE"),
        sum(status not in {"ONLINE", "OFFLINE"} for status in statuses),
    )


def all_status_checks_unknown(
    outcomes: dict[int, str], expected_rows: set[int], *, minimum_checks: int = 2
) -> bool:
    return (
        len(expected_rows) >= minimum_checks
        and expected_rows.issubset(outcomes)
        and all(outcomes[row] == "UNKNOWN" for row in expected_rows)
    )
