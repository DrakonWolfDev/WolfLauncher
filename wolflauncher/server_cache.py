from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .models import DiscoveredServer
from .paths import user_data_dir
from .persistence import ensure_private_directory
from .server_identity import identity_fields, merge_identity, normalize_product

SCHEMA_VERSION = 9
SQLITE_BUSY_TIMEOUT_MS = 5000
DATA_DIR = user_data_dir()
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
    ensure_private_directory(path)


def connect(path: Path = SERVER_CACHE_PATH) -> sqlite3.Connection:
    ensure_data_dir(path.parent)
    connection = sqlite3.connect(path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    try:
        initialize(connection)
    except BaseException:
        connection.close()
        raise
    return connection


def connect_recovering(path: Path = SERVER_CACHE_PATH) -> tuple[sqlite3.Connection, Path | None]:
    """Open the disposable cache, retaining a corrupt copy before rebuilding it.

    Only SQLite database errors trigger recovery. Schema-version incompatibility
    remains a visible error because replacing a valid newer cache would hide an
    unsupported downgrade.
    """
    try:
        return connect(path), None
    except sqlite3.DatabaseError:
        quarantined = quarantine_corrupt_cache(path)
        return connect(path), quarantined


def quarantine_corrupt_cache(path: Path) -> Path | None:
    """Move a disposable cache and its sidecars aside without touching user data."""
    if not path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    quarantined = path.with_name(f"{path.stem}.corrupt-{stamp}{path.suffix}")
    path.replace(quarantined)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{path}{suffix}")
        if sidecar.exists():
            sidecar.replace(Path(f"{quarantined}{suffix}"))
    return quarantined


def initialize(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    # The discovered-server cache is disposable. WAL permits the GUI to read it
    # while a background worker completes a short write transaction.
    connection.execute("PRAGMA journal_mode = WAL")
    # Each cache migration is all-or-nothing. The cache is disposable, but a
    # partial schema update would still make the current session unreliable.
    connection.commit()
    connection.execute("BEGIN IMMEDIATE")
    try:
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
    except BaseException:
        connection.rollback()
        raise


def _initialize_schema_v1(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS discovered_servers (
            cache_key TEXT PRIMARY KEY,
            source TEXT NOT NULL DEFAULT 'discovered',
            product TEXT NOT NULL DEFAULT 'unknown',
            identity_state TEXT NOT NULL DEFAULT 'unknown',
            identity_evidence TEXT NOT NULL DEFAULT '[]',
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
            perspective TEXT NOT NULL DEFAULT 'unknown',
            online INTEGER NOT NULL DEFAULT 0,
            last_checked TEXT NOT NULL DEFAULT '',
            last_seen TEXT NOT NULL DEFAULT '',
            required_mod_count INTEGER,
            mod_metadata_status TEXT NOT NULL DEFAULT '',
            mod_metadata_checked_at TEXT NOT NULL DEFAULT '',
            mod_metadata_expires_at TEXT NOT NULL DEFAULT '',
            mod_metadata_error_code TEXT NOT NULL DEFAULT '',
            mod_manifest_hash TEXT NOT NULL DEFAULT '',
            status_source TEXT NOT NULL DEFAULT 'provider',
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
            quality_flags TEXT NOT NULL DEFAULT '[]',
            country_code TEXT NOT NULL DEFAULT '',
            country_source TEXT NOT NULL DEFAULT '',
            game_time TEXT NOT NULL DEFAULT '',
            day_acceleration REAL,
            night_acceleration REAL,
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
        "CREATE INDEX IF NOT EXISTS idx_discovered_servers_online ON discovered_servers(online)"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_servers_stable_server_id "
        "ON discovered_servers(product, stable_server_id) WHERE stable_server_id != ''"
    )
    _initialize_alias_schema(connection)
    _initialize_identity_indexes(connection)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _initialize_identity_indexes(connection):
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovered_endpoint "
        "ON discovered_servers(host, game_port, query_port)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_discovered_product_name "
        "ON discovered_servers(product, display_name COLLATE NOCASE)"
    )


def _initialize_alias_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS discovered_server_aliases (
            endpoint_id TEXT NOT NULL,
            product TEXT NOT NULL DEFAULT 'unknown',
            cache_key TEXT NOT NULL,
            PRIMARY KEY(product, endpoint_id),
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
    if current_version in (1, 2) and target_version >= 3:
        definitions = (
            "required_mod_count INTEGER",
            "status_source TEXT NOT NULL DEFAULT 'provider'",
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
        )
        existing_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(discovered_servers)")
        }
        for definition in definitions:
            column_name = definition.split(" ", 1)[0]
            if column_name not in existing_columns:
                connection.execute(f"ALTER TABLE discovered_servers ADD COLUMN {definition}")
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_servers_stable_server_id "
            "ON discovered_servers(stable_server_id) WHERE stable_server_id != ''"
        )
        _initialize_alias_schema(connection)
        connection.execute("PRAGMA user_version = 3")
        current_version = 3
    if current_version == 3 and target_version >= 4:
        for definition in (
            "mod_metadata_status TEXT NOT NULL DEFAULT ''",
            "mod_metadata_checked_at TEXT NOT NULL DEFAULT ''",
            "mod_metadata_expires_at TEXT NOT NULL DEFAULT ''",
            "mod_metadata_error_code TEXT NOT NULL DEFAULT ''",
            "mod_manifest_hash TEXT NOT NULL DEFAULT ''",
        ):
            connection.execute(f"ALTER TABLE discovered_servers ADD COLUMN {definition}")
        connection.execute("PRAGMA user_version = 4")
        current_version = 4
    if current_version == 4 and target_version >= 5:
        connection.execute(
            "ALTER TABLE discovered_servers ADD COLUMN quality_flags TEXT NOT NULL DEFAULT '[]'"
        )
        connection.execute("PRAGMA user_version = 5")
        current_version = 5
    if current_version == 5 and target_version >= 6:
        connection.execute(
            "ALTER TABLE discovered_servers ADD COLUMN country_code TEXT NOT NULL DEFAULT ''"
        )
        connection.execute(
            "ALTER TABLE discovered_servers ADD COLUMN country_source TEXT NOT NULL DEFAULT ''"
        )
        connection.execute("PRAGMA user_version = 6")
        current_version = 6
    if current_version == 6 and target_version >= 7:
        for definition in (
            "game_time TEXT NOT NULL DEFAULT ''",
            "day_acceleration REAL",
            "night_acceleration REAL",
        ):
            connection.execute(f"ALTER TABLE discovered_servers ADD COLUMN {definition}")
        connection.execute("PRAGMA user_version = 7")
        current_version = 7
    if current_version == 7 and target_version >= 8:
        for definition in (
            "product TEXT NOT NULL DEFAULT 'unknown'",
            "identity_state TEXT NOT NULL DEFAULT 'unknown'",
            "identity_evidence TEXT NOT NULL DEFAULT '[]'",
        ):
            connection.execute(f"ALTER TABLE discovered_servers ADD COLUMN {definition}")
        # Historical source labels are hints, not proof of the live game.
        connection.execute("DROP INDEX IF EXISTS idx_discovered_servers_stable_server_id")
        connection.execute(
            "CREATE UNIQUE INDEX idx_discovered_servers_stable_server_id "
            "ON discovered_servers(product, stable_server_id) WHERE stable_server_id != ''"
        )
        connection.execute("ALTER TABLE discovered_server_aliases RENAME TO legacy_aliases")
        connection.execute("DROP INDEX IF EXISTS idx_discovered_server_aliases_cache_key")
        _initialize_alias_schema(connection)
        connection.execute(
            "INSERT INTO discovered_server_aliases(endpoint_id, cache_key) "
            "SELECT endpoint_id, cache_key FROM legacy_aliases"
        )
        connection.execute("DROP TABLE legacy_aliases")
        _initialize_identity_indexes(connection)
        connection.execute("PRAGMA user_version = 8")
        current_version = 8
    if current_version == 8 and target_version >= 9:
        connection.execute(
            "ALTER TABLE discovered_servers ADD COLUMN perspective TEXT NOT NULL DEFAULT 'unknown'"
        )
        connection.execute("PRAGMA user_version = 9")
        current_version = 9
    if current_version != target_version:
        raise RuntimeError(
            f"Unsupported server cache migration from version {current_version} to {target_version}."
        )


def upsert_server(connection: sqlite3.Connection, server: DiscoveredServer) -> None:
    with connection:
        _upsert_server(connection, server)


def replace_server_key(
    connection: sqlite3.Connection, old_cache_key: str, server: DiscoveredServer
) -> None:
    """Upsert an enriched row and remove its obsolete pre-correction key."""
    with connection:
        _upsert_server(connection, server)
        if old_cache_key and old_cache_key != server.cache_key:
            connection.execute(
                "DELETE FROM discovered_servers WHERE cache_key = ?", (old_cache_key,)
            )


def _upsert_server(connection: sqlite3.Connection, server: DiscoveredServer) -> None:
    previous = get_server(connection, server.cache_key)
    if previous:
        server = replace(
            server,
            **merge_identity(previous, server),
            endpoint_aliases=tuple(
                dict.fromkeys((*server.endpoint_aliases, *previous.endpoint_aliases))
            ),
        )
    others = connection.execute(
        "SELECT * FROM discovered_servers WHERE host = ? AND game_port = ? "
        "AND query_port = ? AND product != ? AND product != 'unknown'",
        (server.host, server.game_port, server.query_port, server.product),
    ).fetchall()
    if server.product != "unknown":
        for row in others:
            other = _row_to_server(row)
            merged = merge_identity(other, server)
            connection.execute(
                "UPDATE discovered_servers SET identity_state = ?, identity_evidence = ?, "
                "required_mod_count = NULL, mod_manifest_hash = '', mod_metadata_status = '' "
                "WHERE cache_key = ?",
                (
                    merged["identity_state"],
                    json.dumps(merged["identity_evidence"]),
                    other.cache_key,
                ),
            )
            server = replace(
                server,
                **merge_identity(server, other),
                required_mod_count=None,
                mod_manifest_hash="",
                mod_metadata_status="",
            )
    if server.stable_server_id:
        existing = connection.execute(
            "SELECT * FROM discovered_servers WHERE stable_server_id = ? AND product = ?",
            (server.stable_server_id, server.product),
        ).fetchone()
        if existing:
            prior = _row_to_server(existing)
            server = replace(
                server,
                **merge_identity(prior, server),
                endpoint_aliases=tuple(
                    dict.fromkeys(
                        (*server.endpoint_aliases, *prior.endpoint_aliases, prior.cache_key)
                    )
                ),
            )
        if existing and server.status_source != "local":
            server = replace(
                server,
                game_time=str(existing["game_time"]),
                day_acceleration=_optional_float(existing["day_acceleration"]),
                night_acceleration=_optional_float(existing["night_acceleration"]),
            )
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
            product, identity_state, identity_evidence,
            cache_key, source, display_name, server_name, host, game_port, query_port,
            map_name, players_current, players_max, ping_ms, version, password,
            modded, perspective, online, last_checked, last_seen, required_mod_count,
            mod_metadata_status, mod_metadata_checked_at,
            mod_metadata_expires_at, mod_metadata_error_code, mod_manifest_hash,
            status_source, stable_server_id,
            endpoint_aliases, freshness, freshness_expires_at, validation_status,
            validation_checked_at, validation_seen_at, validation_error_code,
            provider_last_checked, provider_last_seen, quality_flags,
            country_code, country_source, game_time,
            day_acceleration, night_acceleration
        )
        VALUES (
            :product, :identity_state, :identity_evidence,
            :cache_key, :source, :display_name, :server_name, :host, :game_port, :query_port,
            :map_name, :players_current, :players_max, :ping_ms, :version, :password,
            :modded, :perspective, :online, :last_checked, :last_seen, :required_mod_count,
            :mod_metadata_status, :mod_metadata_checked_at,
            :mod_metadata_expires_at, :mod_metadata_error_code, :mod_manifest_hash,
            :status_source, :stable_server_id,
            :endpoint_aliases, :freshness, :freshness_expires_at, :validation_status,
            :validation_checked_at, :validation_seen_at, :validation_error_code,
            :provider_last_checked, :provider_last_seen, :quality_flags,
            :country_code, :country_source, :game_time,
            :day_acceleration, :night_acceleration
        )
        ON CONFLICT(cache_key) DO UPDATE SET
            identity_state = excluded.identity_state,
            identity_evidence = excluded.identity_evidence,
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
            perspective = excluded.perspective,
            online = excluded.online,
            last_checked = excluded.last_checked,
            last_seen = excluded.last_seen,
            required_mod_count = excluded.required_mod_count,
            mod_metadata_status = excluded.mod_metadata_status,
            mod_metadata_checked_at = excluded.mod_metadata_checked_at,
            mod_metadata_expires_at = excluded.mod_metadata_expires_at,
            mod_metadata_error_code = excluded.mod_metadata_error_code,
            mod_manifest_hash = excluded.mod_manifest_hash,
            status_source = excluded.status_source,
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
            quality_flags = excluded.quality_flags,
            country_code = excluded.country_code,
            country_source = excluded.country_source,
            game_time = CASE WHEN excluded.status_source = 'local'
                THEN excluded.game_time ELSE discovered_servers.game_time END,
            day_acceleration = CASE WHEN excluded.status_source = 'local'
                THEN excluded.day_acceleration ELSE discovered_servers.day_acceleration END,
            night_acceleration = CASE WHEN excluded.status_source = 'local'
                THEN excluded.night_acceleration ELSE discovered_servers.night_acceleration END,
            updated_at = CURRENT_TIMESTAMP
        """,
        _server_params(server),
    )
    aliases = {
        server.cache_key,
        f"{server.host}:{server.game_port}:{server.query_port}",
        *server.endpoint_aliases,
    }
    for alias in aliases:
        owner = connection.execute(
            "SELECT cache_key FROM discovered_server_aliases WHERE product = ? AND endpoint_id = ?",
            (server.product, alias),
        ).fetchone()
        if owner is not None and owner["cache_key"] != server.cache_key:
            raise ValueError(f"Endpoint alias {alias!r} belongs to another server in this edition.")
    connection.execute(
        "DELETE FROM discovered_server_aliases WHERE cache_key = ?",
        (server.cache_key,),
    )
    connection.executemany(
        """
        INSERT INTO discovered_server_aliases (endpoint_id, cache_key, product)
        VALUES (?, ?, ?)
        ON CONFLICT(product, endpoint_id) DO UPDATE SET cache_key = excluded.cache_key
        """,
        [(alias, server.cache_key, server.product) for alias in sorted(aliases) if alias],
    )


def upsert_servers(connection: sqlite3.Connection, servers: list[DiscoveredServer]) -> int:
    with connection:
        for server in servers:
            _upsert_server(connection, server)
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
    product: str | None = None,
) -> tuple[int, int]:
    with connection:
        return _sync_source_servers(connection, source, servers, product)


def _sync_source_servers(
    connection: sqlite3.Connection,
    source: str,
    servers: list[DiscoveredServer],
    product: str | None = None,
) -> tuple[int, int]:
    source = source.strip()
    if not source:
        raise ValueError("Discovery source is required.")

    if product is not None and any(
        server.product != normalize_product(product) for server in servers
    ):
        raise ValueError("Server identity does not match source sync scope.")
    scope = "source = ?" + (" AND product = ?" if product is not None else "")
    scope_params = (source, normalize_product(product)) if product is not None else (source,)
    normalized = [replace(server, source=source) for server in servers]
    keys = {server.cache_key for server in normalized}
    before = connection.execute(
        f"SELECT COUNT(*) FROM discovered_servers WHERE {scope}",
        scope_params,
    ).fetchone()[0]
    existing_stable_ids = {
        (row["product"], row["stable_server_id"])
        for row in connection.execute(
            "SELECT product, stable_server_id FROM discovered_servers "
            f"WHERE {scope} AND stable_server_id != ''",
            scope_params,
        ).fetchall()
    }

    for server in normalized:
        if server.stable_server_id:
            _upsert_server(connection, server)

    connection.execute(
        "CREATE TEMP TABLE IF NOT EXISTS current_source_keys (cache_key TEXT PRIMARY KEY)"
    )
    connection.execute("DELETE FROM current_source_keys")
    if keys:
        connection.executemany(
            "INSERT OR IGNORE INTO current_source_keys (cache_key) VALUES (?)",
            [(key,) for key in keys],
        )

    connection.execute(
        f"""
        DELETE FROM discovered_servers
        WHERE {scope}
        AND cache_key NOT IN (SELECT cache_key FROM current_source_keys)
        """,
        scope_params,
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
            if (server.product, server.stable_server_id) not in existing_stable_ids:
                inserted += 1
            continue
        if server.cache_key in existing_keys:
            continue
        _upsert_server(connection, server)
        existing_keys.add(server.cache_key)
        inserted += 1

    after = connection.execute(
        f"SELECT COUNT(*) FROM discovered_servers WHERE {scope}",
        scope_params,
    ).fetchone()[0]
    connection.execute("DELETE FROM current_source_keys")
    removed = max(0, before + inserted - after)
    return inserted, removed


def clear_source_servers(
    connection: sqlite3.Connection, source: str, product: str | None = None
) -> int:
    source = source.strip()
    if not source:
        raise ValueError("Discovery source is required.")
    scope = "source = ?" + (" AND product = ?" if product is not None else "")
    params = (source, normalize_product(product)) if product is not None else (source,)
    with connection:
        return connection.execute(f"DELETE FROM discovered_servers WHERE {scope}", params).rowcount


def import_servers_from_file(connection: sqlite3.Connection, path: Path) -> int:
    servers = load_discovered_servers(path)
    return upsert_servers(connection, servers)


def load_discovered_servers(path: Path) -> list[DiscoveredServer]:
    data = _load_import_data(path)
    items = data.get("servers", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("Discovered server import must contain a list or a 'servers' list.")
    return [_server_from_import_item(item, index) for index, item in enumerate(items, start=1)]


def get_server(
    connection: sqlite3.Connection, cache_key: str, product: str | None = None
) -> DiscoveredServer | None:
    if product is not None and normalize_product(product) != "unknown" and "|" not in cache_key:
        cache_key = f"{normalize_product(product)}|{cache_key}"
    row = connection.execute(
        "SELECT * FROM discovered_servers WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    return _row_to_server(row) if row else None


def get_server_by_endpoint_alias(
    connection: sqlite3.Connection,
    endpoint_id: str,
    product: str | None = None,
) -> DiscoveredServer | None:
    clause = " AND discovered_server_aliases.product = ?" if product is not None else ""
    params = (endpoint_id, normalize_product(product)) if product is not None else (endpoint_id,)
    rows = connection.execute(
        "SELECT discovered_servers.* FROM discovered_server_aliases "
        "JOIN discovered_servers ON discovered_servers.cache_key = discovered_server_aliases.cache_key "
        "WHERE discovered_server_aliases.endpoint_id = ?" + clause,
        params,
    ).fetchall()
    return _row_to_server(rows[0]) if len(rows) == 1 else None


def search_servers(
    connection: sqlite3.Connection,
    text: str = "",
    online_only: bool = False,
    map_name: str = "",
    version: str = "",
    source: str = "",
    source_namespace: str = "",
    products: tuple[str, ...] | None = None,
    style_terms: list[str] | None = None,
    modded: bool | None = None,
    perspective: str = "",
    hide_quality_flagged: bool = False,
    hide_malformed_names: bool = False,
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
        source_namespace=source_namespace,
        products=products,
        style_terms=style_terms,
        modded=modded,
        perspective=perspective,
        hide_quality_flagged=hide_quality_flagged,
        hide_malformed_names=hide_malformed_names,
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
    source_namespace: str = "",
    products: tuple[str, ...] | None = None,
    style_terms: list[str] | None = None,
    modded: bool | None = None,
    perspective: str = "",
    hide_quality_flagged: bool = False,
    hide_malformed_names: bool = False,
) -> int:
    where_sql, params = _search_where(
        text=text,
        online_only=online_only,
        map_name=map_name,
        version=version,
        source=source,
        source_namespace=source_namespace,
        products=products,
        style_terms=style_terms,
        modded=modded,
        perspective=perspective,
        hide_quality_flagged=hide_quality_flagged,
        hide_malformed_names=hide_malformed_names,
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


def cache_summary(
    connection: sqlite3.Connection, products: tuple[str, ...] | None = None
) -> dict[str, int]:
    where, params = _search_where(products=products)
    row = connection.execute(
        f"""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN online = 1 THEN 1 ELSE 0 END), 0) AS online,
            COALESCE(SUM(CASE WHEN TRIM(last_checked) != '' THEN 1 ELSE 0 END), 0) AS checked,
            COALESCE(SUM(CASE WHEN TRIM(last_seen) != '' THEN 1 ELSE 0 END), 0) AS seen
        FROM discovered_servers
        {where}
        """,
        params,
    ).fetchone()
    return {
        "total": int(row["total"]),
        "online": int(row["online"]),
        "checked": int(row["checked"]),
        "seen": int(row["seen"]),
    }


def distinct_values(
    connection: sqlite3.Connection,
    field: str,
    limit: int = 250,
    products: tuple[str, ...] | None = None,
) -> list[str]:
    column = FILTER_COLUMNS.get(field)
    if not column:
        raise ValueError(f"Unsupported distinct server field: {field}")
    limit = max(1, min(int(limit), 1000))
    product_clause = (
        " AND product IN (" + ",".join("?" for _ in products) + ")"
        if products
        else " AND 0"
        if products is not None
        else ""
    )
    rows = connection.execute(
        f"""
        SELECT DISTINCT {column} AS value
        FROM discovered_servers
        WHERE {column} IS NOT NULL AND TRIM({column}) != '' {product_clause}
        ORDER BY {column} COLLATE NOCASE ASC
        LIMIT ?
        """,
        (*[normalize_product(p) for p in products or ()], limit),
    ).fetchall()
    return [str(row["value"]) for row in rows]


def _search_where(
    text: str = "",
    online_only: bool = False,
    map_name: str = "",
    version: str = "",
    source: str = "",
    source_namespace: str = "",
    products: tuple[str, ...] | None = None,
    style_terms: list[str] | None = None,
    modded: bool | None = None,
    perspective: str = "",
    hide_quality_flagged: bool = False,
    hide_malformed_names: bool = False,
) -> tuple[str, list[Any]]:
    clauses = []
    params: list[Any] = []
    if products is not None:
        clauses.append("product IN (" + ",".join("?" for _ in products) + ")" if products else "0")
        params.extend(normalize_product(p) for p in products)

    text = text.strip()
    if text:
        clauses.append(
            "(display_name COLLATE NOCASE LIKE ? ESCAPE '\\' "
            "OR server_name COLLATE NOCASE LIKE ? ESCAPE '\\' "
            "OR host COLLATE NOCASE LIKE ? ESCAPE '\\' "
            "OR cache_key COLLATE NOCASE LIKE ? ESCAPE '\\' "
            "OR EXISTS (SELECT 1 FROM discovered_server_aliases AS search_alias "
            "WHERE search_alias.cache_key = discovered_servers.cache_key "
            "AND search_alias.endpoint_id COLLATE NOCASE LIKE ? ESCAPE '\\'))"
        )
        pattern = f"%{_escape_like(text)}%"
        params.extend([pattern, pattern, pattern, pattern, pattern])

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
        if map_name.casefold() == "livonia":
            clauses.append("map_name COLLATE NOCASE IN (?, ?)")
            params.extend(["enoch", "livonia"])
        else:
            clauses.append("map_name = ? COLLATE NOCASE")
            params.append(map_name)
    if version:
        clauses.append("version = ? COLLATE NOCASE")
        params.append(version)
    if source:
        clauses.append("source = ? COLLATE NOCASE")
        params.append(source)
    if source_namespace:
        clauses.append("source COLLATE NOCASE LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(source_namespace)}")
    if perspective:
        clauses.append("perspective = ?")
        params.append(perspective)
    if modded is not None:
        clauses.append("modded = ?")
        params.append(1 if modded else 0)
    if hide_quality_flagged:
        clauses.append("quality_flags = '[]'")
    if hide_malformed_names:
        clauses.append("INSTR(display_name, ?) = 0")
        params.append("\ufffd")
        clauses.append("display_name NOT GLOB ?")
        params.append(f"*[{chr(1)}-{chr(31)}]*")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params


def _server_params(server: DiscoveredServer) -> dict[str, Any]:
    return {
        **identity_fields(server),
        "identity_evidence": json.dumps(server.identity_evidence),
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
        "perspective": server.perspective,
        "online": 1 if server.online else 0,
        "last_checked": server.last_checked,
        "last_seen": server.last_seen,
        "required_mod_count": server.required_mod_count,
        "mod_metadata_status": server.mod_metadata_status,
        "mod_metadata_checked_at": server.mod_metadata_checked_at,
        "mod_metadata_expires_at": server.mod_metadata_expires_at,
        "mod_metadata_error_code": server.mod_metadata_error_code,
        "mod_manifest_hash": server.mod_manifest_hash,
        "status_source": server.status_source,
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
        "quality_flags": json.dumps(list(server.quality_flags)),
        "country_code": server.country_code,
        "country_source": server.country_source,
        "game_time": server.game_time,
        "day_acceleration": server.day_acceleration,
        "night_acceleration": server.night_acceleration,
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
    country_code = _country_code(item.get("country_code"))
    country_source = str(item.get("country_source") or "").strip().lower()
    if country_source != "battlemetrics":
        country_code = ""
        country_source = ""

    return DiscoveredServer(
        **identity_fields(item),
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
        perspective=item.get("perspective", "unknown"),
        online=_optional_bool(item.get("online", False)),
        last_checked=str(item.get("last_checked") or ""),
        last_seen=str(item.get("last_seen") or ""),
        required_mod_count=_optional_int(item.get("required_mod_count")),
        mod_metadata_status=str(item.get("mod_metadata_status") or ""),
        mod_metadata_checked_at=str(item.get("mod_metadata_checked_at") or ""),
        mod_metadata_expires_at=str(item.get("mod_metadata_expires_at") or ""),
        mod_metadata_error_code=str(item.get("mod_metadata_error_code") or ""),
        mod_manifest_hash=str(item.get("mod_manifest_hash") or ""),
        status_source=str(item.get("status_source") or "provider"),
        stable_server_id=str(item.get("stable_server_id") or item.get("server_id") or ""),
        endpoint_aliases=tuple(str(alias) for alias in item.get("endpoint_aliases", []))
        if isinstance(item.get("endpoint_aliases", []), list)
        else (),
        freshness=str(item.get("freshness") or ""),
        freshness_expires_at=str(item.get("freshness_expires_at") or ""),
        validation_status=str(item.get("validation_status") or ""),
        validation_checked_at=str(item.get("validation_checked_at") or ""),
        validation_seen_at=str(item.get("validation_seen_at") or ""),
        validation_error_code=str(item.get("validation_error_code") or ""),
        provider_last_checked=str(item.get("provider_last_checked") or ""),
        provider_last_seen=str(item.get("provider_last_seen") or ""),
        quality_flags=_quality_flags(item.get("quality_flags")),
        country_code=country_code,
        country_source=country_source,
        game_time=str(item.get("game_time") or ""),
        day_acceleration=_optional_float(item.get("day_acceleration")),
        night_acceleration=_optional_float(item.get("night_acceleration")),
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


def _quality_flags(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                value = stripped
        if isinstance(value, str):
            value = value.split(",")
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _row_to_server(row: sqlite3.Row) -> DiscoveredServer:
    return DiscoveredServer(
        product=row["product"],
        identity_state=row["identity_state"],
        identity_evidence=tuple(json.loads(row["identity_evidence"])),
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
        perspective=row["perspective"],
        online=bool(row["online"]),
        last_checked=str(row["last_checked"]),
        last_seen=str(row["last_seen"]),
        required_mod_count=row["required_mod_count"],
        mod_metadata_status=str(row["mod_metadata_status"]),
        mod_metadata_checked_at=str(row["mod_metadata_checked_at"]),
        mod_metadata_expires_at=str(row["mod_metadata_expires_at"]),
        mod_metadata_error_code=str(row["mod_metadata_error_code"]),
        mod_manifest_hash=str(row["mod_manifest_hash"]),
        status_source=str(row["status_source"] or "provider"),
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
        quality_flags=_quality_flags(row["quality_flags"]),
        country_code=_country_code(row["country_code"]),
        country_source=str(row["country_source"]),
        game_time=str(row["game_time"]),
        day_acceleration=_optional_float(row["day_acceleration"]),
        night_acceleration=_optional_float(row["night_acceleration"]),
    )


def _country_code(value: Any) -> str:
    code = str(value or "").strip().upper()
    return code if len(code) == 2 and code.isalpha() else ""


def _optional_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _escape_like(value: str) -> str:
    return re.sub(r"([%_\\])", r"\\\1", value)
