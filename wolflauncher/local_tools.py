"""Pure local-development profile parsing and DayZ Editor defaults."""

from dataclasses import dataclass

DAYZ_EDITOR_MODS = (
    ("2250764298", "DayZ Editor"),
    ("1559212036", "CF"),
    ("2545327648", "Dabs Framework"),
)



@dataclass(frozen=True)
class LocalToolProfile:
    name: str
    mod_paths: tuple[str, ...] = ()
    endpoint: str = ""
    workshop_mod_ids: tuple[str, ...] = ()


def normalise_workshop_ids(value: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    parts = value.replace("\n", ",").split(",") if isinstance(value, str) else value
    seen: set[str] = set()
    result = []
    for item in parts:
        workshop_id = str(item).strip()
        if not workshop_id or not workshop_id.isdigit() or workshop_id in seen:
            continue
        seen.add(workshop_id)
        result.append(workshop_id)
    return tuple(result)


def parse_local_endpoint(value: str) -> tuple[str, int]:
    target = value.strip()
    host, separator, port_text = target.rpartition(":")
    if not separator or not host.strip() or not port_text.isdigit():
        raise ValueError("Enter the LAN server as host:game-port, for example 192.168.1.25:2302.")
    port = int(port_text)
    if not 1 <= port <= 65535:
        raise ValueError("The LAN server port must be between 1 and 65535.")
    return host.strip(), port


def profile_from_data(data: object) -> LocalToolProfile | None:
    if not isinstance(data, dict):
        return None
    name = str(data.get("name") or "").strip()
    if not name:
        return None
    return LocalToolProfile(
        name=name,
        mod_paths=tuple(
            str(item).strip() for item in data.get("mod_paths", []) if str(item).strip()
        ),
        endpoint=str(data.get("endpoint") or "").strip(),
        workshop_mod_ids=normalise_workshop_ids(data.get("workshop_mod_ids", [])),
    )


def profiles_from_settings(value: object) -> list[LocalToolProfile]:
    profiles = [profile_from_data(item) for item in value] if isinstance(value, list) else []
    return [profile for profile in profiles if profile is not None]
