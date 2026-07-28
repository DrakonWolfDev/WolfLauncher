"""Qt presentation and command preparation for native and fallback launches."""

from PySide6.QtWidgets import QMessageBox

from .launch_dialogs import LaunchDialog, NativeLaunchPreviewDialog
from .launch_selection import server_with_resolved_ipv4
from .launcher import DEFAULT_PLAYER_NAME, LaunchError, build_launch_command
from .launch_preflight import usable_mod_result
from .native_launcher import (
    NativeLaunchError,
    format_native_launch_parity_report,
    native_launch_failure_details,
    prepare_native_launch,
    prepare_native_launch_parity_report,
)
from .settings import server_key
from .launch_history import record_launch


class LaunchExecutionCoordinator:
    """Prepare, preview and hand off the selected launch command for one window."""

    def __init__(self, window):
        self.window = window

    def preview_native(self):
        window = self.window
        if not window.last_mod_result or not window.last_mod_result.ok:
            QMessageBox.warning(
                window,
                "No mod check yet",
                "Check selected server mods successfully before preparing a native launch preview.",
            )
            return
        server = window.active_server_context()
        if not server:
            QMessageBox.warning(window, "No server selected", "Select a favourite server first.")
            return
        if server_key(server) != server_key(window.last_mod_result.server):
            QMessageBox.warning(
                window,
                "Mods are for another server",
                "Recheck selected server mods before preparing a native launch preview.",
            )
            return
        install = window.selected_steam_install()
        if not install:
            QMessageBox.critical(
                window,
                "Steam not detected",
                "WolfLauncher could not detect the selected Steam installation.",
            )
            return
        try:
            report = prepare_native_launch_parity_report(
                install,
                window.launcher_path.text(),
                server,
                window.player_name.text().strip() or DEFAULT_PLAYER_NAME,
                window.last_mod_result.required_mods,
                selected_steam_mode=window.native_steam_mode_key(),
            )
        except NativeLaunchError as exc:
            self.show_native_preview_error(exc)
            return
        dialog = NativeLaunchPreviewDialog(
            window,
            f"Native launch preview for {server.name}",
            format_native_launch_parity_report(report),
            report.preview.command,
        )
        dialog.exec()

    def perform(self, server):
        window = self.window
        try:
            command = self.build_command(server)
        except NativeLaunchError as exc:
            self.show_native_launch_error(exc)
            return
        except LaunchError as exc:
            QMessageBox.critical(window, "Launch failed", str(exc))
            return
        handoff_label = (
            "native launch command"
            if window.launch_engine_key() == "native"
            else "external launcher"
        )
        dialog = LaunchDialog(window, command, f"Launching {server.name}", handoff_label)
        dialog.exec()
        try:
            record_launch(server)
            if hasattr(window, "refresh_recent_servers"):
                window.refresh_recent_servers()
        except OSError:
            pass
        try:
            window.save_last_launch_report(dialog.copyable_output_text())
        except OSError as exc:
            QMessageBox.warning(
                window,
                "Could not save launch report",
                "The launch completed, but WolfLauncher could not save its support report.\n\n"
                f"{exc}",
            )

    def build_command(self, server, row: int | None = None) -> list[str]:
        window = self.window
        if row is None and window.active_discovered_server is None:
            row = window.table.currentRow()
        resolved_item = window.table.item(row, 5) if row is not None and row >= 0 else None
        resolved_ip = resolved_item.text().strip() if resolved_item else ""
        launch_server = server_with_resolved_ipv4(server, resolved_ip)
        player_name = window.player_name.text().strip() or DEFAULT_PLAYER_NAME
        if window.launch_engine_key() != "native":
            return build_launch_command(window.launcher_path.text(), player_name, launch_server)
        install = window.selected_steam_install()
        if not install:
            raise NativeLaunchError(
                "Selected Steam installation not detected",
                stage="Steam detection",
                guidance=(
                    "Open Settings health and confirm the selected native Steam install "
                    "or STEAM_ROOT library can be detected."
                ),
            )
        current_mod_result = usable_mod_result(server, window.last_mod_result, install.workshop_dir)
        required_mods = current_mod_result.required_mods if current_mod_result else None
        try:
            prepared = prepare_native_launch(install, launch_server, player_name, required_mods)
        except NativeLaunchError as exc:
            raise exc.with_details(
                native_launch_failure_details(
                    install,
                    window.launcher_path.text(),
                    launch_server,
                    player_name,
                    required_mods,
                    window.native_steam_mode_key(),
                )
            ) from exc
        return prepared.command

    def show_native_launch_error(self, error: NativeLaunchError):
        self._show_native_error(error, "Launch failed")

    def show_native_preview_error(self, error: NativeLaunchError):
        self._show_native_error(error, "Native preview failed")

    def _show_native_error(self, error: NativeLaunchError, title: str):
        box = QMessageBox(self.window)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(f"{title} during {error.stage}")
        box.setText(error.user_message())
        if error.details:
            box.setDetailedText(error.details)
        box.exec()
