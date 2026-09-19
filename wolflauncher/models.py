from dataclasses import dataclass

from .server_identity import identity_fields, identity_key


@dataclass
class Server:
    name: str
    group: str
    host: str
    game_port: int
    query_port: int
    favourite: bool = False
    stable_server_id: str = ""
    endpoint_aliases: tuple[str, ...] = ()
    product: str = "unknown"
    identity_state: str = ""
    identity_evidence: tuple[dict, ...] = ()

    def __post_init__(self):
        for key, value in identity_fields(self).items():
            setattr(self, key, value)

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
    required_mod_count: int | None = None
    mod_metadata_status: str = ""
    mod_metadata_checked_at: str = ""
    mod_metadata_expires_at: str = ""
    mod_metadata_error_code: str = ""
    mod_manifest_hash: str = ""
    status_source: str = "provider"
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
    quality_flags: tuple[str, ...] = ()
    country_code: str = ""
    country_source: str = ""
    game_time: str = ""
    day_acceleration: float | None = None
    night_acceleration: float | None = None
    product: str = "unknown"
    identity_state: str = ""
    identity_evidence: tuple[dict, ...] = ()

    def __post_init__(self):
        for key, value in identity_fields(self).items():
            setattr(self, key, value)

    @property
    def cache_key(self) -> str:
        return identity_key(self)

    @property
    def connect_target(self) -> str:
        return f"{self.host}:{self.game_port}"
