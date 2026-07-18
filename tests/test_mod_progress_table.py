import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressBar, QTableWidget, QTableWidgetItem

from wolflauncher.app import MainWindow
from wolflauncher.models import Server
from wolflauncher.mods import ModCheckResult, RequiredMod
from wolflauncher.workshop_subscription import (
    ITEM_STATE_DOWNLOAD_PENDING,
    ITEM_STATE_DOWNLOADING,
    WorkshopItemProgress,
)


class ModProgressTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        mod = RequiredMod("111", "Example Mod")
        result = ModCheckResult(
            True,
            Server("Example", "Tests", "dayz.test", 2302, 27016),
            [mod],
        )
        table = QTableWidget(1, 5)
        for column, value in enumerate(["✗ Missing", "Example Mod", "111", "1 MiB", "url"]):
            item = QTableWidgetItem(value)
            item.setData(Qt.UserRole, "111")
            table.setItem(0, column, item)
        return SimpleNamespace(
            mods_table=table,
            _selected_mod_result=lambda successful=False: result,
        )

    def test_downloading_item_uses_green_progress_widget(self):
        window = self.make_window()

        MainWindow.update_mod_progress_rows(
            window,
            [WorkshopItemProgress("111", ITEM_STATE_DOWNLOADING, 25, 100)],
        )

        progress = window.mods_table.cellWidget(0, 0)
        self.assertIsInstance(progress, QProgressBar)
        self.assertEqual(progress.value(), 25)
        self.assertEqual(progress.format(), "Downloading 25%")

    def test_pending_item_keeps_text_status_without_progress_widget(self):
        window = self.make_window()

        MainWindow.update_mod_progress_rows(
            window,
            [WorkshopItemProgress("111", ITEM_STATE_DOWNLOAD_PENDING)],
        )

        self.assertIsNone(window.mods_table.cellWidget(0, 0))
        self.assertEqual(window.mods_table.item(0, 0).text(), "… Download pending")


if __name__ == "__main__":
    unittest.main()
