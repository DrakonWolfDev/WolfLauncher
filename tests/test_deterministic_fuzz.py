"""Seeded, dependency-free robustness checks for untrusted persisted and provider data."""

import random
import unittest

from wolflauncher.config import normalize_server_endpoint
from wolflauncher.server_discovery import (
    parse_battlemetrics_servers,
    parse_steam_web_api_servers,
    parse_wolfapi_servers,
)
from wolflauncher.settings import SETTINGS_SCHEMA_VERSION, normalize_settings


class DeterministicFuzzTests(unittest.TestCase):
    def test_endpoint_normalization_never_raises_or_changes_unrelated_ports(self):
        randomizer = random.Random(164104)
        alphabet = "abcDEF0123.:-[] \t"
        for _ in range(500):
            host = "".join(randomizer.choice(alphabet) for _ in range(randomizer.randrange(80)))
            game_port = randomizer.randrange(-10, 70000)
            query_port = randomizer.randrange(-10, 70000)

            normalized_host, normalized_game, normalized_query = normalize_server_endpoint(
                host, game_port, query_port
            )

            self.assertIsInstance(normalized_host, str)
            self.assertIsInstance(normalized_game, int)
            self.assertIsInstance(normalized_query, int)
            if normalized_game == game_port:
                self.assertEqual(normalized_query, query_port)

    def test_provider_row_fuzz_drops_or_normalizes_without_raising(self):
        randomizer = random.Random(11035)
        scalars = (None, "", "bad", -1, 0, 1, 2302, 65536, True, False, [], {})
        for _ in range(250):
            value = lambda: randomizer.choice(scalars)
            steam_row = {"addr": value(), "ip": value(), "gameport": value(), "name": value()}
            wolfapi_row = {
                "addr": value(),
                "ip": value(),
                "port": value(),
                "query_port": value(),
                "name": value(),
            }
            battlemetrics_row = {
                "attributes": {
                    "ip": value(),
                    "port": value(),
                    "portQuery": value(),
                    "name": value(),
                    "details": value(),
                }
            }

            self.assertIsInstance(
                parse_steam_web_api_servers({"response": {"servers": [steam_row]}}), list
            )
            self.assertIsInstance(parse_wolfapi_servers({"servers": [wolfapi_row]}), list)
            self.assertIsInstance(parse_battlemetrics_servers({"data": [battlemetrics_row]}), list)

    def test_settings_migration_preserves_unknown_mapping_values(self):
        randomizer = random.Random(4417)
        values = (None, "", "future", -1, 0, 1, [], {"nested": True})
        for _ in range(200):
            future_value = randomizer.choice(values)
            schema_version = randomizer.choice(values)
            settings = normalize_settings(
                {"future_setting": future_value, "schema_version": schema_version}
            )

            self.assertEqual(settings["future_setting"], future_value)
            self.assertIsInstance(settings["schema_version"], int)
            self.assertGreaterEqual(settings["schema_version"], SETTINGS_SCHEMA_VERSION)

    def test_settings_migration_rejects_non_mapping_fuzz_inputs(self):
        randomizer = random.Random(729)
        values = (None, "text", 42, True, [], (), {1, 2})
        for _ in range(100):
            self.assertEqual(
                normalize_settings(randomizer.choice(values)),
                {"schema_version": SETTINGS_SCHEMA_VERSION},
            )


if __name__ == "__main__":
    unittest.main()
