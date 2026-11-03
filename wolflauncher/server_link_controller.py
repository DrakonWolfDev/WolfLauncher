"""Review incoming links before entering the existing selected-server checks."""

from dataclasses import dataclass

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from .models import Server
from .server_links import ServerLinkError, parse_server_link


@dataclass(frozen=True)
class LinkMetadata:
    server: Server
    notice: str


def resolve_link_metadata(target, *, resolver=None, host_resolver=None):
    """Bind a directory reference only at the supplied game endpoint.

    If that reference cannot be confirmed, offer the explicit endpoint fallback.
    Never silently redirect to another game address, or trust an edition hint.
    """
    server = Server(
        f"Shared server at {target.host}:{target.game_port}",
        "Shared link (read-only)",
        target.host,
        target.game_port,
        target.query_port,
        strict_endpoint=True,
    )
    if not target.server_id:
        return LinkMetadata(
            server, "This link uses its supplied address. Live checks will verify the DayZ edition."
        )
    from .server_discovery import resolve_dayz_server_wolfapi_v1
    from .status import resolve_host

    resolver = resolver or resolve_dayz_server_wolfapi_v1
    host_resolver = host_resolver or resolve_host
    try:
        rows = resolver(target.host, game_port=target.game_port, product="all", timeout=4)
        address = host_resolver(target.host) if rows else target.host
        matches = [
            row
            for row in rows
            if row.stable_server_id == target.server_id
            and row.host in {target.host, address}
            and row.game_port == target.game_port
        ]
        if len(matches) == 1:
            row = matches[0]
            server.name = " ".join((row.server_name or row.name or server.name).split())[:160]
            server.stable_server_id = target.server_id
            server.query_port = row.query_port
            return LinkMetadata(
                server,
                "The directory reference matches this game address. The live DayZ edition and mods still need checking.",
            )
    except (OSError, ValueError, RuntimeError):
        pass
    return LinkMetadata(
        server,
        "The directory reference could not be confirmed at this address. The link may be out of date. "
        "Inspect the supplied address only if it is the server you intend to use.",
    )


class LinkMetadataWorker(QThread):
    metadata_ready = Signal(object)

    def __init__(self, target, parent=None):
        super().__init__(parent)
        self.target = target

    def cancel(self):
        self.requestInterruption()

    def run(self):
        if self.isInterruptionRequested():
            return
        try:
            result = resolve_link_metadata(self.target)
        except Exception:
            result = LinkMetadata(
                Server(
                    f"Shared server at {self.target.host}:{self.target.game_port}",
                    "Shared link (read-only)",
                    self.target.host,
                    self.target.game_port,
                    self.target.query_port,
                    strict_endpoint=True,
                ),
                "The directory reference could not be checked. Review the supplied address before continuing.",
            )
        if not self.isInterruptionRequested():
            self.metadata_ready.emit(result)


class ServerLinkReviewDialog(QDialog):
    def __init__(self, parent, target):
        super().__init__(parent)
        self.setWindowTitle("Review shared DayZ server")
        self.setMinimumWidth(500)
        self.resize(620, 300)
        self.server = None
        self.scan_worker = None
        layout = QVBoxLayout(self)
        self.details = QLabel()
        self.details.setTextFormat(Qt.PlainText)
        self.details.setWordWrap(True)
        self.details.setText(
            f"Address: {target.host}\nGame port: {target.game_port}\nQuery port: {target.query_port}"
            + (
                f"\nEdition hint: {target.product} (not verified)"
                if target.product != "unknown"
                else ""
            )
        )
        layout.addWidget(self.details)
        self.notice = QLabel("Checking the directory reference…")
        self.notice.setTextFormat(Qt.PlainText)
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        explanation = QLabel(
            "Inspecting shows this server's edition and mod requirements. "
            "Use Connect after reviewing those results. Workshop downloads keep their existing confirmation."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.inspect = buttons.addButton("Inspect server", QDialogButtonBox.AcceptRole)
        self.inspect.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def show_metadata(self, result):
        self.server = result.server
        self.details.setText(
            f"{result.server.name}\nAddress: {result.server.host}\n"
            f"Game port: {result.server.game_port}\nQuery port: {result.server.query_port}"
        )
        self.notice.setText(result.notice)
        self.inspect.setText(
            "Inspect server" if result.server.stable_server_id else "Inspect supplied address"
        )
        self.inspect.setEnabled(True)

    def scan_finished(self):
        self.scan_worker = None

    def reject(self):
        if self.scan_worker is not None:
            self.scan_worker.cancel()
        super().reject()


def link_review_blocked(window):
    if getattr(window, "_shutting_down", False) or getattr(window, "_game_session_active", False):
        return True
    dialog = getattr(window, "preflight_dialog", None)
    if dialog is not None and dialog.isVisible():
        return True
    for name in ("workshop_subscription_worker", "workshop_unsubscribe_worker"):
        worker = getattr(window, name, None)
        if worker is not None and worker.isRunning():
            return True
    return False


class ServerLinkCoordinator:
    def __init__(self, window):
        self.window = window
        self.reviewing = False

    def prompt(self):
        value, accepted = QInputDialog.getText(
            self.window, "Open server link", "Paste a shared WolfLauncher link:"
        )
        if accepted:
            self.receive(value.strip())

    def receive(self, value):
        window = self.window
        if getattr(window, "_shutting_down", False):
            return
        if self.reviewing or link_review_blocked(window):
            window.statusBar().showMessage(
                "Finish the current server review, connection or Workshop operation, then open the link again.",
                10000,
            )
            return
        try:
            target = parse_server_link(value)
        except ServerLinkError as exc:
            QMessageBox.warning(window, "Server link unavailable", str(exc))
            return
        active = getattr(window, "link_metadata_worker", None)
        if active is not None and active.isRunning():
            window.statusBar().showMessage(
                "The previous link check is stopping. Open the link again shortly.", 5000
            )
            return
        self.reviewing = True
        dialog = ServerLinkReviewDialog(window, target)
        worker = None
        if target.server_id:
            worker = LinkMetadataWorker(target, window)
            window.link_metadata_worker = worker
            dialog.scan_worker = worker
            worker.metadata_ready.connect(dialog.show_metadata)
            worker.finished.connect(dialog.scan_finished)
            worker.finished.connect(lambda: self._finished(worker))
            worker.finished.connect(worker.deleteLater)
            worker.start()
        else:
            dialog.show_metadata(resolve_link_metadata(target))
        try:
            if (
                dialog.exec() != QDialog.Accepted
                or dialog.server is None
                or link_review_blocked(window)
            ):
                return
            # A link creates an in-memory target, never a saved favourite or an
            # automatic join/subscription. The normal checks reject stale owners.
            window.server_launch.invalidate()
            window.active_discovered_server = dialog.server
            window.active_discovered_cache_key = ""
            window.last_mod_result = None
            window.update_launch_button_text()
            window.tabs.setCurrentIndex(window.mods_tab_index)
            window.check_server_mods(dialog.server, force=True)
        finally:
            if worker is not None and dialog.scan_worker is not None:
                worker.cancel()
            self.reviewing = False
            dialog.deleteLater()

    def _finished(self, worker):
        if getattr(self.window, "link_metadata_worker", None) is worker:
            self.window.link_metadata_worker = None
