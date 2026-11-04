"""Bounded, user-local activation and URL handoff for the desktop application."""

from __future__ import annotations

import json
import time
from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .server_links import MAX_SERVER_LINK_BYTES

SERVER_NAME = "WolfLauncher-single-instance-v1"
ACTIVATION_TIMEOUT_MS = 500
MAX_FRAME_BYTES = 4096
MAX_CLIENTS = 16
MAX_PENDING_URLS = 4


def _unique_fields(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Repeated IPC field")
    return result


def activate_window(window) -> None:
    """Restore and request focus for the existing main window."""
    if window.isMinimized():
        window.showNormal()
    else:
        window.show()
    window.raise_()
    window.activateWindow()


class SingleInstanceGuard:
    """Own a local server or send one bounded request to the existing instance."""

    def __init__(self, server_name: str = SERVER_NAME) -> None:
        self.server_name = server_name
        self.server = QLocalServer()
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        self.server.setMaxPendingConnections(MAX_CLIENTS)
        self._activate: Callable[[], None] | None = None
        self._url_handler: Callable[[str], None] | None = None
        self._activation_pending = False
        self._pending_urls: list[str] = []
        self._clients: dict[QLocalSocket, bytearray] = {}
        self.delivery_error = ""

    def start_or_notify(self, url: str | None = None) -> bool:
        """Return True for the primary, otherwise forward activation/the URL."""
        if self._notify_existing_instance(url):
            return False
        QLocalServer.removeServer(self.server_name)
        if not self.server.listen(self.server_name):
            if self._notify_existing_instance(url):
                return False
            raise RuntimeError("WolfLauncher could not establish its single-instance connection.")
        self.server.newConnection.connect(self._handle_activation_request)
        return True

    def set_activation_handler(self, handler: Callable[[], None]) -> None:
        self._activate = handler
        if self._activation_pending:
            self._activation_pending = False
            handler()

    def set_url_handler(self, handler: Callable[[str], None]) -> None:
        self._url_handler = handler
        pending, self._pending_urls = self._pending_urls, []
        for url in pending:
            QTimer.singleShot(0, lambda value=url: handler(value))

    def close(self) -> None:
        for socket in list(self._clients):
            self._finish(socket)
        # A secondary must never unlink the primary's listening socket.
        if self.server.isListening():
            self.server.close()
            QLocalServer.removeServer(self.server_name)

    def _notify_existing_instance(self, url=None) -> bool:
        self.delivery_error = ""
        if url is not None and (
            not isinstance(url, str) or len(url.encode("utf-8")) > MAX_SERVER_LINK_BYTES
        ):
            raise ValueError("This server link is too long.")
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(ACTIVATION_TIMEOUT_MS):
            return False
        frame = (
            b"activate"
            if url is None
            else (
                json.dumps({"action": "open_url", "url": url}, ensure_ascii=False).encode("utf-8")
                + b"\n"
            )
        )
        socket.write(frame)
        socket.waitForBytesWritten(ACTIVATION_TIMEOUT_MS)
        # Keep the sender alive until the primary has received the frame. This
        # also avoids losing activation-only writes on Windows named pipes.
        response = bytearray()
        deadline = time.monotonic() + 1
        while b"\n" not in response and len(response) < 32:
            if socket.bytesAvailable():
                response.extend(bytes(socket.read(32 - len(response))))
                continue
            remaining = int((deadline - time.monotonic()) * 1000)
            if remaining <= 0 or not socket.waitForReadyRead(remaining):
                break
        acknowledgement = bytes(response)
        if acknowledgement != b"accepted\n":
            self.delivery_error = (
                "The running WolfLauncher did not confirm this server link. "
                "Close that instance and open the link again."
                if url is not None
                else "The running WolfLauncher did not confirm activation. "
                "Close that instance and open WolfLauncher again."
            )
        socket.disconnectFromServer()
        return True

    def _handle_activation_request(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            if len(self._clients) >= MAX_CLIENTS:
                socket.abort()
                socket.deleteLater()
                continue
            socket.setReadBufferSize(MAX_FRAME_BYTES + 1)
            self._clients[socket] = bytearray()
            timer = QTimer(socket)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda client=socket: self._finish(client))
            timer.start(1000)
            socket.readyRead.connect(lambda client=socket: self._read(client))
            socket.disconnected.connect(lambda client=socket: self._disconnected(client))
            self._read(socket)

    def _finish(self, socket):
        if socket not in self._clients:
            return
        self._clients.pop(socket)
        socket.abort()
        socket.deleteLater()

    def _disconnected(self, socket):
        self._read(socket)
        self._finish(socket)

    def _read(self, socket):
        buffer = self._clients.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.read(MAX_FRAME_BYTES + 1)))
        if len(buffer) > MAX_FRAME_BYTES:
            self._finish(socket)
            return
        if buffer == b"activate":
            self._accept(socket)
            self._activate_primary()
            return
        if b"\n" not in buffer:
            return
        frame, extra = bytes(buffer).split(b"\n", 1)
        try:
            data = json.loads(frame, object_pairs_hook=_unique_fields)
            if extra or not isinstance(data, dict) or set(data) != {"action", "url"}:
                raise ValueError
            url = data["url"]
            if (
                data["action"] != "open_url"
                or not isinstance(url, str)
                or len(url.encode("utf-8")) > MAX_SERVER_LINK_BYTES
            ):
                raise ValueError
        except (ValueError, UnicodeError, RecursionError):
            self._finish(socket)
            return
        if self._url_handler is None and len(self._pending_urls) >= MAX_PENDING_URLS:
            self._finish(socket)
            return
        self._accept(socket)
        self._activate_primary()
        if self._url_handler is not None:
            # Queue delivery so a modal review never blocks socket cleanup.
            QTimer.singleShot(0, lambda: self._url_handler(url))
        elif len(self._pending_urls) < MAX_PENDING_URLS:
            self._pending_urls.append(url)

    def _accept(self, socket):
        socket.write(b"accepted\n")
        socket.flush()
        self._clients.pop(socket, None)
        socket.disconnectFromServer()
        socket.deleteLater()

    def _activate_primary(self):
        if self._activate is None:
            self._activation_pending = True
        else:
            self._activate()
