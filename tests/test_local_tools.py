import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit, QListWidget

from wolflauncher.local_tools import (
    DAYZ_EDITOR_MODS,
    normalise_workshop_ids,
    parse_local_endpoint,
    profiles_from_settings,
)
from wolflauncher.local_tools_feature import LocalToolsFeatureMixin


class EditorModPickerHarness(LocalToolsFeatureMixin):
    def __init__(self):
        self.editor_mod_picker = QListWidget()
        self.editor_mod_picker.setUniformItemSizes(True)
        self.editor_mod_picker.setSpacing(1)
        self.editor_mod_picker.resize(480, 180)
        self.editor_mod_filter = QLineEdit()
        self.editor_extra_mod_ids = {"1005", "1059"}
        self.local_extra_mod_ids = set()
        self.mod_selection_target = "editor"
        self.editor_dependency_mod_ids = set()
        self.editor_dependency_excluded_ids = set()
        self.editor_dependency_metadata = {}

    def selected_local_tool_install(self, *, editor=None):
        return SimpleNamespace(workshop_dir="/workshop")

    def _update_mod_selection_summary(self):
        pass


class LocalToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

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

    def test_parse_local_endpoint(self):
        self.assertEqual(parse_local_endpoint("192.168.1.25:2302"), ("192.168.1.25", 2302))
        with self.assertRaisesRegex(ValueError, "host:game-port"):
            parse_local_endpoint("192.168.1.25")

    def test_profiles_from_settings_discards_invalid_profiles(self):
        profiles = profiles_from_settings(
            [
                {
                    "name": "Weapons",
                    "mod_paths": ["C:/mods/@Weapons", ""],
                    "endpoint": "lan:2302",
                    "workshop_mod_ids": ["123", "invalid", "123", "456"],
                },
                {"name": "", "mod_paths": ["C:/mods/@Other"]},
                "invalid",
            ]
        )
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].mod_paths, ("C:/mods/@Weapons",))
        self.assertEqual(profiles[0].workshop_mod_ids, ("123", "456"))

    def test_long_editor_mod_list_survives_scroll_filter_and_refresh(self):
        mods = {str(1000 + index): f"Workshop Mod {index:02d}" for index in range(60)}
        picker = EditorModPickerHarness()
        picker.editor_mod_picker.show()

        with patch("wolflauncher.local_tools_feature.scan_installed_mods", return_value=mods):
            picker._refresh_editor_mod_picker()
            self.app.processEvents()

            self.assertEqual(picker.editor_mod_picker.count(), 60)
            self.assertIsNone(picker.editor_mod_picker.graphicsEffect())
            self.assertEqual(
                sum(
                    not picker.editor_mod_picker.item(row).isHidden()
                    for row in range(picker.editor_mod_picker.count())
                ),
                60,
            )

            selected = picker.editor_mod_picker.item(5)
            picker.editor_mod_picker.setCurrentItem(selected)
            original_checks = {
                picker.editor_mod_picker.item(row).data(Qt.UserRole): picker.editor_mod_picker.item(
                    row
                ).checkState()
                for row in range(picker.editor_mod_picker.count())
            }

            last = picker.editor_mod_picker.item(59)
            first = picker.editor_mod_picker.item(0)
            picker.editor_mod_picker.scrollToItem(last)
            self.app.processEvents()
            self.assertTrue(
                picker.editor_mod_picker.visualItemRect(last).intersects(
                    picker.editor_mod_picker.viewport().rect()
                )
            )
            picker.editor_mod_picker.scrollToItem(first)
            self.app.processEvents()
            self.assertTrue(
                picker.editor_mod_picker.visualItemRect(first).intersects(
                    picker.editor_mod_picker.viewport().rect()
                )
            )
            self.assertIs(picker.editor_mod_picker.currentItem(), selected)

            picker._filter_editor_mod_picker("Workshop Mod 5")
            self.assertEqual(
                sum(
                    not picker.editor_mod_picker.item(row).isHidden()
                    for row in range(picker.editor_mod_picker.count())
                ),
                10,
            )
            picker._filter_editor_mod_picker("")
            picker._refresh_editor_mod_picker()

        self.assertEqual(picker.editor_mod_picker.count(), 60)
        self.assertEqual(
            {
                picker.editor_mod_picker.item(row).data(Qt.UserRole): picker.editor_mod_picker.item(
                    row
                ).checkState()
                for row in range(picker.editor_mod_picker.count())
            },
            original_checks,
        )


if __name__ == "__main__":
    unittest.main()
