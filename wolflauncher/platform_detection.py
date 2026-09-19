import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .dayz_product import STABLE, DayZProduct
from .platforms import current_platform

STEAM_APP_ID_DAYZ = 221100
DAYZ_PROCESS_PATTERNS = (
    "DayZ_x64.exe",
    "DayZ_BE.exe",
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
    compatdata_dir: Path | None = None
    library_steamapps: list[Path] = field(default_factory=list)
    product: DayZProduct = STABLE


@dataclass
class ProcessCheck:
    running: bool
    detail: str


@dataclass(frozen=True)
class SteamSelectionReport:
    status: str
    detail: str
    selected_label: str
    candidates: list[str]


NATIVE_STEAM_ROOTS = list(current_platform().native_steam_roots())


def _is_running(process_name: str) -> bool:
    return current_platform().process_running(process_name)


def _matching_process_lines(patterns: tuple[str, ...]) -> list[str]:
    return current_platform().matching_process_lines(patterns)


LIBRARY_PATH_RE = re.compile(r'"path"\s+"((?:\\.|[^"\\])*)"')
INSTALLDIR_RE = re.compile(r'"installdir"\s+"((?:\\.|[^"\\])*)"', re.IGNORECASE)


def _unescape_vdf_string(value: str) -> str:
    return value.replace(r"\\", "\\").replace(r"\"", '"')


def parse_libraryfolders_paths(text: str) -> list[Path]:
    paths = []
    for match in LIBRARY_PATH_RE.finditer(text):
        path = Path(_unescape_vdf_string(match.group(1))).expanduser()
        if path not in paths:
            paths.append(path)
    return paths


def parse_appmanifest_installdir(text: str) -> str:
    match = INSTALLDIR_RE.search(text)
    return _unescape_vdf_string(match.group(1)).strip() if match else ""


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


def _dayz_from_steamapps(steamapps: Path | None, product: DayZProduct = STABLE) -> Path | None:
    if not steamapps:
        return None
    manifest = steamapps / f"appmanifest_{product.client_app_id}.acf"
    try:
        installdir = parse_appmanifest_installdir(manifest.read_text(errors="ignore"))
    except OSError:
        installdir = ""
    if installdir:
        dayz = steamapps / "common" / installdir
        if dayz.exists():
            return dayz
    dayz = steamapps / "common" / ("DayZ Exp" if product.experimental else "DayZ")
    return dayz if dayz.exists() else None


def _workshop_from_steamapps(steamapps: Path | None) -> Path | None:
    if not steamapps:
        return None
    workshop = steamapps / "workshop" / "content" / str(STEAM_APP_ID_DAYZ)
    return workshop if workshop.exists() else None


def _compatdata_from_steamapps(steamapps: Path | None) -> Path | None:
    if not steamapps:
        return None
    compatdata = steamapps / "compatdata" / str(STEAM_APP_ID_DAYZ)
    return compatdata if compatdata.exists() else None


def _dayz_from_libraries(libraries: list[Path], product: DayZProduct = STABLE) -> Path | None:
    for steamapps in libraries:
        dayz = _dayz_from_steamapps(steamapps, product)
        if dayz:
            return dayz
    return None


def _workshop_from_libraries(libraries: list[Path]) -> Path | None:
    for steamapps in libraries:
        workshop = _workshop_from_steamapps(steamapps)
        if workshop:
            return workshop
    return None


def _compatdata_from_libraries(libraries: list[Path]) -> Path | None:
    for steamapps in libraries:
        compatdata = _compatdata_from_steamapps(steamapps)
        if compatdata:
            return compatdata
    return None


def _select_visible_steamapps(libraries: list[Path], product: DayZProduct = STABLE) -> Path | None:
    for steamapps in libraries:
        if _dayz_from_steamapps(steamapps, product) or _workshop_from_steamapps(steamapps):
            return steamapps
    return libraries[0] if libraries else None


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def detect_steam(product: DayZProduct = STABLE) -> list[SteamInstall]:
    installs: list[SteamInstall] = []

    native_root = _first_existing(NATIVE_STEAM_ROOTS)
    native_executable = current_platform().native_steam_executable()
    native_running = _is_running("steam")
    native_libraries = _library_steamapps_from_root(native_root)
    native_steamapps = _select_visible_steamapps(native_libraries, product)

    installs.append(
        SteamInstall(
            mode="native",
            executable=native_executable,
            running=native_running,
            root=native_root,
            steamapps=native_steamapps,
            dayz_dir=_dayz_from_libraries(native_libraries, product),
            workshop_dir=_workshop_from_libraries(native_libraries),
            compatdata_dir=_compatdata_from_libraries(native_libraries),
            library_steamapps=native_libraries,
            product=product,
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
                executable=native_executable,
                running=native_running,
                root=root,
                steamapps=_select_visible_steamapps(env_libraries, product),
                dayz_dir=_dayz_from_libraries(env_libraries, product),
                workshop_dir=_workshop_from_libraries(env_libraries),
                compatdata_dir=_compatdata_from_libraries(env_libraries),
                library_steamapps=env_libraries,
                product=product,
            )
        )

    return installs


def best_install(product: DayZProduct = STABLE) -> SteamInstall | None:
    return best_install_from(detect_steam(product))


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
        "STEAM_ROOT env": "STEAM_ROOT Steam library",
    }
    return labels.get(mode, "Auto")


def select_steam_install(
    mode: str, installs: list[SteamInstall] | None = None
) -> SteamInstall | None:
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
    if install.mode == "STEAM_ROOT env":
        return "STEAM_ROOT Steam library"
    return f"{install.mode} Steam"


def steam_command_detail(install: SteamInstall | None) -> str:
    if not install or not install.executable:
        return "not detected"
    return install.executable


def build_steam_start_command(install: SteamInstall) -> list[str]:
    """Build the selected client's normal start command without launching a game."""
    return [install.executable] if install.executable else []


def steam_install_summary(install: SteamInstall | None) -> str:
    if not install:
        return "Not detected"
    _status, detail = install_readiness(install)
    return f"{detail}; command: {steam_command_detail(install)}"


def selected_install_summary(install: SteamInstall | None) -> str:
    if install and install.dayz_dir and install.workshop_dir:
        state = "DayZ OK | Workshop OK"
    elif install and install.dayz_dir:
        state = "DayZ OK | Workshop missing"
    elif install and (install.root or install.executable):
        state = "DayZ not found yet"
    else:
        return "Selected Steam/DayZ not detected"
    return f"Selected {install_label(install)} | {state} | command: {steam_command_detail(install)}"


def steam_selection_readiness(
    mode: str, installs: list[SteamInstall] | None = None
) -> tuple[str, str]:
    report = steam_selection_report(mode, installs)
    return report.status, report.detail


def steam_selection_report(
    mode: str, installs: list[SteamInstall] | None = None
) -> SteamSelectionReport:
    detected = installs if installs is not None else detect_steam()
    install = select_steam_install(mode, detected)
    candidates = [
        steam_install_summary(candidate)
        for candidate in detected
        if candidate.root or candidate.executable
    ]
    if mode == "auto":
        if not install:
            return SteamSelectionReport(
                "MISSING", "Auto selection found no Steam install", "None", candidates
            )
        status, _detail = install_readiness(install)
        return SteamSelectionReport(
            status,
            f"Auto selected {steam_install_summary(install)}",
            install_label(install),
            candidates,
        )
    if not install:
        return SteamSelectionReport(
            "MISSING", f"{steam_mode_label(mode)} not detected", "None", candidates
        )
    status, _detail = install_readiness(install)
    return SteamSelectionReport(
        status, steam_install_summary(install), install_label(install), candidates
    )


def steam_selection_candidates_detail(report: SteamSelectionReport) -> str:
    if not report.candidates:
        return "No native or STEAM_ROOT Steam installs detected"
    return "; ".join(report.candidates)


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
    if install.dayz_dir and install.workshop_dir and not install.executable:
        return "WARN", f"{label} ready, but Steam command is not detected ({state})"
    if install.dayz_dir and install.workshop_dir:
        return "OK", f"{label} ready ({state})"
    return "WARN", f"{label} partially detected ({state})"


def dayz_process_check() -> ProcessCheck:
    lines = _matching_process_lines(DAYZ_PROCESS_PATTERNS)
    if not lines:
        return ProcessCheck(False, "No known DayZ process detected")
    names = []
    for line in lines:
        lower_line = line.lower()
        for pattern in DAYZ_PROCESS_PATTERNS:
            if pattern.lower() in lower_line and pattern not in names:
                names.append(pattern)
    if not names:
        return ProcessCheck(False, "No known DayZ process detected")
    detail = "Detected known DayZ process: " + ", ".join(names)
    if len(lines) > len(names):
        detail += f" ({len(lines)} matching process lines)"
    return ProcessCheck(True, detail)


def ok_missing(value: bool) -> str:
    return "OK" if value else "MISSING"


def yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def proton_compatdata_detail(install: SteamInstall | None) -> str:
    if not current_platform().capabilities.uses_proton:
        return "not applicable on Windows"
    if install and install.compatdata_dir:
        return str(install.compatdata_dir)
    if install and (install.root or install.steamapps or install.dayz_dir):
        return "not detected yet; Steam may create it on first Proton launch"
    return "not detected"
