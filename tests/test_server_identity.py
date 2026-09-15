import json
import unittest
import urllib.parse
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from wolflauncher.http_client import HttpClientError
from wolflauncher.server_discovery import (
    WolfApiError,
    discover_dayz_servers_wolfapi_v1,
    resolve_dayz_server_wolfapi_v1,
    search_dayz_servers_wolfapi_v1,
)
from wolflauncher.server_identity import (
    LiveIdentity,
    directory_identity,
    product_from_app_id,
    resolve_launch_identity,
)

EVIDENCE = (
    Path(__file__).resolve().parents[1] / "docs/evidence/phase0-product-identity-2026-09-15.json"
)


class ServerIdentityContractTests(unittest.TestCase):
    def setUp(self):
        self.endpoint = ("203.0.113.10", 2302, 27016)
        self.live = LiveIdentity(self.endpoint, "selection-1", 100.0, 1024020)

    def resolve(self, evidence, now=110.0):
        return resolve_launch_identity(
            evidence, endpoint=self.endpoint, request_id="selection-1", now=now
        )

    def test_recorded_direct_and_gamedig_evidence_identifies_both_editions(self):
        recorded = json.loads(EVIDENCE.read_text())
        responding = [row for row in recorded["a2s"] if "error" not in row]
        self.assertEqual(len(responding), 5)
        for row in responding:
            with self.subTest(endpoint=row["host"]):
                self.assertEqual(product_from_app_id(row["full_app_id"]), row["label"])
                self.assertEqual(product_from_app_id(row["short_app_id"]), "unknown")
        self.assertEqual(
            [product_from_app_id(row["appId"]) for row in recorded["gamedig"]],
            ["stable", "experimental"],
        )

    def test_invalid_or_unsupported_ids_never_default_to_stable(self):
        for value in (None, 0, -1, True, "1024020", 1024020.0, [], {}, 1042420, 223350, 730):
            with self.subTest(value=value):
                self.assertEqual(self.resolve(replace(self.live, app_id=value)), "unknown")

    def test_names_and_equal_versions_do_not_classify_directory_rows(self):
        rows = [
            {"name": "Stable", "version": "1.30", "product": "experimental"},
            {"name": "Experimental", "version": "1.30", "product": "stable"},
        ]
        self.assertEqual(directory_identity(rows), "conflict")
        for product in (None, "", "all", "invalid", [], {}):
            self.assertEqual(directory_identity([{"product": product}]), "unknown")
        self.assertEqual(directory_identity([]), "unknown")

    def test_recorded_resolve_conflict_and_empty_control(self):
        cases = {row["case"]: row for row in json.loads(EVIDENCE.read_text())["http"]}
        conflict = cases["experimental_resolve_all"]["sample"]
        self.assertEqual(directory_identity(conflict), "conflict")
        self.assertEqual(len({(r["ip"], r["game_port"], r["query_port"]) for r in conflict}), 1)
        self.assertEqual(directory_identity(cases["missing_resolve"]["sample"]), "unknown")
        self.assertEqual(directory_identity(cases["stable_resolve_all"]["sample"]), "stable")

    def test_live_id_settles_either_direction_of_conflict_or_directory_miss(self):
        for app_id, expected in ((221100, "stable"), (1024020, "experimental")):
            self.assertEqual(self.resolve(replace(self.live, app_id=app_id)), expected)
        self.assertEqual(self.resolve(None), "unknown")

    def test_freshness_boundary_and_invalid_clock_values(self):
        self.assertEqual(self.resolve(self.live, now=130), "experimental")
        for now in (130.001, 99.9, float("inf"), float("nan")):
            self.assertEqual(self.resolve(self.live, now=now), "unknown")

    def test_incomplete_timeout_and_stale_callback_cannot_authorize_join(self):
        for evidence in (
            None,
            replace(self.live, complete=False),
            replace(self.live, request_id="previous-selection"),
            replace(self.live, endpoint=("203.0.113.11", 2302, 27016)),
            replace(self.live, endpoint=("203.0.113.10", 27016, 2302)),
            replace(self.live, endpoint=("203.0.113.10", 2303, 27016)),
        ):
            self.assertEqual(self.resolve(evidence), "unknown")


class CombinedDirectoryContractTests(unittest.TestCase):
    def payload(self, rows):
        return {
            "contract_version": "1",
            "generated_at": "2026-09-15T16:20:00+00:00",
            "validation_policy": {"live_for_seconds": 1800},
            "validation_queue": {"ready": 1},
            "coverage": {"eligible": 100},
            "total_count": len(rows),
            "servers": rows,
        }

    @patch("wolflauncher.server_discovery.fetch_json")
    def test_combined_requests_accept_mixed_recorded_rows_and_preserve_ports(self, fetch):
        cases = {row["case"]: row for row in json.loads(EVIDENCE.read_text())["http"]}
        rows = cases["experimental_resolve_all"]["sample"]
        # Reduced observations omit opaque IDs. Supply distinct fixture IDs so the
        # existing converter does not collapse this intentional endpoint conflict.
        rows = [dict(row, server_id=f"fixture-{i}") for i, row in enumerate(rows)]
        fetch.return_value = self.payload(rows)
        calls = (
            lambda: discover_dayz_servers_wolfapi_v1(product="all", limit=2, offset=2),
            lambda: search_dayz_servers_wolfapi_v1("Example", product="all"),
            lambda: resolve_dayz_server_wolfapi_v1(
                rows[0]["ip"], game_port=11100, query_port=11101, product="all"
            ),
        )
        for call in calls:
            result = call()
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].game_port, 11100)
            self.assertEqual(result[0].query_port, 11101)
            query = urllib.parse.parse_qs(urllib.parse.urlparse(fetch.call_args.args[0]).query)
            self.assertEqual(query["product"], ["all"])
        self.assertEqual(query["game_port"], ["11100"])
        self.assertEqual(query["query_port"], ["11101"])

    @patch("wolflauncher.server_discovery.fetch_json")
    def test_directory_miss_is_distinct_from_transport_failure(self, fetch):
        fetch.return_value = self.payload([])
        self.assertEqual(
            resolve_dayz_server_wolfapi_v1("192.0.2.1", game_port=2302, product="all"), []
        )
        fetch.side_effect = HttpClientError("timeout", "request timed out")
        with self.assertRaises(WolfApiError):
            resolve_dayz_server_wolfapi_v1("192.0.2.1", game_port=2302, product="all")
