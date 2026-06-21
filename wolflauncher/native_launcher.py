import base64
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .models import Server
from .mods import RequiredMod, fetch_required_mods
from .platform_detection import FLATPAK_STEAM_ID, STEAM_APP_ID_DAYZ, SteamInstall
from .status import resolve_host


class NativeLaunchError(RuntimeError):
    def __init__(self, message: str, *, stage: str = "native launch", guidance: str = ""):
        super().__init__(message)
        self.stage = stage
        self.guidance = guidance

    def user_message(self) -> str:
        if not self.guidance:
            return str(self)
        return f"{self}\n\n{self.guidance}"


FLATPAK_STEAM_PARAMS = [
    "--branch=stable",
    "--arch=x86_64",
    "--command=/app/bin/steam-wrapper",
]
MOD_NAME_RE = re.compile(r'name\s*=\s*"([^"]+)"')


@dataclass
class PreparedNativeLaunch:
    command: list[str]
    mod_links: list[str] = field(default_factory=list)
    missing_mod_ids: list[str] = field(default_factory=list)
    prepared_mods: list["PreparedModLink"] = field(default_factory=list)


@dataclass
class PreparedModLink:
    workshop_id: str
    name: str
    source_path: Path
    link_path: Path
    link_name: str
    created: bool


@dataclass
class NativeModSetup:
    mod_links: list[str] = field(default_factory=list)
    prepared_mods: list[PreparedModLink] = field(default_factory=list)
    missing_mod_ids: list[str] = field(default_factory=list)


@dataclass
class NativeLaunchPreview:
    server: Server
    command: list[str]
    mod_setup: NativeModSetup

    @property
    def ready(self) -> bool:
        return not self.mod_setup.missing_mod_ids


def compact_mod_link_name(workshop_id: str | int) -> str:
    """Return the legacy launcher's shortened @base64modid link name."""
    try:
        value = int(str(workshop_id).strip(), 10)
    except ValueError as exc:
        raise NativeLaunchError(
            f"Invalid Workshop mod ID: {workshop_id}",
            stage="mod setup",
            guidance="Recheck the server's required mod list before trying the native launcher again.",
        ) from exc
    if value < 0:
        raise NativeLaunchError(
            f"Invalid Workshop mod ID: {workshop_id}",
            stage="mod setup",
            guidance="Recheck the server's required mod list before trying the native launcher again.",
        )

    encoded = bytearray()
    while True:
        encoded.append(value & 0xFF)
        value >>= 8
        if value <= 0:
            break
    token = base64.b64encode(bytes(encoded)).decode("ascii")
    token = token.replace("/", "-").replace("+", "_").rstrip("=")
    return f"@{token}"


def build_steam_launch_command(
    install: SteamInstall,
    server: Server,
    player_name: str,
    mod_links: list[str],
    extra_params: list[str] | None = None,
) -> list[str]:
    safe_name = player_name.strip()
    command = _steam_command_prefix(install)
    command.extend(["-applaunch", str(STEAM_APP_ID_DAYZ)])

    if mod_links:
        command.append(f"-mod={';'.join(mod_links)}")
    command.extend([f"-connect={server.host}:{server.game_port}", "-nolauncher", "-world=empty"])
    if safe_name:
        command.append(f"-name={safe_name}")
    if extra_params:
        command.extend(extra_params)
    return command


def prepare_native_launch(
    install: SteamInstall,
    server: Server,
    player_name: str,
    required_mods: list[RequiredMod] | None = None,
    extra_params: list[str] | None = None,
) -> PreparedNativeLaunch:
    """Prepare DayZ mod symlinks and build the Steam launch command.

    This mirrors the vendored shell launcher core while staying behind a Python
    interface. Callers can pass already-fetched mods to keep GUI preflight and
    native preparation in sync; otherwise the DayZSA API is queried here.
    """
    dayz_dir = _require_dir(install.dayz_dir, "DayZ install")
    workshop_dir = _require_dir(install.workshop_dir, "DayZ Workshop")
    launch_server = _resolved_server(server)
    mods = required_mods if required_mods is not None else fetch_required_mods(launch_server)

    mod_setup = prepare_mod_links(dayz_dir, workshop_dir, mods)

    if mod_setup.missing_mod_ids:
        raise NativeLaunchError(
            "Missing mod directories for: " + ", ".join(mod_setup.missing_mod_ids),
            stage="mod setup",
            guidance=(
                "Open the missing Workshop pages from the Mods tab, let Steam finish downloading them, "
                "then run the mod check again."
            ),
        )

    return PreparedNativeLaunch(
        command=build_steam_launch_command(install, launch_server, player_name, mod_setup.mod_links, extra_params),
        mod_links=mod_setup.mod_links,
        missing_mod_ids=mod_setup.missing_mod_ids,
        prepared_mods=mod_setup.prepared_mods,
    )


def prepare_native_launch_preview(
    install: SteamInstall,
    server: Server,
    player_name: str,
    required_mods: list[RequiredMod],
    extra_params: list[str] | None = None,
) -> NativeLaunchPreview:
    """Prepare installed mod links and return a non-executing launch preview."""
    dayz_dir = _require_dir(install.dayz_dir, "DayZ install")
    workshop_dir = _require_dir(install.workshop_dir, "DayZ Workshop")
    launch_server = _resolved_server(server)
    mod_setup = prepare_mod_links(dayz_dir, workshop_dir, required_mods)
    command = []
    if not mod_setup.missing_mod_ids:
        command = build_steam_launch_command(install, launch_server, player_name, mod_setup.mod_links, extra_params)
    return NativeLaunchPreview(server=launch_server, command=command, mod_setup=mod_setup)


def prepare_mod_links(dayz_dir: Path, workshop_dir: Path, required_mods: list[RequiredMod]) -> NativeModSetup:
    """Prepare the legacy-compatible DayZ @mod symlinks for installed mods."""
    setup = NativeModSetup()

    for mod in required_mods:
        workshop_id = str(mod.workshop_id).strip()
        compact_name = compact_mod_link_name(workshop_id)
        mod_path = workshop_dir / workshop_id
        if not mod_path.is_dir():
            setup.missing_mod_ids.append(workshop_id)
            continue

        if not (mod_path / "meta.cpp").is_file():
            raise NativeLaunchError(
                f"Missing mod metadata for: {workshop_id}",
                stage="mod setup",
                guidance="Let Steam verify or redownload the Workshop item, then recheck mods.",
            )
        mod_name = mod.name.strip() or _read_mod_name(mod_path / "meta.cpp")
        if not mod_name:
            raise NativeLaunchError(
                f"Missing mod name for: {workshop_id}",
                stage="mod setup",
                guidance="Let Steam verify or redownload the Workshop item, then recheck mods.",
            )

        link_path = dayz_dir / compact_name
        created = _ensure_relative_symlink(mod_path, link_path)
        setup.mod_links.append(compact_name)
        setup.prepared_mods.append(
            PreparedModLink(
                workshop_id=workshop_id,
                name=mod_name,
                source_path=mod_path,
                link_path=link_path,
                link_name=compact_name,
                created=created,
            )
        )

    return setup


def _steam_command_prefix(install: SteamInstall) -> list[str]:
    if install.mode == "flatpak":
        if not install.executable:
            raise NativeLaunchError(
                "Flatpak executable not detected",
                stage="Steam detection",
                guidance="Install Flatpak Steam or switch to a detected native Steam installation.",
            )
        return ["flatpak", "run", *FLATPAK_STEAM_PARAMS, FLATPAK_STEAM_ID]

    executable = install.executable or "steam"
    return [executable]


def _require_dir(path: Path | None, label: str) -> Path:
    if not path or not path.is_dir():
        raise NativeLaunchError(
            f"{label} directory not detected",
            stage="Steam library detection",
            guidance="Check Settings health and confirm DayZ is installed in the detected Steam library.",
        )
    return path


def _resolved_server(server: Server) -> Server:
    try:
        host = resolve_host(server.host)
    except OSError as exc:
        raise NativeLaunchError(
            f"Could not resolve server host {server.host}: {exc}",
            stage="server DNS",
            guidance="Check the server address, network connection and DNS before launching.",
        ) from exc
    return Server(
        name=server.name,
        group=server.group,
        host=host,
        game_port=server.game_port,
        query_port=server.query_port,
        favourite=server.favourite,
    )


def _read_mod_name(meta_path: Path) -> str:
    if not meta_path.is_file():
        return ""
    try:
        text = meta_path.read_text(errors="ignore")
    except OSError:
        return ""
    match = MOD_NAME_RE.search(text)
    return match.group(1).strip() if match else ""


def _ensure_relative_symlink(target: Path, link_path: Path) -> bool:
    if link_path.is_symlink():
        return False
    if link_path.exists():
        raise NativeLaunchError(
            f"Mod link path already exists and is not a symlink: {link_path}",
            stage="mod setup",
            guidance="Move or remove the conflicting path in the DayZ install directory before retrying.",
        )

    relative_target = os.path.relpath(target, start=link_path.parent)
    try:
        link_path.symlink_to(relative_target)
        return True
    except OSError as exc:
        raise NativeLaunchError(
            f"Could not create mod symlink {link_path}: {exc}",
            stage="mod setup",
            guidance="Check write permissions on the DayZ install directory.",
        ) from exc
