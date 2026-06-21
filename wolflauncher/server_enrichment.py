from __future__ import annotations

from .models import DiscoveredServer
from .status import ServerStatus


def enrich_discovered_server(
    server: DiscoveredServer,
    status: ServerStatus,
    checked_at: str,
) -> DiscoveredServer:
    if not status.online:
        return DiscoveredServer(
            name=server.name,
            source=server.source,
            server_name=server.server_name,
            host=server.host,
            game_port=server.game_port,
            query_port=server.query_port,
            map_name=server.map_name,
            players_current=server.players_current,
            players_max=server.players_max,
            ping_ms=server.ping_ms,
            version=server.version,
            password=server.password,
            modded=server.modded,
            online=False,
            last_checked=checked_at,
            last_seen=server.last_seen,
        )

    players_current, players_max = parse_players(status.players)
    game_port = parse_connect_port(status.connect) or server.game_port

    return DiscoveredServer(
        name=server.name,
        source=server.source,
        server_name=status.server_name,
        host=server.host,
        game_port=game_port,
        query_port=server.query_port,
        map_name=status.map_name,
        players_current=players_current,
        players_max=players_max,
        ping_ms=_optional_int(status.ping),
        version=status.version,
        password=status.password,
        modded=status.modded,
        online=True,
        last_checked=checked_at,
        last_seen=checked_at,
    )


def parse_players(value: str) -> tuple[int | None, int | None]:
    if not value or "/" not in value:
        return None, None
    current, maximum = value.split("/", 1)
    return _optional_int(current), _optional_int(maximum)


def parse_connect_port(value: str) -> int | None:
    if not value or ":" not in value:
        return None
    _host, port_text = value.rsplit(":", 1)
    port = _optional_int(port_text)
    if port is None or port <= 0 or port > 65535:
        return None
    return port


def _optional_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
