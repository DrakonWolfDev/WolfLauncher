"""Presentation grouping for the Settings health overview."""

from dataclasses import dataclass

from .settings_health import HealthRow


@dataclass(frozen=True)
class HealthGroup:
    key: str
    title: str
    status: str
    rows: tuple[HealthRow, ...]


GROUP_SPECS = (
    (
        "steam",
        "Steam and DayZ",
        ("Selected Steam", "DayZ Stable", "DayZ Experimental", "Workshop"),
    ),
    (
        "launcher",
        "Launcher readiness",
        ("Server API",),
    ),
    (
        "graphics",
        "Linux graphics and compatibility",
        ("Proton compatdata",),
    ),
)


def aggregate_health_status(rows: tuple[HealthRow, ...]) -> str:
    statuses = {status.upper() for _name, status, _detail in rows}
    if statuses & {"MISSING", "ERROR", "FAILED"}:
        return "MISSING"
    if "WARN" in statuses:
        return "WARN"
    return "OK"


def settings_health_groups(rows: tuple[HealthRow, ...]) -> tuple[HealthGroup, ...]:
    by_name = {name: (name, status, detail) for name, status, detail in rows}
    groups = []
    for key, title, names in GROUP_SPECS:
        group_rows = tuple(by_name[name] for name in names if name in by_name)
        groups.append(HealthGroup(key, title, aggregate_health_status(group_rows), group_rows))
    return tuple(groups)
