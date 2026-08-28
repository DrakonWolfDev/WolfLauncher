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
        roots = (
            Path.home() / ".local/share/Steam",
            Path.home() / ".steam/steam",
        )
        # Add Flatpak Steam path
        flatpak_path = Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam"
        if flatpak_path.exists():
            roots += (flatpak_path,)
        # Add Snap Steam path
        snap_path = Path.home() / "snap/steam/common/.local/share/Steam"
        if snap_path.exists():
            roots += (snap_path,)
        return roots

    def native_steam_executable(self) -> str:
        # Check for flatpak steam first
        flatpak_flatpak = shutil.which("flatpak")
        if flatpak_flatpak:
            # Verify flatpak steam is installed
            import subprocess
            try:
                result = subprocess.run(
                    ["flatpak", "info", "com.valvesoftware.Steam"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0:
                    # Return a special indicator that we'll handle in _steam_command_prefix
                    return "flatpak"
            except Exception:
                pass
        
        # Check for snap steam
        snap_path = Path("/snap/bin/steam")
        if snap_path.exists():
            return str(snap_path)
            
        # Fall back to regular steam
        return shutil.which("steam") or ""

    def process_running(self, process_name: str) -> bool:
        # Special handling for flatpak steam
        if process_name == "steam":
            # Check for regular steam process
            try:
                result = subprocess.run(
                    ["pgrep", "-x", "steam"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0:
                    return True
            except Exception:
                pass
            
            # Check for flatpak steam process
            try:
                result = subprocess.run(
                    ["flatpak", "ps"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0 and "com.valvesoftware.Steam" in result.stdout:
                    return True
            except Exception:
                pass
                
            return False
        else:
            # For other processes, use the standard approach
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
                # Flatpak Steam path
                Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam/steamrt64/libsteam_api.so",
                # Snap Steam path
                Path.home() / "snap/steam/common/.local/share/Steam/steamrt64/libsteam_api.so",
            ]
        )
        return tuple(candidates)
