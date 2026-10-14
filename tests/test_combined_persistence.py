import json
import pickle
import sqlite3
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

import yaml

from wolflauncher import server_cache
from wolflauncher.models import DiscoveredServer, Server
from wolflauncher.persistence import atomic_write_text
from wolflauncher.saved_servers import SavedServerRepository
from wolflauncher.server_identity import (
    LiveIdentity,
    identity_fields,
    provider_identity,
    resolve_launch_identity,
    saved_launch_error,
)
from wolflauncher.settings import normalize_settings, server_key


class CombinedPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def server(self, product="unknown", **kwargs):
        return Server(
            "Original",
            "Community",
            "dayz.test",
            2302,
            27016,
            True,
            **provider_identity(
                None if product == "unknown" else product, "wolfapi", "2026-09-15T00:00:00Z"
            ),
            **kwargs,
        )

    def write_profile(self, servers, experimental=False, extra=None):
        path = self.root / ("servers-experimental.yaml" if experimental else "servers.yaml")
        path.write_text(
            yaml.safe_dump(
                {
                    "servers": [asdict(s) if isinstance(s, Server) else s for s in servers],
                    **(extra or {}),
                }
            )
        )
        return path

    def repository(self):
        repo = SavedServerRepository(self.root)
        return repo, repo.load()

    def cache(self):
        connection = server_cache.connect(self.root / "cache.db")
        self.addCleanup(connection.close)
        return connection

    def discovered(self, product, **kwargs):
        return DiscoveredServer(
            "Original",
            "dayz.test",
            2302,
            27016,
            **provider_identity(product, "wolfapi", "2026-09-15"),
            **kwargs,
        )

    def test_profiles_empty_single_and_both_reopen_without_rewriting(self):
        repo, rows = self.repository()
        self.assertEqual(rows, [])
        for experimental in (False, True):
            self.write_profile([replace(self.server(), host=f"{experimental}.test")], experimental)
            rows = repo.load()
            self.assertEqual(len(rows), 2 if experimental else 1)
            self.assertTrue(all(s.product == "unknown" for s in rows))
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(rows, repo.load())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_alias_collision_rolls_back_entire_cache_write(self):
        connection = self.cache()
        first = self.discovered("stable", stable_server_id="first", endpoint_aliases=("alias",))
        server_cache.upsert_server(connection, first)
        second = replace(first, host="second.test", stable_server_id="second")
        with self.assertRaisesRegex(ValueError, "alias"):
            server_cache.upsert_server(connection, second)
        self.assertIsNone(server_cache.get_server(connection, second.cache_key))
        self.assertEqual(
            server_cache.get_server_by_endpoint_alias(
                connection, "alias", product="stable"
            ).cache_key,
            first.cache_key,
        )

    def test_alias_merged_profiles_remove_all_rows_and_stars(self):
        first = self.server("stable", endpoint_aliases=("other.test:2302:27016",))
        second = replace(first, host="other.test", endpoint_aliases=())
        self.write_profile([first])
        self.write_profile([second], experimental=True)
        (self.root / "favourites-experimental.json").write_text(json.dumps([server_key(second)]))
        repo, rows = self.repository()
        self.assertEqual(len(rows), 1)
        self.assertTrue(repo.remove(rows[0]))
        self.assertEqual(repo.load(), [])
        self.assertEqual(json.loads((self.root / "favourites-experimental.json").read_text()), [])

    def test_unstar_merged_alias_does_not_return_after_restart(self):
        first = self.server("stable", endpoint_aliases=("other.test:2302:27016",))
        self.write_profile([first])
        second = replace(first, host="other.test", endpoint_aliases=())
        self.write_profile([second], experimental=True)
        (self.root / "favourites-experimental.json").write_text(json.dumps([server_key(second)]))
        repo, rows = self.repository()
        self.assertTrue(rows[0].favourite)
        repo.save_favourites(set())
        reopened = SavedServerRepository(self.root).load()
        self.assertEqual(len(reopened), 1)
        self.assertFalse(reopened[0].favourite)

    def test_legacy_rename_preserves_star_and_unknown_yaml_fields(self):
        server = self.server()
        path = self.write_profile(
            [{**asdict(server), "custom": {"keep": True}}], extra={"future": 42}
        )
        (self.root / "favourites.json").write_text(json.dumps(["dayz.test:2302:27016:Old name"]))
        repo, rows = self.repository()
        self.assertTrue(rows[0].favourite)
        self.assertTrue(repo.update(rows[0], replace(rows[0], name="Renamed")))
        saved = yaml.safe_load(path.read_text())
        self.assertEqual(saved["future"], 42)
        self.assertEqual(saved["servers"][0]["custom"], {"keep": True})
        self.assertTrue(repo.load()[0].favourite)
        self.assertTrue(path.with_suffix(".yaml.bak").exists())

    def test_duplicate_profiles_merge_one_star_and_conflicting_evidence(self):
        self.write_profile([replace(self.server("stable"), favourite=False)])
        self.write_profile([self.server("experimental")], True)
        repo, rows = self.repository()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].favourite)
        self.assertEqual(rows[0].identity_state, "conflict")
        self.assertEqual(len(rows[0].identity_evidence), 2)
        self.assertTrue(saved_launch_error(rows[0], "stable"))
        repo.update(rows[0], replace(rows[0], favourite=False))
        self.assertFalse(repo.load()[0].favourite)
        self.assertTrue(repo.remove(repo.load()[0]))
        self.assertEqual(repo.load(), [])

    def test_duplicate_rows_same_file_are_both_updated(self):
        self.write_profile([self.server(), self.server()])
        repo, rows = self.repository()
        repo.update(rows[0], replace(rows[0], name="Renamed"))
        raw = yaml.safe_load((self.root / "servers.yaml").read_text())
        self.assertEqual([r["name"] for r in raw["servers"]], ["Renamed", "Renamed"])

    def test_partially_malformed_profile_recovers_entries_but_refuses_rewrite(self):
        path = self.write_profile([self.server(), {"host": "broken"}, "bad"])
        original = path.read_bytes()
        repo, rows = self.repository()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(repo.errors), 2)
        with self.assertRaises(ValueError):
            repo.update(rows[0], replace(rows[0], name="Changed"))
        self.assertEqual(path.read_bytes(), original)

    def test_invalid_profile_does_not_hide_other_profile(self):
        (self.root / "servers.yaml").write_text("servers: [broken")
        self.write_profile([self.server("experimental")], True)
        repo, rows = self.repository()
        self.assertEqual(len(rows), 1)
        self.assertTrue(repo.errors)

    def test_multifile_failure_rolls_back_and_retry_succeeds(self):
        self.write_profile([self.server()])
        self.write_profile([self.server()], True)
        repo, rows = self.repository()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        writes = 0

        def fail_second(path, text, **kwargs):
            nonlocal writes
            writes += 1
            if writes == 3:  # journal, first profile, then failure
                raise OSError("injected write failure")
            atomic_write_text(path, text, **kwargs)

        with patch("wolflauncher.saved_servers.atomic_write_text", side_effect=fail_second):
            with self.assertRaises(OSError):
                repo.update(rows[0], replace(rows[0], name="Changed"))
        for name, contents in before.items():
            self.assertEqual((self.root / name).read_bytes(), contents)
        self.assertFalse(repo.journal.exists())
        repo.update(rows[0], replace(rows[0], name="Changed"))
        self.assertEqual(repo.load()[0].name, "Changed")

    def test_interrupted_transaction_recovers_on_open(self):
        path = self.write_profile([self.server()])
        original = path.read_text()
        (self.root / "saved-servers-transaction.json").write_text(json.dumps({path.name: original}))
        path.write_text("servers: []")
        repo, rows = self.repository()
        self.assertEqual(len(rows), 1)
        self.assertFalse(repo.journal.exists())
        self.assertEqual(path.read_text(), original)

    def test_misfiled_legacy_favourite_requires_live_resolution(self):
        self.write_profile([self.server()])
        repo, rows = self.repository()
        original = rows[0]
        self.assertEqual(original.product, "unknown")
        self.assertTrue(saved_launch_error(original, "stable"))
        endpoint = (original.host, original.game_port, original.query_port)
        evidence = LiveIdentity(endpoint, "request", 100, 1024020)
        product = resolve_launch_identity(
            evidence, endpoint=endpoint, request_id="request", now=101
        )
        updated = replace(original, **provider_identity(product, "live_gamedig", "2026-09-16"))
        repo.update(original, updated)
        self.assertEqual(repo.load()[0].product, "experimental")
        self.assertTrue(repo.load()[0].favourite)
        self.assertTrue(saved_launch_error(updated, "stable"))
        self.assertFalse(saved_launch_error(updated, "experimental"))
        self.assertTrue((self.root / "servers.yaml").exists())

    def test_product_scoped_cache_ids_aliases_and_conflicts(self):
        connection = self.cache()
        stable = self.discovered(
            "stable",
            stable_server_id="shared",
            endpoint_aliases=("alias:2302:27016",),
            required_mod_count=3,
            mod_manifest_hash="old",
        )
        experimental = self.discovered(
            "experimental", stable_server_id="shared", endpoint_aliases=stable.endpoint_aliases
        )
        server_cache.upsert_servers(connection, [stable, experimental])
        self.assertEqual(server_cache.count_search_servers(connection), 2)
        self.assertIsNone(
            server_cache.get_server_by_endpoint_alias(connection, stable.endpoint_aliases[0])
        )
        for product in ("stable", "experimental"):
            row = server_cache.get_server_by_endpoint_alias(
                connection, stable.endpoint_aliases[0], product
            )
            self.assertEqual(row.product, product)
            self.assertEqual(row.identity_state, "conflict")
            self.assertEqual(row.mod_manifest_hash, "")
        self.assertEqual(
            server_cache.count_search_servers(connection, products=("experimental",)), 1
        )
        server_cache.sync_source_servers(connection, "discovered", [], product="experimental")
        self.assertEqual(server_cache.count_search_servers(connection), 1)

    def test_status_updates_keep_evidence_and_import_worker_roundtrips(self):
        connection = self.cache()
        server = self.discovered(
            "experimental", stable_server_id="id", endpoint_aliases=("alias:2302:27016",)
        )
        path = self.root / "export.json"
        path.write_text(json.dumps([asdict(server)]))
        server_cache.import_servers_from_file(connection, path)
        server_cache.upsert_server(connection, replace(server, identity_evidence=(), online=False))
        cached = server_cache.get_server(connection, server.cache_key)
        self.assertEqual(cached.identity_evidence, server.identity_evidence)
        self.assertEqual(pickle.loads(pickle.dumps(cached)), cached)
        self.assertEqual(
            identity_fields(DiscoveredServer(**json.loads(json.dumps(asdict(cached))))),
            identity_fields(cached),
        )

    def test_settings_migration_retains_engine_preferences_and_unknown_keys(self):
        original = {
            "schema_version": 9,
            "dayz_product": "experimental",
            "launch_engine": "external",
            "future": 42,
        }
        migrated = normalize_settings(original)
        self.assertEqual(migrated["local_tool_product"], "experimental")
        self.assertEqual(migrated["launch_engine"], "external")
        self.assertEqual(migrated["future"], 42)
        self.assertEqual(normalize_settings(migrated), migrated)
        self.assertEqual(
            server_key(self.server()), server_key(replace(self.server(), name="Renamed"))
        )

    def test_corrupted_settings_are_not_replaced_by_defaults(self):
        from wolflauncher import settings

        path = self.root / "settings.json"
        for content in ("{broken", "[]"):
            path.write_text(content)
            with patch.object(settings, "SETTINGS_PATH", path):
                with self.assertRaisesRegex(OSError, "damaged"):
                    settings.save_settings({"launch_engine": "native"})
            self.assertEqual(path.read_text(), content)

    def test_cache_v7_migration_is_atomic_and_repeatable(self):
        path = self.root / "old.db"
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        sql = (Path(__file__).parent / "fixtures/server_cache_v7.sql").read_text()
        connection.executescript(sql)
        connection.execute(
            "INSERT INTO discovered_servers(cache_key,display_name,host,game_port,query_port,stable_server_id) VALUES('dayz.test:2302:27016','Old','dayz.test',2302,27016,'id')"
        )
        connection.execute(
            "INSERT INTO discovered_server_aliases VALUES('alias','dayz.test:2302:27016')"
        )
        connection.commit()
        connection.set_authorizer(
            lambda action, arg1, arg2, db, trigger: (
                sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_ALTER_TABLE else sqlite3.SQLITE_OK
            )
        )
        with self.assertRaises(sqlite3.DatabaseError):
            server_cache.initialize(connection)
        connection.set_authorizer(None)
        self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 7)
        self.assertNotIn(
            "product", {r[1] for r in connection.execute("PRAGMA table_info(discovered_servers)")}
        )
        server_cache.initialize(connection)
        server_cache.initialize(connection)
        self.assertEqual(server_cache.count_search_servers(connection), 1)
        self.assertEqual(
            server_cache.get_server_by_endpoint_alias(connection, "alias").product, "unknown"
        )
        connection.close()

    def test_all_legacy_cache_versions_preserve_rows_when_reopened(self):
        # Derive historical layouts by removing only columns introduced later.
        introduced = {
            3: (
                "required_mod_count",
                "status_source",
                "stable_server_id",
                "endpoint_aliases",
                "freshness",
                "freshness_expires_at",
                "validation_status",
                "validation_checked_at",
                "validation_seen_at",
                "validation_error_code",
                "provider_last_checked",
                "provider_last_seen",
            ),
            4: (
                "mod_metadata_status",
                "mod_metadata_checked_at",
                "mod_metadata_expires_at",
                "mod_metadata_error_code",
                "mod_manifest_hash",
            ),
            5: ("quality_flags",),
            6: ("country_code", "country_source"),
            7: ("game_time", "day_acceleration", "night_acceleration"),
        }
        sql = (Path(__file__).parent / "fixtures/server_cache_v7.sql").read_text()
        for version in range(1, 8):
            with self.subTest(version=version):
                path = self.root / f"v{version}.db"
                connection = sqlite3.connect(path)
                connection.executescript(sql)
                if version < 3:
                    connection.execute("DROP INDEX idx_discovered_servers_stable_server_id")
                    connection.execute("DROP TABLE discovered_server_aliases")
                for added, columns in introduced.items():
                    if added > version:
                        for column in columns:
                            connection.execute(
                                f"ALTER TABLE discovered_servers DROP COLUMN {column}"
                            )
                connection.execute(f"PRAGMA user_version = {version}")
                connection.execute(
                    "INSERT INTO discovered_servers(cache_key,display_name,host,game_port,query_port) "
                    "VALUES('legacy:2302:27016','Legacy','legacy',2302,27016)"
                )
                connection.commit()
                connection.close()
                for _ in range(2):
                    migrated = server_cache.connect(path)
                    try:
                        self.assertEqual(server_cache.count_search_servers(migrated), 1)
                        self.assertEqual(
                            server_cache.get_server(migrated, "legacy:2302:27016").product,
                            "unknown",
                        )
                        self.assertEqual(migrated.execute("PRAGMA user_version").fetchone()[0], 8)
                    finally:
                        migrated.close()
