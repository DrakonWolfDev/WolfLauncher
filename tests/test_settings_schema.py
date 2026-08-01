import unittest

from wolflauncher.settings import SETTINGS_SCHEMA_VERSION, normalize_settings


class SettingsSchemaTests(unittest.TestCase):
    def test_legacy_settings_gain_schema_version_without_losing_unknown_keys(self):
        settings = normalize_settings({"player_name": "Survivor", "future_setting": {"keep": True}})

        self.assertEqual(settings["schema_version"], SETTINGS_SCHEMA_VERSION)
        self.assertEqual(settings["local_tool_profiles"], [])
        self.assertEqual(settings["editor_extra_mod_ids"], [])
        self.assertEqual(settings["local_host_settings"], {})
        self.assertEqual(settings["dayz_product"], "stable")
        self.assertTrue(settings["hide_quality_flagged"])
        self.assertEqual(settings["future_setting"], {"keep": True})

    def test_invalid_settings_are_replaced_with_a_minimal_valid_schema(self):
        self.assertEqual(
            normalize_settings(["not", "a", "mapping"]),
            {"schema_version": SETTINGS_SCHEMA_VERSION},
        )
        self.assertEqual(
            normalize_settings({"schema_version": "bad"})["schema_version"],
            SETTINGS_SCHEMA_VERSION,
        )

    def test_unsupported_packaged_steam_modes_migrate_to_auto(self):
        for mode in ("flatpak", "snap"):
            with self.subTest(mode=mode):
                settings = normalize_settings(
                    {"schema_version": 1, "native_steam_mode": mode}
                )
                self.assertEqual(settings["native_steam_mode"], "auto")
                self.assertEqual(settings["schema_version"], SETTINGS_SCHEMA_VERSION)

    def test_newer_settings_schema_is_preserved_for_forward_compatibility(self):
        self.assertEqual(normalize_settings({"schema_version": 99, "new": True}), {"schema_version": 99, "new": True})
