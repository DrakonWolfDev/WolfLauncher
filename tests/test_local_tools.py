import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QVBoxLayout, QWidget

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


class SelectedModPillsHarness(LocalToolsFeatureMixin):
    def __init__(self):
        self.mod_selection_target = "editor"
        self.selected_mods_title = QLabel()
        self.selected_mods_hint = QLabel()
        self.selected_mods_widget = QWidget()
        self.selected_mods_layout = QVBoxLayout(self.selected_mods_widget)


class LocalWorkspaceHarness(LocalToolsFeatureMixin, QWidget):
    def __init__(self, profiles):
        super().__init__()
        self.settings = {"local_tool_profiles": profiles}

    def selected_local_tool_install(self, *, editor=None):
        return None


class LocalToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_workspace_construction_scans_once_and_later_refreshes_stay_fresh(self):
        profile = {
            "name": "Local test",
            "mod_paths": [],
            "endpoint": "localhost:2302",
            "workshop_mod_ids": ["1005"],
            "query_port": "2305",
        }
        for profiles in ([], [profile]):
            with self.subTest(saved_profile=bool(profiles)):
                workspace = LocalWorkspaceHarness(profiles)
                self.addCleanup(workspace.deleteLater)
                mods = {"1005": "First mod", "1006": "Second mod"}
                with (
                    patch.object(workspace, "_load_editor_image"),
                    patch(
                        "wolflauncher.local_tools_feature.scan_installed_mods", return_value=mods
                    ) as scan,
                ):
                    page = workspace._build_local_tools_tab()
                    self.addCleanup(page.deleteLater)
                    scan.assert_called_once_with(None)
                    self.assertEqual(workspace.editor_mod_picker.count(), 2)
                    self.assertEqual(workspace.mod_selection_target, "editor")
                    self.assertEqual(workspace.local_extra_mod_ids, {"1005"} if profiles else set())
                    scan.return_value = {"1006": "Updated name"}
                    workspace._refresh_editor_mod_picker()
                    self.assertEqual(scan.call_count, 2)
                    self.assertEqual(workspace.editor_mod_picker.count(), 1)
                    self.assertIn("Updated name", workspace.editor_mod_picker.item(0).text())
                    workspace._set_mod_selection_target("local")
                    self.assertEqual(scan.call_count, 3)
                    self.assertEqual(workspace.local_extra_mod_ids, {"1005"} if profiles else set())

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

    def test_long_selected_mod_summary_uses_static_effect_free_pills(self):
        picker = SelectedModPillsHarness()
        entries = [f"Workshop Mod {index:02d} ({1000 + index})" for index in range(46)]

        picker._update_selected_mod_pills(entries, [])
        self.app.processEvents()

        self.assertEqual(picker.selected_mods_layout.count(), 46)
        for index in range(picker.selected_mods_layout.count()):
            pill = picker.selected_mods_layout.itemAt(index).widget()
            self.assertIsNotNone(pill)
            self.assertIsNone(pill.graphicsEffect())
            self.assertFalse(hasattr(pill, "_selection_animation"))


if __name__ == "__main__":
    unittest.main()


class LanModDiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def harness(self):
        from unittest.mock import Mock

        from wolflauncher.local_tools import LocalToolProfile

        profile = LocalToolProfile("LAN", endpoint="192.168.1.25:2302", query_port="27016")
        harness = SimpleNamespace(
            _current_local_tool_profile=lambda: profile,
            _local_required_mods=lambda **kwargs: [],
            local_tools_status=QLabel(),
            _launch_local_server_with_mods=Mock(),
            _local_missing_mod_status=LocalToolsFeatureMixin._local_missing_mod_status,
            _update_mod_selection_summary=Mock(),
        )
        return harness, profile

    def test_discovered_installed_mods_launch_without_manual_selection(self):
        from wolflauncher.models import Server
        from wolflauncher.mods import ModCheckResult, RequiredMod

        harness, profile = self.harness()
        mods = [RequiredMod("123", "CF", installed=True)]
        result = ModCheckResult(True, Server("LAN", "LAN", "lan", 2302, 27016), mods)
        LocalToolsFeatureMixin._finish_local_server_mod_check(harness, result, "install", profile)
        harness._launch_local_server_with_mods.assert_called_once_with(
            "install", result.server, mods
        )

    def test_missing_mods_are_listed_and_launch_is_blocked(self):
        from wolflauncher.models import Server
        from wolflauncher.mods import ModCheckResult, RequiredMod

        harness, profile = self.harness()
        mods = [
            RequiredMod("123", "CF", workshop_state=0),
            RequiredMod("456", "Other", workshop_state=1),
        ]
        result = ModCheckResult(True, Server("LAN", "LAN", "lan", 2302, 27016), mods)
        with patch("wolflauncher.local_tools_feature.QMessageBox.warning") as warning:
            LocalToolsFeatureMixin._finish_local_server_mod_check(
                harness, result, "install", profile
            )
        message = warning.call_args.args[2]
        self.assertIn("CF (123) - not subscribed", message)
        self.assertIn("Other (456) - subscribed; download incomplete", message)
        self.assertIn("?id=123", message)
        harness._launch_local_server_with_mods.assert_not_called()

    def test_changed_profile_discards_query_result(self):
        harness, profile = self.harness()
        harness._current_local_tool_profile = lambda: None
        LocalToolsFeatureMixin._finish_local_server_mod_check(harness, None, "install", profile)
        harness._launch_local_server_with_mods.assert_not_called()

    def test_query_failure_requires_explicit_manual_fallback(self):
        from PySide6.QtWidgets import QMessageBox

        from wolflauncher.models import Server
        from wolflauncher.mods import ModCheckResult

        harness, profile = self.harness()
        result = ModCheckResult(
            False, Server("LAN", "LAN", "lan", 2302, 27016), [], error="timeout"
        )
        with patch(
            "wolflauncher.local_tools_feature.QMessageBox.question", return_value=QMessageBox.No
        ):
            LocalToolsFeatureMixin._finish_local_server_mod_check(
                harness, result, "install", profile
            )
        harness._launch_local_server_with_mods.assert_not_called()
        with patch(
            "wolflauncher.local_tools_feature.QMessageBox.question", return_value=QMessageBox.Yes
        ):
            LocalToolsFeatureMixin._finish_local_server_mod_check(
                harness, result, "install", profile
            )
        harness._launch_local_server_with_mods.assert_called_once_with("install", result.server, [])

    def test_query_port_survives_profile_loading(self):
        profile = profiles_from_settings([{"name": "LAN", "query_port": "27016"}])[0]
        self.assertEqual(profile.query_port, "27016")

    def test_discovery_uses_query_port_and_keeps_game_port(self):
        from unittest.mock import Mock

        harness, profile = self.harness()
        harness.local_mod_worker = None
        harness._finish_local_server_mod_check = Mock()
        harness._clear_local_mod_worker = Mock()
        install = SimpleNamespace(workshop_dir="workshop")
        with patch("wolflauncher.local_tools_feature.ModWorker") as worker:
            LocalToolsFeatureMixin._launch_verified_local_test_server(harness, install)
        server = worker.call_args.args[0]
        self.assertEqual(server.game_port, 2302)
        self.assertEqual(server.query_port, 27016)
        worker.return_value.start.assert_called_once()


class LanReviewTests(unittest.TestCase):
    setUpClass = LanModDiscoveryTests.setUpClass
    harness = LanModDiscoveryTests.harness

    def test_query_lists_requirements_without_launching(self):
        from wolflauncher.models import Server
        from wolflauncher.mods import ModCheckResult, RequiredMod

        harness, profile = self.harness()
        result = ModCheckResult(
            True,
            Server("LAN", "LAN", "lan", 2302, 27016),
            [RequiredMod("123", "CF", installed=True)],
        )
        LocalToolsFeatureMixin._finish_local_server_mod_check(
            harness, result, "install", profile, launch_after_query=False
        )
        self.assertEqual(harness.local_server_mods, result.required_mods)
        self.assertEqual(harness.local_server_query_profile, profile)
        harness._update_mod_selection_summary.assert_called_once_with()
        harness._launch_local_server_with_mods.assert_not_called()
        self.assertIn("Review", harness.local_tools_status.text())

    def test_vanilla_server_gaining_mods_requires_review_before_join(self):
        from wolflauncher.models import Server
        from wolflauncher.mods import ModCheckResult, RequiredMod

        harness, profile = self.harness()
        harness.local_server_query_profile = profile
        harness.local_server_mods = []
        result = ModCheckResult(
            True,
            Server("LAN", "LAN", "lan", 2302, 27016),
            [RequiredMod("123", "CF", installed=True)],
        )
        LocalToolsFeatureMixin._finish_local_server_mod_check(harness, result, "install", profile)
        harness._launch_local_server_with_mods.assert_not_called()
        self.assertEqual(harness.local_server_mods, result.required_mods)

    def test_failed_preview_clears_old_mods_without_manual_launch_prompt(self):
        from wolflauncher.models import Server
        from wolflauncher.mods import ModCheckResult, RequiredMod

        harness, profile = self.harness()
        harness.local_server_mods = [RequiredMod("123", "Old", installed=True)]
        result = ModCheckResult(
            False, Server("LAN", "LAN", "lan", 2302, 27016), [], error="timeout"
        )
        with patch("wolflauncher.local_tools_feature.QMessageBox.question") as question:
            LocalToolsFeatureMixin._finish_local_server_mod_check(
                harness, result, "install", profile, launch_after_query=False
            )
        self.assertEqual(harness.local_server_mods, [])
        question.assert_not_called()
        harness._launch_local_server_with_mods.assert_not_called()

    def test_legacy_endpoint_populates_explicit_address_and_port_fields(self):
        from wolflauncher.local_tools import LocalToolProfile, local_endpoint_fields

        self.assertEqual(
            local_endpoint_fields(
                LocalToolProfile("LAN", endpoint="192.168.1.180:3302", query_port="3303")
            ),
            ("192.168.1.180", 3302, 3303),
        )
        self.assertEqual(
            local_endpoint_fields(LocalToolProfile("LAN", endpoint="lan:2302")), ("lan", 2302, 2305)
        )

    def test_server_requirements_appear_in_selection_and_are_not_duplicated_as_extras(self):
        from wolflauncher.mods import RequiredMod

        picker = EditorModPickerHarness()
        picker.local_extra_mod_ids = {"123"}
        picker.local_server_mods = [
            RequiredMod("123", "CF", installed=True),
            RequiredMod("456", "Missing", workshop_state=0),
        ]
        with patch(
            "wolflauncher.local_tools_feature.scan_installed_mods", return_value={"123": "CF"}
        ):
            entries = LocalToolsFeatureMixin._enabled_mod_entries(picker, editor=False)
        self.assertEqual(len(entries), 2)
        self.assertIn("installed - included automatically", entries[0])
        self.assertIn("not subscribed", entries[1])

    def test_first_join_queries_and_stops_for_review(self):
        from unittest.mock import Mock

        harness, _ = self.harness()
        harness._query_local_server_mods = Mock()
        LocalToolsFeatureMixin._join_local_test_server(harness)
        harness._query_local_server_mods.assert_called_once_with()
        harness._launch_local_server_with_mods.assert_not_called()
