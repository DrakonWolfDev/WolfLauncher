"""Restore the launcher after an automatically minimized game session."""

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

    def start(self):
        self.missing_checks = 0
        self.timer.start()

    def check(self):
        if dayz_game_process_check().running:
            self.missing_checks = 0
            return
        # Allow a transient missing snapshot before treating the session as over.
        self.missing_checks += 1
        if self.missing_checks < 2:
            return
        self.timer.stop()
        activate_window(self.window)


def minimize_for_game(window):
    """Arm a window-owned monitor only when a verified launch minimizes us."""
    monitor = getattr(window, "game_session_monitor", None)
    if monitor is None:
        monitor = GameSessionMonitor(window)
        window.game_session_monitor = monitor
    monitor.start()
    window.showMinimized()
