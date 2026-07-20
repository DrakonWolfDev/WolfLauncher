from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


@dataclass(frozen=True)
class PlatformCapabilities:
    platform_id: str
    display_name: str
    supports_flatpak: bool
    uses_proton: bool
    supports_external_launcher: bool
    mod_link_strategy: str
    diagnostic_tools: tuple[str, ...]


class PlatformBackend(Protocol):
    capabilities: PlatformCapabilities

    def user_config_dir(self) -> Path: ...

    def user_data_dir(self) -> Path: ...

    def native_steam_roots(self) -> Sequence[Path]: ...

    def flatpak_steam_root(self) -> Path | None: ...

    def native_steam_executable(self) -> str: ...

    def process_running(self, process_name: str) -> bool: ...

    def matching_process_lines(self, patterns: tuple[str, ...]) -> list[str]: ...

    def flatpak_steam_installed(self) -> bool: ...

    def flatpak_steam_running(self) -> bool: ...

    def steam_api_library_candidates(
        self, steam_root: Path | None, dayz_dir: Path | None
    ) -> Sequence[Path]: ...
