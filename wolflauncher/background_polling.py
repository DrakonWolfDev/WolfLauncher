"""Defer optional polling while the user is joining, playing or away."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget


def optional_polling_paused(window):
    if getattr(window, "_shutting_down", False) is True:
        return True
    if isinstance(window, QWidget) and (not window.isVisible() or window.isMinimized()):
        return True
    if getattr(window, "_game_session_active", False) is True:
        return True
    dialog = getattr(window, "preflight_dialog", None)
    if dialog is not None and dialog.isVisible():
        return True
    for name in ("identity_workers", "context_mod_workers"):
        workers = getattr(window, name, None)
        if isinstance(workers, dict) and workers:
            return True
    worker = getattr(window, "workshop_subscription_worker", None)
    return bool(worker is not None and worker.isRunning())


class OptionalPollingController:
    """Observe current owners; an old callback cannot release a newer join."""

    def __init__(self, window):
        self.window = window
        self.paused = False
        window.optional_polling_timer = QTimer(window)
        window.optional_polling_timer.setInterval(1000)
        window.optional_polling_timer.timeout.connect(self.check)
        window.optional_polling_timer.start()

    def check(self):
        paused = optional_polling_paused(self.window)
        was_paused, self.paused = self.paused, paused
        if not was_paused or paused:
            return
        window = self.window
        window.refresh_automatic_statuses()
        window.maybe_auto_refresh_configured_provider()
        if window.tabs.currentIndex() == window.server_browser_tab_index:
            window.schedule_selected_discovered_server_check()
            window.schedule_initial_results_freshness_check()
