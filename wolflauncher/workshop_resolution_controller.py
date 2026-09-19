"""Qt entry points for confirmed Steam Workshop resolution."""

from PySide6.QtWidgets import QMessageBox, QProgressDialog

from .mod_presenter import combined_download_estimate, mod_download_size
from .platform_detection import best_install, install_label
from .settings import server_key
from .workers import WorkshopSubscriptionWorker
from .workshop_subscription import workshop_automation_unavailable_reason, workshop_recovery_state


class WorkshopResolutionCoordinator:
    """Start a single Steam-managed Workshop resolution session for a window."""

    def __init__(self, window):
        self.window = window

    def subscribe_missing_mods(self):
        window = self.window
        result = window._selected_mod_result(successful=True)
        if not result:
            QMessageBox.warning(
                window,
                "No mod check yet",
                "Check the selected server mods successfully before subscribing.",
            )
            return
        missing = result.missing_mods
        if not missing:
            QMessageBox.information(
                window, "No missing mods", "All required mods appear to be installed."
            )
            return
        worker = window.workshop_subscription_worker
        if worker and worker.isRunning():
            if window.workshop_subscription_dialog:
                window.workshop_subscription_monitor_hidden = False
                window.workshop_subscription_dialog.show()
                window.workshop_subscription_dialog.raise_()
                window.workshop_subscription_dialog.activateWindow()
            window.statusBar().showMessage(
                "Showing the existing Steam Workshop monitor; no new session was started.", 5000
            )
            return
        install = self._install()
        recovery = workshop_recovery_state(install, (mod.workshop_id for mod in missing))
        if recovery.active:
            QMessageBox.information(
                window,
                "Steam Workshop activity detected",
                "Steam appears to have required DayZ Workshop items in its download staging "
                "area from an earlier session. Check Steam Downloads and wait for it to finish, "
                "then use Recheck mods. WolfLauncher will not start a second helper session yet.",
            )
            return
        if not install or not install.workshop_dir:
            QMessageBox.warning(
                window,
                "Steam installation unavailable",
                "WolfLauncher could not find the selected Steam/DayZ Workshop installation.",
            )
            return
        if not install.running:
            QMessageBox.warning(
                window,
                "Steam is not running",
                f"{install_label(install)} is currently not running.\n\n"
                "Open Steam, sign in to an account that owns DayZ, then try subscribing again.",
            )
            return
        unavailable = workshop_automation_unavailable_reason(install)
        if unavailable:
            QMessageBox.information(window, "Use Steam Workshop pages", unavailable)
            return
        names = "\n".join(
            f"- {mod.name or mod.workshop_id} — {mod_download_size(mod)}" for mod in missing[:12]
        )
        if len(missing) > 12:
            names += f"\n- ...and {len(missing) - 12} more"
        reply = QMessageBox.question(
            window,
            "Resolve using Steam?",
            f"Steam will resolve {len(missing)} required item(s) "
            f"({len(result.absent_mods)} missing, {len(result.update_mods)} update/pending) "
            "using the signed-in Steam account. Missing items will be subscribed; existing "
            f"items will be asked to update.\n\n{names}\n\n{combined_download_estimate(missing)}\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.start_resolution(
                missing,
                result,
                install,
                force_update=any(mod.remote_update_available for mod in missing),
            )

    def check_update_mod(self, row: int):
        window = self.window
        result = window._selected_mod_result(successful=True)
        workshop_id = window._mods_cell(row, 2)
        mod = (
            next((item for item in result.required_mods if item.workshop_id == workshop_id), None)
            if result
            else None
        )
        if mod is None:
            QMessageBox.warning(
                window,
                "Mod check unavailable",
                "Recheck the selected server before updating this mod.",
            )
            return
        if mod.ready:
            QMessageBox.information(
                window,
                "Mod already ready",
                f"{mod.name or mod.workshop_id} is already reported ready.",
            )
            return
        if window.workshop_subscription_worker and window.workshop_subscription_worker.isRunning():
            self.subscribe_missing_mods()
            return
        install = self._install()
        if not install or not install.workshop_dir or not install.running:
            QMessageBox.warning(
                window,
                "Steam unavailable",
                "Start the selected Steam client and confirm its DayZ Workshop installation, then try again.",
            )
            return
        reply = QMessageBox.question(
            window,
            "Check/update using Steam?",
            f"Ask Steam to resolve {mod.name or mod.workshop_id}, then wait for a verified ready state?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.start_resolution([mod], result, install, force_update=mod.remote_update_available)

    def force_update_mod(self, row: int):
        window = self.window
        result = window._selected_mod_result(successful=True)
        workshop_id = window._mods_cell(row, 2)
        mod = (
            next((item for item in result.required_mods if item.workshop_id == workshop_id), None)
            if result
            else None
        )
        if mod is None:
            QMessageBox.warning(
                window,
                "Mod check unavailable",
                "Recheck the selected server before forcing an update.",
            )
            return
        if window.workshop_subscription_worker and window.workshop_subscription_worker.isRunning():
            self.subscribe_missing_mods()
            return
        install = self._install()
        if not install or not install.workshop_dir or not install.running:
            QMessageBox.warning(
                window,
                "Steam unavailable",
                "Start the selected Steam client and confirm its DayZ Workshop installation, then try again.",
            )
            return
        reply = QMessageBox.question(
            window,
            "Force Steam update?",
            f"Ask Steam to prioritise a fresh download check for {mod.name or mod.workshop_id}?\n\n"
            "This keeps the subscription. Steam controls whether content needs downloading; "
            "WolfLauncher will recheck the mod when the request finishes.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.start_resolution([mod], result, install, force_update=True)

    def start_resolution(self, mods, result, install, *, force_update: bool = False):
        window = self.window
        window.workshop_subscription_names = {
            mod.workshop_id: (mod.name or mod.workshop_id) for mod in mods
        }
        window.workshop_subscription_server_key = server_key(result.server)
        window.workshop_subscription_server = result.server
        dialog = QProgressDialog(
            "Requesting Steam Workshop update..."
            if force_update
            else "Sending subscriptions to Steam...",
            "Hide monitor",
            0,
            100,
            window,
        )
        dialog.setWindowTitle("Steam Workshop")
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        window.workshop_subscription_dialog = dialog
        window.workshop_subscription_monitor_hidden = False
        worker = WorkshopSubscriptionWorker(
            [mod.workshop_id for mod in mods], install, force_update=force_update
        )
        window.workshop_subscription_worker = worker
        context = window.server_launch.context if hasattr(window, "server_launch") else None

        def valid():
            return context is None or window.server_launch.current(context, require_fresh=False)

        worker.progress_ready.connect(
            lambda result: window.update_workshop_subscription_progress(result) if valid() else None
        )
        worker.subscription_ready.connect(
            lambda result: window.finish_workshop_subscription(result) if valid() else None
        )
        worker.finished.connect(window.clear_workshop_subscription_worker)
        dialog.canceled.connect(window.stop_workshop_subscription_monitoring)
        window.launch_button.setEnabled(False)
        worker.start()

    def _install(self):
        window = self.window
        return (
            window.selected_steam_install()
            if hasattr(window, "server_launch") or window.launch_engine_key() == "native"
            else best_install()
        )
