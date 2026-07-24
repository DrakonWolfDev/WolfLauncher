import unittest

from wolflauncher.settings import SETTINGS_SCHEMA_VERSION, normalize_settings


class SettingsSchemaTests(unittest.TestCase):
    def test_legacy_settings_gain_schema_version_without_losing_unknown_keys(self):
        settings = normalize_settings({"player_name": "Survivor", "future_setting": {"keep": True}})

        self.assertEqual(settings["schema_version"], SETTINGS_SCHEMA_VERSION)
        self.assertEqual(settings["future_setting"], {"keep": True})

    def test_invalid_settings_are_replaced_with_a_minimal_valid_schema(self):
        self.assertEqual(normalize_settings(["not", "a", "mapping"]), {"schema_version": 1})
        self.assertEqual(normalize_settings({"schema_version": "bad"})["schema_version"], 1)

    def test_newer_settings_schema_is_preserved_for_forward_compatibility(self):
        self.assertEqual(normalize_settings({"schema_version": 99, "new": True}), {"schema_version": 99, "new": True})
