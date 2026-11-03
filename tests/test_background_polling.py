import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from wolflauncher.background_polling import OptionalPollingController, optional_polling_paused
from wolflauncher.curated_servers_controller import CuratedServersMixin
from wolflauncher.server_browser_feature import ServerBrowserMixin


class BackgroundPollingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def window(self):
        return SimpleNamespace(
            _game_session_active=False,
            preflight_dialog=None,
            identity_workers={},
            context_mod_workers={},
            workshop_subscription_worker=None,
            refresh_seconds=Mock(value=Mock(return_value=30)),
            refresh_statuses=Mock(),
            refresh_automatic_statuses=Mock(),
            maybe_auto_refresh_configured_provider=Mock(),
            schedule_selected_discovered_server_check=Mock(),
            schedule_initial_results_freshness_check=Mock(),
            tabs=Mock(currentIndex=Mock(return_value=1)),
            server_browser_tab_index=1,
        )

    def test_automatic_status_ticks_do_no_work_during_game_then_resume(self):
        window = self.window()
        window._game_session_active = True
        for _ in range(10):
            CuratedServersMixin.refresh_automatic_statuses(window)
        window.refresh_statuses.assert_not_called()
        window._game_session_active = False
        CuratedServersMixin.refresh_automatic_statuses(window)
        window.refresh_statuses.assert_called_once_with()

    def test_hidden_and_minimised_window_pause_optional_checks(self):
        window = QWidget()
        self.assertTrue(optional_polling_paused(window))
        window.show()
        self.app.processEvents()
        self.assertFalse(optional_polling_paused(window))
        window.showMinimized()
        self.app.processEvents()
        self.assertTrue(optional_polling_paused(window))
        window.close()

    def test_old_request_finishing_does_not_release_new_request(self):
        window = self.window()
        window.identity_workers = {"old": Mock(), "new": Mock()}
        self.assertTrue(optional_polling_paused(window))
        window.identity_workers.pop("old")
        self.assertTrue(optional_polling_paused(window))
        window.identity_workers.pop("new")
        self.assertFalse(optional_polling_paused(window))

    def test_pause_does_not_cancel_downloads_or_process_monitor(self):
        window = self.window()
        worker = Mock(isRunning=Mock(return_value=True))
        window.workshop_subscription_worker = worker
        window.game_session_monitor = Mock()
        self.assertTrue(optional_polling_paused(window))
        worker.cancel.assert_not_called()
        window.game_session_monitor.timer.stop.assert_not_called()

    def test_resume_refreshes_visible_stale_data_once(self):
        window = self.window()
        with patch("wolflauncher.background_polling.QTimer"):
            controller = OptionalPollingController(window)
        window._game_session_active = True
        controller.check()
        window.schedule_initial_results_freshness_check.assert_not_called()
        window._game_session_active = False
        controller.check()
        controller.check()
        window.refresh_automatic_statuses.assert_called_once_with()
        window.maybe_auto_refresh_configured_provider.assert_called_once_with()
        window.schedule_selected_discovered_server_check.assert_called_once_with()
        window.schedule_initial_results_freshness_check.assert_called_once_with()

    def test_paused_freshness_and_auto_provider_do_not_create_workers(self):
        window = self.window()
        window._game_session_active = True
        # These return before touching provider/database/worker setup.
        ServerBrowserMixin._schedule_results_freshness_check(window)
        ServerBrowserMixin.maybe_auto_refresh_configured_provider(window)
        ServerBrowserMixin.check_selected_discovered_server_status(window)

    def test_disabled_automatic_status_refresh_stays_disabled(self):
        window = self.window()
        window.refresh_seconds.value.return_value = 0
        CuratedServersMixin.refresh_automatic_statuses(window)
        window.refresh_statuses.assert_not_called()
