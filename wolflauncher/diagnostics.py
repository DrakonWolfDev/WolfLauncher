import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_LAUNCHER_PATHS
from .models import Server
from .platform_detection import (
    dayz_process_check,
    detect_steam,
    install_label,
    install_readiness,
    ok_missing,
    steam_selection_candidates_detail,
    steam_selection_report,
    yes_no,
)
from .status import resolve_host


PRIME_ENV_VARS = (
    "__NV_PRIME_RENDER_OFFLOAD",
    "__GLX_VENDOR_LIBRARY_NAME",
    "DRI_PRIME",
)


@dataclass(frozen=True)
class PrimeEnvironmentReport:
    status: str
    summary: str
    details: list[str]


def prime_environment_report(environ=None) -> PrimeEnvironmentReport:
    env = environ if environ is not None else os.environ
    offload = env.get("__NV_PRIME_RENDER_OFFLOAD")
    glx_vendor = env.get("__GLX_VENDOR_LIBRARY_NAME")
    dri_prime = env.get("DRI_PRIME")

    if offload == "1" and glx_vendor == "nvidia":
        return PrimeEnvironmentReport(
            status="WARN",
            summary="Known problematic NVIDIA PRIME offload variables are visible to WolfLauncher.",
            details=[
                "This matches the known bad Steam launch-option pattern for DayZ.",
                "WolfLauncher cannot confirm whether Steam applies the same per-game launch option.",
                "Test DayZ directly from Steam with no per-game launch options before testing WolfLauncher handoff.",
                "For hybrid-GPU checks, test PRIME outside WolfLauncher first, for example prime-run glxinfo -B and prime-run steam.",
            ],
        )

    if offload or glx_vendor or dri_prime:
        return PrimeEnvironmentReport(
            status="OK",
            summary="PRIME-related variables are present, but not the known bad NVIDIA launch-option pair.",
            details=[
                "WolfLauncher reports only the environment it can see.",
                "Per-game Steam launch options still need to be checked in Steam if DayZ does not start.",
            ],
        )

    return PrimeEnvironmentReport(
        status="OK",
        summary="No PRIME-related variables are visible to WolfLauncher; Steam launch options may still set them.",
        details=[
            "This does not prove Steam has no per-game launch options.",
            "Check Steam's DayZ launch options directly if Proton or DayZ does not start after handoff.",
        ],
    )


def run_diagnostics(launcher_path: str, servers: list[Server]) -> str:
    lines: list[str] = []
    lines.append("WolfLauncher diagnostics")
    lines.append("========================")
    lines.append("")

    path = Path(launcher_path).expanduser()
    lines.append(f"Launcher script: {path}")
    lines.append(f"  Exists: {ok_missing(path.exists())}")
    lines.append(f"  File: {ok_missing(path.exists() and path.is_file())}")
    lines.append("")

    lines.append("Required tools:")
    for command in ["python3", "gamedig", "node", "npm", "dig", "curl", "jq", "gawk"]:
        found = shutil.which(command)
        lines.append(f"  {command}: {found or 'not found'}")
    lines.append("")

    lines.append("Steam / DayZ detection:")
    installs = detect_steam()
    selection = steam_selection_report("auto", installs)
    lines.append(f"  Auto selection: {selection.status} - {selection.detail}")
    lines.append(f"  Auto candidates: {steam_selection_candidates_detail(selection)}")
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
        lines.append(f"    running: {yes_no(install.running)}")
        lines.append(f"    root: {install.root or 'not found'}")
        lines.append(f"    steamapps: {install.steamapps or 'not found'}")
        if install.library_steamapps:
            lines.append("    libraries:")
            for library in install.library_steamapps:
                lines.append(f"      {library}")
        lines.append(f"    DayZ: {ok_missing(bool(install.dayz_dir))} {install.dayz_dir or ''}")
        lines.append(f"    Workshop: {ok_missing(bool(install.workshop_dir))} {install.workshop_dir or ''}")
    lines.append("")

    lines.append("Launch option environment:")
    for name in PRIME_ENV_VARS:
        lines.append(f"  {name}: {os.environ.get(name) or 'not set'}")
    prime = prime_environment_report()
    lines.append(f"  PRIME status: {prime.status} - {prime.summary}")
    for detail in prime.details:
        lines.append(f"  PRIME guidance: {detail}")
    lines.append("  Steam launch options: not readable by WolfLauncher")
    lines.append("")

    process_check = dayz_process_check()
    lines.append("DayZ process check:")
    lines.append(f"  {process_check.detail}")
    lines.append("")

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

    return "\n".join(lines)
