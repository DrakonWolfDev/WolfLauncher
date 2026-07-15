from .models import Server
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

    flags = []
    if status.password:
        flags.append("Password")
    if status.modded:
        flags.append("Mods")
    values[3] = status.server_name or server.name
    values[8] = "ONLINE"
    values[9] = status.map_name
    values[10] = status.players
    values[11] = status.time
    values[12] = f"{status.ping}ms" if status.ping else ""
    values[13] = status.version
    values[14] = ", ".join(flags) if flags else "Vanilla/unknown"
    values[15] = status.connect
    return values
