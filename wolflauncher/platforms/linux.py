from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .base import PlatformCapabilities

FLATPAK_STEAM_ID = "com.valvesoftware.Steam"


class LinuxPlatformBackend:
    capabilities = PlatformCapabilities(
        platform_id="linux",
        display_name="Linux",
        supports_flatpak=True,
        uses_proton=True,
        supports_external_launcher=True,
        mod_link_strategy="relative_symlink",
    )

    def user_config_dir(self) -> Path:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "wolflauncher"

    def user_data_dir(self) -> Path:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return base / "wolflauncher"

    def native_steam_roots(self) -> tuple[Path, ...]:
        return (
            Path.home() / ".local/share/Steam",
            Path.home() / ".steam/steam",
        )

    def flatpak_steam_root(self) -> Path:
        return Path.home() / ".var/app" / FLATPAK_STEAM_ID / "data" / "Steam"

    def native_steam_executable(self) -> str:
        return shutil.which("steam") or ""

    def process_running(self, process_name: str) -> bool:
        try:
            result = subprocess.run(
                ["pgrep", "-x", process_name],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.returncode == 0
        except Exception:
            return False

    def matching_process_lines(self, patterns: tuple[str, ...]) -> list[str]:
        try:
            result = subprocess.run(
                ["pgrep", "-afi", "|".join(patterns)],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except Exception:
            return []
        if result.returncode != 0:
            return []
        return [
            line
            for line in result.stdout.splitlines()
            if any(pattern.lower() in line.lower() for pattern in patterns)
        ]

    def flatpak_steam_installed(self) -> bool:
        if not shutil.which("flatpak"):
            return False
        try:
            result = subprocess.run(
                ["flatpak", "info", FLATPAK_STEAM_ID],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return result.returncode == 0
        except Exception:
            return False

    def flatpak_steam_running(self) -> bool:
        if not shutil.which("flatpak"):
            return False
        try:
            result = subprocess.run(["flatpak", "ps"], capture_output=True, text=True, timeout=3)
            return result.returncode == 0 and FLATPAK_STEAM_ID in result.stdout
        except Exception:
            return False
