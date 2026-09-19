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
        );
CREATE INDEX IF NOT EXISTS idx_discovered_servers_name ON discovered_servers(display_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_discovered_servers_map ON discovered_servers(map_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_discovered_servers_online ON discovered_servers(online);
CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_servers_stable_server_id ON discovered_servers(stable_server_id) WHERE stable_server_id != '';
CREATE TABLE IF NOT EXISTS discovered_server_aliases (
            endpoint_id TEXT PRIMARY KEY,
            cache_key TEXT NOT NULL,
            FOREIGN KEY(cache_key) REFERENCES discovered_servers(cache_key)
                ON UPDATE CASCADE ON DELETE CASCADE
        );
CREATE INDEX IF NOT EXISTS idx_discovered_server_aliases_cache_key ON discovered_server_aliases(cache_key);
PRAGMA user_version = 7;
