import json
import os
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Server


@dataclass
class ServerStatus:
    online: bool
    resolved_ip: str = ""
    server_name: str = ""
    map_name: str = ""
    players: str = ""
    time: str = ""
    day_acceleration: float | None = None
    night_acceleration: float | None = None
    version: str = ""
    ping: str = ""
    password: bool = False
    modded: bool = False
    connect: str = ""
    error: str = ""


def resolve_host(host: str) -> str:
    try:
        socket.inet_aton(host)
        return host
    except OSError:
        return socket.gethostbyname(host)


def _get(data: dict[str, Any], *path: str, default: Any = "") -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def gamedig_command() -> list[str] | None:
    bundled_script = os.environ.get("WOLFLAUNCHER_GAMEDIG_SCRIPT", "").strip()
    if bundled_script and Path(bundled_script).is_file():
        node = shutil.which("node")
        if node:
            return [node, bundled_script]
    gamedig = shutil.which("gamedig")
    return [gamedig] if gamedig else None


def _hidden_process_kwargs() -> dict[str, int]:
    if os.name != "nt":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def check_server(
    server: Server,
    *,
    socket_timeout_ms: int = 1500,
    process_timeout: float = 5,
    cancel_event=None,
) -> ServerStatus:
    try:
        ip = resolve_host(server.host)
    except OSError as exc:
        return ServerStatus(False, error=f"DNS failed: {exc}")

    command = gamedig_command()
    if command is None:
        return ServerStatus(False, resolved_ip=ip, error="gamedig not installed")

    arguments = [
        *command,
        "--type",
        "dayz",
        f"{ip}:{server.query_port}",
        "--maxAttempts",
        "1",
        "--socketTimeout",
        str(socket_timeout_ms),
    ]
    try:
        if cancel_event is None:
            result = subprocess.run(
                arguments,
                check=False,
                capture_output=True,
                text=True,
                timeout=process_timeout,
                **_hidden_process_kwargs(),
            )
        else:
            result = _run_cancellable(arguments, process_timeout, cancel_event)
            if result is None:
                return ServerStatus(False, resolved_ip=ip, error="status check cancelled")
    except subprocess.TimeoutExpired:
        return ServerStatus(False, resolved_ip=ip, error="status check timed out")

    if result.returncode != 0:
        details = result.stderr.strip() or "offline or no response"
        return ServerStatus(False, resolved_ip=ip, error=details)

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ServerStatus(False, resolved_ip=ip, error="invalid gamedig response")

    # Some restart/offline states can produce a partial response. Treat those
    # as unavailable instead of showing ONLINE with Unknown / 0/? fields.
    if not data.get("name") or data.get("maxplayers") is None:
        return ServerStatus(
            False, resolved_ip=ip, error="offline, restarting, or incomplete query response"
        )

    raw = data.get("raw", {}) if isinstance(data.get("raw"), dict) else {}
    tags = raw.get("tags", []) if isinstance(raw.get("tags"), list) else []

    num_players = data.get("numplayers", 0)
    max_players = data.get("maxplayers", "?")
    map_name = data.get("map") or raw.get("map") or "Unknown"
    server_time = raw.get("time") or data.get("time") or "N/A"
    day_acceleration = _optional_float(raw.get("dayAcceleration"))
    night_acceleration = _optional_float(raw.get("nightAcceleration"))
    version = data.get("version") or raw.get("version") or ""
    ping = data.get("ping", "")
    connect = data.get("connect") or f"{ip}:{server.game_port}"
    modded = "mod" in tags

    return ServerStatus(
        online=True,
        resolved_ip=ip,
        server_name=str(data.get("name", "")),
        map_name=str(map_name),
        players=f"{num_players}/{max_players}",
        time=str(server_time),
        day_acceleration=day_acceleration,
        night_acceleration=night_acceleration,
        version=str(version),
        ping=str(ping) if ping != "" else "",
        password=bool(data.get("password", False)),
        modded=modded,
        connect=str(connect),
    )


def _run_cancellable(arguments: list[str], timeout: float, cancel_event):
    process = subprocess.Popen(
        arguments,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **_hidden_process_kwargs(),
    )
    deadline = time.monotonic() + timeout
    while process.poll() is None:
        if cancel_event.is_set():
            process.terminate()
            try:
                process.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return None
        if time.monotonic() >= deadline:
            process.kill()
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(arguments, timeout, stdout, stderr)
        time.sleep(0.025)
    stdout, stderr = process.communicate()
    return subprocess.CompletedProcess(arguments, process.returncode, stdout, stderr)


def _optional_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
