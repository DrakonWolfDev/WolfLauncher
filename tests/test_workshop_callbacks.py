import ctypes
import unittest
from pathlib import Path
from unittest.mock import Mock

from wolflauncher.linux_steam_client import LinuxSteamWorkshopClient
from wolflauncher.workshop_callbacks import (
    CallbackMessage,
    DownloadItemResult,
    record_download_result,
)
from wolflauncher.workshop_subscription import SteamWorkshopClient


class WorkshopCallbackTests(unittest.TestCase):
    def message(self, *, app=221100, result=1, callback=3406):
        payload = DownloadItemResult(app, 2**40 + 123, result)
        message = CallbackMessage(0, callback, ctypes.addressof(payload), ctypes.sizeof(payload))
        return message, payload

    def test_copies_success_and_failure_without_truncating_item_id(self):
        for code in (1, 9):
            message, payload = self.message(result=code)
            results = {}
            record_download_result(message, results)
            self.assertEqual(results, {str(payload.workshop_id): code})

    def test_ignores_other_apps_callback_types_and_invalid_buffers(self):
        for options in ({"app": 480}, {"callback": 3405}):
            message, _payload = self.message(**options)
            results = {}
            record_download_result(message, results)
            self.assertEqual(results, {})
        message, _payload = self.message()
        message.size = 1
        results = {}
        record_download_result(message, results)
        message.size = ctypes.sizeof(DownloadItemResult)
        message.data = None
        record_download_result(message, results)
        self.assertEqual(results, {})

    def test_both_backends_copy_callback_before_freeing_buffer(self):
        for backend in (SteamWorkshopClient, LinuxSteamWorkshopClient):
            with self.subTest(backend=backend):
                client = backend(Path("steam-library"))
                message, payload = self.message()
                calls = 0

                def next_callback(_pipe, target, *_args):
                    nonlocal calls
                    calls += 1
                    if calls != 1:
                        return False
                    ctypes.memmove(target, ctypes.byref(message), ctypes.sizeof(message))
                    return True

                def free_callback(_pipe):
                    payload.result = 0

                free = Mock(side_effect=free_callback)
                client._pipe = 1
                if backend is SteamWorkshopClient:
                    client._library = Mock()
                    client._library.SteamAPI_ManualDispatch_GetNextCallback = next_callback
                    client._library.SteamAPI_ManualDispatch_FreeLastCallback = free
                else:
                    client._callback = next_callback
                    client._free_callback = free
                client.run_callbacks()
                self.assertEqual(client.download_completions, {str(payload.workshop_id): 1})
                free.assert_called_once_with(1)

    def test_new_request_clears_old_completion_on_both_backends(self):
        for backend in (SteamWorkshopClient, LinuxSteamWorkshopClient):
            client = backend(Path("steam-library"))
            client.download_completions["123"] = 1
            if backend is SteamWorkshopClient:
                client._library = Mock()
                client._ugc = 1
            else:
                client._download = Mock(return_value=True)
            self.assertTrue(client.request_download("123"))
            self.assertNotIn("123", client.download_completions)
