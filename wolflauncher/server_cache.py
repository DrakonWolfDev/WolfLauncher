from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from .models import DiscoveredServer


SCHEMA_VERSION = 1
DATA_DIR = Path.home() / ".local" / "share" / "wolflauncher"
SERVER_CACHE_PATH = DATA_DIR / "server_cache.sqlite3"

SORT_COLUMNS = {
    "name": "display_name COLLATE NOCASE",
    "players": "players_current",
    "ping": "ping_ms",
    "map": "map_name COLLATE NOCASE",
    "version": "version COLLATE NOCASE",
    "last_seen": "last_seen",
}


def ensure_data_dir(path: Path = DATA_DIR) -> None:
    path.mkdir(parents=True, exist_ok=True)


def connect(path: Path = SERVER_CACHE_PATH) -> sqlite3.Connection:
    ensure_data_dir(path.parent)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    initialize(connection)
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS discovered_servers (
            cache_key TEXT PRIMARY KEY,
            source TEXT NOT NULL DEFAULT 'discovered',
            display_name TEXT NOT NULL,
            server_name TEXT NOT NULL DEFAULT '',
            host TEXT NOT NULL,
            game_port INTEGER NOT NULL,
            query_port INTEGER NOT NULL,
            map_name TEXT NOT NULL DEFAULT '',
            players_current INTEGER,
            players_max INTEGER,
            ping_ms INTEGER,
            version TEXT NOT NULL DEFAULT '',
            password INTEGER NOT NULL DEFAULT 0,
            modded INTEGER NOT NULL DEFAULT 0,
            online INTEGER NOT NULL DEFAULT 0,
            last_checked TEXT NOT NULL DEFAULT '',
            last_seen TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovered_servers_name "
        "ON discovered_servers(display_name COLLATE NOCASE)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovered_servers_map "
        "ON discovered_servers(map_name COLLATE NOCASE)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovered_servers_online "
        "ON discovered_servers(online)"
    )
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    connection.commit()


def upsert_server(connection: sqlite3.Connection, server: DiscoveredServer) -> None:
    connection.execute(
        """
        INSERT INTO discovered_servers (
            cache_key, source, display_name, server_name, host, game_port, query_port,
            map_name, players_current, players_max, ping_ms, version, password,
            modded, online, last_checked, last_seen
        )
        VALUES (
            :cache_key, :source, :display_name, :server_name, :host, :game_port, :query_port,
            :map_name, :players_current, :players_max, :ping_ms, :version, :password,
            :modded, :online, :last_checked, :last_seen
        )
        ON CONFLICT(cache_key) DO UPDATE SET
            source = excluded.source,
            display_name = excluded.display_name,
            server_name = excluded.server_name,
            host = excluded.host,
            game_port = excluded.game_port,
            query_port = excluded.query_port,
            map_name = excluded.map_name,
            players_current = excluded.players_current,
            players_max = excluded.players_max,
            ping_ms = excluded.ping_ms,
            version = excluded.version,
            password = excluded.password,
            modded = excluded.modded,
            online = excluded.online,
            last_checked = excluded.last_checked,
            last_seen = excluded.last_seen,
            updated_at = CURRENT_TIMESTAMP
        """,
        _server_params(server),
    )
    connection.commit()


def get_server(connection: sqlite3.Connection, cache_key: str) -> DiscoveredServer | None:
    row = connection.execute(
        "SELECT * FROM discovered_servers WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    return _row_to_server(row) if row else None


def search_servers(
    connection: sqlite3.Connection,
    text: str = "",
    online_only: bool = False,
    map_name: str = "",
    version: str = "",
    modded: bool | None = None,
    sort_by: str = "name",
    descending: bool = False,
    limit: int = 200,
) -> list[DiscoveredServer]:
    clauses = []
    params: list[Any] = []

    text = text.strip()
    if text:
        clauses.append(
            "(display_name COLLATE NOCASE LIKE ? ESCAPE '\\' "
            "OR server_name COLLATE NOCASE LIKE ? ESCAPE '\\' "
            "OR host COLLATE NOCASE LIKE ? ESCAPE '\\')"
        )
        pattern = f"%{_escape_like(text)}%"
        params.extend([pattern, pattern, pattern])

    if online_only:
        clauses.append("online = 1")
    if map_name:
        clauses.append("map_name = ? COLLATE NOCASE")
        params.append(map_name)
    if version:
        clauses.append("version = ? COLLATE NOCASE")
        params.append(version)
    if modded is not None:
        clauses.append("modded = ?")
        params.append(1 if modded else 0)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order_sql = SORT_COLUMNS.get(sort_by, SORT_COLUMNS["name"])
    direction = "DESC" if descending else "ASC"
    limit = max(1, min(int(limit), 1000))

    rows = connection.execute(
        f"""
        SELECT * FROM discovered_servers
        {where_sql}
        ORDER BY {order_sql} {direction}, display_name COLLATE NOCASE ASC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    return [_row_to_server(row) for row in rows]


def _server_params(server: DiscoveredServer) -> dict[str, Any]:
    return {
        "cache_key": server.cache_key,
        "source": server.source,
        "display_name": server.name,
        "server_name": server.server_name,
        "host": server.host,
        "game_port": server.game_port,
        "query_port": server.query_port,
        "map_name": server.map_name,
        "players_current": server.players_current,
        "players_max": server.players_max,
        "ping_ms": server.ping_ms,
        "version": server.version,
        "password": 1 if server.password else 0,
        "modded": 1 if server.modded else 0,
        "online": 1 if server.online else 0,
        "last_checked": server.last_checked,
        "last_seen": server.last_seen,
    }


def _row_to_server(row: sqlite3.Row) -> DiscoveredServer:
    return DiscoveredServer(
        name=str(row["display_name"]),
        source=str(row["source"]),
        server_name=str(row["server_name"]),
        host=str(row["host"]),
        game_port=int(row["game_port"]),
        query_port=int(row["query_port"]),
        map_name=str(row["map_name"]),
        players_current=row["players_current"],
        players_max=row["players_max"],
        ping_ms=row["ping_ms"],
        version=str(row["version"]),
        password=bool(row["password"]),
        modded=bool(row["modded"]),
        online=bool(row["online"]),
        last_checked=str(row["last_checked"]),
        last_seen=str(row["last_seen"]),
    )


def _escape_like(value: str) -> str:
    return re.sub(r"([%_\\])", r"\\\1", value)
