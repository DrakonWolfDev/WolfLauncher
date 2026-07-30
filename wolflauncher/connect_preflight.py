"""Qt coordination for the guarded connect-to-server workflow."""

from PySide6.QtCore import QProcess, QTimer

from .launch_dialogs import PreflightLaunchDialog
from .launcher import LaunchError
from .models import Server
from .mods import ModCheckResult
from .native_launcher import NativeLaunchError
from .platform_detection import best_install, build_steam_start_command, install_label
from .settings import server_key
from .workers import ModWorker, WorkshopSubscriptionWorker
from .workshop_subscription import current_workshop_item, workshop_automation_unavailable_reason


class ConnectPreflightCoordinator:
    """Run Steam and Workshop preparation while the window retains UI state."""

    def __init__(self, window):
        self.window = window

    def start(self, server: Server):
        window = self.window
        window.preflight_server = server
        window.preflight_dialog = PreflightLaunchDialog(window, server.name)
        window.preflight_dialog.finished.connect(self.cancel)
        window.preflight_dialog.launch_report_ready.connect(window.persist_launch_report)
        window.preflight_dialog.launcher_minimize_requested.connect(window.showMinimized)
        window.preflight_dialog.show()
        window.launch_button.setEnabled(False)
        self.ensure_steam()

    def cancel(self, *_args):
        window = self.window
        worker = window.preflight_workshop_worker
        if worker and worker.isRunning():
            worker.cancel()
        window.launch_button.setEnabled(True)

    def fail(self, key: str, detail: str):
        window = self.window
        if window.preflight_dialog:
            window.preflight_dialog.set_failed(key, detail)
        window.launch_button.setEnabled(True)

    def _install(self):
        window = self.window
        if window.launch_engine_key() == "native":
            return window.selected_steam_install()
        return best_install()

    def ensure_steam(self):
        window = self.window
        dialog = window.preflight_dialog
        if not dialog or not dialog.isVisible():
            return
        install = self._install()
        if not install or not install.dayz_dir:
            self.fail(
                "steam",
                "The selected Steam/DayZ installation was not detected. Check Settings health.",
            )
            return
        if not install.workshop_dir:
            self.fail("mods", "The DayZ Workshop folder was not detected. Check Settings health.")
            return
        if install.running:
            dialog.set_complete(
                "steam", f"{install_label(install)} is running. Checking required mods…"
            )
            self.start_mod_check(install)
            return
        command = build_steam_start_command(install)
        if not command:
            self.fail("steam", "The selected Steam client has no runnable command.")
            return
        dialog.set_working("steam", f"Starting {install_label(install)}…")
        started, _pid = QProcess.startDetached(command[0], command[1:])
        if not started:
            self.fail("steam", "Steam could not be started.")
            return
        window.preflight_steam_attempts = 0
        QTimer.singleShot(1000, self.poll_steam)

    def poll_steam(self):
        window = self.window
        dialog = window.preflight_dialog
        if not dialog or not dialog.isVisible():
            return
        window.preflight_steam_attempts += 1
        install = self._install()
        if install and install.running:
            dialog.set_complete(
                "steam", f"{install_label(install)} is running. Checking required mods…"
            )
            self.start_mod_check(install)
            return
        if window.preflight_steam_attempts >= 60:
            self.fail(
                "steam",
                "Steam was started, but did not become ready within 60 seconds. "
                "Sign in to Steam and try again.",
            )
            return
        QTimer.singleShot(1000, self.poll_steam)

    def start_mod_check(self, install):
        window = self.window
        dialog, server = window.preflight_dialog, window.preflight_server
        if not dialog or not server:
            return
        dialog.set_working("mods", "Checking the server manifest and local Workshop state…")
        window.preflight_mod_worker = ModWorker(
            server,
            install.workshop_dir,
            window.mod_check_steam_context(install),
            workshop_install=install,
        )
        window.preflight_mod_worker.mods_ready.connect(self.finish_mod_check)
        window.preflight_mod_worker.start()

    def finish_mod_check(self, result: ModCheckResult):
        window = self.window
        window.preflight_mod_worker = None
        dialog, server = window.preflight_dialog, window.preflight_server
        if not dialog or not dialog.isVisible() or not server:
            return
        if server_key(result.server) != server_key(server) or not result.ok:
            self.fail("mods", result.error or "The required-mod check failed.")
            return
        window.last_mod_result = result
        window.display_mods_result(result)
        if not result.missing_mods:
            dialog.set_complete(
                "mods", f"All {len(result.required_mods)} required mod(s) are ready."
            )
            self.finish()
            return
        install = self._install()
        if not install or not install.running:
            self.fail("mods", "Steam stopped before required mods could be installed.")
            return
        unavailable = workshop_automation_unavailable_reason(install)
        if unavailable:
            self.fail("mods", unavailable)
            return
        dialog.set_working(
            "mods",
            f"Installing or updating {len(result.missing_mods)} required Workshop item(s)…",
        )
        window.preflight_workshop_worker = WorkshopSubscriptionWorker(
            [mod.workshop_id for mod in result.missing_mods], install
        )
        window.preflight_workshop_worker.progress_ready.connect(self.update_workshop_progress)
        window.preflight_workshop_worker.subscription_ready.connect(self.finish_workshop)
        window.preflight_workshop_worker.start()

    def update_workshop_progress(self, snapshots):
        dialog = self.window.preflight_dialog
        if not dialog or not snapshots:
            return
        installed = sum(1 for item in snapshots if item.installed)
        active = current_workshop_item(snapshots)
        suffix = (
            f"; current item {active.percent}%" if active and active.percent is not None else ""
        )
        dialog.set_working(
            "mods", f"Steam has prepared {installed} of {len(snapshots)} required item(s){suffix}."
        )

    def finish_workshop(self, result):
        window = self.window
        window.preflight_workshop_worker = None
        if not result.ok:
            self.fail("mods", result.error or "Steam did not finish every required Workshop item.")
            return
        install = self._install()
        if not install:
            self.fail("mods", "The selected Steam installation is no longer available.")
            return
        self.start_mod_check(install)

    def finish(self):
        window = self.window
        dialog, server = window.preflight_dialog, window.preflight_server
        if not dialog or not server:
            return
        dialog.set_working("launcher", "Building the Steam launch command…")
        try:
            command = window.launch_execution.build_command(server)
        except (NativeLaunchError, LaunchError) as exc:
            self.fail("launcher", str(exc))
            return
        dialog.start_launch(command)
