import shutil
from pathlib import Path

from .config import DEFAULT_LAUNCHER_PATHS
from .models import Server
from .platform_detection import detect_steam, ok_missing, yes_no
from .status import resolve_host


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
    for command in ["python3", "gamedig", "node", "npm", "dig"]:
        found = shutil.which(command)
        lines.append(f"  {command}: {found or 'not found'}")
    lines.append("")

    lines.append("Steam / DayZ detection:")
    for install in detect_steam():
        has_install = bool(install.executable or install.root or install.steamapps)
        label = install.mode.capitalize()
        if not has_install:
            lines.append(f"  {label}: Not configured")
            continue
        lines.append(f"  {label} Steam")
        lines.append(f"    executable: {install.executable or 'not found'}")
        lines.append(f"    running: {yes_no(install.running)}")
        lines.append(f"    root: {install.root or 'not found'}")
        lines.append(f"    steamapps: {install.steamapps or 'not found'}")
        lines.append(f"    DayZ: {ok_missing(bool(install.dayz_dir))} {install.dayz_dir or ''}")
        lines.append(f"    Workshop: {ok_missing(bool(install.workshop_dir))} {install.workshop_dir or ''}")
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
