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
