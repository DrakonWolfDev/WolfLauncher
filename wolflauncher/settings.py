import json
from pathlib import Path
from typing import Any

APP_DIR = Path.home() / ".config" / "wolflauncher"
SETTINGS_PATH = APP_DIR / "settings.json"
FAVOURITES_PATH = APP_DIR / "favourites.json"
DEFAULT_DISCOVERY_PROVIDER = "wolfapi_v1"


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    except (OSError, json.JSONDecodeError):
        pass
    return default


def save_json(path: Path, data: Any) -> None:
    ensure_app_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    tmp.replace(path)


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
