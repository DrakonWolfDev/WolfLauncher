import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QMessageBox

from wolflauncher.mods import RequiredMod
from wolflauncher.mods_feature import ModsFeatureMixin
from wolflauncher.workshop_subscription import ITEM_STATE_NEEDS_UPDATE


class InstalledWorkshopLibraryTests(unittest.TestCase):
    def test_uninstall_button_is_visible_only_in_stable_installed_library(self):
        def window(viewing_library, experimental=False):
            return SimpleNamespace(
                viewing_installed_workshop_library=Mock(return_value=viewing_library),
                show_installed_workshop_library=Mock(),
                last_mod_result=None,
                update_installed_mods_button=Mock(),
                mod_detail_uninstall_button=Mock(),
                recheck_mods_button=Mock(),
                dayz_product=Mock(return_value=SimpleNamespace(experimental=experimental)),
            )

        required_view = window(False)
        ModsFeatureMixin.change_mod_view(required_view, 0)
        required_view.mod_detail_uninstall_button.setVisible.assert_called_once_with(False)

        installed_view = window(True)
        ModsFeatureMixin.change_mod_view(installed_view, 1)
        installed_view.mod_detail_uninstall_button.setVisible.assert_called_once_with(True)

        experimental_view = window(True, experimental=True)
        ModsFeatureMixin.change_mod_view(experimental_view, 1)
        experimental_view.mod_detail_uninstall_button.setVisible.assert_called_once_with(False)

    @patch("wolflauncher.mods_feature.WorkshopUnsubscribeWorker")
    @patch("wolflauncher.mods_feature.QMessageBox.warning", return_value=QMessageBox.Yes)
    def test_confirmed_uninstall_uses_steam_worker(self, warning, worker_type):
        worker = Mock()
        worker_type.return_value = worker
        mod = RequiredMod("111", name="Example Mod", installed=True)
        install = SimpleNamespace(workshop_dir=object(), running=True)
        window = SimpleNamespace(
            viewing_installed_workshop_library=Mock(return_value=True),
            selected_required_mod=Mock(return_value=mod),
            experimental_product_active=Mock(return_value=False),
            selected_steam_install=Mock(return_value=install),
            workshop_unsubscribe_worker=None,
            mod_detail_uninstall_button=Mock(),
            finish_workshop_uninstall=Mock(),
            clear_workshop_unsubscribe_worker=Mock(),
        )

        ModsFeatureMixin.uninstall_selected_workshop_mod(window)

        worker_type.assert_called_once_with("111", install)
        worker.start.assert_called_once_with()
        self.assertIn("will not delete folders directly", warning.call_args.args[2])

    @patch("wolflauncher.mods_feature.WorkshopUnsubscribeWorker")
    @patch("wolflauncher.mods_feature.QMessageBox.warning", return_value=QMessageBox.Cancel)
    def test_cancelled_uninstall_does_not_start_worker(self, _warning, worker_type):
        mod = RequiredMod("111", name="Example Mod", installed=True)
        window = SimpleNamespace(
            viewing_installed_workshop_library=Mock(return_value=True),
            selected_required_mod=Mock(return_value=mod),
            experimental_product_active=Mock(return_value=False),
            selected_steam_install=Mock(
                return_value=SimpleNamespace(workshop_dir=object(), running=True)
            ),
            workshop_unsubscribe_worker=None,
        )

        ModsFeatureMixin.uninstall_selected_workshop_mod(window)

        worker_type.assert_not_called()

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
