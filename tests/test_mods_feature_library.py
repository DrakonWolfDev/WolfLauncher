import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QMessageBox

from wolflauncher.mods import RequiredMod
from wolflauncher.mods_feature import ModsFeatureMixin
from wolflauncher.workshop_subscription import ITEM_STATE_NEEDS_UPDATE


class InstalledWorkshopLibraryTests(unittest.TestCase):
    def test_experimental_can_start_confirmed_missing_mod_resolution(self):
        resolution = Mock()
        window = SimpleNamespace(workshop_resolution=resolution)

        ModsFeatureMixin.subscribe_missing_workshop_mods(window)

        resolution.subscribe_missing_mods.assert_called_once_with()

    def test_recheck_follows_the_active_mod_view(self):
        library_window = SimpleNamespace(
            viewing_installed_workshop_library=Mock(return_value=True),
            show_installed_workshop_library=Mock(),
            check_selected_server_mods=Mock(),
        )
        ModsFeatureMixin.recheck_current_mod_view(library_window)
        library_window.show_installed_workshop_library.assert_called_once_with()
        library_window.check_selected_server_mods.assert_not_called()

        server_window = SimpleNamespace(
            viewing_installed_workshop_library=Mock(return_value=False),
            show_installed_workshop_library=Mock(),
            check_selected_server_mods=Mock(),
        )
        ModsFeatureMixin.recheck_current_mod_view(server_window)
        server_window.show_installed_workshop_library.assert_not_called()
        server_window.check_selected_server_mods.assert_called_once_with(force=True)

    @patch("wolflauncher.mods_feature.WorkshopSubscriptionWorker")
    @patch("wolflauncher.mods_feature.QProgressDialog")
    @patch("wolflauncher.mods_feature.QMessageBox.question", return_value=QMessageBox.Yes)
    def test_update_all_starts_a_monitor_for_only_pending_items(
        self, _question, dialog_type, worker_type
    ):
        dialog = Mock()
        dialog_type.return_value = dialog
        worker = Mock()
        worker_type.return_value = worker
        install = SimpleNamespace(workshop_dir=object(), running=True)
        pending = RequiredMod(
            "111", name="Pending", installed=True, workshop_state=ITEM_STATE_NEEDS_UPDATE
        )
        ready = RequiredMod("222", name="Ready", installed=True)
        window = SimpleNamespace(
            viewing_installed_workshop_library=Mock(return_value=True),
            installed_workshop_mods=[pending, ready],
            workshop_subscription_worker=None,
            launch_engine_key=Mock(return_value="native"),
            selected_steam_install=Mock(return_value=install),
            workshop_subscription_names={},
            workshop_subscription_dialog=None,
            workshop_subscription_monitor_hidden=False,
            update_workshop_subscription_progress=Mock(),
            finish_installed_workshop_update=Mock(),
            clear_workshop_subscription_worker=Mock(),
            stop_workshop_subscription_monitoring=Mock(),
        )

        ModsFeatureMixin.update_all_installed_mods(window)

        dialog_type.assert_called_once()
        worker_type.assert_called_once_with(
            ["111"], install, force_update=True, subscribe_missing=False
        )
        worker.start.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
