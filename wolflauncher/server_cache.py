from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from .models import DiscoveredServer


SCHEMA_VERSION = 2
DATA_DIR = Path.home() / ".local" / "share" / "wolflauncher"
SERVER_CACHE_PATH = DATA_DIR / "server_cache.sqlite3"

SORT_COLUMNS = {
    "name": "display_name COLLATE NOCASE",
    "players": "players_current IS NULL, players_current",
    "ping": "ping_ms IS NULL, ping_ms",
    "map": "map_name COLLATE NOCASE",
    "version": "version COLLATE NOCASE",
    "last_checked": "TRIM(last_checked) = '', last_checked",
    "last_seen": "TRIM(last_seen) = '', last_seen",
}

FILTER_COLUMNS = {
    "map": "map_name",
    "version": "version",
    "source": "source",
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
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version > SCHEMA_VERSION:
        raise RuntimeError(
            f"Server cache schema version {version} is newer than WolfLauncher supports ({SCHEMA_VERSION})."
        )
    if version == 0:
        _initialize_schema_v1(connection)
    elif version < SCHEMA_VERSION:
        _migrate(connection, version, SCHEMA_VERSION)
    else:
        _initialize_schema_v1(connection)
    connection.commit()


def _initialize_schema_v1(connection: sqlite3.Connection) -> None:
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
            stable_server_id TEXT NOT NULL DEFAULT '',
            endpoint_aliases TEXT NOT NULL DEFAULT '[]',
            freshness TEXT NOT NULL DEFAULT '',
            freshness_expires_at TEXT NOT NULL DEFAULT '',
            validation_status TEXT NOT NULL DEFAULT '',
            validation_checked_at TEXT NOT NULL DEFAULT '',
            validation_seen_at TEXT NOT NULL DEFAULT '',
            validation_error_code TEXT NOT NULL DEFAULT '',
            provider_last_checked TEXT NOT NULL DEFAULT '',
            provider_last_seen TEXT NOT NULL DEFAULT '',
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
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_servers_stable_server_id "
        "ON discovered_servers(stable_server_id) WHERE stable_server_id != ''"
    )
    _initialize_alias_schema(connection)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _initialize_alias_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS discovered_server_aliases (
            endpoint_id TEXT PRIMARY KEY,
            cache_key TEXT NOT NULL,
            FOREIGN KEY(cache_key) REFERENCES discovered_servers(cache_key)
                ON UPDATE CASCADE ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovered_server_aliases_cache_key "
        "ON discovered_server_aliases(cache_key)"
    )


def _migrate(connection: sqlite3.Connection, current_version: int, target_version: int) -> None:
    if current_version == 1 and target_version >= 2:
        for definition in (
            "stable_server_id TEXT NOT NULL DEFAULT ''",
            "endpoint_aliases TEXT NOT NULL DEFAULT '[]'",
            "freshness TEXT NOT NULL DEFAULT ''",
            "freshness_expires_at TEXT NOT NULL DEFAULT ''",
            "validation_status TEXT NOT NULL DEFAULT ''",
            "validation_checked_at TEXT NOT NULL DEFAULT ''",
            "validation_seen_at TEXT NOT NULL DEFAULT ''",
            "validation_error_code TEXT NOT NULL DEFAULT ''",
            "provider_last_checked TEXT NOT NULL DEFAULT ''",
            "provider_last_seen TEXT NOT NULL DEFAULT ''",
        ):
            connection.execute(f"ALTER TABLE discovered_servers ADD COLUMN {definition}")
        connection.execute(
            "CREATE UNIQUE INDEX idx_discovered_servers_stable_server_id "
            "ON discovered_servers(stable_server_id) WHERE stable_server_id != ''"
        )
        _initialize_alias_schema(connection)
        connection.execute("PRAGMA user_version = 2")
        current_version = 2
    if current_version != target_version:
        raise RuntimeError(
            f"Unsupported server cache migration from version {current_version} to {target_version}."
        )


def upsert_server(connection: sqlite3.Connection, server: DiscoveredServer) -> None:
    _upsert_server(connection, server)
    connection.commit()


def _upsert_server(connection: sqlite3.Connection, server: DiscoveredServer) -> None:
    if server.stable_server_id:
        existing = connection.execute(
            "SELECT cache_key FROM discovered_servers WHERE stable_server_id = ?",
            (server.stable_server_id,),
        ).fetchone()
        if existing and existing["cache_key"] != server.cache_key:
            conflict = connection.execute(
                "SELECT stable_server_id FROM discovered_servers WHERE cache_key = ?",
                (server.cache_key,),
            ).fetchone()
            if conflict and conflict["stable_server_id"] not in {"", server.stable_server_id}:
                raise ValueError("Corrected endpoint belongs to another stable server.")
            connection.execute(
                "DELETE FROM discovered_servers WHERE cache_key = ?",
                (existing["cache_key"],),
            )
    connection.execute(
        """
        INSERT INTO discovered_servers (
            cache_key, source, display_name, server_name, host, game_port, query_port,
            map_name, players_current, players_max, ping_ms, version, password,
            modded, online, last_checked, last_seen, stable_server_id,
            endpoint_aliases, freshness, freshness_expires_at, validation_status,
            validation_checked_at, validation_seen_at, validation_error_code,
            provider_last_checked, provider_last_seen
        )
        VALUES (
            :cache_key, :source, :display_name, :server_name, :host, :game_port, :query_port,
            :map_name, :players_current, :players_max, :ping_ms, :version, :password,
            :modded, :online, :last_checked, :last_seen, :stable_server_id,
            :endpoint_aliases, :freshness, :freshness_expires_at, :validation_status,
            :validation_checked_at, :validation_seen_at, :validation_error_code,
            :provider_last_checked, :provider_last_seen
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
            stable_server_id = excluded.stable_server_id,
            endpoint_aliases = excluded.endpoint_aliases,
            freshness = excluded.freshness,
            freshness_expires_at = excluded.freshness_expires_at,
            validation_status = excluded.validation_status,
            validation_checked_at = excluded.validation_checked_at,
            validation_seen_at = excluded.validation_seen_at,
            validation_error_code = excluded.validation_error_code,
            provider_last_checked = excluded.provider_last_checked,
            provider_last_seen = excluded.provider_last_seen,
            updated_at = CURRENT_TIMESTAMP
        """,
        _server_params(server),
    )
    if server.stable_server_id:
        aliases = {server.cache_key, *server.endpoint_aliases}
        connection.execute(
            "DELETE FROM discovered_server_aliases WHERE cache_key = ?",
            (server.cache_key,),
        )
        connection.executemany(
            """
            INSERT INTO discovered_server_aliases (endpoint_id, cache_key)
            VALUES (?, ?)
            ON CONFLICT(endpoint_id) DO UPDATE SET cache_key = excluded.cache_key
            """,
            [(alias, server.cache_key) for alias in sorted(aliases) if alias],
        )


def upsert_servers(connection: sqlite3.Connection, servers: list[DiscoveredServer]) -> int:
    for server in servers:
        _upsert_server(connection, server)
    connection.commit()
    return len(servers)


def merge_source_servers(
    connection: sqlite3.Connection,
    source: str,
    servers: list[DiscoveredServer],
) -> int:
    """Merge a bounded provider page without deleting rows outside that page."""
    source = source.strip()
    if not source:
        raise ValueError("Discovery source is required.")
    normalized = [replace(server, source=source) for server in servers]
    return upsert_servers(connection, normalized)


def sync_source_servers(
    connection: sqlite3.Connection,
    source: str,
    servers: list[DiscoveredServer],
) -> tuple[int, int]:
    source = source.strip()
    if not source:
        raise ValueError("Discovery source is required.")

    normalized = [replace(server, source=source) for server in servers]
    keys = {server.cache_key for server in normalized}
    before = connection.execute(
        "SELECT COUNT(*) FROM discovered_servers WHERE source = ?",
        (source,),
    ).fetchone()[0]
    existing_stable_ids = {
        row["stable_server_id"]
        for row in connection.execute(
            "SELECT stable_server_id FROM discovered_servers "
            "WHERE source = ? AND stable_server_id != ''",
            (source,),
        ).fetchall()
    }

    for server in normalized:
        if server.stable_server_id:
            _upsert_server(connection, server)

    connection.execute("CREATE TEMP TABLE IF NOT EXISTS current_source_keys (cache_key TEXT PRIMARY KEY)")
    connection.execute("DELETE FROM current_source_keys")
    if keys:
        connection.executemany(
            "INSERT OR IGNORE INTO current_source_keys (cache_key) VALUES (?)",
            [(key,) for key in keys],
        )

    connection.execute(
        """
        DELETE FROM discovered_servers
        WHERE source = ?
        AND cache_key NOT IN (SELECT cache_key FROM current_source_keys)
        """,
        (source,),
    )

    existing_keys = {
        row["cache_key"]
        for row in connection.execute(
            "SELECT cache_key FROM discovered_servers WHERE cache_key IN (SELECT cache_key FROM current_source_keys)"
        ).fetchall()
    }
    inserted = 0
    for server in normalized:
        if server.stable_server_id:
            if server.stable_server_id not in existing_stable_ids:
                inserted += 1
            continue
        if server.cache_key in existing_keys:
            continue
        _upsert_server(connection, server)
        existing_keys.add(server.cache_key)
        inserted += 1

    after = connection.execute(
        "SELECT COUNT(*) FROM discovered_servers WHERE source = ?",
        (source,),
    ).fetchone()[0]
    connection.execute("DELETE FROM current_source_keys")
    connection.commit()
    removed = max(0, before + inserted - after)
    return inserted, removed


def clear_source_servers(connection: sqlite3.Connection, source: str) -> int:
    source = source.strip()
    if not source:
        raise ValueError("Discovery source is required.")
    before = connection.execute(
        "SELECT COUNT(*) FROM discovered_servers WHERE source = ?",
        (source,),
    ).fetchone()[0]
    connection.execute("DELETE FROM discovered_servers WHERE source = ?", (source,))
    connection.commit()
    return int(before)


def import_servers_from_file(connection: sqlite3.Connection, path: Path) -> int:
    servers = load_discovered_servers(path)
    return upsert_servers(connection, servers)


def load_discovered_servers(path: Path) -> list[DiscoveredServer]:
    data = _load_import_data(path)
    items = data.get("servers", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("Discovered server import must contain a list or a 'servers' list.")
    return [_server_from_import_item(item, index) for index, item in enumerate(items, start=1)]


def get_server(connection: sqlite3.Connection, cache_key: str) -> DiscoveredServer | None:
    row = connection.execute(
        "SELECT * FROM discovered_servers WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    return _row_to_server(row) if row else None


def get_server_by_endpoint_alias(
    connection: sqlite3.Connection,
    endpoint_id: str,
) -> DiscoveredServer | None:
    row = connection.execute(
        """
        SELECT discovered_servers.*
        FROM discovered_server_aliases
        JOIN discovered_servers
            ON discovered_servers.cache_key = discovered_server_aliases.cache_key
        WHERE discovered_server_aliases.endpoint_id = ?
        """,
        (endpoint_id,),
    ).fetchone()
    return _row_to_server(row) if row else None


def search_servers(
    connection: sqlite3.Connection,
    text: str = "",
    online_only: bool = False,
    map_name: str = "",
    version: str = "",
    source: str = "",
    style_terms: list[str] | None = None,
    modded: bool | None = None,
    sort_by: str = "name",
    descending: bool = False,
    limit: int = 200,
) -> list[DiscoveredServer]:
    where_sql, params = _search_where(
        text=text,
        online_only=online_only,
        map_name=map_name,
        version=version,
        source=source,
        style_terms=style_terms,
        modded=modded,
    )
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


def count_search_servers(
    connection: sqlite3.Connection,
    text: str = "",
    online_only: bool = False,
    map_name: str = "",
    version: str = "",
    source: str = "",
    style_terms: list[str] | None = None,
    modded: bool | None = None,
) -> int:
    where_sql, params = _search_where(
        text=text,
        online_only=online_only,
        map_name=map_name,
        version=version,
        source=source,
        style_terms=style_terms,
        modded=modded,
    )
    row = connection.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM discovered_servers
        {where_sql}
        """,
        params,
    ).fetchone()
    return int(row["count"])


def cache_summary(connection: sqlite3.Connection) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN online = 1 THEN 1 ELSE 0 END), 0) AS online,
            COALESCE(SUM(CASE WHEN TRIM(last_checked) != '' THEN 1 ELSE 0 END), 0) AS checked,
            COALESCE(SUM(CASE WHEN TRIM(last_seen) != '' THEN 1 ELSE 0 END), 0) AS seen
        FROM discovered_servers
        """
    ).fetchone()
    return {
        "total": int(row["total"]),
        "online": int(row["online"]),
        "checked": int(row["checked"]),
        "seen": int(row["seen"]),
    }


def distinct_values(connection: sqlite3.Connection, field: str, limit: int = 250) -> list[str]:
    column = FILTER_COLUMNS.get(field)
    if not column:
        raise ValueError(f"Unsupported distinct server field: {field}")
    limit = max(1, min(int(limit), 1000))
    rows = connection.execute(
        f"""
        SELECT DISTINCT {column} AS value
        FROM discovered_servers
        WHERE {column} IS NOT NULL AND TRIM({column}) != ''
        ORDER BY {column} COLLATE NOCASE ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [str(row["value"]) for row in rows]


def _search_where(
    text: str = "",
    online_only: bool = False,
    map_name: str = "",
    version: str = "",
    source: str = "",
    style_terms: list[str] | None = None,
    modded: bool | None = None,
) -> tuple[str, list[Any]]:
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

    terms = [term.strip() for term in (style_terms or []) if term.strip()]
    if terms:
        term_clauses = []
        for term in terms:
            term_clauses.append(
                "(display_name COLLATE NOCASE LIKE ? ESCAPE '\\' "
                "OR server_name COLLATE NOCASE LIKE ? ESCAPE '\\')"
            )
            pattern = f"%{_escape_like(term)}%"
            params.extend([pattern, pattern])
        clauses.append(f"({' OR '.join(term_clauses)})")

    if online_only:
        clauses.append("online = 1")
    if map_name:
        clauses.append("map_name = ? COLLATE NOCASE")
        params.append(map_name)
    if version:
        clauses.append("version = ? COLLATE NOCASE")
        params.append(version)
    if source:
        clauses.append("source = ? COLLATE NOCASE")
        params.append(source)
    if modded is not None:
        clauses.append("modded = ?")
        params.append(1 if modded else 0)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params


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
        "stable_server_id": server.stable_server_id,
        "endpoint_aliases": json.dumps(list(server.endpoint_aliases)),
        "freshness": server.freshness,
        "freshness_expires_at": server.freshness_expires_at,
        "validation_status": server.validation_status,
        "validation_checked_at": server.validation_checked_at,
        "validation_seen_at": server.validation_seen_at,
        "validation_error_code": server.validation_error_code,
        "provider_last_checked": server.provider_last_checked,
        "provider_last_seen": server.provider_last_seen,
    }


def _load_import_data(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            if path.suffix.lower() == ".json":
                return json.load(handle)
            return yaml.safe_load(handle) or []
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Could not read discovered server import: {exc}") from exc


def _server_from_import_item(item: Any, index: int) -> DiscoveredServer:
    if not isinstance(item, dict):
        raise ValueError(f"Discovered server row {index} must be a mapping.")

    host = _required_text(item, "host", index)
    game_port = _required_int(item, "game_port", index)
    query_port = _required_int(item, "query_port", index)
    name = str(item.get("name") or item.get("display_name") or host)

    return DiscoveredServer(
        name=name,
        source=str(item.get("source") or "import"),
        server_name=str(item.get("server_name") or ""),
        host=host,
        game_port=game_port,
        query_port=query_port,
        map_name=str(item.get("map_name") or item.get("map") or ""),
        players_current=_optional_int(item.get("players_current")),
        players_max=_optional_int(item.get("players_max")),
        ping_ms=_optional_int(item["ping_ms"] if "ping_ms" in item else item.get("ping")),
        version=str(item.get("version") or ""),
        password=_optional_bool(item.get("password", False)),
        modded=_optional_bool(item.get("modded", False)),
        online=_optional_bool(item.get("online", False)),
        last_checked=str(item.get("last_checked") or ""),
        last_seen=str(item.get("last_seen") or ""),
        stable_server_id=str(item.get("stable_server_id") or item.get("server_id") or ""),
        endpoint_aliases=tuple(
            str(alias) for alias in item.get("endpoint_aliases", [])
        ) if isinstance(item.get("endpoint_aliases", []), list) else (),
        freshness=str(item.get("freshness") or ""),
        freshness_expires_at=str(item.get("freshness_expires_at") or ""),
        validation_status=str(item.get("validation_status") or ""),
        validation_checked_at=str(item.get("validation_checked_at") or ""),
        validation_seen_at=str(item.get("validation_seen_at") or ""),
        validation_error_code=str(item.get("validation_error_code") or ""),
        provider_last_checked=str(item.get("provider_last_checked") or ""),
        provider_last_seen=str(item.get("provider_last_seen") or ""),
    )


def _required_text(item: dict[str, Any], key: str, index: int) -> str:
    value = str(item.get(key) or "").strip()
    if not value:
        raise ValueError(f"Discovered server row {index} is missing '{key}'.")
    return value


def _required_int(item: dict[str, Any], key: str, index: int) -> int:
    value = _optional_int(item.get(key))
    if value is None:
        raise ValueError(f"Discovered server row {index} is missing '{key}'.")
    return value


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected integer value, got {value!r}.") from exc


def _optional_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return False
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "on"}:
            return True
        if normalized in {"false", "no", "0", "off"}:
            return False
    raise ValueError(f"Expected boolean value, got {value!r}.")


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
        stable_server_id=str(row["stable_server_id"]),
        endpoint_aliases=tuple(json.loads(row["endpoint_aliases"] or "[]")),
        freshness=str(row["freshness"]),
        freshness_expires_at=str(row["freshness_expires_at"]),
        validation_status=str(row["validation_status"]),
        validation_checked_at=str(row["validation_checked_at"]),
        validation_seen_at=str(row["validation_seen_at"]),
        validation_error_code=str(row["validation_error_code"]),
        provider_last_checked=str(row["provider_last_checked"]),
        provider_last_seen=str(row["provider_last_seen"]),
    )


def _escape_like(value: str) -> str:
    return re.sub(r"([%_\\])", r"\\\1", value)
