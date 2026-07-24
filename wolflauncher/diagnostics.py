import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .config import DEFAULT_LAUNCHER_PATHS
from .models import Server
from .platform_detection import (
    dayz_process_check,
    detect_steam,
    install_label,
    install_readiness,
    ok_missing,
    proton_compatdata_detail,
    select_steam_install,
    steam_command_detail,
    steam_mode_label,
    steam_selection_candidates_detail,
    steam_selection_report,
    yes_no,
)
from .platforms import current_platform
from .redaction import redact_support_text
from .status import resolve_host

@dataclass(frozen=True)
class LaunchTroubleshootingReport:
    status: str
    summary: str
    details: list[str]
    next_steps: list[str]


def format_settings_health_report(
    summary: str,
    rows: Sequence[Sequence[str]],
    generated_at: datetime | None = None,
) -> str:
    lines = ["WolfLauncher Settings Health"]
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    lines.append(
        f"Generated at: {timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat()}"
    )
    clean_summary = summary.strip()
    if clean_summary:
        lines.extend(["", f"Summary: {clean_summary}"])
    lines.append("")
    for row in rows:
        lines.append(" | ".join(value.strip() for value in row))
    return redact_support_text("\n".join(lines).strip())


def format_launch_output_report(
    command_text: str,
    output_text: str,
    generated_at: datetime | None = None,
) -> str:
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return redact_support_text(
        "\n".join(
            [
                "WolfLauncher launch output",
                f"Generated at: {timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat()}",
                "",
                f"Command: {command_text.strip()}",
                "",
                "Output:",
                output_text.strip(),
            ]
        ).strip()
    )


def launch_troubleshooting_report(
    selected_mode: str = "auto",
    installs=None,
    process_check=None,
    environ=None,
) -> LaunchTroubleshootingReport:
    detected = installs if installs is not None else detect_steam()
    selection = steam_selection_report(selected_mode, detected)
    install = select_steam_install(selected_mode, detected)
    process = process_check if process_check is not None else dayz_process_check()
    capabilities = current_platform().capabilities
    status = "OK"
    if selection.status == "MISSING":
        status = "MISSING"
    elif selection.status == "WARN":
        status = "WARN"

    details = [
        f"Selected Steam mode: {steam_mode_label(selected_mode)}",
        f"Selected install: {selection.selected_label}",
        f"Steam readiness: {selection.status} - {selection.detail}",
        f"Steam candidates: {steam_selection_candidates_detail(selection)}",
        f"Steam command: {steam_command_detail(install)}",
        f"Steam running: {yes_no(bool(install and install.running))}",
        f"Steam root: {(install.root if install and install.root else 'not detected')}",
        f"Steam library: {(install.steamapps if install and install.steamapps else 'not detected')}",
        f"DayZ install: {(install.dayz_dir if install and install.dayz_dir else 'not detected')}",
        f"Workshop folder: {(install.workshop_dir if install and install.workshop_dir else 'not detected')}",
        f"Known DayZ process visibility: {process.detail}",
    ]
    if capabilities.uses_proton:
        details.extend(
            [
                f"Proton compatdata: {proton_compatdata_detail(install)}",
            ]
        )

    next_steps: list[str] = []
    if selection.status == "MISSING":
        next_steps.append(
            "Open Settings health and choose a Steam install mode that detects Steam or STEAM_ROOT."
        )
    elif selection.status == "WARN":
        next_steps.append(
            "Fix the selected Steam install warning before launch, especially missing DayZ or Workshop paths."
        )
    if install and install.dayz_dir and install.workshop_dir and not process.running:
        next_steps.append(
            "If this was captured after a successful handoff, allow Steam time to start DayZ, then check Steam downloads and BattlEye prompts."
        )
    if (
        capabilities.uses_proton
        and install
        and install.dayz_dir
        and install.workshop_dir
        and not install.compatdata_dir
    ):
        next_steps.append(
            "If DayZ has not been launched through this Steam install yet, start it once directly from Steam so Proton can create compatdata and show first-run prompts."
        )
    if not next_steps:
        next_steps.append(
            "If DayZ still does not start, test it directly from the selected Steam installation with the same Workshop content."
        )

    return LaunchTroubleshootingReport(
        status=status,
        summary="; ".join(part for part in (selection.detail, process.detail) if part),
        details=details,
        next_steps=next_steps,
    )


def run_diagnostics(
    launcher_path: str,
    servers: list[Server],
    selected_steam_mode: str = "auto",
    launch_engine: str = "",
    generated_at: datetime | None = None,
) -> str:
    lines: list[str] = []
    lines.append("WolfLauncher diagnostics")
    lines.append("========================")
    lines.append("")
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    lines.append(
        f"Generated at: {timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat()}"
    )
    if launch_engine:
        lines.append(f"Launch engine: {launch_engine_label(launch_engine)}")
    lines.append("")

    capabilities = current_platform().capabilities
    if capabilities.supports_external_launcher:
        path = Path(launcher_path).expanduser()
        lines.append(f"Launcher script: {path}")
        lines.append(f"  Exists: {ok_missing(path.exists())}")
        lines.append(f"  File: {ok_missing(path.exists() and path.is_file())}")
        lines.append("")

    lines.append("Required tools:")
    for command in capabilities.diagnostic_tools:
        found = shutil.which(command)
        lines.append(f"  {command}: {found or 'not found'}")
    lines.append("")

    lines.append("Steam / DayZ detection:")
    installs = detect_steam()
    selection = steam_selection_report("auto", installs)
    selected_selection = steam_selection_report(selected_steam_mode, installs)
    lines.append(f"  Auto selection: {selection.status} - {selection.detail}")
    lines.append(f"  Auto candidates: {steam_selection_candidates_detail(selection)}")
    lines.append(f"  Selected Steam mode: {steam_mode_label(selected_steam_mode)}")
    lines.append(
        f"  Selected Steam install: {selected_selection.status} - {selected_selection.detail}"
    )
    for install in installs:
        has_install = bool(install.executable or install.root or install.steamapps)
        label = install_label(install)
        if not has_install:
            lines.append(f"  {label}: Not configured")
            continue
        status, detail = install_readiness(install)
        lines.append(f"  {label}")
        lines.append(f"    readiness: {status} - {detail}")
        lines.append(f"    executable: {install.executable or 'not found'}")
        lines.append(f"    launch command: {steam_command_detail(install)}")
        lines.append(f"    running: {yes_no(install.running)}")
        lines.append(f"    root: {install.root or 'not found'}")
        lines.append(f"    steamapps: {install.steamapps or 'not found'}")
        if capabilities.uses_proton:
            lines.append(f"    compatdata: {proton_compatdata_detail(install)}")
        if install.library_steamapps:
            lines.append("    libraries:")
            for library in install.library_steamapps:
                lines.append(f"      {library}")
        lines.append(f"    DayZ: {ok_missing(bool(install.dayz_dir))} {install.dayz_dir or ''}")
        lines.append(
            f"    Workshop: {ok_missing(bool(install.workshop_dir))} {install.workshop_dir or ''}"
        )
    lines.append("")

    process_check = dayz_process_check()
    lines.append("DayZ process check:")
    lines.append(f"  {process_check.detail}")
    lines.append("")

    launch_report = launch_troubleshooting_report(
        selected_steam_mode, installs, process_check
    )
    lines.append("Launch troubleshooting:")
    lines.append(f"  Status: {launch_report.status}")
    lines.append(f"  Summary: {launch_report.summary}")
    for detail in launch_report.details:
        lines.append(f"  Detail: {detail}")
    for step in launch_report.next_steps:
        lines.append(f"  Next step: {step}")
    lines.append("")

    if capabilities.supports_external_launcher:
        lines.append("Default launcher path candidates:")
        for candidate in DEFAULT_LAUNCHER_PATHS:
            lines.append(f"  {candidate}: {ok_missing(candidate.exists())}")
        lines.append("")

    lines.append("Server DNS checks:")
    for server in servers:
        try:
            ip = resolve_host(server.host)
            lines.append(f"  {server.name}: {server.host} -> {ip}")
        except OSError as exc:
            lines.append(f"  {server.name}: {server.host} -> DNS failed: {exc}")

    return redact_support_text("\n".join(lines))


def launch_engine_label(value: str) -> str:
    labels = {
        "external": "External launcher",
        "native": "Native launcher",
    }
    return labels.get(value, value)
