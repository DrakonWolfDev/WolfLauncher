from pathlib import Path
import yaml

from .models import Server


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENDORED_LAUNCHER_PATH = PROJECT_ROOT / "external/dayz-linux-cli-launcher/dayz-launcher.sh"

DEFAULT_LAUNCHER_PATHS = [
    Path.home() / ".local/bin/dayz-launcher.sh",
    Path("/opt/wolflauncher/dayz-launcher.sh"),
    Path.home() / "dayz-launcher.sh",
    VENDORED_LAUNCHER_PATH,
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


def add_curated_server(path: Path, server: Server) -> None:
    data = _load_server_yaml(path)
    servers = data.setdefault("servers", [])
    if not isinstance(servers, list):
        raise ValueError("servers.yaml must contain a 'servers' list.")

    for item in servers:
        if not isinstance(item, dict):
            continue
        if (
            str(item.get("host")) == server.host
            and int(item.get("game_port", 0)) == server.game_port
            and int(item.get("query_port", 0)) == server.query_port
        ):
            raise ValueError("This server is already in the curated server list.")

    servers.append(
        {
            "name": server.name,
            "group": server.group,
            "host": server.host,
            "game_port": server.game_port,
            "query_port": server.query_port,
            "favourite": server.favourite,
        }
    )
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def remove_curated_server(path: Path, server: Server) -> bool:
    data = _load_server_yaml(path)
    servers = data.setdefault("servers", [])
    if not isinstance(servers, list):
        raise ValueError("servers.yaml must contain a 'servers' list.")

    for index, item in enumerate(servers):
        if not isinstance(item, dict):
            continue
        if (
            str(item.get("host")) == server.host
            and int(item.get("game_port", 0)) == server.game_port
            and int(item.get("query_port", 0)) == server.query_port
        ):
            del servers[index]
            with path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump(data, handle, sort_keys=False)
            return True

    return False


def update_curated_server(path: Path, original: Server, updated: Server) -> bool:
    data = _load_server_yaml(path)
    servers = data.setdefault("servers", [])
    if not isinstance(servers, list):
        raise ValueError("servers.yaml must contain a 'servers' list.")

    match_index = None
    for index, item in enumerate(servers):
        if not isinstance(item, dict):
            continue
        if _same_server_entry(item, original):
            match_index = index
            break

    if match_index is None:
        return False

    for index, item in enumerate(servers):
        if index == match_index or not isinstance(item, dict):
            continue
        if _same_server_entry(item, updated):
            raise ValueError("Another curated server already uses that host and port combination.")

    servers[match_index] = {
        "name": updated.name,
        "group": updated.group,
        "host": updated.host,
        "game_port": updated.game_port,
        "query_port": updated.query_port,
        "favourite": updated.favourite,
    }
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    return True


def _same_server_entry(item: dict, server: Server) -> bool:
    return (
        str(item.get("host")) == server.host
        and int(item.get("game_port", 0)) == server.game_port
        and int(item.get("query_port", 0)) == server.query_port
    )


def _load_server_yaml(path: Path) -> dict:
    if not path.exists():
        return {"servers": []}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("servers.yaml must contain a mapping.")
    return data
