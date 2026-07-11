from dataclasses import dataclass
from enum import Enum


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
