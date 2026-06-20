from pathlib import Path
import yaml

from .models import Server


DEFAULT_LAUNCHER_PATHS = [
    Path.home() / ".local/bin/dayz-launcher.sh",
    Path("/opt/wolflauncher/dayz-launcher.sh"),
    Path.home() / "dayz-launcher.sh",
]


def find_default_launcher_path() -> str:
    for path in DEFAULT_LAUNCHER_PATHS:
        if path.exists():
            return str(path)
    return str(DEFAULT_LAUNCHER_PATHS[0])


def load_servers(path: Path) -> list[Server]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    servers = []
    for item in data.get("servers", []):
        servers.append(
            Server(
                name=str(item["name"]),
                group=str(item.get("group", "Community")),
                host=str(item["host"]),
                game_port=int(item["game_port"]),
                query_port=int(item["query_port"]),
                favourite=bool(item.get("favourite", False)),
            )
        )
    return servers
