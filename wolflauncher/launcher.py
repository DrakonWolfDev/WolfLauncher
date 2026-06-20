import subprocess
from pathlib import Path

from .models import Server
from .status import resolve_host


class LaunchError(RuntimeError):
    pass


def build_launch_command(launcher_path: str, player_name: str, server: Server) -> list[str]:
    """Build the external dayz-launcher.sh command for a selected server.

    The upstream dayz-linux-cli-launcher API lookup is more reliable when given
    a resolved IP address instead of a DNS hostname. The old terminal menu did
    this resolution before calling the script, so WolfLauncher mirrors that
    behaviour here.
    """
    path = Path(launcher_path).expanduser()
    if not path.exists():
        raise LaunchError(f"Launcher script not found: {path}")
    if not path.is_file():
        raise LaunchError(f"Launcher path is not a file: {path}")

    try:
        launch_host = resolve_host(server.host)
    except OSError as exc:
        raise LaunchError(f"Could not resolve server host {server.host}: {exc}") from exc

    safe_name = player_name.strip() or "Survivor"
    return [
        "bash",
        str(path),
        "-s",
        f"{launch_host}:{server.game_port}",
        "-p",
        str(server.query_port),
        "-n",
        safe_name,
        "--launch",
    ]


def launch_dayz(launcher_path: str, player_name: str, server: Server) -> subprocess.Popen:
    command = build_launch_command(launcher_path, player_name, server)
    return subprocess.Popen(command)
