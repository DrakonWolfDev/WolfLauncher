import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

STEAM_APP_ID_DAYZ = 221100
FLATPAK_STEAM_ID = "com.valvesoftware.Steam"
DAYZ_PROCESS_PATTERNS = (
    "DayZ_x64.exe",
    "DayZ_BE.exe",
    "DayZDiag_x64.exe",
)


@dataclass
class SteamInstall:
    mode: str
    executable: str
    running: bool
    root: Path | None
    steamapps: Path | None
    dayz_dir: Path | None
    workshop_dir: Path | None


@dataclass
class ProcessCheck:
    running: bool
    detail: str


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


def _matching_process_lines(patterns: tuple[str, ...]) -> list[str]:
    try:
        result = subprocess.run(["pgrep", "-af", "|".join(patterns)], capture_output=True, text=True, timeout=2)
    except Exception:
        return []
    if result.returncode != 0:
        return []
    lines = []
    for line in result.stdout.splitlines():
        if any(pattern in line for pattern in patterns):
            lines.append(line)
    return lines


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


def install_label(install: SteamInstall) -> str:
    if install.mode == "native":
        return "Native Steam"
    if install.mode == "flatpak":
        return "Flatpak Steam"
    if install.mode == "STEAM_ROOT env":
        return "STEAM_ROOT Steam library"
    return f"{install.mode} Steam"


def install_readiness(install: SteamInstall | None) -> tuple[str, str]:
    if not install:
        return "MISSING", "Steam not detected"

    label = install_label(install)
    state = "running" if install.running else "not running"
    if not (install.executable or install.root or install.steamapps):
        return "MISSING", f"{label} not detected"
    if not install.root and install.executable:
        return "WARN", f"{label} executable found, but Steam data root was not detected ({state})"
    if install.root and not install.steamapps:
        return "WARN", f"{label} root found, but steamapps folder was not detected ({state})"
    if install.steamapps and not install.dayz_dir:
        return "WARN", f"{label} library found, but DayZ install is not visible ({state})"
    if install.dayz_dir and not install.workshop_dir:
        return "WARN", f"{label} DayZ found, but Workshop folder is not visible ({state})"
    if install.dayz_dir and install.workshop_dir:
        return "OK", f"{label} ready ({state})"
    return "WARN", f"{label} partially detected ({state})"


def dayz_process_check() -> ProcessCheck:
    lines = _matching_process_lines(DAYZ_PROCESS_PATTERNS)
    if not lines:
        return ProcessCheck(False, "No known DayZ process detected")
    names = []
    for line in lines:
        for pattern in DAYZ_PROCESS_PATTERNS:
            if pattern in line and pattern not in names:
                names.append(pattern)
    detail = "Detected known DayZ process: " + ", ".join(names)
    if len(lines) > len(names):
        detail += f" ({len(lines)} matching process lines)"
    return ProcessCheck(True, detail)


def ok_missing(value: bool) -> str:
    return "OK" if value else "MISSING"


def yes_no(value: bool) -> str:
    return "Yes" if value else "No"
