from PySide6.QtWidgets import (
    QMessageBox,
)

from .launch_preflight import (
    LaunchPreflightAction,
    build_launch_preflight_state,
    next_launch_preflight_action,
)
from .models import Server
from .mods import (
    apply_workshop_item_states,
)
from .native_launcher import (
    NativeLaunchError,
)
from .platform_detection import (
    SteamInstall,
    best_install,
    best_install_from,
    install_label,
    select_steam_install,
)
from .settings import (
    server_key,
)
from .theme import (
    set_ui_role,
)


class LaunchFeatureMixin:
    def launch_engine_key(self) -> str:
        if not hasattr(self, "launch_engine"):
            return str(self.settings.get("launch_engine") or "native")
        return "native" if self.launch_engine.currentText() == "Native launcher" else "external"

    def native_steam_mode_key(self) -> str:
        if not hasattr(self, "native_steam_mode"):
            return str(self.settings.get("native_steam_mode") or "auto")
        keys = {
            "Auto": "auto",
            "Native Steam": "native",
            "Flatpak Steam": "flatpak",
            "STEAM_ROOT Steam library": "STEAM_ROOT env",
        }
        return keys.get(self.native_steam_mode.currentText(), "auto")

    def selected_steam_install(self) -> SteamInstall | None:
        return select_steam_install(self.native_steam_mode_key())

    def selected_browser_preview_install(self) -> SteamInstall | None:
        """Reuse the latest health snapshot so browsing never scans Steam on the UI thread."""
        installs = list(self.detected_steam_installs)
        if not installs:
            return None
        if self.launch_engine_key() == "native":
            return select_steam_install(self.native_steam_mode_key(), installs=installs)
        return best_install_from(installs)

    def check_startup_steam_state(self):
        """Surface Steam availability once the initial window has opened."""
        install = self.selected_steam_install()
        if install and install.running:
            return
        if install:
            detail = f"{install_label(install)} was detected, but it is not currently running."
        else:
            detail = "WolfLauncher could not detect the selected Steam installation."
        QMessageBox.warning(
            self,
            "Steam is not running",
            f"{detail}\n\n"
            "Start Steam and sign in for complete Workshop mod information, sizes and "
            "download operations. You can continue browsing servers in the meantime.",
        )

    def preview_native_launch(self):
        self.launch_execution.preview_native()

    def launch_selected(self):
        workshop_block = self.workshop_launch_block_reason()
        if workshop_block:
            QMessageBox.information(self, "Steam Workshop in progress", workshop_block)
            return
        server = self.active_server_context()
        if not server:
            QMessageBox.warning(self, "No server selected", "Select a server first.")
            return

        self.save_user_settings(silent=True)
        self.connect_preflight.start(server)

    def finish_prelaunch_workshop_check(self, server, result, state_result):
        current = self.active_server_context()
        if not current or server_key(current) != server_key(server):
            QMessageBox.warning(
                self,
                "Server selection changed",
                "Launch was cancelled because the active server changed.",
            )
            return
        if state_result.error:
            QMessageBox.warning(
                self,
                "Workshop verification unavailable",
                "WolfLauncher could not complete the final Steam Workshop readiness check, "
                f"so launch was not started.\n\n{state_result.error}",
            )
            return
        apply_workshop_item_states(result, state_result.items)
        self.last_mod_result = result
        self.display_mods_result(result)
        if result.missing_mods:
            QMessageBox.warning(
                self,
                "Workshop items not ready",
                f"Steam reports {len(result.missing_mods)} required item(s) as update pending "
                "or downloading. Review the Mods tab and resolve them before launching.",
            )
            return
        self.perform_launch(server)

    def clear_workshop_state_worker(self):
        self.workshop_state_worker = None
        self.launch_button.setEnabled(True)

    def perform_launch(self, server: Server):
        self.launch_execution.perform(server)

    def build_selected_launch_command(self, server: Server, row: int | None = None) -> list[str]:
        return self.launch_execution.build_command(server, row)

    def show_native_launch_error(self, error: NativeLaunchError):
        self.launch_execution.show_native_launch_error(error)

    def show_native_preview_error(self, error: NativeLaunchError):
        self.launch_execution.show_native_preview_error(error)

    def confirm_launch_preflight(self, server: Server) -> bool:
        install = (
            self.selected_steam_install()
            if self.launch_engine_key() == "native"
            else best_install()
        )
        state = build_launch_preflight_state(
            install,
            server,
            self.last_mod_result,
            native_engine=self.launch_engine_key() == "native",
        )
        missing = self.last_mod_result.missing_mods if state.mods_checked else []
        steam_stopped_confirmed = False

        action = next_launch_preflight_action(state)
        if action == LaunchPreflightAction.BLOCK_MISSING_DAYZ:
            QMessageBox.critical(
                self,
                "DayZ not detected",
                "WolfLauncher could not detect a DayZ installation. Check Settings health before launching.",
            )
            return False

        if action == LaunchPreflightAction.BLOCK_MISSING_WORKSHOP:
            QMessageBox.critical(
                self,
                "Workshop folder not detected",
                "WolfLauncher could not detect the DayZ Workshop folder. Check Settings health before launching.",
            )
            return False

        if action == LaunchPreflightAction.CONFIRM_STEAM_STOPPED:
            reply = QMessageBox.question(
                self,
                "Steam is not running",
                f"{install.mode.title()} Steam was detected, but it does not appear to be running.\n\n"
                "The selected launch engine may still be able to start Steam, but starting Steam first is recommended.\n\n"
                "Launch anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return False
            steam_stopped_confirmed = True
            action = next_launch_preflight_action(
                state, steam_stopped_confirmed=steam_stopped_confirmed
            )

        if action in {
            LaunchPreflightAction.BLOCK_NATIVE_MISSING_MODS,
            LaunchPreflightAction.CONFIRM_EXTERNAL_MISSING_MODS,
        }:
            if missing:
                names = "\n".join(f"- {mod.name or mod.workshop_id}" for mod in missing[:12])
                if len(missing) > 12:
                    names += f"\n- ...and {len(missing) - 12} more"
                if action == LaunchPreflightAction.BLOCK_NATIVE_MISSING_MODS:
                    box = QMessageBox(self)
                    box.setIcon(QMessageBox.Warning)
                    box.setWindowTitle("Missing required mods")
                    box.setText(f"{server.name} is missing {len(missing)} required mod(s).")
                    box.setInformativeText(
                        f"{names}\n\n"
                        "The native launcher needs every required Workshop directory before it can "
                        "build the DayZ mod command."
                    )
                    open_button = box.addButton("Open Workshop", QMessageBox.ButtonRole.ActionRole)
                    install_button = box.addButton(
                        "Install/update mods", QMessageBox.ButtonRole.ActionRole
                    )
                    cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                    box.setDefaultButton(cancel_button)
                    box.exec()
                    clicked = box.clickedButton()
                    if clicked == open_button:
                        self.open_missing_workshop_pages()
                    elif clicked == install_button:
                        self.subscribe_missing_workshop_mods()
                    return False

                box = QMessageBox(self)
                box.setIcon(QMessageBox.Warning)
                box.setWindowTitle("Missing required mods")
                box.setText(f"{server.name} is missing {len(missing)} required mod(s).")
                box.setInformativeText(
                    f"{names}\n\nOpen the missing Workshop page(s), launch anyway, or cancel?"
                )
                open_button = box.addButton("Open Workshop", QMessageBox.ButtonRole.ActionRole)
                install_button = box.addButton(
                    "Install/update mods", QMessageBox.ButtonRole.ActionRole
                )
                launch_button = box.addButton(
                    "Launch anyway", QMessageBox.ButtonRole.DestructiveRole
                )
                set_ui_role(launch_button, "destructive")
                cancel_button = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                box.setDefaultButton(cancel_button)
                box.exec()
                clicked = box.clickedButton()
                if clicked == open_button:
                    self.open_missing_workshop_pages()
                    return False
                if clicked == install_button:
                    self.subscribe_missing_workshop_mods()
                    return False
                if clicked != launch_button:
                    return False
        elif action == LaunchPreflightAction.CONFIRM_MODS_UNCHECKED:
            reply = QMessageBox.question(
                self,
                "Mods not checked",
                "Required mods have not been checked for this server in this session.\n\nLaunch anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return False

        return True
