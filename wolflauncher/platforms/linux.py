from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .base import PlatformCapabilities


class LinuxPlatformBackend:
    capabilities = PlatformCapabilities(
        platform_id="linux",
        display_name="Linux",
        uses_proton=True,
        supports_external_launcher=True,
        mod_link_strategy="relative_symlink",
        diagnostic_tools=("python3", "gamedig", "node", "npm", "dig", "curl", "jq", "gawk"),
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

    def native_steam_executable(self) -> str:
        executable = shutil.which("steam") or ""
        # A Snap shim on PATH must not be treated as native Steam.
        if executable and (
            "snap" in Path(executable).parts
            or "snap" in Path(executable).resolve().parts
            or Path(executable).resolve().name == "snap"
        ):
            return ""
        return executable

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

    def steam_api_library_candidates(
        self, steam_root: Path | None, _dayz_dir: Path | None
    ) -> tuple[Path, ...]:
        candidates: list[Path] = []
        if steam_root:
            candidates.append(steam_root / "steamrt64" / "libsteam_api.so")
        candidates.extend(
            [
                Path.home() / ".local/share/Steam/steamrt64/libsteam_api.so",
                Path.home() / ".steam/steam/steamrt64/libsteam_api.so",
            ]
        )
        return tuple(candidates)
