from .models import Server
from .server_display import display_map_name, display_server_flags, is_displayable_server_name
from .status import ServerStatus


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
        values[8] = "OFFLINE"
        values[9] = status.error
        return values

    configured_name = server.name if is_displayable_server_name(server.name) else server.host
    values[2] = configured_name
    values[3] = (
        status.server_name if is_displayable_server_name(status.server_name) else configured_name
    )
    values[8] = "ONLINE"
    values[9] = display_map_name(status.map_name)
    values[10] = status.players
    values[11] = status.time
    values[12] = f"{status.ping}ms" if status.ping else ""
    values[13] = status.version
    values[14] = display_server_flags(status.password, status.modded)
    values[15] = status.connect
    return values
