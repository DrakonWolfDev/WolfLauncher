import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Server
from .status import resolve_host

DAYZSA_QUERY_URL = "https://dayzsalauncher.com/api/v1/query/{address}/{port}"
WORKSHOP_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id={mod_id}"


@dataclass
class RequiredMod:
    workshop_id: str
    name: str = ""
    installed: bool = False
    installed_name: str = ""
    workshop_url: str = ""


@dataclass
class ModCheckResult:
    ok: bool
    server: Server
    required_mods: list[RequiredMod]
    installed_count: int = 0
    error: str = ""

    @property
    def missing_mods(self) -> list[RequiredMod]:
        return [mod for mod in self.required_mods if not mod.installed]


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


def _mod_name_from_api(mod: dict[str, Any]) -> str:
    for key in ("name", "title", "modName", "workshopTitle"):
        value = mod.get(key)
        if value:
            return str(value)
    return ""


def fetch_required_mods(server: Server) -> list[RequiredMod]:
    """Query DZSA-style API for a server's required Steam Workshop mods."""
    address = resolve_host(server.host)
    url = DAYZSA_QUERY_URL.format(address=address, port=server.query_port)
    request = urllib.request.Request(url, headers={"User-Agent": "WolfLauncher/0.4"})

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"mod API HTTP error: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"mod API connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("mod API timed out") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError("mod API returned invalid JSON") from exc

    result = data.get("result", {}) if isinstance(data, dict) else {}
    mods = result.get("mods", []) if isinstance(result, dict) else []
    if mods is None:
        mods = []
    if not isinstance(mods, list):
        raise RuntimeError("mod API response did not contain a mods list")

    required: list[RequiredMod] = []
    seen: set[str] = set()
    for mod in mods:
        if not isinstance(mod, dict):
            continue
        workshop_id = mod.get("steamWorkshopId") or mod.get("workshopId") or mod.get("id")
        if workshop_id is None:
            continue
        workshop_id = str(workshop_id).strip()
        if not workshop_id or workshop_id in seen:
            continue
        seen.add(workshop_id)
        required.append(
            RequiredMod(
                workshop_id=workshop_id,
                name=_mod_name_from_api(mod),
                workshop_url=WORKSHOP_URL.format(mod_id=workshop_id),
            )
        )
    return required


def check_server_mods(server: Server, workshop_dir: Path | None) -> ModCheckResult:
    installed = scan_installed_mods(workshop_dir)
    try:
        required = fetch_required_mods(server)
    except Exception as exc:
        return ModCheckResult(False, server, [], installed_count=len(installed), error=str(exc))

    for mod in required:
        mod.installed = mod.workshop_id in installed
        mod.installed_name = installed.get(mod.workshop_id, "")
        if not mod.name:
            mod.name = mod.installed_name
    return ModCheckResult(True, server, required, installed_count=len(installed))
