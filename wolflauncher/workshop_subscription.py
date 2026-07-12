"""Experimental Steam-native Workshop subscription support.

This module deliberately loads Valve's Steam API redistributable from an
existing Steam installation.  WolfLauncher does not vendor or modify it.
"""

from __future__ import annotations

import ctypes
import multiprocessing
import os
import queue
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .platform_detection import STEAM_APP_ID_DAYZ, SteamInstall


ITEM_STATE_SUBSCRIBED = 1
ITEM_STATE_INSTALLED = 4
ITEM_STATE_NEEDS_UPDATE = 8
ITEM_STATE_DOWNLOADING = 16
ITEM_STATE_DOWNLOAD_PENDING = 32
DOWNLOAD_REQUEST_RETRY_SECONDS = 15.0


def silence_helper_output() -> None:
    """Discard native SteamAPI console noise inside a disposable helper process."""
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except (AttributeError, OSError):
        pass
    null_fd = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(null_fd, 1)
        os.dup2(null_fd, 2)
    finally:
        if null_fd > 2:
            os.close(null_fd)


class WorkshopSubscriptionError(RuntimeError):
    """A recoverable Steamworks initialization or subscription failure."""


@dataclass(frozen=True)
class WorkshopItemProgress:
    workshop_id: str
    state: int
    downloaded: int = 0
    total: int = 0

    @property
    def installed(self) -> bool:
        return bool(self.state & ITEM_STATE_INSTALLED) and not bool(
            self.state & ITEM_STATE_NEEDS_UPDATE
        )

    @property
    def percent(self) -> int | None:
        if self.total <= 0:
            return None
        return min(100, int(self.downloaded * 100 / self.total))


def current_workshop_item(
    snapshots: Iterable[WorkshopItemProgress],
) -> WorkshopItemProgress | None:
    """Return the item Steam most clearly identifies as current work."""
    incomplete = [item for item in snapshots if not item.installed]
    downloading = [item for item in incomplete if item.state & ITEM_STATE_DOWNLOADING]
    if downloading:
        return max(downloading, key=lambda item: item.downloaded)
    measurable = [
        item for item in incomplete
        if item.percent is not None and 0 < item.downloaded < item.total
    ]
    if measurable:
        return max(measurable, key=lambda item: item.downloaded)
    return next(
        (item for item in incomplete if item.state & ITEM_STATE_DOWNLOAD_PENDING),
        None,
    )


@dataclass(frozen=True)
class WorkshopSubscriptionResult:
    installed_ids: tuple[str, ...]
    incomplete_ids: tuple[str, ...]
    cancelled: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.cancelled and not self.error and not self.incomplete_ids


@dataclass(frozen=True)
class WorkshopStateResult:
    items: tuple[WorkshopItemProgress, ...] = ()
    error: str = ""


@dataclass(frozen=True)
class WorkshopRecoveryState:
    """Filesystem evidence of DayZ Workshop items left in Steam's staging area."""

    item_ids: tuple[str, ...] = ()
    staging_dirs: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return bool(self.item_ids)


def workshop_recovery_state(
    install: SteamInstall | None,
    relevant_ids: Iterable[str] = (),
) -> WorkshopRecoveryState:
    """Find relevant numeric item folders in Steam's Workshop download staging area.

    This is deliberately a conservative restart/recovery signal. Steam's local
    Workshop manifest is a catalogue, not a dependable live queue, while item
    folders under ``workshop/downloads/221100`` are direct evidence of staged
    DayZ Workshop work. Missing or unreadable folders are treated as no signal.
    """
    if not install:
        return WorkshopRecoveryState()
    wanted = {
        str(item).strip() for item in relevant_ids if str(item).strip().isdigit()
    }
    if not wanted:
        return WorkshopRecoveryState()
    steamapps_candidates = list(install.library_steamapps)
    if install.steamapps and install.steamapps not in steamapps_candidates:
        steamapps_candidates.append(install.steamapps)

    found: set[str] = set()
    staging_dirs: list[str] = []
    for steamapps in steamapps_candidates:
        staging = steamapps / "workshop" / "downloads" / str(STEAM_APP_ID_DAYZ)
        try:
            item_ids = {
                child.name for child in staging.iterdir()
                if child.is_dir() and child.name.isdigit()
            }
        except OSError:
            continue
        item_ids &= wanted
        if item_ids:
            found.update(item_ids)
            staging_dirs.append(str(staging))
    return WorkshopRecoveryState(tuple(sorted(found, key=int)), tuple(staging_dirs))


def steam_api_library_candidates(install: SteamInstall | None) -> list[Path]:
    """Return likely official 64-bit Steam API redistributables in priority order."""
    candidates: list[Path] = []
    override = os.environ.get("WOLFLAUNCHER_STEAM_API_LIBRARY", "").strip()
    if override:
        candidates.append(Path(override).expanduser())
    if install and install.root:
        candidates.append(install.root / "steamrt64" / "libsteam_api.so")
    candidates.extend(
        [
            Path.home() / ".local/share/Steam/steamrt64/libsteam_api.so",
            Path.home() / ".steam/steam/steamrt64/libsteam_api.so",
            Path.home()
            / ".var/app/com.valvesoftware.Steam/data/Steam/steamrt64/libsteam_api.so",
            Path.home()
            / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamrt64/libsteam_api.so",
        ]
    )
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def find_steam_api_library(install: SteamInstall | None) -> Path | None:
    return next((path for path in steam_api_library_candidates(install) if path.is_file()), None)


class SteamWorkshopClient:
    """Minimal binding for the official Steamworks ISteamUGC flat exports."""

    def __init__(self, library_path: Path):
        self.library_path = Path(library_path)
        self._library: ctypes.CDLL | None = None
        self._ugc = None
        self._previous_environment: dict[str, str | None] = {}

    def __enter__(self) -> "SteamWorkshopClient":
        for key in ("SteamAppId", "SteamGameId"):
            self._previous_environment[key] = os.environ.get(key)
            os.environ[key] = str(STEAM_APP_ID_DAYZ)
        try:
            self._library = ctypes.CDLL(str(self.library_path))
            self._bind()
            if not self._library.SteamAPI_InitSafe():
                raise WorkshopSubscriptionError(
                    "Steamworks could not initialize. Start the selected Steam client, confirm "
                    "that its current account owns DayZ, and try again."
                )
            self._ugc = self._ugc_accessor()
            if not self._ugc:
                raise WorkshopSubscriptionError("Steamworks did not provide the Workshop interface.")
            return self
        except Exception:
            self.close()
            raise

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def _bind(self) -> None:
        assert self._library is not None
        library = self._library
        library.SteamAPI_InitSafe.argtypes = []
        library.SteamAPI_InitSafe.restype = ctypes.c_bool
        library.SteamAPI_Shutdown.argtypes = []
        library.SteamAPI_Shutdown.restype = None
        library.SteamAPI_RunCallbacks.argtypes = []
        library.SteamAPI_RunCallbacks.restype = None

        self._ugc_accessor = None
        for version in range(21, 13, -1):
            accessor = getattr(library, f"SteamAPI_SteamUGC_v{version:03d}", None)
            if accessor:
                accessor.argtypes = []
                accessor.restype = ctypes.c_void_p
                self._ugc_accessor = accessor
                break
        if self._ugc_accessor is None:
            raise WorkshopSubscriptionError(
                "The installed Steam API library does not expose a supported Workshop interface."
            )

        library.SteamAPI_ISteamUGC_SubscribeItem.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        library.SteamAPI_ISteamUGC_SubscribeItem.restype = ctypes.c_uint64
        library.SteamAPI_ISteamUGC_GetItemState.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        library.SteamAPI_ISteamUGC_GetItemState.restype = ctypes.c_uint32
        library.SteamAPI_ISteamUGC_GetItemDownloadInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint64,
            ctypes.POINTER(ctypes.c_uint64),
            ctypes.POINTER(ctypes.c_uint64),
        ]
        library.SteamAPI_ISteamUGC_GetItemDownloadInfo.restype = ctypes.c_bool
        library.SteamAPI_ISteamUGC_DownloadItem.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint64,
            ctypes.c_bool,
        ]
        library.SteamAPI_ISteamUGC_DownloadItem.restype = ctypes.c_bool

    def close(self) -> None:
        if self._library is not None:
            try:
                self._library.SteamAPI_Shutdown()
            except (AttributeError, OSError):
                pass
        self._ugc = None
        self._library = None
        for key, value in self._previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._previous_environment.clear()

    def run_callbacks(self) -> None:
        assert self._library is not None
        self._library.SteamAPI_RunCallbacks()

    def subscribe(self, workshop_id: str) -> None:
        assert self._library is not None and self._ugc
        call = self._library.SteamAPI_ISteamUGC_SubscribeItem(
            self._ugc, ctypes.c_uint64(int(workshop_id))
        )
        if not call:
            raise WorkshopSubscriptionError(
                f"Steam rejected the subscription request for Workshop item {workshop_id}."
            )

    def request_download(self, workshop_id: str) -> bool:
        assert self._library is not None and self._ugc
        return bool(
            self._library.SteamAPI_ISteamUGC_DownloadItem(
                self._ugc, ctypes.c_uint64(int(workshop_id)), False
            )
        )

    def item_progress(self, workshop_id: str) -> WorkshopItemProgress:
        assert self._library is not None and self._ugc
        item_id = ctypes.c_uint64(int(workshop_id))
        state = int(self._library.SteamAPI_ISteamUGC_GetItemState(self._ugc, item_id))
        downloaded = ctypes.c_uint64()
        total = ctypes.c_uint64()
        has_progress = self._library.SteamAPI_ISteamUGC_GetItemDownloadInfo(
            self._ugc, item_id, ctypes.byref(downloaded), ctypes.byref(total)
        )
        return WorkshopItemProgress(
            workshop_id,
            state,
            int(downloaded.value) if has_progress else 0,
            int(total.value) if has_progress else 0,
        )


def subscribe_workshop_items(
    workshop_ids: Iterable[str],
    install: SteamInstall,
    *,
    progress_callback: Callable[[tuple[WorkshopItemProgress, ...]], None] | None = None,
    cancelled: threading.Event | None = None,
    timeout_seconds: float = 1800,
    poll_seconds: float = 0.5,
) -> WorkshopSubscriptionResult:
    """Subscribe through Steam and wait until local item directories are ready."""
    ids = tuple(dict.fromkeys(str(item).strip() for item in workshop_ids if str(item).strip()))
    if not ids:
        return WorkshopSubscriptionResult((), ())
    if any(not item.isdigit() or int(item) <= 0 for item in ids):
        raise WorkshopSubscriptionError("The missing-mod list contains an invalid Workshop ID.")
    library_path = find_steam_api_library(install)
    if not library_path:
        raise WorkshopSubscriptionError(
            "The selected Steam installation has no 64-bit Steam API redistributable. "
            "Use the manual Workshop links instead."
        )
    if not install.workshop_dir:
        raise WorkshopSubscriptionError("The selected DayZ Workshop directory is unavailable.")

    cancel_event = cancelled or threading.Event()
    started = time.monotonic()
    download_requested_at: dict[str, float] = {}
    with SteamWorkshopClient(library_path) as client:
        for workshop_id in ids:
            client.subscribe(workshop_id)

        while True:
            client.run_callbacks()
            snapshots = tuple(client.item_progress(workshop_id) for workshop_id in ids)
            if progress_callback:
                progress_callback(snapshots)

            installed = tuple(
                item.workshop_id
                for item in snapshots
                if item.installed
                and (install.workshop_dir / item.workshop_id).is_dir()
            )
            if len(installed) == len(ids):
                return WorkshopSubscriptionResult(installed, ())
            if cancel_event.is_set():
                return WorkshopSubscriptionResult(
                    installed,
                    tuple(item for item in ids if item not in installed),
                    cancelled=True,
                )
            if time.monotonic() - started >= timeout_seconds:
                incomplete = tuple(item for item in ids if item not in installed)
                return WorkshopSubscriptionResult(
                    installed,
                    incomplete,
                    error=(
                        "Steam did not finish installing every Workshop item before the timeout. "
                        f"Still incomplete: {', '.join(incomplete)}."
                    ),
                )

            for snapshot in snapshots:
                if snapshot.installed:
                    continue
                if snapshot.state & ITEM_STATE_SUBSCRIBED:
                    last_request = download_requested_at.get(snapshot.workshop_id, 0.0)
                    now = time.monotonic()
                    if now - last_request < DOWNLOAD_REQUEST_RETRY_SECONDS:
                        continue
                    if client.request_download(snapshot.workshop_id):
                        download_requested_at[snapshot.workshop_id] = now
            time.sleep(poll_seconds)


def query_workshop_item_states(
    workshop_ids: Iterable[str],
    install: SteamInstall,
) -> WorkshopStateResult:
    """Read current Steam Workshop state without changing subscriptions."""
    ids = tuple(dict.fromkeys(str(item).strip() for item in workshop_ids if str(item).strip()))
    if not ids:
        return WorkshopStateResult()
    if any(not item.isdigit() or int(item) <= 0 for item in ids):
        return WorkshopStateResult(error="The required-mod list contains an invalid Workshop ID.")
    library_path = find_steam_api_library(install)
    if not library_path:
        return WorkshopStateResult(
            error="The selected Steam installation has no 64-bit Steam API redistributable."
        )
    try:
        with SteamWorkshopClient(library_path) as client:
            client.run_callbacks()
            return WorkshopStateResult(tuple(client.item_progress(item) for item in ids))
    except Exception as exc:
        return WorkshopStateResult(error=str(exc))


def _state_process_main(
    workshop_ids: tuple[str, ...], install: SteamInstall, messages
) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    silence_helper_output()
    messages.put(query_workshop_item_states(workshop_ids, install))


def query_workshop_item_states_isolated(
    workshop_ids: Iterable[str],
    install: SteamInstall,
    *,
    timeout_seconds: float = 30,
) -> WorkshopStateResult:
    """Query item states in a disposable process and wait for SteamAPI shutdown."""
    ids = tuple(dict.fromkeys(str(item).strip() for item in workshop_ids if str(item).strip()))
    if not ids:
        return WorkshopStateResult()
    context = multiprocessing.get_context("spawn")
    messages = context.Queue()
    process = context.Process(
        target=_state_process_main,
        args=(ids, install, messages),
        name="wolflauncher-steam-workshop-state",
    )
    process.start()
    try:
        try:
            result = messages.get(timeout=timeout_seconds)
        except queue.Empty:
            result = WorkshopStateResult(error="Steam Workshop state check timed out.")
    finally:
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        messages.close()
        messages.join_thread()
    return result


def _subscription_process_main(
    workshop_ids: tuple[str, ...],
    install: SteamInstall,
    messages,
    cancelled,
    timeout_seconds: float,
    poll_seconds: float,
) -> None:
    """Own Steamworks in a disposable process so Steam sees a hard shutdown."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    silence_helper_output()
    try:
        result = subscribe_workshop_items(
            workshop_ids,
            install,
            progress_callback=lambda snapshots: messages.put(("progress", snapshots)),
            cancelled=cancelled,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        )
    except Exception as exc:
        result = WorkshopSubscriptionResult(
            (), workshop_ids, error=str(exc)
        )
    messages.put(("result", result))


def subscribe_workshop_items_isolated(
    workshop_ids: Iterable[str],
    install: SteamInstall,
    *,
    progress_callback: Callable[[tuple[WorkshopItemProgress, ...]], None] | None = None,
    cancelled: threading.Event | None = None,
    timeout_seconds: float = 1800,
    poll_seconds: float = 0.5,
) -> WorkshopSubscriptionResult:
    """Run the Steamworks session in a spawned process and wait for its exit.

    Steam associates ``SteamAPI_InitSafe`` with DayZ's app ID. Keeping that API
    loaded in WolfLauncher's long-lived GUI process can leave Steam treating
    DayZ as busy after Workshop completion. A spawned helper provides an
    unambiguous process-lifetime boundary before launch is enabled again.
    """
    ids = tuple(dict.fromkeys(str(item).strip() for item in workshop_ids if str(item).strip()))
    if not ids:
        return WorkshopSubscriptionResult((), ())

    context = multiprocessing.get_context("spawn")
    messages = context.Queue()
    process_cancelled = context.Event()
    process = context.Process(
        target=_subscription_process_main,
        args=(
            ids,
            install,
            messages,
            process_cancelled,
            timeout_seconds,
            poll_seconds,
        ),
        name="wolflauncher-steam-workshop",
    )
    process.start()
    result: WorkshopSubscriptionResult | None = None
    try:
        while result is None:
            if cancelled and cancelled.is_set():
                process_cancelled.set()
            try:
                message_type, payload = messages.get(timeout=0.1)
            except queue.Empty:
                if not process.is_alive():
                    break
                continue
            if message_type == "progress" and progress_callback:
                progress_callback(payload)
            elif message_type == "result":
                result = payload
    finally:
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        messages.close()
        messages.join_thread()

    if result is not None:
        return result
    return WorkshopSubscriptionResult(
        (),
        ids,
        error=(
            "The isolated Steam Workshop helper exited without a result "
            f"(exit code {process.exitcode})."
        ),
    )
