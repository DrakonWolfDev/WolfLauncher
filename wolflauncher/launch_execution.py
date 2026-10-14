"""Qt presentation and command preparation for native and fallback launches."""

from dataclasses import replace

from PySide6.QtWidgets import QMessageBox

from .launch_dialogs import LaunchDialog, NativeLaunchPreviewDialog
from .launch_preflight import usable_mod_result
from .launch_selection import server_with_resolved_ipv4
from .launcher import DEFAULT_PLAYER_NAME, LaunchError, build_launch_command
from .native_launcher import (
    NativeLaunchError,
    format_native_launch_parity_report,
    native_launch_failure_details,
    prepare_native_launch,
    prepare_native_launch_parity_report,
)
from .product_availability import installation_still_present
from .settings import server_key


class LaunchExecutionCoordinator:
    """Prepare, preview and hand off the selected launch command for one window."""

    def __init__(self, window):
        self.window = window

    def preview_native(self):
        window = self.window
        if hasattr(window, "server_launch"):
            server = window.active_server_context()
            if server:
                window.server_launch.prepare(
                    server,
                    lambda context: window.server_launch.check_mods(
                        context,
                        lambda result: (
                            window.server_launch.revalidate(context, self._preview_resolved)
                            if result.ok
                            else None
                        ),
                    ),
                )
            return
        self._preview_resolved(None)

    def _preview_resolved(self, context):
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
        if context is not None:
            if not window.server_launch.current(context):
                return
            context = replace(context, engine="native")
            window.server_launch.context = context
            server = context.server
        if server_key(server) != server_key(window.last_mod_result.server):
            QMessageBox.warning(
                window,
                "Mods are for another server",
                "Recheck selected server mods before preparing a native launch preview.",
            )
            return
        install = context.install if context is not None else window.selected_steam_install()
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
            **(
                {"launch_callback": lambda: self._launch_from_preview(context)}
                if context is not None
                else {}
            ),
        )
        if context is not None:
            dialog.launch_callback = lambda: (dialog.accept(), self._launch_from_preview(context))
        dialog.exec()

    def _launch_from_preview(self, context):
        if not self.window.server_launch.current(context, require_fresh=False):
            QMessageBox.warning(
                self.window,
                "Preview no longer current",
                "Server selection changed. Prepare a new preview before joining.",
            )
            return
        self.window.connect_preflight.start(
            self.window.active_server_context(), engine_override="native"
        )

    def perform(self, server):
        window = self.window
        if hasattr(window, "server_launch"):
            window.connect_preflight.start(server)
            return
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
            window.save_last_launch_report(dialog.copyable_output_text())
        except OSError as exc:
            QMessageBox.warning(
                window,
                "Could not save launch report",
                "The launch completed, but WolfLauncher could not save its support report.\n\n"
                f"{exc}",
            )

    def build_command(self, server, row: int | None = None, *, context=None) -> list[str]:
        window = self.window
        if hasattr(window, "server_launch"):
            context = context or window.server_launch.context
            if not window.server_launch.current(context) or not context.matches(server):
                raise LaunchError(
                    "A fresh identity check is required for this exact server. Retry Join."
                )
            if not installation_still_present(context.install):
                raise LaunchError(
                    "The selected installation is no longer complete. Rescan and retry."
                )
            result = window.last_mod_result
            if (
                result is None
                or not result.ok
                or result.request_id != context.request_id
                or result.launch_context_key != context.mod_context_key
            ):
                raise LaunchError(
                    "Required mods were not checked for this launch context. Retry Join."
                )
            launch_server = context.server
            player_name = window.player_name.text().strip() or DEFAULT_PLAYER_NAME
            if context.engine == "external":
                steamapps = context.install.dayz_dir.parent.parent
                if (
                    context.install.dayz_dir != steamapps / "common" / "DayZ"
                    or context.install.workshop_dir != steamapps / "workshop" / "content" / "221100"
                ):
                    raise LaunchError(
                        "The external launcher requires DayZ and Workshop in the same Steam "
                        "library with the default DayZ directory name. Choose Native launcher "
                        "for this installation layout."
                    )
                return [
                    "env",
                    f"STEAM_ROOT={steamapps.parent}",
                    *build_launch_command(window.launcher_path.text(), player_name, launch_server),
                ]
            return prepare_native_launch(
                context.install, launch_server, player_name, result.required_mods
            ).command
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
