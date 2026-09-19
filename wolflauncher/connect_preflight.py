"""Qt coordination for the guarded connect-to-server workflow."""

import time

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QMessageBox

from .launch_dialogs import PreflightLaunchDialog
from .launcher import LaunchError
from .models import Server
from .mods import ModCheckResult
from .native_launcher import NativeLaunchError
from .platform_detection import (
    best_install,
    build_steam_start_command,
    dayz_process_check,
    install_label,
)
from .platforms import current_platform
from .product_availability import installation_still_present
from .settings import server_key
from .workers import ModWorker, WorkshopSubscriptionWorker
from .workshop_subscription import current_workshop_item, workshop_automation_unavailable_reason


class ConnectPreflightCoordinator:
    """Run Steam and Workshop preparation while the window retains UI state."""

    def __init__(self, window):
        self.window = window
        self.context = None
        self.handoff_at = None
        window.preflight_workers = {}

    def start(self, server: Server, *, engine_override=None):
        if self.handoff_at is not None and time.monotonic() - self.handoff_at < 60:
            QMessageBox.information(
                self.window,
                "Launch in progress",
                "A launch handoff is already in progress. Wait for it to finish before joining again.",
            )
            return
        if hasattr(self.window, "server_launch"):
            self.window.server_launch.prepare(
                server, self.start_resolved, force=True, engine_override=engine_override
            )
        else:
            self._start(server)

    def start_resolved(self, context):
        self.context = context
        self._start(context.server)

    def _current(self):
        if hasattr(self.window, "server_launch"):
            return self.window.server_launch.current(self.context, require_fresh=False)
        return True

    def invalidate(self):
        self.context = None
        for name in ("preflight_mod_worker", "preflight_workshop_worker"):
            worker = getattr(self.window, name, None)
            if worker and worker.isRunning():
                cancel = getattr(worker, "cancel", None)
                if callable(cancel):
                    cancel()
        dialog = getattr(self.window, "preflight_dialog", None)
        if dialog and dialog.isVisible():
            dialog.set_failed("launcher", "Server selection or launch request changed. Retry Join.")

    def _start(self, server):
        window = self.window
        if not self._current():
            return
        process = dayz_process_check()
        if process.running:
            QMessageBox.warning(
                window,
                "DayZ is already running",
                f"{process.detail}.\n\n"
                "Close DayZ completely before connecting to another server. "
                "WolfLauncher will not send another Steam launch request while the existing "
                "DayZ/BattlEye session is active.",
            )
            return
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
        self.context = None
        if hasattr(window, "server_launch"):
            window.server_launch.invalidate()
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
        if self.context is not None:
            from dataclasses import replace

            return replace(
                self.context.install, running=current_platform().process_running("steam")
            )
        if window.launch_engine_key() == "native":
            return window.selected_steam_install()
        return best_install()

    def ensure_steam(self):
        if not self._current():
            return
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
        QTimer.singleShot(
            1000,
            lambda context=self.context: self.poll_steam() if context is self.context else None,
        )

    def poll_steam(self):
        if not self._current():
            return
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
        QTimer.singleShot(
            1000,
            lambda context=self.context: self.poll_steam() if context is self.context else None,
        )

    def start_mod_check(self, install):
        if not self._current():
            return
        window = self.window
        dialog, server = window.preflight_dialog, window.preflight_server
        if not dialog or not server:
            return
        if self.context is not None and not self.context.fresh():
            window.server_launch.revalidate(self.context, self._resume_mod_check)
            return
        dialog.set_working("mods", "Checking the server manifest and local Workshop state…")
        if self.context is not None:
            context = self.context
            window.server_launch.check_mods(
                context,
                lambda result: (
                    self.finish_mod_check(result)
                    if self.context is not None and self.context.request_id == context.request_id
                    else None
                ),
                force=True,
            )
            return
        window.preflight_mod_worker = ModWorker(
            server,
            install.workshop_dir,
            window.mod_check_steam_context(install),
            workshop_install=install,
            launch_context=self.context,
        )
        context = self.context
        window.preflight_mod_worker.mods_ready.connect(
            lambda result: self.finish_mod_check(result) if context is self.context else None
        )
        worker = window.preflight_mod_worker
        window.preflight_workers[id(worker)] = worker
        worker.finished.connect(lambda: window.preflight_workers.pop(id(worker), None))
        worker.start()

    def _resume_mod_check(self, context):
        self.context = context
        self.start_mod_check(self._install())

    def finish_mod_check(self, result: ModCheckResult):
        if not self._current():
            return
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
        context = self.context
        window.preflight_workshop_worker.progress_ready.connect(
            lambda result: (
                self.update_workshop_progress(result) if context is self.context else None
            )
        )
        window.preflight_workshop_worker.subscription_ready.connect(
            lambda result: self.finish_workshop(result) if context is self.context else None
        )
        worker = window.preflight_workshop_worker
        window.preflight_workers[id(worker)] = worker
        worker.finished.connect(lambda: window.preflight_workers.pop(id(worker), None))
        worker.start()

    def update_workshop_progress(self, snapshots):
        if not self._current():
            return
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
        if not self._current():
            return
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
        if not self._current():
            return
        if self.context is not None:
            self.window.server_launch.revalidate(self.context, self._handoff)
        else:
            self._handoff(None)

    def _handoff(self, context):
        if self.handoff_at is not None and time.monotonic() - self.handoff_at < 60:
            return
        if context is not None:
            self.context = context
        if not self._current():
            return
        window = self.window
        dialog, server = window.preflight_dialog, window.preflight_server
        if not dialog or not dialog.isVisible() or not server:
            return
        if context is not None and not installation_still_present(context.install):
            self.fail(
                "launcher",
                "The selected game installation disappeared or became incomplete. Rescan and retry.",
            )
            return
        running = dayz_process_check()
        if running.running:
            self.fail(
                "launcher", "DayZ is already running. Close it before joining another server."
            )
            return
        dialog.set_working("launcher", "Building the Steam launch command…")
        try:
            command = window.launch_execution.build_command(server, context=context)
        except (NativeLaunchError, LaunchError) as exc:
            self.fail("launcher", str(exc))
            return
        if context is not None:
            dialog.process.setWorkingDirectory(str(context.install.dayz_dir))
            dialog.output.append(
                f"Edition: {context.product.label}\nGame installation: {context.install.dayz_dir}\nWorkshop source: {context.install.workshop_dir}\nRequest: {context.request_id}"
            )
        self.handoff_at = time.monotonic()
        dialog.start_launch(command)
        # History records a launch attempt once command handoff starts.
        from .launch_history import record_launch

        try:
            record_launch(context.server if context is not None else server)
            window.refresh_recent_servers()
        except (OSError, ValueError) as exc:
            window.statusBar().showMessage(f"Could not save recent server: {exc}", 10000)
