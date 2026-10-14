import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QThread
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTableWidget

from wolflauncher.mods import RequiredMod
from wolflauncher.mods_feature import ModsFeatureMixin
from wolflauncher.workshop_subscription import WorkshopUnsubscribeResult


class LibraryWindow(ModsFeatureMixin):
    def __init__(self):
        self.mods_table = QTableWidget(0, 5)
        self.mods_table.resize(600, 250)
        self.workshop_library_cache = {}
        self.workshop_library_key = None
        self.workshop_library_showing = False
        self.workshop_library_worker = None
        self.workshop_unsubscribe_worker = None
        self.installed_workshop_mods = []
        self.server_launch = object()
        self.install = SimpleNamespace(workshop_dir=Path("workshop"), dayz_dir=Path("DayZ"))
        self.selected_steam_install = Mock(side_effect=lambda: self.install)
        self.viewing_installed_workshop_library = Mock(return_value=True)
        self.mod_server_title = Mock()
        self.mod_readiness = Mock()
        self.mod_summary = Mock()
        self.subscribe_missing_button = Mock()
        self.force_update_button = Mock()
        self.update_mod_detail_card = Mock()


class WorkshopLibraryLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def window(self):
        window = LibraryWindow()
        self.addCleanup(window.mods_table.close)
        return window

    @patch("wolflauncher.mods_feature.WorkshopLibraryWorker")
    def test_cached_rows_are_visible_before_worker_starts(self, worker_type):
        window = self.window()
        key = window._workshop_library_install_key(window.install)
        window.workshop_library_cache[key] = [RequiredMod("111", name="Cached", installed=True)]
        worker_type.return_value.start.side_effect = lambda: self.assertEqual(
            window.mods_table.item(0, 1).text(), "Cached"
        )
        window.show_installed_workshop_library()
        worker_type.return_value.start.assert_called_once_with()

    def test_refresh_preserves_selected_id_sort_and_scroll(self):
        window = self.window()
        mods = [RequiredMod(str(i), name=f"Mod {i:03}", installed=True) for i in range(100)]
        window.installed_workshop_mods = mods
        window._display_mod_rows(mods)
        window.mods_table.show()
        self.app.processEvents()
        window.mods_table.setSortingEnabled(True)
        window.mods_table.sortItems(1, Qt.DescendingOrder)
        window.mods_table.selectRow(60)
        selected_id = window._mods_cell(60, 2)
        window.mods_table.verticalScrollBar().setValue(55)
        scroll = window.mods_table.verticalScrollBar().value()

        window.finish_installed_workshop_library_load(list(reversed(mods)), "")

        self.assertEqual(window._mods_cell(window.mods_table.currentRow(), 2), selected_id)
        self.assertEqual(window.mods_table.verticalScrollBar().value(), scroll)
        self.assertTrue(window.mods_table.isSortingEnabled())
        self.assertEqual(window.mods_table.item(0, 1).text(), "Mod 099")

    def test_local_rows_are_usable_while_network_is_still_waiting(self):
        window = self.window()
        release_network = threading.Event()
        original_receive = window.receive_workshop_library_snapshot

        def receive(*args, **kwargs):
            self.assertEqual(QThread.currentThread(), self.app.thread())
            original_receive(*args, **kwargs)

        window.receive_workshop_library_snapshot = receive

        def metadata(_ids):
            release_network.wait(3)
            return {"111": {"title": "Published name"}}

        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "111").mkdir()
            window.install = SimpleNamespace(workshop_dir=Path(directory), running=False)
            with (
                patch("wolflauncher.workers.fetch_workshop_metadata", side_effect=metadata),
                patch("wolflauncher.workers.workshop_install_timestamps", return_value={}),
            ):
                window.show_installed_workshop_library()
                worker = window.workshop_library_worker
                try:
                    deadline = time.monotonic() + 2
                    while window.mods_table.rowCount() == 0 and time.monotonic() < deadline:
                        QTest.qWait(10)
                    self.assertEqual(window.mods_table.item(0, 2).text(), "111")
                    self.assertEqual(window.mods_table.item(0, 1).text(), "111")
                    self.assertTrue(worker.isRunning())
                finally:
                    release_network.set()
                    worker.wait(3000)
                    self.app.processEvents()
                self.assertEqual(window.mods_table.item(0, 1).text(), "Published name")

    def test_stale_install_result_is_cached_without_replacing_current_view(self):
        window = self.window()
        old_key = window._workshop_library_install_key(window.install)
        window.workshop_library_key = ("other-workshop", "other-DayZ", "stable")
        worker = SimpleNamespace(library_key=old_key, removed_ids=set())
        window.receive_workshop_library_snapshot(worker, [RequiredMod("111")])
        self.assertEqual(window.mods_table.rowCount(), 0)
        self.assertEqual(window.workshop_library_cache[old_key][0].workshop_id, "111")

    def test_local_snapshot_keeps_cached_workshop_names_until_final_refresh(self):
        window = self.window()
        key = window._workshop_library_install_key(window.install)
        window.workshop_library_key = key
        cached = RequiredMod("111", name="Cached title", installed=True)
        window.workshop_library_cache[key] = [cached]
        worker = SimpleNamespace(library_key=key, removed_ids=set())
        window.receive_workshop_library_snapshot(
            worker, [RequiredMod("111", name="111", installed=True)], local=True
        )
        self.assertIs(window.workshop_library_cache[key][0], cached)
        window.receive_workshop_library_snapshot(
            worker, [RequiredMod("111", name="Fresh title", installed=True)]
        )
        self.assertEqual(window.mods_table.item(0, 1).text(), "Fresh title")

    def test_shutdown_does_not_restart_refresh_for_pending_install_switch(self):
        window = self.window()
        window._shutting_down = True
        window.workshop_library_worker = Mock(library_key=("old", "old", "stable"))
        window.workshop_library_key = ("new", "new", "stable")
        window.show_installed_workshop_library = Mock()
        window.clear_installed_workshop_library_worker()
        window.show_installed_workshop_library.assert_not_called()

    def test_install_switch_waits_for_worker_completion_before_restarting(self):
        window = self.window()
        worker = Mock(library_key=("old", "old", "stable"))
        window.workshop_library_worker = worker
        window.workshop_library_key = ("new", "new", "stable")
        window.show_installed_workshop_library = Mock()
        window.clear_installed_workshop_library_worker()
        self.assertIsNone(window.workshop_library_worker)
        worker.deleteLater.assert_called_once_with()
        window.show_installed_workshop_library.assert_called_once_with()

    @patch("wolflauncher.mods_feature.QMessageBox.information")
    def test_refresh_does_not_restore_uninstalled_mod(self, _information):
        window = self.window()
        key = window._workshop_library_install_key(window.install)
        worker = SimpleNamespace(library_key=key, removed_ids=set())
        window.workshop_library_key = key
        window.workshop_library_worker = worker
        window.workshop_unsubscribe_worker = SimpleNamespace(install=window.install)
        mods = [RequiredMod("111", installed=True), RequiredMod("222", installed=True)]
        window.receive_workshop_library_snapshot(worker, mods)

        window.finish_workshop_uninstall(WorkshopUnsubscribeResult("111", unsubscribed=True))
        window.receive_workshop_library_snapshot(worker, mods)

        self.assertEqual([mod.workshop_id for mod in window.installed_workshop_mods], ["222"])
        self.assertEqual(window.mods_table.rowCount(), 1)
        self.assertEqual(window.workshop_library_cache[key][0].workshop_id, "222")
