"""Restore the launcher after an automatically minimized game session."""

import time

from PySide6.QtCore import QTimer

from .platform_detection import dayz_game_process_check
from .single_instance import activate_window


class GameSessionMonitor:
    def __init__(self, window):
        self.window = window
        self.missing_checks = 0
        self.timer = QTimer(window)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.check)

    def start(self, *, restore_window=True):
        self.restore_window = restore_window
        self.window._game_session_active = True
        self.started_at = time.monotonic()
        self.observed_game = False
        self.missing_checks = 0
        self.timer.start()

    def check(self):
        if getattr(self.window, "_shutting_down", False) is True:
            self.timer.stop()
            return
        if dayz_game_process_check().running:
            self.observed_game = True
            self.missing_checks = 0
            return
        if not self.observed_game and time.monotonic() - self.started_at < 30:
            return
        # Allow a transient missing snapshot before treating the session as over.
        self.missing_checks += 1
        if self.missing_checks < 2:
            return
        self.timer.stop()
        self.window._game_session_active = False
        if self.restore_window:
            activate_window(self.window)


def minimize_for_game(window):
    """Arm a window-owned monitor only when a verified launch minimizes us."""
    monitor = getattr(window, "game_session_monitor", None)
    if monitor is None:
        monitor = GameSessionMonitor(window)
        window.game_session_monitor = monitor
    monitor.start()
    window.showMinimized()


def monitor_game_handoff(window):
    """Monitor a launched session even when automatic minimising is disabled."""
    monitor = getattr(window, "game_session_monitor", None)
    if monitor is None:
        monitor = GameSessionMonitor(window)
        window.game_session_monitor = monitor
    monitor.start(restore_window=False)
