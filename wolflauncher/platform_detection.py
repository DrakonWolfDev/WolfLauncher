import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
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
    library_steamapps: list[Path] = field(default_factory=list)


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


LIBRARY_PATH_RE = re.compile(r'"path"\s+"((?:\\.|[^"\\])*)"')


def _unescape_vdf_string(value: str) -> str:
    return value.replace(r"\\", "\\").replace(r"\"", '"')


def parse_libraryfolders_paths(text: str) -> list[Path]:
    paths = []
    for match in LIBRARY_PATH_RE.finditer(text):
        path = Path(_unescape_vdf_string(match.group(1))).expanduser()
        if path not in paths:
            paths.append(path)
    return paths


def _steamapps_from_root(root: Path | None) -> Path | None:
    if not root:
        return None
    steamapps = root / "steamapps"
    return steamapps if steamapps.exists() else None


def _library_steamapps_from_root(root: Path | None) -> list[Path]:
    primary = _steamapps_from_root(root)
    if not primary:
        return []

    libraries = [primary]
    libraryfolders = primary / "libraryfolders.vdf"
    try:
        extra_roots = parse_libraryfolders_paths(libraryfolders.read_text(errors="ignore"))
    except OSError:
        extra_roots = []

    for library_root in extra_roots:
        steamapps = library_root / "steamapps"
        if steamapps.exists() and steamapps not in libraries:
            libraries.append(steamapps)
    return libraries


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


def _dayz_from_libraries(libraries: list[Path]) -> Path | None:
    for steamapps in libraries:
        dayz = _dayz_from_steamapps(steamapps)
        if dayz:
            return dayz
    return None


def _workshop_from_libraries(libraries: list[Path]) -> Path | None:
    for steamapps in libraries:
        workshop = _workshop_from_steamapps(steamapps)
        if workshop:
            return workshop
    return None


def _select_visible_steamapps(libraries: list[Path]) -> Path | None:
    for steamapps in libraries:
        if _dayz_from_steamapps(steamapps) or _workshop_from_steamapps(steamapps):
            return steamapps
    return libraries[0] if libraries else None


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def detect_steam() -> list[SteamInstall]:
    installs: list[SteamInstall] = []

    native_root = _first_existing(NATIVE_STEAM_ROOTS)
    native_libraries = _library_steamapps_from_root(native_root)
    native_steamapps = _select_visible_steamapps(native_libraries)
    installs.append(
        SteamInstall(
            mode="native",
            executable=shutil.which("steam") or "",
            running=_is_running("steam"),
            root=native_root,
            steamapps=native_steamapps,
            dayz_dir=_dayz_from_libraries(native_libraries),
            workshop_dir=_workshop_from_libraries(native_libraries),
            library_steamapps=native_libraries,
        )
    )

    flatpak_root = FLATPAK_STEAM_ROOT if FLATPAK_STEAM_ROOT.exists() else None
    flatpak_libraries = _library_steamapps_from_root(flatpak_root)
    flatpak_steamapps = _select_visible_steamapps(flatpak_libraries)
    installs.append(
        SteamInstall(
            mode="flatpak",
            executable=FLATPAK_STEAM_ID if shutil.which("flatpak") else "",
            running=_flatpak_steam_running(),
            root=flatpak_root,
            steamapps=flatpak_steamapps,
            dayz_dir=_dayz_from_libraries(flatpak_libraries),
            workshop_dir=_workshop_from_libraries(flatpak_libraries),
            library_steamapps=flatpak_libraries,
        )
    )

    env_root = os.environ.get("STEAM_ROOT")
    if env_root:
        root = Path(env_root).expanduser()
        steamapps = root / "steamapps" if (root / "steamapps").exists() else root
        env_libraries = [steamapps] if steamapps.exists() else []
        installs.append(
            SteamInstall(
                mode="STEAM_ROOT env",
                executable="",
                running=False,
                root=root,
                steamapps=_select_visible_steamapps(env_libraries),
                dayz_dir=_dayz_from_libraries(env_libraries),
                workshop_dir=_workshop_from_libraries(env_libraries),
                library_steamapps=env_libraries,
            )
        )

    return installs


def best_install() -> SteamInstall | None:
    return best_install_from(detect_steam())


def best_install_from(installs: list[SteamInstall]) -> SteamInstall | None:
    for install in installs:
        if install.dayz_dir and install.workshop_dir:
            return install
    for install in installs:
        if install.root or install.executable:
            return install
    return installs[0] if installs else None


def steam_mode_label(mode: str) -> str:
    labels = {
        "auto": "Auto",
        "native": "Native Steam",
        "flatpak": "Flatpak Steam",
        "STEAM_ROOT env": "STEAM_ROOT Steam library",
    }
    return labels.get(mode, "Auto")


def select_steam_install(mode: str, installs: list[SteamInstall] | None = None) -> SteamInstall | None:
    detected = installs if installs is not None else detect_steam()
    if mode == "auto":
        return best_install_from(detected)
    for install in detected:
        if install.mode == mode:
            return install
    return None


def install_label(install: SteamInstall) -> str:
    if install.mode == "native":
        return "Native Steam"
    if install.mode == "flatpak":
        return "Flatpak Steam"
    if install.mode == "STEAM_ROOT env":
        return "STEAM_ROOT Steam library"
    return f"{install.mode} Steam"


def steam_selection_readiness(mode: str, installs: list[SteamInstall] | None = None) -> tuple[str, str]:
    install = select_steam_install(mode, installs)
    if mode == "auto":
        if not install:
            return "MISSING", "Auto selection found no Steam install"
        status, detail = install_readiness(install)
        return status, f"Auto selected {detail}"
    if not install:
        return "MISSING", f"{steam_mode_label(mode)} not detected"
    return install_readiness(install)


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
