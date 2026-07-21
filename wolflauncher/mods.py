import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dayz_mod_query import query_dayz_required_mods
from .models import Server
from .redaction import redact_support_text
from .status import resolve_host

WORKSHOP_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"
WORKSHOP_DETAILS_URL = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)


@dataclass
class RequiredMod:
    workshop_id: str
    name: str = ""
    installed: bool = False
    installed_name: str = ""
    workshop_url: str = ""
    workshop_state: int | None = None
    workshop_downloaded: int = 0
    workshop_total: int = 0
    workshop_file_size: int = 0
    workshop_description: str = ""
    workshop_preview_url: str = ""

    @property
    def ready(self) -> bool:
        if not self.installed:
            return False
        if self.workshop_state is None:
            return True
        from .workshop_subscription import (
            ITEM_STATE_DOWNLOAD_PENDING,
            ITEM_STATE_DOWNLOADING,
            ITEM_STATE_NEEDS_UPDATE,
        )

        blocked = ITEM_STATE_NEEDS_UPDATE | ITEM_STATE_DOWNLOADING | ITEM_STATE_DOWNLOAD_PENDING
        return not bool(self.workshop_state & blocked)


@dataclass
class ModCheckResult:
    ok: bool
    server: Server
    required_mods: list[RequiredMod]
    installed_count: int = 0
    error: str = ""
    steam_context: str = ""
    workshop_dir: str = ""
    workshop_state_error: str = ""

    @property
    def missing_mods(self) -> list[RequiredMod]:
        return [mod for mod in self.required_mods if not mod.ready]

    @property
    def absent_mods(self) -> list[RequiredMod]:
        return [mod for mod in self.required_mods if not mod.installed]

    @property
    def update_mods(self) -> list[RequiredMod]:
        return [mod for mod in self.required_mods if mod.installed and not mod.ready]


def apply_workshop_item_states(result: ModCheckResult, states) -> ModCheckResult:
    """Attach Steam item-state snapshots to an existing local-directory check."""
    by_id = {item.workshop_id: item for item in states}
    for mod in result.required_mods:
        item = by_id.get(mod.workshop_id)
        if item is None:
            continue
        mod.workshop_state = item.state
        mod.workshop_downloaded = item.downloaded
        mod.workshop_total = item.total
    return result


def fetch_workshop_file_sizes(workshop_ids) -> dict[str, int]:
    """Fetch published Workshop file sizes from Steam's public batch endpoint."""
    ids = tuple(dict.fromkeys(str(item).strip() for item in workshop_ids if str(item).strip()))
    if not ids:
        return {}
    fields = [("itemcount", str(len(ids)))]
    fields.extend((f"publishedfileids[{index}]", item) for index, item in enumerate(ids))
    request = urllib.request.Request(
        WORKSHOP_DETAILS_URL,
        data=urllib.parse.urlencode(fields).encode("ascii"),
        headers={"User-Agent": "WolfLauncher/0.8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError, urllib.error.URLError):
        return {}
    details = payload.get("response", {}).get("publishedfiledetails", [])
    sizes = {}
    for detail in details if isinstance(details, list) else []:
        try:
            workshop_id = str(detail["publishedfileid"])
            size = int(detail.get("file_size") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if workshop_id in ids and size > 0:
            sizes[workshop_id] = size
    return sizes


def fetch_workshop_metadata(workshop_ids) -> dict[str, dict[str, Any]]:
    """Fetch public display metadata for Workshop items in one bounded batch."""
    ids = tuple(dict.fromkeys(str(item).strip() for item in workshop_ids if str(item).strip()))
    if not ids:
        return {}
    fields = [("itemcount", str(len(ids)))]
    fields.extend((f"publishedfileids[{index}]", item) for index, item in enumerate(ids))
    request = urllib.request.Request(
        WORKSHOP_DETAILS_URL,
        data=urllib.parse.urlencode(fields).encode("ascii"),
        headers={"User-Agent": "WolfLauncher/0.8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError, urllib.error.URLError):
        return {}
    details = payload.get("response", {}).get("publishedfiledetails", [])
    metadata = {}
    for detail in details if isinstance(details, list) else []:
        try:
            workshop_id = str(detail["publishedfileid"])
        except (KeyError, TypeError, ValueError):
            continue
        if workshop_id not in ids or int(detail.get("result") or 0) != 1:
            continue
        metadata[workshop_id] = {
            "file_size": max(0, int(detail.get("file_size") or 0)),
            "description": str(detail.get("description") or "").strip(),
            "preview_url": str(detail.get("preview_url") or "").strip(),
        }
    return metadata


def apply_workshop_file_sizes(result: ModCheckResult, sizes: dict[str, int]) -> ModCheckResult:
    for mod in result.required_mods:
        mod.workshop_file_size = max(0, int(sizes.get(mod.workshop_id, 0)))
    return result


def apply_workshop_metadata(
    result: ModCheckResult, metadata: dict[str, dict[str, Any]]
) -> ModCheckResult:
    for mod in result.required_mods:
        detail = metadata.get(mod.workshop_id, {})
        mod.workshop_file_size = max(0, int(detail.get("file_size") or 0))
        mod.workshop_description = str(detail.get("description") or "").strip()
        mod.workshop_preview_url = str(detail.get("preview_url") or "").strip()
    return result


_NAME_RE = re.compile(r'name\s*=\s*"([^"]+)"')


def _read_mod_name(meta_path: Path) -> str:
    try:
        text = meta_path.read_text(errors="ignore")
    except OSError:
        return ""
    match = _NAME_RE.search(text)
    return match.group(1).strip() if match else ""


def scan_installed_mods(workshop_dir: Path | None) -> dict[str, str]:
    """Return installed DayZ Workshop mods as {workshop_id: display_name}."""
    if not workshop_dir or not workshop_dir.exists():
        return {}

    mods: dict[str, str] = {}
    for child in workshop_dir.iterdir():
        if not child.is_dir() or not child.name.isdigit():
            continue
        mod_name = _read_mod_name(child / "meta.cpp") or child.name
        mods[child.name] = mod_name
    return mods


def fetch_required_mods(server: Server) -> list[RequiredMod]:
    """Query the game server directly for its required Steam Workshop mods."""
    address = resolve_host(server.host)
    return [
        RequiredMod(
            workshop_id=str(mod.workshop_id),
            name=mod.name,
            workshop_url=WORKSHOP_URL.format(mod_id=mod.workshop_id),
        )
        for mod in query_dayz_required_mods(address, server.query_port)
    ]


def check_server_mods(
    server: Server,
    workshop_dir: Path | None,
    steam_context: str = "",
) -> ModCheckResult:
    installed = scan_installed_mods(workshop_dir)
    workshop_dir_text = str(workshop_dir) if workshop_dir else ""
    try:
        required = fetch_required_mods(server)
    except Exception as exc:
        return ModCheckResult(
            False,
            server,
            [],
            installed_count=len(installed),
            error=str(exc),
            steam_context=steam_context,
            workshop_dir=workshop_dir_text,
        )

    for mod in required:
        mod.installed = mod.workshop_id in installed
        mod.installed_name = installed.get(mod.workshop_id, "")
        if not mod.name:
            mod.name = mod.installed_name
    return ModCheckResult(
        True,
        server,
        required,
        installed_count=len(installed),
        steam_context=steam_context,
        workshop_dir=workshop_dir_text,
    )


def format_mod_check_report(
    result: ModCheckResult,
    generated_at: datetime | None = None,
) -> str:
    """Return a copyable required-mod report for parity testing and support."""
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    lines = [
        "WolfLauncher mod check report",
        f"Generated at: {timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat()}",
        "",
        f"Server: {result.server.name}",
        f"Group: {result.server.group}",
        f"Connect target: {result.server.connect_target}",
        f"Query port: {result.server.query_port}",
        f"Result: {'OK' if result.ok else 'ERROR'}",
        f"Local Workshop mods found: {result.installed_count}",
    ]
    if result.steam_context:
        lines.append(f"Steam install context: {result.steam_context}")
    if result.workshop_dir:
        lines.append(f"Workshop path checked: {result.workshop_dir}")

    if not result.ok:
        lines.extend(["", f"Error: {result.error or 'mod check failed'}"])
        return redact_support_text("\n".join(lines).strip())

    required = result.required_mods
    missing = result.missing_mods
    installed = [mod for mod in required if mod.installed]
    lines.extend(
        [
            f"Required mod count: {len(required)}",
            f"Installed required mods: {len(installed)}",
            f"Missing required mods: {len(missing)}",
            "",
        ]
    )

    if required:
        lines.append("Required Workshop mods:")
        for mod in required:
            state = "installed" if mod.installed else "missing"
            lines.append(f"- {_mod_report_label(mod)} [{state}]")
            if mod.installed_name and mod.installed_name != mod.name:
                lines.append(f"  local name: {mod.installed_name}")
            if mod.workshop_url:
                lines.append(f"  url: {mod.workshop_url}")
    else:
        lines.append("Required Workshop mods: none reported by the game server")

    if missing:
        lines.extend(["", "Missing Workshop IDs:"])
        lines.extend(f"- {mod.workshop_id}" for mod in missing)
    return redact_support_text("\n".join(lines).strip())


def format_missing_workshop_links(result: ModCheckResult) -> str:
    """Return copyable missing Workshop links for a completed mod check."""
    if not result.ok:
        return ""
    lines = []
    for mod in result.missing_mods:
        label = _mod_report_label(mod)
        url = mod.workshop_url or WORKSHOP_URL.format(mod_id=mod.workshop_id)
        lines.append(f"{label}: {url}")
    return "\n".join(lines)


def _mod_report_label(mod: RequiredMod) -> str:
    name = (mod.name or mod.installed_name).strip()
    return f"{name} ({mod.workshop_id})" if name else mod.workshop_id
