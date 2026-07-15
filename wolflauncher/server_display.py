"""Shared, presentation-only labels for server data."""


def display_map_name(map_name: str) -> str:
    value = map_name.strip()
    if not value:
        return ""
    if value.casefold() == "enoch":
        return "Livonia"
    return value[:1].upper() + value[1:]


def display_server_flags(
    password: bool,
    modded: bool,
    quality_warning: bool = False,
) -> str:
    flags = []
    if password:
        flags.append("Password")
    flags.append("Modded" if modded else "Vanilla")
    if quality_warning:
        flags.append("Quality warning")
    return ", ".join(flags)


def display_required_mod_count(count: int | None) -> str:
    return str(count) if count is not None and count > 0 else "–"
