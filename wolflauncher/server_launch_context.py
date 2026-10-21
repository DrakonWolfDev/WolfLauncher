"""Immutable, exact-request launch inputs resolved before Workshop preparation."""

import json
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from .dayz_product import EXPERIMENTAL, STABLE, DayZProduct
from .models import Server
from .platform_detection import SteamInstall, detect_steam, select_steam_install
from .product_availability import inspect_install, setup_message
from .server_identity import (
    LiveIdentity,
    endpoint_key,
    resolve_launch_identity,
    saved_server_fields,
)
from .status import check_server


class IdentityResolutionError(ValueError):
    def __init__(self, message: str, resolved_server: Server | None = None):
        super().__init__(message)
        self.resolved_server = resolved_server


@dataclass(frozen=True)
class InstallationSnapshot:
    mode: str
    executable: str
    running: bool
    root: Path | None
    steamapps: Path | None
    dayz_dir: Path | None
    workshop_dir: Path | None
    compatdata_dir: Path | None
    library_steamapps: tuple[Path, ...]
    product: DayZProduct

    @classmethod
    def capture(cls, install: SteamInstall):
        return cls(
            install.mode,
            install.executable,
            install.running,
            install.root,
            install.steamapps,
            install.dayz_dir,
            install.workshop_dir,
            install.compatdata_dir,
            tuple(install.library_steamapps),
            install.product,
        )

    def restore(self) -> SteamInstall:
        return SteamInstall(
            self.mode,
            self.executable,
            self.running,
            self.root,
            self.steamapps,
            self.dayz_dir,
            self.workshop_dir,
            self.compatdata_dir,
            list(self.library_steamapps),
            self.product,
        )


@dataclass(frozen=True)
class ServerLaunchContext:
    request_id: str
    original_endpoint: str
    server_json: str
    product: DayZProduct
    installation: InstallationSnapshot
    engine: str
    steam_mode: str
    live_identity: LiveIdentity

    @property
    def server(self) -> Server:
        return Server(**json.loads(self.server_json))

    @property
    def install(self) -> SteamInstall:
        return self.installation.restore()

    @property
    def mod_context_key(self) -> tuple:
        return (
            self.live_identity.endpoint,
            self.product.key,
            self.installation.mode,
            str(self.installation.root),
            str(self.installation.dayz_dir),
            str(self.installation.workshop_dir),
        )

    def matches(self, server: Server | None) -> bool:
        return server is not None and endpoint_key(server) in {
            self.original_endpoint,
            endpoint_key(self.server),
        }

    def fresh(self, now: float | None = None) -> bool:
        return (
            resolve_launch_identity(
                self.live_identity,
                endpoint=self.live_identity.endpoint,
                request_id=self.request_id,
                now=time.monotonic() if now is None else now,
            )
            == self.product.key
        )


def resolve_context(
    server: Server,
    request_id: str,
    steam_mode: str,
    stable_engine: str,
    cancel_event=None,
    *,
    checker=None,
    detector=None,
    resolver=None,
    monotonic=None,
) -> ServerLaunchContext:
    """Always require a supported live game ID; directory hints locate query ports only."""
    checker = checker or check_server
    detector = detector or detect_steam
    monotonic = monotonic or time.monotonic
    original = server
    candidates = [server]
    if server.product == "unknown":
        if resolver is None:
            from .server_discovery import resolve_dayz_server_wolfapi_v1

            resolver = resolve_dayz_server_wolfapi_v1
        try:
            rows = resolver(server.host, game_port=server.game_port, product="all", timeout=4)
            # Keep the user's target game endpoint. Directory aliases may supply
            # a corrected query port, but cannot redirect to another game port.
            for row in rows:
                if row.game_port == server.game_port:
                    candidate = replace(server, query_port=row.query_port)
                    if candidate.query_port not in {s.query_port for s in candidates}:
                        candidates.append(candidate)
        except (OSError, ValueError, RuntimeError) as exc:
            directory_error = str(exc)
        else:
            directory_error = ""
    else:
        directory_error = ""
    status = None
    for candidate in candidates[:3]:
        if cancel_event is not None and cancel_event.is_set():
            raise IdentityResolutionError("Server identity check cancelled.")
        status = checker(candidate, process_timeout=5, cancel_event=cancel_event)
        if not status.online or not status.resolved_ip:
            continue
        from .server_enrichment import parse_connect_port

        game_port = parse_connect_port(status.connect) or candidate.game_port
        endpoint = (status.resolved_ip, game_port, candidate.query_port)
        live = LiveIdentity(endpoint, request_id, monotonic(), status.app_id)
        product_key = resolve_launch_identity(
            live, endpoint=endpoint, request_id=request_id, now=monotonic()
        )
        if product_key == "unknown":
            continue
        product = EXPERIMENTAL if product_key == "experimental" else STABLE
        if cancel_event is not None and cancel_event.is_set():
            raise IdentityResolutionError("Server identity check cancelled.")
        historical = (
            *original.identity_evidence,
            {
                "product": product.key,
                "source": "live_gamedig",
                "verified": True,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "app_id": status.app_id,
                "endpoint": list(endpoint),
            },
        )
        resolved = replace(
            original,
            host=endpoint[0],
            game_port=endpoint[1],
            query_port=endpoint[2],
            product=product.key,
            identity_state="known",
            identity_evidence=historical,
        )
        install = select_steam_install(steam_mode, detector(product))
        availability = inspect_install(install, product)
        if not availability.detected:
            raise IdentityResolutionError(setup_message(product, availability.detail), resolved)
        if not install.workshop_dir:
            if not install.steamapps or not install.steamapps.is_dir():
                raise IdentityResolutionError(
                    f"{product.label}: could not locate the Steam library. "
                    "Check Settings health and rescan installations.",
                    resolved,
                )
            # Steam creates this folder only after the first Workshop download.
            # Scanning a nonexistent path correctly reports no installed mods.
            install = replace(
                install, workshop_dir=install.steamapps / "workshop" / "content" / "221100"
            )
        data = {
            "name": resolved.name,
            "group": resolved.group,
            "host": resolved.host,
            "game_port": resolved.game_port,
            "query_port": resolved.query_port,
            "favourite": resolved.favourite,
            **saved_server_fields(resolved),
        }
        return ServerLaunchContext(
            request_id,
            endpoint_key(original),
            json.dumps(data),
            product,
            InstallationSnapshot.capture(install),
            "native" if product.experimental else stable_engine,
            steam_mode,
            live,
        )
    detail = status.error if status and status.error else "No supported full game ID was returned."
    raise IdentityResolutionError(
        f"Could not verify this server's DayZ edition: {detail} "
        f"{directory_error} Retry when the server responds; no game was launched."
    )
