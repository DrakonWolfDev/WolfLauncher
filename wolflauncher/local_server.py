"""Pure local DayZ dedicated-server command and public-key helpers."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


DAYZ_SERVER_APP_ID = "223350"


@dataclass(frozen=True)
class LocalServerLaunch:
    root: Path
    executable: Path
    config: Path
    profiles: Path
    port: int
    mod_paths: tuple[Path, ...] = ()
    server_mod_paths: tuple[Path, ...] = ()
    file_patching: bool = False


def server_executable(root: Path) -> Path | None:
    for name in ("DayZServer_x64.exe", "DayZServer"):
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def build_local_server_command(launch: LocalServerLaunch) -> list[str]:
    if not launch.executable.is_file():
        raise ValueError("DayZ dedicated-server executable was not found in the selected server root.")
    if not launch.config.is_file():
        raise ValueError("Select an existing serverDZ.cfg file before starting the local server.")
    if not 1 <= launch.port <= 65535:
        raise ValueError("The dedicated-server port must be between 1 and 65535.")
    command = [
        str(launch.executable),
        f"-config={launch.config}",
        f"-port={launch.port}",
        f"-profiles={launch.profiles}",
        "-dologs",
        "-adminlog",
        "-netlog",
        "-freezecheck",
    ]
    if launch.mod_paths:
        command.append("-mod=" + ";".join(str(path) for path in launch.mod_paths))
    if launch.server_mod_paths:
        command.append("-serverMod=" + ";".join(str(path) for path in launch.server_mod_paths))
    if launch.file_patching:
        command.append("-filePatching")
    return command


def build_steamcmd_install_command(steamcmd: Path, destination: Path) -> list[str]:
    if not steamcmd.is_file():
        raise ValueError("Select the SteamCMD executable/script before installing a temporary server.")
    if not destination.name:
        raise ValueError("Select a dedicated temporary-server folder.")
    return [
        str(steamcmd),
        "+force_install_dir",
        str(destination),
        "+login",
        "anonymous",
        "+app_update",
        DAYZ_SERVER_APP_ID,
        "validate",
        "+quit",
    ]


def public_key_files(mod_paths: tuple[Path, ...]) -> tuple[Path, ...]:
    keys = []
    for mod_path in mod_paths:
        key_dir = mod_path / "Keys"
        if key_dir.is_dir():
            keys.extend(path for path in key_dir.glob("*.bikey") if path.is_file())
    return tuple(sorted(set(keys), key=lambda path: path.name.casefold()))


def sync_public_keys(mod_paths: tuple[Path, ...], server_root: Path) -> tuple[Path, ...]:
    destination = server_root / "keys"
    if not server_root.is_dir():
        raise ValueError("Select an existing dedicated-server root before syncing public keys.")
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    for key in public_key_files(mod_paths):
        target = destination / key.name
        shutil.copy2(key, target)
        copied.append(target)
    return tuple(copied)
