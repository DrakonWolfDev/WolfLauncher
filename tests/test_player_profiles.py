import os
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QWidget

from wolflauncher.dayz_product import EXPERIMENTAL, STABLE
from wolflauncher.lifecycle import begin_runtime_shutdown
from wolflauncher.player_profile_dialog import PlayerProfileDialog, PlayerProfileWorker
from wolflauncher.player_profiles import (
    PlayerProfile,
    ProfileDiscoveryResult,
    discover_player_profiles,
    profile_context_key,
    profile_documents_directories,
    profile_name_from_filename,
    profile_still_exists,
)
from wolflauncher.settings_feature import SettingsFeatureMixin


class PlayerProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.install = SimpleNamespace(
            product=STABLE,
            mode="native",
            dayz_dir=self.root / "steamapps/common/DayZ",
            compatdata_dir=self.root / "wrong-library/compatdata/221100",
        )
        self.documents = self.root / "Redirected Documents"

    def write_profile(self, relative, modified=None):
        path = self.documents / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic profile contents")
        if modified is not None:
            os.utime(path, ns=(modified, modified))
        return path

    def discover(self, install=None, **kwargs):
        return discover_player_profiles(
            install or self.install, platform_id="windows", documents_dir=self.documents, **kwargs
        )

    def selected_profile(self):
        path = self.write_profile("DayZ/Wolf Player.DayZProfile")
        return PlayerProfile("Wolf Player", (path,), path.stat().st_mtime_ns)

    def window(self):
        return SimpleNamespace(
            player_name=QLineEdit("Keep This Name"),
            selected_steam_install=Mock(return_value=self.install),
            save_user_settings=Mock(return_value=True),
            statusBar=Mock(return_value=Mock()),
            apply_existing_player_profile=Mock(),
            _profile_search_finished=Mock(),
        )

    def test_primary_filenames_exclude_caches_backups_and_ambiguous_encoded_names(self):
        for filename in (
            "chars.DayZProfile",
            "Wolf.vars.DayZProfile",
            "Wolf.chars.DayZProfile",
            "Wolf.DayZProfile.bak",
            "Wolf.core.xml",
            "Wolf.dayz_preset_User.xml",
            "Wolf%20Player.DayZProfile",
            " Wolf.DayZProfile",
            "Wolf\nName.DayZProfile",
            "..DayZProfile",
            ".DayZProfile",
        ):
            with self.subTest(filename=filename):
                self.assertIsNone(profile_name_from_filename(filename))
        self.assertEqual(profile_name_from_filename("Wolf Player.DAYZPROFILE"), "Wolf Player")
        self.assertEqual(profile_name_from_filename("Éowyn.DayZProfile"), "Éowyn")

    def test_read_only_discovery_groups_names_and_sorts_by_primary_file_modification(self):
        first = self.write_profile("DayZ/Wolf Player.DayZProfile", 1_000_000_000)
        second = self.write_profile(
            "DayZ Other Profiles/Wolf Player/Wolf Player.DayZProfile", 2_000_000_000
        )
        newest = self.write_profile("DayZ/Éowyn.DayZProfile", 3_000_000_000)
        self.write_profile("DayZ/chars.DayZProfile")
        self.write_profile("DayZ/Wolf Player.vars.DayZProfile")
        self.write_profile("DayZ/backup/Wrong.DayZProfile")
        self.write_profile("DayZ Other Profiles/WrongFolder/Misplaced.DayZProfile")
        self.write_profile("DayZ Other Profiles/Loose.DayZProfile")
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (first, second, newest)}
        with patch("pathlib.Path.open", side_effect=AssertionError("Do not read profile contents")):
            result = self.discover()
        self.assertEqual([p.name for p in result.profiles], ["Éowyn", "Wolf Player"])
        self.assertEqual(set(result.profiles[1].files), {first, second})
        self.assertEqual(result.note, "")
        after = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}
        self.assertEqual(after, before)

    def test_windows_uses_the_redirected_documents_location_without_a_home_fallback(self):
        self.write_profile("DayZ/Wolf.DayZProfile")
        with patch(
            "PySide6.QtCore.QStandardPaths.writableLocation", return_value=str(self.documents)
        ) as location:
            result = discover_player_profiles(self.install, platform_id="windows")
        location.assert_called_once()
        self.assertEqual([p.name for p in result.profiles], ["Wolf"])
        with patch("PySide6.QtCore.QStandardPaths.writableLocation", return_value=""):
            missing = discover_player_profiles(self.install, platform_id="windows")
        self.assertEqual(missing.profiles, ())
        self.assertEqual(missing.checked_folders, ())
        self.assertIn("could not be determined", missing.note)

    def test_stable_and_experimental_folders_never_mix(self):
        self.write_profile("DayZ/Stable Player.DayZProfile")
        self.write_profile("DayZ Exp/Experimental Player.DayZProfile")
        self.write_profile("DayZ Exp Other Profiles/Custom/Custom.DayZProfile")
        exp = SimpleNamespace(**{**vars(self.install), "product": EXPERIMENTAL})
        self.assertEqual([p.name for p in self.discover().profiles], ["Stable Player"])
        self.assertEqual(
            {p.name for p in self.discover(exp).profiles}, {"Experimental Player", "Custom"}
        )

    def test_proton_uses_the_actual_game_library_and_edition_not_a_stale_prefix(self):
        for product in (STABLE, EXPERIMENTAL):
            install = SimpleNamespace(**{**vars(self.install), "product": product})
            directories = profile_documents_directories(install, platform_id="linux")
            expected = (
                self.root
                / "steamapps/compatdata"
                / str(product.client_app_id)
                / "pfx/drive_c/users/steamuser/Documents"
            )
            self.assertEqual(directories[0], expected)
            folder = "DayZ Exp" if product.experimental else "DayZ"
            path = expected / folder / "Correct.DayZProfile"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"profile")
            with patch("PySide6.QtCore.QStandardPaths.writableLocation") as host_documents:
                result = discover_player_profiles(install, platform_id="linux")
            host_documents.assert_not_called()
            self.assertEqual([p.name for p in result.profiles], ["Correct"])
            self.assertTrue(all("wrong-library" not in str(p) for p in result.checked_folders))

    def test_proton_documents_aliases_are_deduplicated(self):
        documents, alias = profile_documents_directories(self.install, platform_id="linux")
        path = documents / "DayZ/Player.DayZProfile"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"profile")
        try:
            alias.symlink_to(documents, target_is_directory=True)
        except OSError:
            self.skipTest("Directory symlinks unavailable")
        result = discover_player_profiles(self.install, platform_id="linux")
        self.assertEqual(len(result.profiles), 1)
        self.assertEqual(len(result.profiles[0].files), 1)
        self.assertEqual(len(result.checked_folders), 2)

    def test_empty_missing_encoded_and_linked_files_do_not_become_guessed_profiles(self):
        self.assertEqual(self.discover().profiles, ())
        self.assertFalse(self.documents.exists())
        empty = self.write_profile("DayZ/Empty.DayZProfile")
        empty.write_bytes(b"")
        self.write_profile("DayZ/Wolf%20Player.DayZProfile")
        result = self.discover()
        self.assertEqual(result.profiles, ())
        self.assertIn("Encoded profile names", result.note)
        target = self.root / "outside.DayZProfile"
        target.write_bytes(b"profile")
        try:
            (empty.parent / "Linked.DayZProfile").symlink_to(target)
        except OSError:
            self.skipTest("File symlinks unavailable")
        self.assertEqual(self.discover().profiles, ())

    def test_unreadable_folders_and_limits_have_explicit_partial_search_notes(self):
        with patch("wolflauncher.player_profiles.os.scandir", side_effect=PermissionError):
            result = self.discover()
        self.assertEqual(result.profiles, ())
        self.assertIn("could not be checked", result.note)
        for limit, value in (("MAX_ENTRIES", 0), ("SCAN_SECONDS", -1)):
            with patch("wolflauncher.player_profiles." + limit, value):
                result = self.discover()
            self.assertEqual(result.profiles, ())
            self.assertIn("limit", result.note)
        cancelled = self.discover(cancelled=lambda: True)
        self.assertEqual(cancelled.profiles, ())
        self.assertIn("cancelled", cancelled.note)

    def test_selection_revalidation_rejects_removed_or_mismatched_files(self):
        profile = self.selected_profile()
        self.assertTrue(profile_still_exists(profile))
        self.assertFalse(profile_still_exists(replace(profile, name="Other Name")))
        profile.files[0].unlink()
        self.assertFalse(profile_still_exists(profile))

    def test_shared_game_directory_does_not_merge_two_libraries_profile_contexts(self):
        shared = self.root / "shared-game"
        shared.mkdir()
        contexts = []
        for name in ("first", "second"):
            game = self.root / name / "steamapps/common/DayZ"
            game.parent.mkdir(parents=True)
            try:
                game.symlink_to(shared, target_is_directory=True)
            except OSError:
                self.skipTest("Directory symlinks unavailable")
            install = SimpleNamespace(**{**vars(self.install), "dayz_dir": game})
            contexts.append(profile_context_key(install))
        self.assertNotEqual(*contexts)

    def test_apply_changes_only_the_configured_name_after_explicit_selection(self):
        profile = self.selected_profile()
        before = profile.files[0].read_bytes()
        window = self.window()
        SettingsFeatureMixin.apply_existing_player_profile(
            window, profile, profile_context_key(self.install)
        )
        self.assertEqual(window.player_name.text(), "Wolf Player")
        window.save_user_settings.assert_called_once_with(silent=True)
        self.assertEqual(profile.files[0].read_bytes(), before)

    def test_install_or_edition_changes_and_removed_profiles_leave_the_name_alone(self):
        profile = self.selected_profile()
        context = profile_context_key(self.install)
        changes = (
            {"product": EXPERIMENTAL},
            {"dayz_dir": self.root / "another/common/DayZ"},
            {"mode": "STEAM_ROOT env"},
        )
        with patch("wolflauncher.settings_feature.QMessageBox.information"):
            for changed in changes:
                window = self.window()
                window.selected_steam_install.return_value = SimpleNamespace(
                    **{**vars(self.install), **changed}
                )
                SettingsFeatureMixin.apply_existing_player_profile(window, profile, context)
                self.assertEqual(window.player_name.text(), "Keep This Name")
                window.save_user_settings.assert_not_called()
            profile.files[0].unlink()
            window = self.window()
            SettingsFeatureMixin.apply_existing_player_profile(window, profile, context)
        window.save_user_settings.assert_not_called()

    def test_save_failure_restores_the_previous_name_and_shutdown_suppresses_changes(self):
        profile = self.selected_profile()
        window = self.window()
        window.save_user_settings.return_value = False
        SettingsFeatureMixin.apply_existing_player_profile(
            window, profile, profile_context_key(self.install)
        )
        self.assertEqual(window.player_name.text(), "Keep This Name")
        window.statusBar.return_value.showMessage.assert_not_called()
        window._shutting_down = True
        window.save_user_settings.reset_mock()
        SettingsFeatureMixin.apply_existing_player_profile(
            window, profile, profile_context_key(self.install)
        )
        window.save_user_settings.assert_not_called()

    def test_dialog_preserves_current_selection_and_only_accepts_an_existing_profile(self):
        profile = self.selected_profile()
        other = self.write_profile("DayZ/Other.DayZProfile")
        dialog = PlayerProfileDialog(None, STABLE.label, profile.name)
        self.addCleanup(dialog.deleteLater)
        self.assertFalse(dialog.use_button.isEnabled())
        dialog.show_profiles(ProfileDiscoveryResult((PlayerProfile("Other", (other,), 0), profile)))
        self.assertEqual(dialog.table.currentRow(), 1)
        self.assertIsNone(dialog.selected_profile)
        dialog.accept_selection()
        self.assertEqual(dialog.result(), QDialog.Accepted)
        self.assertEqual(dialog.selected_profile, profile)

    def test_dialog_handles_empty_results_removed_profiles_and_cancel_without_applying(self):
        dialog = PlayerProfileDialog(None, STABLE.label, "Keep This Name")
        self.addCleanup(dialog.deleteLater)
        dialog.show_profiles(ProfileDiscoveryResult(note="Some folders could not be checked."))
        self.assertFalse(dialog.use_button.isEnabled())
        self.assertIn("could not be checked", dialog.status.text())
        profile = self.selected_profile()
        dialog.show_profiles(ProfileDiscoveryResult((profile,)))
        profile.files[0].unlink()
        dialog.accept_selection()
        self.assertIsNone(dialog.selected_profile)
        self.assertIn("no longer available", dialog.status.text())
        dialog.scan_worker = Mock()
        dialog.reject()
        dialog.scan_worker.cancel.assert_called_once()

    def test_chooser_cancel_keeps_name_and_cancels_the_scan(self):
        window = self.window()
        with (
            patch("wolflauncher.settings_feature.PlayerProfileDialog") as dialog,
            patch("wolflauncher.settings_feature.PlayerProfileWorker") as worker,
        ):
            dialog.return_value.exec.return_value = QDialog.Rejected
            SettingsFeatureMixin.choose_existing_player_profile(window)
        self.assertEqual(window.player_name.text(), "Keep This Name")
        window.apply_existing_player_profile.assert_not_called()
        worker.return_value.cancel.assert_called_once()
        dialog.return_value.deleteLater.assert_called_once()

    def test_chooser_passes_the_captured_installation_to_explicit_application(self):
        window = self.window()
        profile = self.selected_profile()
        with (
            patch("wolflauncher.settings_feature.PlayerProfileDialog") as dialog,
            patch("wolflauncher.settings_feature.PlayerProfileWorker"),
        ):
            dialog.return_value.exec.return_value = QDialog.Accepted
            dialog.return_value.selected_profile = profile
            SettingsFeatureMixin.choose_existing_player_profile(window)
        window.apply_existing_player_profile.assert_called_once_with(
            profile, profile_context_key(self.install)
        )

    def test_worker_failure_and_cancellation_never_produce_a_profile_choice(self):
        worker = PlayerProfileWorker(self.install, "linux")
        results = []
        worker.profiles_ready.connect(results.append)
        with patch(
            "wolflauncher.player_profile_dialog.discover_player_profiles", side_effect=OSError
        ):
            worker.run()
        self.assertEqual(results[0].profiles, ())
        self.assertIn("could not be checked", results[0].note)
        with (
            patch.object(worker, "isInterruptionRequested", return_value=True),
            patch("wolflauncher.player_profile_dialog.discover_player_profiles"),
        ):
            worker.run()
        self.assertEqual(len(results), 1)

    def test_profile_worker_participates_in_application_shutdown(self):
        worker = Mock()
        worker.isRunning.return_value = True
        owner = SimpleNamespace(profile_discovery_worker=worker)
        begin_runtime_shutdown(owner)
        worker.cancel.assert_called_once()

    def test_closing_a_real_picker_keeps_its_worker_alive_until_cancellation_finishes(self):
        class Window(QWidget, SettingsFeatureMixin):
            pass

        window = Window()
        window.player_name = QLineEdit("Keep This Name", window)
        window.selected_steam_install = Mock(return_value=self.install)
        window.save_user_settings = Mock()
        window.statusBar = Mock(return_value=Mock())
        entered = threading.Event()
        stopped = threading.Event()

        def discover(install, *, cancelled, **kwargs):
            entered.set()
            deadline = time.monotonic() + 2
            while not cancelled() and time.monotonic() < deadline:
                time.sleep(0.001)
            stopped.set()
            return ProfileDiscoveryResult()

        def close_picker():
            if not entered.is_set():
                QTimer.singleShot(1, close_picker)
                return
            window.findChild(PlayerProfileDialog).reject()

        QTimer.singleShot(0, close_picker)
        with patch(
            "wolflauncher.player_profile_dialog.discover_player_profiles", side_effect=discover
        ):
            window.choose_existing_player_profile()
            worker = window.profile_discovery_worker
            if worker is not None:
                self.assertTrue(worker.wait(2000))
            self.app.processEvents()
        self.assertTrue(stopped.is_set())
        self.assertIsNone(window.profile_discovery_worker)
        self.assertEqual(window.player_name.text(), "Keep This Name")
        window.save_user_settings.assert_not_called()
        window.deleteLater()
