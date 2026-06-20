import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

STEAM_APP_ID_DAYZ = 221100
FLATPAK_STEAM_ID = "com.valvesoftware.Steam"


@dataclass
class SteamInstall:
    mode: str
    executable: str
    running: bool
    root: Path | None
    steamapps: Path | None
    dayz_dir: Path | None
    workshop_dir: Path | None


NATIVE_STEAM_ROOTS = [
    Path.home() / ".local/share/Steam",
    Path.home() / ".steam/steam",
]

FLATPAK_STEAM_ROOT = Path.home() / ".var/app" / FLATPAK_STEAM_ID / "data" / "Steam"


def _is_running(process_name: str) -> bool:
    try:
        result = subprocess.run(["pgrep", "-x", process_name], capture_output=True, text=True, timeout=2)
        return result.returncode == 0
    except Exception:
        return False


def _flatpak_steam_running() -> bool:
    if not shutil.which("flatpak"):
        return False
    try:
        result = subprocess.run(["flatpak", "ps"], capture_output=True, text=True, timeout=3)
        return FLATPAK_STEAM_ID in result.stdout
    except Exception:
        return False


def _steamapps_from_root(root: Path | None) -> Path | None:
    if not root:
        return None
    steamapps = root / "steamapps"
    return steamapps if steamapps.exists() else None


def _dayz_from_steamapps(steamapps: Path | None) -> Path | None:
    if not steamapps:
        return None
    dayz = steamapps / "common" / "DayZ"
    return dayz if dayz.exists() else None


def _workshop_from_steamapps(steamapps: Path | None) -> Path | None:
    if not steamapps:
        return None
    workshop = steamapps / "workshop" / "content" / str(STEAM_APP_ID_DAYZ)
    return workshop if workshop.exists() else None


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def detect_steam() -> list[SteamInstall]:
    installs: list[SteamInstall] = []

    native_root = _first_existing(NATIVE_STEAM_ROOTS)
    native_steamapps = _steamapps_from_root(native_root)
    installs.append(
        SteamInstall(
            mode="native",
            executable=shutil.which("steam") or "",
            running=_is_running("steam"),
            root=native_root,
            steamapps=native_steamapps,
            dayz_dir=_dayz_from_steamapps(native_steamapps),
            workshop_dir=_workshop_from_steamapps(native_steamapps),
        )
    )

    flatpak_root = FLATPAK_STEAM_ROOT if FLATPAK_STEAM_ROOT.exists() else None
    flatpak_steamapps = _steamapps_from_root(flatpak_root)
    installs.append(
        SteamInstall(
            mode="flatpak",
            executable=FLATPAK_STEAM_ID if shutil.which("flatpak") else "",
            running=_flatpak_steam_running(),
            root=flatpak_root,
            steamapps=flatpak_steamapps,
            dayz_dir=_dayz_from_steamapps(flatpak_steamapps),
            workshop_dir=_workshop_from_steamapps(flatpak_steamapps),
        )
    )

    env_root = os.environ.get("STEAM_ROOT")
    if env_root:
        root = Path(env_root).expanduser()
        steamapps = root / "steamapps" if (root / "steamapps").exists() else root
        installs.append(
            SteamInstall(
                mode="STEAM_ROOT env",
                executable="",
                running=False,
                root=root,
                steamapps=steamapps if steamapps.exists() else None,
                dayz_dir=_dayz_from_steamapps(steamapps if steamapps.exists() else None),
                workshop_dir=_workshop_from_steamapps(steamapps if steamapps.exists() else None),
            )
        )

    return installs


def best_install() -> SteamInstall | None:
    installs = detect_steam()
    for install in installs:
        if install.dayz_dir and install.workshop_dir:
            return install
    for install in installs:
        if install.root or install.executable:
            return install
    return installs[0] if installs else None


def ok_missing(value: bool) -> str:
    return "OK" if value else "MISSING"


def yes_no(value: bool) -> str:
    return "Yes" if value else "No"
