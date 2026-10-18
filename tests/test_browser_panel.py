import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from wolflauncher.models import DiscoveredServer
from wolflauncher.server_browser_feature import ServerBrowserMixin
from wolflauncher.theme import apply_application_theme


class BrowserHarness(QWidget):
    _build_server_browser_tab = ServerBrowserMixin._build_server_browser_tab
    update_browser_active_filters = ServerBrowserMixin.update_browser_active_filters
    update_browser_detail_card = ServerBrowserMixin.update_browser_detail_card
    update_browser_selection_context = ServerBrowserMixin.update_browser_selection_context
    reset_browser_filters = ServerBrowserMixin.reset_browser_filters

    def __init__(self):
        super().__init__()
        self.settings = {}
        self.browser_mod_results = {}
        self.product_availability = {}
        self.selected_discovered_server = Mock(return_value=None)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        callback = Mock()
        setattr(self, name, callback)
        return callback


class BrowserPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        apply_application_theme(cls.app)

    def setUp(self):
        self.window = BrowserHarness()
        self.widget = self.window._build_server_browser_tab()
        self.widget.resize(1350, 720)
        self.widget.show()
        self.app.processEvents()
        self.addCleanup(self.widget.close)
        self.addCleanup(self.window.close)

    def test_map_filter_groups_official_maps_and_preserves_selection(self):
        from wolflauncher.browser_filter_options import set_combo_filter_options

        combo = self.window.browser_map
        values = ["namalsk", "enoch", "sakhal", "banov", "chernarusplus", "nasdara"]
        set_combo_filter_options(combo, "Any map", values)
        self.assertEqual(
            [combo.itemText(index) for index in range(combo.count())],
            ["Any map", "ChernarusPlus", "Livonia", "Sakhal", "Nasdara", "", "Banov", "Namalsk"],
        )
        self.assertFalse(combo.model().item(5).isEnabled())
        combo.setCurrentText("Namalsk")
        set_combo_filter_options(combo, "Any map", [*values, "deerisle"])
        self.assertEqual(combo.currentText(), "Namalsk")

    def test_filters_are_default_and_details_collapsed(self):
        self.assertEqual(self.window.browser_side_tabs.currentIndex(), 0)
        self.assertFalse(self.window.browser_details_toggle.isChecked())
        self.assertTrue(self.window.browser_perspective.isVisible())
        self.assertFalse(self.window.browser_advanced_panel.isVisible())

    def test_selection_opens_server_but_refresh_respects_filters(self):
        server = DiscoveredServer("Example", "203.0.113.1", 2302, 27016)
        self.window.selected_discovered_server.return_value = server
        self.window.update_browser_selection_context()
        self.assertEqual(self.window.browser_side_tabs.currentIndex(), 1)
        self.window.browser_side_tabs.setCurrentIndex(0)
        self.window.update_browser_selection_context()
        self.assertEqual(self.window.browser_side_tabs.currentIndex(), 0)
        self.window.selected_discovered_server.return_value = None
        self.window.update_browser_selection_context()
        self.assertEqual(self.window.browser_side_tabs.currentIndex(), 0)

    def test_filter_refresh_does_not_open_new_selection(self):
        server = DiscoveredServer("Example", "203.0.113.1", 2302, 27016)
        self.window.selected_discovered_server.return_value = server
        self.window.update_browser_selection_context(follow_selection=False)
        self.assertEqual(self.window.browser_side_tabs.currentIndex(), 0)
        self.window.update_browser_selection_context()
        self.assertEqual(self.window.browser_side_tabs.currentIndex(), 0)
        ServerBrowserMixin.handle_browser_cell_clicked(self.window, 0, 1)
        self.assertEqual(self.window.browser_side_tabs.currentIndex(), 1)

    def test_summary_and_clear_preserve_selection(self):
        self.window.browser_perspective.setCurrentIndex(1)
        self.window.update_browser_active_filters()
        summary = self.window.browser_active_filters_layout.itemAt(0).widget()
        self.assertIn("First-person only", summary.text())
        self.assertIn("&times;", summary.text())
        self.assertNotIn("?", summary.text())
        summary.linkActivated.emit("0")
        self.assertEqual(self.window.browser_perspective.currentIndex(), 0)
        self.window.browser_perspective.setCurrentIndex(1)
        self.window.reset_browser_filters()
        self.assertEqual(self.window.browser_perspective.currentIndex(), 0)


if __name__ == "__main__":
    unittest.main()
