"""Workshop access through the user's installed 64-bit Linux Steam client.

Only the named SteamClient021 / STEAMUGC_INTERFACE_VERSION020 ABI is used.
Method positions and signatures follow Valve's Proton steamworks_sdk_161
isteamclient.h and isteamugc.h. No SDK binary or compiler is required.
This client must run in the disposable Workshop helper, never the GUI.
"""

from __future__ import annotations

import ctypes
import os
import platform
from pathlib import Path

from .workshop_subscription import WorkshopItemProgress, WorkshopSubscriptionError


class _Callback(ctypes.Structure):
    _fields_ = [
        ("user", ctypes.c_int32),
        ("callback", ctypes.c_int32),
        ("data", ctypes.c_void_p),
        ("size", ctypes.c_int32),
    ]


def _method(pointer, index, result, *arguments):
    """Bind one method of an explicitly versioned Linux C++ interface."""
    if not pointer:
        raise WorkshopSubscriptionError("Steam returned an unavailable Workshop interface.")
    table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    function = ctypes.CFUNCTYPE(result, ctypes.c_void_p, *arguments)(table[index])
    return lambda *args: function(pointer, *args)


class LinuxSteamWorkshopClient:
    def __init__(self, library_path: Path):
        self.library_path = Path(library_path)
        self._library = None
        self._client = None
        self._pipe = 0
        self._user = 0
        self._environment = {}

    def __enter__(self):
        if (
            platform.machine().lower() not in ("x86_64", "amd64")
            or ctypes.sizeof(ctypes.c_void_p) != 8
        ):
            raise WorkshopSubscriptionError("Steam Workshop automation requires 64-bit x86 Linux.")
        for key in ("SteamAppId", "SteamGameId"):
            self._environment[key] = os.environ.get(key)
            os.environ[key] = "221100"
        try:
            self._library = ctypes.CDLL(str(self.library_path))
            create = self._library.CreateInterface
            create.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
            create.restype = ctypes.c_void_p
            self._client = create(b"SteamClient021", None)
            if not self._client:
                raise WorkshopSubscriptionError(
                    "This Steam client has no supported Workshop interface. Update Steam and retry."
                )
            self._release_pipe = _method(self._client, 1, ctypes.c_bool, ctypes.c_int32)
            self._release_user = _method(self._client, 4, None, ctypes.c_int32, ctypes.c_int32)
            self._pipe = _method(self._client, 0, ctypes.c_int32)()
            if not self._pipe:
                raise WorkshopSubscriptionError(
                    "Could not connect to Steam. Start Steam and retry."
                )
            self._user = _method(self._client, 2, ctypes.c_int32, ctypes.c_int32)(self._pipe)
            if not self._user:
                raise WorkshopSubscriptionError(
                    "Sign in to Steam with an account that owns DayZ, then retry."
                )
            apps = _method(
                self._client,
                15,
                ctypes.c_void_p,
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.c_char_p,
            )(self._user, self._pipe, b"STEAMAPPS_INTERFACE_VERSION008")
            if not apps or not _method(apps, 6, ctypes.c_bool, ctypes.c_uint32)(221100):
                raise WorkshopSubscriptionError(
                    "The signed-in Steam account must own DayZ to download its Workshop mods."
                )
            ugc = _method(
                self._client,
                26,
                ctypes.c_void_p,
                ctypes.c_int32,
                ctypes.c_int32,
                ctypes.c_char_p,
            )(self._user, self._pipe, b"STEAMUGC_INTERFACE_VERSION020")
            if not ugc:
                raise WorkshopSubscriptionError(
                    "Steam did not provide the supported Workshop interface. Update Steam and retry."
                )
            self._subscribe = _method(ugc, 72, ctypes.c_uint64, ctypes.c_uint64)
            self._unsubscribe = _method(ugc, 73, ctypes.c_uint64, ctypes.c_uint64)
            self._state = _method(ugc, 76, ctypes.c_uint32, ctypes.c_uint64)
            self._progress = _method(
                ugc,
                78,
                ctypes.c_bool,
                ctypes.c_uint64,
                ctypes.POINTER(ctypes.c_uint64),
                ctypes.POINTER(ctypes.c_uint64),
            )
            self._download = _method(ugc, 79, ctypes.c_bool, ctypes.c_uint64, ctypes.c_bool)
            self._callback = self._library.Steam_BGetCallback
            self._callback.argtypes = [
                ctypes.c_int32,
                ctypes.POINTER(_Callback),
                ctypes.POINTER(ctypes.c_int32),
            ]
            self._callback.restype = ctypes.c_bool
            self._free_callback = self._library.Steam_FreeLastCallback
            self._free_callback.argtypes = [ctypes.c_int32]
            self._free_callback.restype = ctypes.c_bool
            return self
        except Exception:
            self.close()
            raise

    def __exit__(self, *_args):
        self.close()

    def close(self):
        try:
            if self._user:
                self._release_user(self._pipe, self._user)
        finally:
            self._user = 0
            try:
                if self._pipe:
                    self._release_pipe(self._pipe)
            finally:
                self._pipe = 0
                for key, value in self._environment.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
                self._environment.clear()

    def run_callbacks(self):
        # Steam owns the downloads; drain notifications while polling item state.
        message = _Callback()
        ignored = ctypes.c_int32()
        for _ in range(1000):
            if not self._callback(self._pipe, ctypes.byref(message), ctypes.byref(ignored)):
                break
            self._free_callback(self._pipe)

    def subscribe(self, workshop_id: str):
        if not self._subscribe(int(workshop_id)):
            raise WorkshopSubscriptionError(f"Steam rejected the subscription for {workshop_id}.")

    def unsubscribe(self, workshop_id: str):
        if not self._unsubscribe(int(workshop_id)):
            raise WorkshopSubscriptionError(
                f"Steam rejected the unsubscribe request for {workshop_id}."
            )

    def request_download(self, workshop_id: str, *, high_priority=False):
        return bool(self._download(int(workshop_id), high_priority))

    def item_progress(self, workshop_id: str):
        state = self._state(int(workshop_id))
        downloaded, total = ctypes.c_uint64(), ctypes.c_uint64()
        known = self._progress(int(workshop_id), ctypes.byref(downloaded), ctypes.byref(total))
        return WorkshopItemProgress(
            workshop_id, state, downloaded.value if known else 0, total.value if known else 0
        )
