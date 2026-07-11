from dataclasses import dataclass
from enum import Enum

from .models import Server
from .mods import ModCheckResult
from .platform_detection import SteamInstall
from .settings import server_key


class LaunchPreflightAction(str, Enum):
    READY = "ready"
    BLOCK_MISSING_DAYZ = "block_missing_dayz"
    BLOCK_MISSING_WORKSHOP = "block_missing_workshop"
    CONFIRM_STEAM_STOPPED = "confirm_steam_stopped"
    CONFIRM_MODS_UNCHECKED = "confirm_mods_unchecked"
    BLOCK_NATIVE_MISSING_MODS = "block_native_missing_mods"
    CONFIRM_EXTERNAL_MISSING_MODS = "confirm_external_missing_mods"


@dataclass(frozen=True)
class LaunchPreflightState:
    has_install: bool
    has_dayz: bool
    has_workshop: bool
    steam_running: bool
    mods_checked: bool
    missing_mod_count: int
    native_engine: bool


def matching_mod_result(
    server: Server,
    mod_result: ModCheckResult | None,
    workshop_dir=None,
) -> ModCheckResult | None:
    """Return a cached result only when its server and optional Workshop context match."""
    if not mod_result or server_key(mod_result.server) != server_key(server):
        return None
    if workshop_dir is not None and mod_result.workshop_dir != str(workshop_dir):
        return None
    return mod_result


def usable_mod_result(
    server: Server,
    mod_result: ModCheckResult | None,
    workshop_dir=None,
) -> ModCheckResult | None:
    """Return a successful cached result only when it belongs to the server."""
    matching_result = matching_mod_result(server, mod_result, workshop_dir)
    return matching_result if matching_result and matching_result.ok else None


def build_launch_preflight_state(
    install: SteamInstall | None,
    server: Server,
    mod_result: ModCheckResult | None,
    *,
    native_engine: bool,
) -> LaunchPreflightState:
    """Build policy state from detected install and cached mod-check context."""
    workshop_dir = install.workshop_dir if install else None
    current_mod_result = usable_mod_result(server, mod_result, workshop_dir)
    mods_checked = current_mod_result is not None
    missing_mod_count = len(current_mod_result.missing_mods) if current_mod_result else 0
    return LaunchPreflightState(
        has_install=install is not None,
        has_dayz=bool(install and install.dayz_dir),
        has_workshop=bool(install and install.workshop_dir),
        steam_running=bool(install and install.running),
        mods_checked=mods_checked,
        missing_mod_count=missing_mod_count,
        native_engine=native_engine,
    )


def next_launch_preflight_action(
    state: LaunchPreflightState,
    *,
    steam_stopped_confirmed: bool = False,
) -> LaunchPreflightAction:
    """Return the next ordered launch decision the GUI must present.

    Steam confirmation is passed back into the function after the user accepts
    it so later mod policy can be evaluated without coupling this module to Qt.
    """
    if not state.has_install or not state.has_dayz:
        return LaunchPreflightAction.BLOCK_MISSING_DAYZ
    if not state.has_workshop:
        return LaunchPreflightAction.BLOCK_MISSING_WORKSHOP
    if not state.steam_running and not steam_stopped_confirmed:
        return LaunchPreflightAction.CONFIRM_STEAM_STOPPED
    if not state.mods_checked:
        return LaunchPreflightAction.CONFIRM_MODS_UNCHECKED
    if state.missing_mod_count > 0:
        if state.native_engine:
            return LaunchPreflightAction.BLOCK_NATIVE_MISSING_MODS
        return LaunchPreflightAction.CONFIRM_EXTERNAL_MISSING_MODS
    return LaunchPreflightAction.READY
