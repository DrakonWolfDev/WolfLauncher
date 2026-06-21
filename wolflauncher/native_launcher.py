import base64
import os
from dataclasses import dataclass, field
from pathlib import Path

from .models import Server
from .mods import RequiredMod, fetch_required_mods
from .platform_detection import FLATPAK_STEAM_ID, STEAM_APP_ID_DAYZ, SteamInstall
from .status import resolve_host


class NativeLaunchError(RuntimeError):
    pass


FLATPAK_STEAM_PARAMS = [
    "--branch=stable",
    "--arch=x86_64",
    "--command=/app/bin/steam-wrapper",
]


@dataclass
class PreparedNativeLaunch:
    command: list[str]
    mod_links: list[str] = field(default_factory=list)
    missing_mod_ids: list[str] = field(default_factory=list)


def compact_mod_link_name(workshop_id: str | int) -> str:
    """Return the legacy launcher's shortened @base64modid link name."""
    try:
        value = int(str(workshop_id).strip(), 10)
    except ValueError as exc:
        raise NativeLaunchError(f"Invalid Workshop mod ID: {workshop_id}") from exc
    if value < 0:
        raise NativeLaunchError(f"Invalid Workshop mod ID: {workshop_id}")

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

    mod_links: list[str] = []
    missing_mod_ids: list[str] = []
    for mod in mods:
        mod_path = workshop_dir / mod.workshop_id
        if not mod_path.is_dir():
            missing_mod_ids.append(mod.workshop_id)
            continue
        if not (mod_path / "meta.cpp").is_file():
            raise NativeLaunchError(f"Missing mod metadata for: {mod.workshop_id}")

        mod_link = compact_mod_link_name(mod.workshop_id)
        _ensure_relative_symlink(mod_path, dayz_dir / mod_link)
        mod_links.append(mod_link)

    if missing_mod_ids:
        raise NativeLaunchError("Missing mod directories for: " + ", ".join(missing_mod_ids))

    return PreparedNativeLaunch(
        command=build_steam_launch_command(install, launch_server, player_name, mod_links, extra_params),
        mod_links=mod_links,
        missing_mod_ids=missing_mod_ids,
    )


def _steam_command_prefix(install: SteamInstall) -> list[str]:
    if install.mode == "flatpak":
        if not install.executable:
            raise NativeLaunchError("Flatpak executable not detected")
        return ["flatpak", "run", *FLATPAK_STEAM_PARAMS, FLATPAK_STEAM_ID]

    executable = install.executable or "steam"
    return [executable]


def _require_dir(path: Path | None, label: str) -> Path:
    if not path or not path.is_dir():
        raise NativeLaunchError(f"{label} directory not detected")
    return path


def _resolved_server(server: Server) -> Server:
    try:
        host = resolve_host(server.host)
    except OSError as exc:
        raise NativeLaunchError(f"Could not resolve server host {server.host}: {exc}") from exc
    return Server(
        name=server.name,
        group=server.group,
        host=host,
        game_port=server.game_port,
        query_port=server.query_port,
        favourite=server.favourite,
    )


def _ensure_relative_symlink(target: Path, link_path: Path) -> None:
    if link_path.is_symlink():
        return
    if link_path.exists():
        raise NativeLaunchError(f"Mod link path already exists and is not a symlink: {link_path}")

    relative_target = os.path.relpath(target, start=link_path.parent)
    try:
        link_path.symlink_to(relative_target)
    except OSError as exc:
        raise NativeLaunchError(f"Could not create mod symlink {link_path}: {exc}") from exc
