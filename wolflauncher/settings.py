import json
from pathlib import Path
from typing import Any

from .paths import user_config_dir
from .persistence import atomic_write_text, ensure_private_directory

APP_DIR = user_config_dir()
SETTINGS_PATH = APP_DIR / "settings.json"
FAVOURITES_PATH = APP_DIR / "favourites.json"
CURATED_SERVERS_PATH = APP_DIR / "servers.yaml"
DEFAULT_DISCOVERY_PROVIDER = "wolfapi_v1"


def ensure_app_dir() -> None:
    ensure_private_directory(APP_DIR)


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    except (OSError, json.JSONDecodeError):
        pass
    return default


def save_json(path: Path, data: Any) -> None:
    serialized = json.dumps(data, indent=2) + "\n"
    # Validate the complete representation before replacing the live file.
    json.loads(serialized)
    atomic_write_text(path, serialized)


def load_settings() -> dict[str, Any]:
    data = load_json(SETTINGS_PATH, {})
    return data if isinstance(data, dict) else {}


def save_settings(data: dict[str, Any]) -> None:
    save_json(SETTINGS_PATH, data)


def server_key(server) -> str:
    return f"{server.host}:{server.game_port}:{server.query_port}:{server.name}"


def load_favourites() -> set[str]:
    data = load_json(FAVOURITES_PATH, [])
    if isinstance(data, list):
        return {str(item) for item in data}
    return set()


def save_favourites(keys: set[str]) -> None:
    save_json(FAVOURITES_PATH, sorted(keys))
