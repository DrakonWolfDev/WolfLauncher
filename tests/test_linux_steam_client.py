import ctypes
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from wolflauncher.linux_steam_client import LinuxSteamWorkshopClient, _method
from wolflauncher.workshop_subscription import WorkshopSubscriptionError, _workshop_client


class LinuxSteamClientTests(unittest.TestCase):
    def client(self, *, owns=True, client_available=True, ugc_available=True):
        client = LinuxSteamWorkshopClient(Path("/steam/linux64/steamclient.so"))
        library = Mock()
        library.CreateInterface.return_value = 1 if client_available else None
        calls = {}

        def bind(pointer, index, *_signature):
            key = (pointer, index)
            if key not in calls:
                values = {
                    (1, 0): 10,
                    (1, 1): True,
                    (1, 2): 20,
                    (1, 15): 2,
                    (1, 26): 3 if ugc_available else None,
                    (2, 6): owns,
                    (3, 72): 123,
                    (3, 73): 124,
                    (3, 76): 5,
                    (3, 78): False,
                    (3, 79): True,
                }
                calls[key] = Mock(return_value=values.get(key))
            return calls[key]

        cdll_patch = patch("wolflauncher.linux_steam_client.ctypes.CDLL", return_value=library)
        method_patch = patch("wolflauncher.linux_steam_client._method", side_effect=bind)
        machine_patch = patch(
            "wolflauncher.linux_steam_client.platform.machine", return_value="x86_64"
        )
        cdll_patch.start()
        method_patch.start()
        machine_patch.start()
        self.addCleanup(cdll_patch.stop)
        self.addCleanup(method_patch.stop)
        self.addCleanup(machine_patch.stop)
        return client, library, calls

    def test_native_method_passes_this_pointer_and_uint64_without_truncation(self):
        seen = []
        callback = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint64)(
            lambda pointer, item: seen.append((pointer, item)) or item
        )
        table = (ctypes.c_void_p * 1)(ctypes.cast(callback, ctypes.c_void_p).value)
        instance = ctypes.pointer(ctypes.cast(table, ctypes.POINTER(ctypes.c_void_p)))
        pointer = ctypes.cast(instance, ctypes.c_void_p).value
        method = _method(pointer, 0, ctypes.c_uint64, ctypes.c_uint64)
        self.assertEqual(method(2**63 + 1), 2**63 + 1)
        self.assertEqual(seen, [(pointer, 2**63 + 1)])

    def test_owns_dayz_uses_exact_interfaces_and_releases_only_its_pipe(self):
        client, library, calls = self.client()
        with patch.dict(os.environ, {"SteamAppId": "old"}, clear=True):
            with client:
                self.assertEqual(os.environ["SteamAppId"], "221100")
                client.subscribe("2602208478")
                client.unsubscribe("2602208478")
                self.assertTrue(client.request_download("2602208478", high_priority=True))
                self.assertEqual(client.item_progress("2602208478").state, 5)
                library.Steam_BGetCallback.side_effect = [True, False]
                client.run_callbacks()
            self.assertEqual(os.environ["SteamAppId"], "old")
            self.assertNotIn("SteamGameId", os.environ)
        library.CreateInterface.assert_called_once_with(b"SteamClient021", None)
        calls[1, 15].assert_called_once_with(20, 10, b"STEAMAPPS_INTERFACE_VERSION008")
        calls[2, 6].assert_called_once_with(221100)
        calls[1, 26].assert_called_once_with(20, 10, b"STEAMUGC_INTERFACE_VERSION020")
        calls[3, 72].assert_called_once_with(2602208478)
        calls[3, 73].assert_called_once_with(2602208478)
        calls[3, 79].assert_called_once_with(2602208478, True)
        calls[1, 4].assert_called_once_with(10, 20)
        calls[1, 1].assert_called_once_with(10)
        library.Steam_FreeLastCallback.assert_called_once_with(10)
        client.close()
        calls[1, 1].assert_called_once()

    def test_non_owner_cannot_access_workshop_and_resources_are_released(self):
        client, _, calls = self.client(owns=False)
        with self.assertRaisesRegex(WorkshopSubscriptionError, "must own DayZ"):
            client.__enter__()
        self.assertNotIn((1, 26), calls)
        calls[1, 4].assert_called_once_with(10, 20)
        calls[1, 1].assert_called_once_with(10)

    def test_unsupported_interfaces_fail_without_guessing_versions(self):
        client, library, calls = self.client(client_available=False)
        with self.assertRaisesRegex(WorkshopSubscriptionError, "Update Steam"):
            client.__enter__()
        library.CreateInterface.assert_called_once()
        self.assertEqual(calls, {})

    def test_missing_ugc_releases_resources(self):
        client, _, calls = self.client(ugc_available=False)
        with self.assertRaisesRegex(WorkshopSubscriptionError, "Update Steam"):
            client.__enter__()
        calls[1, 4].assert_called_once_with(10, 20)
        calls[1, 1].assert_called_once_with(10)

    def test_factory_keeps_existing_redistributable_backend(self):
        with patch("wolflauncher.workshop_subscription.sys.platform", "linux"):
            self.assertIsInstance(
                _workshop_client(Path("/steam/linux64/steamclient.so")), LinuxSteamWorkshopClient
            )
            with patch("wolflauncher.workshop_subscription.SteamWorkshopClient") as original:
                _workshop_client(Path("/steam/libsteam_api.so"))
            original.assert_called_once_with(Path("/steam/libsteam_api.so"))
