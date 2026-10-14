import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QTableWidget, QTableWidgetItem

from wolflauncher.mods import RequiredMod
from wolflauncher.mods_feature import ModsFeatureMixin
from wolflauncher.workshop_subscription import ITEM_STATE_NEEDS_UPDATE, WorkshopUnsubscribeResult


class InstalledWorkshopLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def uninstall_window(self):
        mods = [RequiredMod(str(i), name=f"Mod {i}", installed=True) for i in range(100)]
        table = QTableWidget(100, 5)
        for row, mod in enumerate(mods):
            table.setItem(row, 2, QTableWidgetItem(mod.workshop_id))
        table.resize(500, 250)
        table.show()
        table.selectRow(60)
        self.app.processEvents()
        table.verticalScrollBar().setValue(55)
        window = SimpleNamespace(
            installed_workshop_mods=mods,
            mods_table=table,
            viewing_installed_workshop_library=Mock(return_value=True),
            _mods_cell=lambda row, column: table.item(row, column).text(),
            mod_summary=Mock(),
            update_mod_detail_card=Mock(),
            show_installed_workshop_library=Mock(),
            workshop_unsubscribe_worker=Mock(),
        )
        self.addCleanup(table.close)
        return window

    @patch("wolflauncher.mods_feature.QMessageBox.information")
    def test_successful_uninstall_removes_row_without_resetting_scroll(self, _information):
        window = self.uninstall_window()
        window.mods_table.sortItems(2, Qt.DescendingOrder)
        window.mods_table.verticalScrollBar().setValue(55)
        scroll = window.mods_table.verticalScrollBar().value()

        ModsFeatureMixin.finish_workshop_uninstall(
            window, WorkshopUnsubscribeResult("60", unsubscribed=True)
        )
        ModsFeatureMixin.clear_workshop_unsubscribe_worker(window)

        self.assertEqual(window.mods_table.rowCount(), 99)
        self.assertNotIn("60", [m.workshop_id for m in window.installed_workshop_mods])
        self.assertNotIn("60", [window.mods_table.item(row, 2).text() for row in range(99)])
        self.assertEqual(window.mods_table.verticalScrollBar().value(), scroll)
        window.show_installed_workshop_library.assert_not_called()
        self.assertIsNone(window.workshop_unsubscribe_worker)

    @patch("wolflauncher.mods_feature.QMessageBox.warning")
    def test_failed_uninstall_keeps_row_selection_and_scroll(self, _warning):
        window = self.uninstall_window()
        scroll = window.mods_table.verticalScrollBar().value()

        ModsFeatureMixin.finish_workshop_uninstall(
            window, WorkshopUnsubscribeResult("60", error="Steam unavailable")
        )
        ModsFeatureMixin.clear_workshop_unsubscribe_worker(window)

        self.assertEqual(len(window.installed_workshop_mods), 100)
        self.assertEqual(window.mods_table.rowCount(), 100)
        self.assertEqual(window.mods_table.currentRow(), 60)
        self.assertEqual(window.mods_table.verticalScrollBar().value(), scroll)
        window.show_installed_workshop_library.assert_not_called()
        window.update_mod_detail_card.assert_called_once_with()

    @patch("wolflauncher.mods_feature.QMessageBox.information")
    @patch("wolflauncher.mods_feature.remove_local_workshop_mod")
    @patch("wolflauncher.mods_feature.QMessageBox.warning")
    def test_leftover_cleanup_requires_confirmation(self, warning, remove, _information):
        for reply in (QMessageBox.Cancel, QMessageBox.Yes):
            with self.subTest(reply=reply):
                window = self.uninstall_window()
                window.workshop_unsubscribe_worker.install = SimpleNamespace(
                    workshop_dir=Path("selected-workshop")
                )
                warning.return_value = reply
                remove.reset_mock()
                ModsFeatureMixin.finish_workshop_uninstall(
                    window, WorkshopUnsubscribeResult("60", not_subscribed=True)
                )
                if reply == QMessageBox.Yes:
                    remove.assert_called_once_with(Path("selected-workshop"), "60")
                    self.assertEqual(window.mods_table.rowCount(), 99)
                else:
                    remove.assert_not_called()
                    self.assertEqual(window.mods_table.rowCount(), 100)

    @patch("wolflauncher.mods_feature.QMessageBox.information")
    @patch("wolflauncher.mods_feature.remove_local_workshop_mod", side_effect=OSError("Denied"))
    @patch("wolflauncher.mods_feature.QMessageBox.warning", return_value=QMessageBox.Yes)
    def test_failed_leftover_cleanup_keeps_mod(self, warning, _remove, information):
        window = self.uninstall_window()
        window.workshop_unsubscribe_worker.install = SimpleNamespace(
            workshop_dir=Path("selected-workshop")
        )
        ModsFeatureMixin.finish_workshop_uninstall(
            window, WorkshopUnsubscribeResult("60", not_subscribed=True)
        )
        self.assertEqual(window.mods_table.rowCount(), 100)
        self.assertEqual(len(window.installed_workshop_mods), 100)
        self.assertEqual(warning.call_args.args[1], "Could not remove local mod")
        information.assert_not_called()

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
