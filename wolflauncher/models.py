from dataclasses import dataclass


@dataclass
class Server:
    name: str
    group: str
    host: str
    game_port: int
    query_port: int
    favourite: bool = False

    @property
    def connect_target(self) -> str:
        return f"{self.host}:{self.game_port}"


@dataclass
class DiscoveredServer:
    name: str
    host: str
    game_port: int
    query_port: int
    source: str = "discovered"
    server_name: str = ""
    map_name: str = ""
    players_current: int | None = None
    players_max: int | None = None
    ping_ms: int | None = None
    version: str = ""
    password: bool = False
    modded: bool = False
    online: bool = False
    last_checked: str = ""
    last_seen: str = ""
    stable_server_id: str = ""
    endpoint_aliases: tuple[str, ...] = ()
    freshness: str = ""
    freshness_expires_at: str = ""
    validation_status: str = ""
    validation_checked_at: str = ""
    validation_seen_at: str = ""
    validation_error_code: str = ""
    provider_last_checked: str = ""
    provider_last_seen: str = ""

    @property
    def cache_key(self) -> str:
        return f"{self.host}:{self.game_port}:{self.query_port}"

    @property
    def connect_target(self) -> str:
        return f"{self.host}:{self.game_port}"
