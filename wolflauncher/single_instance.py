"""Cross-platform single-instance coordination for the desktop application."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "WolfLauncher-single-instance-v1"
ACTIVATION_TIMEOUT_MS = 500


def activate_window(window) -> None:
    """Restore and request focus for the existing main window."""
    if window.isMinimized():
        window.showNormal()
    else:
        window.show()
    window.raise_()
    window.activateWindow()


class SingleInstanceGuard:
    """Own a local server or notify the existing WolfLauncher instance."""

    def __init__(self, server_name: str = SERVER_NAME) -> None:
        self.server_name = server_name
        self.server = QLocalServer()
        self._activate: Callable[[], None] | None = None
        self._activation_pending = False

    def start_or_notify(self) -> bool:
        """Return True for the primary instance, otherwise notify it and return False."""
        if self._notify_existing_instance():
            return False

        # A crashed instance can leave a stale named socket on Unix. It is safe
        # to remove only after a connection attempt has established no owner.
        QLocalServer.removeServer(self.server_name)
        if not self.server.listen(self.server_name):
            # A concurrent launch may have won the race to listen.
            return not self._notify_existing_instance()
        self.server.newConnection.connect(self._handle_activation_request)
        return True

    def set_activation_handler(self, handler: Callable[[], None]) -> None:
        self._activate = handler
        if self._activation_pending:
            self._activation_pending = False
            handler()

    def close(self) -> None:
        if self.server.isListening():
            self.server.close()
        QLocalServer.removeServer(self.server_name)

    def _notify_existing_instance(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(ACTIVATION_TIMEOUT_MS):
            return False
        socket.write(b"activate")
        socket.waitForBytesWritten(ACTIVATION_TIMEOUT_MS)
        socket.disconnectFromServer()
        return True

    def _handle_activation_request(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.readAll()
            socket.disconnectFromServer()
            if self._activate is None:
                self._activation_pending = True
            else:
                self._activate()
