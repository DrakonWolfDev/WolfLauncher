import unittest
from types import SimpleNamespace

from wolflauncher.local_tools_feature import LocalToolsFeatureMixin
from wolflauncher.local_tools import (
    DAYZ_EDITOR_MODS,
    editor_compatibility_metadata,
    expand_editor_mod_requirements,
    normalise_workshop_ids,
    parse_local_endpoint,
    profiles_from_settings,
)


class LocalToolsTests(unittest.TestCase):
    def test_editor_defaults_are_the_documented_required_mods(self):
        self.assertEqual(
            DAYZ_EDITOR_MODS,
            (
                ("2250764298", "DayZ Editor"),
                ("1559212036", "CF"),
                ("2545327648", "Dabs Framework"),
            ),
        )

    def test_normalise_workshop_ids_rejects_invalid_and_duplicate_entries(self):
        self.assertEqual(
            normalise_workshop_ids(" 123, no, 456\n123,  "),
            ("123", "456"),
        )

    def test_pripyat_editor_requirements_include_the_matching_gsc_release(self):
        self.assertEqual(
            expand_editor_mod_requirements(("3136720512",)),
            ("3136720512", "2868091107"),
        )
        self.assertEqual(
            editor_compatibility_metadata(("3711024720",)),
            {"3711012403": {"title": "GSC Gameworld Assets 2026"}},
        )

    def test_unchecked_auto_detected_editor_requirement_is_excluded_from_launch(self):
        feature = SimpleNamespace(
            editor_extra_mod_ids={"3136720512"},
            editor_dependency_mod_ids={"2868091107"},
            editor_dependency_excluded_ids={"2868091107"},
        )

        self.assertEqual(
            LocalToolsFeatureMixin._selected_editor_extra_mod_ids(feature),
            ("3136720512",),
        )

    def test_parse_local_endpoint(self):
        self.assertEqual(parse_local_endpoint("192.168.1.25:2302"), ("192.168.1.25", 2302))
        with self.assertRaisesRegex(ValueError, "host:game-port"):
            parse_local_endpoint("192.168.1.25")

    def test_profiles_from_settings_discards_invalid_profiles(self):
        profiles = profiles_from_settings(
            [
                {"name": "Weapons", "mod_paths": ["C:/mods/@Weapons", ""], "endpoint": "lan:2302"},
                {"name": "", "mod_paths": ["C:/mods/@Other"]},
                "invalid",
            ]
        )
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].mod_paths, ("C:/mods/@Weapons",))


if __name__ == "__main__":
    unittest.main()
