import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .config import DEFAULT_LAUNCHER_PATHS
from .diagnostics import (
    launch_troubleshooting_report,
)
from .dayz_product import DayZProduct, STABLE
from .platform_detection import (
    SteamInstall,
    proton_compatdata_detail,
    select_steam_install,
    selected_install_summary,
    steam_install_summary,
    steam_selection_candidates_detail,
    steam_selection_report,
)
from .platforms import current_platform

HealthRow = tuple[str, str, str]


@dataclass(frozen=True)
class SettingsHealthSnapshot:
    summary: str
    rows: tuple[HealthRow, ...]


def build_settings_health_snapshot(
    launcher_path: str,
    launch_engine: str,
    selected_steam_mode: str,
    provider_status: str,
    provider_detail: str,
    install_rows: Iterable[SteamInstall],
    *,
    product: DayZProduct = STABLE,
    command_lookup: Callable[[str], str | None] = shutil.which,
    launcher_candidates: Iterable[Path] = DEFAULT_LAUNCHER_PATHS,
) -> SettingsHealthSnapshot:
    installs = list(install_rows)
    selected_install = select_steam_install(selected_steam_mode, installs)
    path = Path(launcher_path).expanduser()
    auto_steam_report = steam_selection_report("auto", installs)
    steam_report = steam_selection_report(selected_steam_mode, installs)
    selected_steam_status = steam_report.status
    selected_steam_detail = steam_report.detail
    if selected_steam_status == "OK" and selected_install and not selected_install.running:
        selected_steam_status = "WARN"
        selected_steam_detail += "; Connect will start Steam"
    capabilities = current_platform().capabilities
    missing_tools = [
        command for command in capabilities.diagnostic_tools if not command_lookup(command)
    ]
    existing_launcher_candidates = [
        str(candidate) for candidate in launcher_candidates if candidate.exists()
    ]
    launch_report = launch_troubleshooting_report(selected_steam_mode, installs)

    rows: list[HealthRow] = [
        (
            "Launch engine",
            "OK",
            "Native launcher" if launch_engine == "native" else "External launcher (fallback)",
        ),
        (
            "Launcher script",
            "OK" if launch_engine == "native" or path.is_file() else "MISSING",
            "Not required for native mode" if launch_engine == "native" else str(path),
        ),
        ("Server API", provider_status, provider_detail),
        (
            "Required tools",
            "OK" if not missing_tools else "WARN",
            "All found" if not missing_tools else "Missing: " + ", ".join(missing_tools),
        ),
        ("Selected Steam", selected_steam_status, selected_steam_detail),
        ("Auto Steam", auto_steam_report.status, auto_steam_report.detail),
        ("Launch troubleshooting", launch_report.status, "; ".join(launch_report.next_steps)),
        (
            "Steam candidates",
            "OK" if steam_report.candidates else "WARN",
            steam_selection_candidates_detail(steam_report),
        ),
        (
            product.label,
            "OK" if selected_install and selected_install.dayz_dir else "MISSING",
            str(selected_install.dayz_dir)
            if selected_install and selected_install.dayz_dir
            else "Not detected",
        ),
        (
            "Workshop",
            "OK" if selected_install and selected_install.workshop_dir else "MISSING",
            str(selected_install.workshop_dir)
            if selected_install and selected_install.workshop_dir
            else "Not detected",
        ),
        (
            "Configured Steam installs",
            "OK" if any(item.root or item.executable for item in installs) else "WARN",
            ", ".join(
                steam_install_summary(item) for item in installs if item.root or item.executable
            )
            or "No Steam roots found",
        ),
    ]
    if capabilities.uses_proton:
        rows.extend(
            [
                ("Proton compatdata", "OK", proton_compatdata_detail(selected_install)),
            ]
        )
    if capabilities.supports_external_launcher:
        rows.append(
            (
                "Launcher candidates",
                "OK" if existing_launcher_candidates else "WARN",
                ", ".join(existing_launcher_candidates) or "No default candidate exists",
            )
        )
    return SettingsHealthSnapshot(selected_install_summary(selected_install), tuple(rows))
