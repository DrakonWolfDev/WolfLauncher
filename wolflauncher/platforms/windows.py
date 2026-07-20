from __future__ import annotations

import csv
import importlib
import os
import shutil
import subprocess
from io import StringIO
from pathlib import Path

from .base import PlatformCapabilities

winreg = importlib.import_module("winreg") if os.name == "nt" else None


class WindowsPlatformBackend:
    capabilities = PlatformCapabilities(
        platform_id="windows",
        display_name="Windows",
        supports_flatpak=False,
        uses_proton=False,
        supports_external_launcher=False,
        mod_link_strategy="absolute_path",
        diagnostic_tools=("gamedig", "node", "npm"),
    )

    def user_config_dir(self) -> Path:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "wolflauncher"

    def user_data_dir(self) -> Path:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "wolflauncher"

    def native_steam_roots(self) -> tuple[Path, ...]:
        candidates: list[Path] = []
        for hive, key, value_name in self._registry_locations():
            value = self._read_registry_string(hive, key, value_name)
            if value:
                candidates.append(Path(value))
        program_files_x86 = os.environ.get("PROGRAMFILES(X86)")
        program_files = os.environ.get("PROGRAMFILES")
        if program_files_x86:
            candidates.append(Path(program_files_x86) / "Steam")
        if program_files:
            candidates.append(Path(program_files) / "Steam")
        return tuple(dict.fromkeys(candidates))

    def flatpak_steam_root(self) -> None:
        return None

    def native_steam_executable(self) -> str:
        steam_exe = self._read_registry_string(
            self._hkey_current_user(), r"Software\Valve\Steam", "SteamExe"
        )
        if steam_exe and Path(steam_exe).is_file():
            return str(Path(steam_exe))
        for root in self.native_steam_roots():
            candidate = root / "steam.exe"
            if candidate.is_file():
                return str(candidate)
        return shutil.which("steam.exe") or shutil.which("steam") or ""

    def process_running(self, process_name: str) -> bool:
        wanted = self._exe_name(process_name).lower()
        return any(name.lower() == wanted for name in self._task_names())

    def matching_process_lines(self, patterns: tuple[str, ...]) -> list[str]:
        wanted = {self._exe_name(pattern).lower() for pattern in patterns}
        return [name for name in self._task_names() if name.lower() in wanted]

    def flatpak_steam_installed(self) -> bool:
        return False

    def flatpak_steam_running(self) -> bool:
        return False

    def steam_api_library_candidates(
        self, _steam_root: Path | None, dayz_dir: Path | None
    ) -> tuple[Path, ...]:
        if not dayz_dir:
            return ()
        return (dayz_dir / "steam_api64.dll",)

    @staticmethod
    def _exe_name(process_name: str) -> str:
        return process_name if process_name.lower().endswith(".exe") else f"{process_name}.exe"

    @staticmethod
    def _task_names() -> list[str]:
        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if result.returncode != 0:
            return []
        return [row[0] for row in csv.reader(StringIO(result.stdout)) if row]

    @staticmethod
    def _hkey_current_user():
        return winreg.HKEY_CURRENT_USER if winreg else None

    @staticmethod
    def _registry_locations():
        if not winreg:
            return ()
        return (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        )

    @staticmethod
    def _read_registry_string(hive, key: str, value_name: str) -> str:
        if winreg is None or hive is None:
            return ""
        try:
            with winreg.OpenKey(hive, key) as handle:
                value, _kind = winreg.QueryValueEx(handle, value_name)
        except OSError:
            return ""
        return str(value).strip() if value else ""
