"""Steamworks download notifications shared by the two helper backends.

ABI: Valve Steamworks CallbackMsg_t and DownloadItemResult_t (callback 3406).
Callback packing is 8 on Windows and 4 on POSIX, as in Valve's headers.
"""

import ctypes
import sys


class CallbackMessage(ctypes.Structure):
    _pack_ = 8 if sys.platform == "win32" else 4
    _fields_ = [
        ("user", ctypes.c_int32),
        ("callback", ctypes.c_int32),
        ("data", ctypes.c_void_p),
        ("size", ctypes.c_int32),
    ]


class DownloadItemResult(ctypes.Structure):
    _pack_ = 8 if sys.platform == "win32" else 4
    _fields_ = [
        ("app_id", ctypes.c_uint32),
        ("workshop_id", ctypes.c_uint64),
        ("result", ctypes.c_int32),
    ]


def record_download_result(message, results):
    """Copy DayZ results before Steam frees its callback buffer."""
    if message.callback != 3406 or not message.data:
        return
    if message.size != ctypes.sizeof(DownloadItemResult):
        return
    result = DownloadItemResult.from_buffer_copy(ctypes.string_at(message.data, message.size))
    if result.app_id == 221100:
        results[str(result.workshop_id)] = result.result
