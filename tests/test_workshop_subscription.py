import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher.platform_detection import SteamInstall
from wolflauncher.workshop_subscription import (
    ITEM_STATE_INSTALLED,
    ITEM_STATE_SUBSCRIBED,
    SteamWorkshopClient,
    WorkshopItemProgress,
    WorkshopSubscriptionError,
    find_steam_api_library,
    steam_api_library_candidates,
    subscribe_workshop_items,
)


def install_for(root: Path, workshop_dir: Path) -> SteamInstall:
    return SteamInstall(
        mode="native",
        executable="steam",
        running=True,
        root=root,
        steamapps=root / "steamapps",
        dayz_dir=root / "DayZ",
        workshop_dir=workshop_dir,
    )


class WorkshopItemProgressTests(unittest.TestCase):
    def test_installed_and_percent_are_safe(self):
        progress = WorkshopItemProgress("123", ITEM_STATE_INSTALLED, 5, 10)

        self.assertTrue(progress.installed)
        self.assertEqual(progress.percent, 50)
        self.assertIsNone(WorkshopItemProgress("123", 0).percent)


class SteamApiLibraryTests(unittest.TestCase):
    def test_override_is_first_candidate(self):
        with patch.dict(os.environ, {"WOLFLAUNCHER_STEAM_API_LIBRARY": "/custom/lib.so"}):
            candidates = steam_api_library_candidates(None)

        self.assertEqual(candidates[0], Path("/custom/lib.so"))

    def test_finds_library_in_selected_steam_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            library = root / "steamrt64/libsteam_api.so"
            library.parent.mkdir()
            library.touch()
            install = install_for(root, root / "workshop")

            self.assertEqual(find_steam_api_library(install), library)


class FakeWorkshopClient:
    snapshots = []
    subscribed = []
    downloads = []

    def __init__(self, _path):
        self.index = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def subscribe(self, workshop_id):
        self.subscribed.append(workshop_id)

    def run_callbacks(self):
        return None

    def item_progress(self, workshop_id):
        states = self.snapshots[min(self.index, len(self.snapshots) - 1)]
        result = states[workshop_id]
        if workshop_id == list(states)[-1]:
            self.index += 1
        return result

    def request_download(self, workshop_id):
        self.downloads.append(workshop_id)
        return True


class SubscribeWorkshopItemsTests(unittest.TestCase):
    def setUp(self):
        FakeWorkshopClient.snapshots = []
        FakeWorkshopClient.subscribed = []
        FakeWorkshopClient.downloads = []

    def test_subscribes_requests_download_and_waits_for_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workshop = root / "workshop"
            workshop.mkdir()
            for item in ("111", "222"):
                (workshop / item).mkdir()
            install = install_for(root, workshop)
            FakeWorkshopClient.snapshots = [
                {
                    "111": WorkshopItemProgress("111", ITEM_STATE_SUBSCRIBED),
                    "222": WorkshopItemProgress("222", ITEM_STATE_SUBSCRIBED),
                },
                {
                    "111": WorkshopItemProgress("111", ITEM_STATE_INSTALLED),
                    "222": WorkshopItemProgress("222", ITEM_STATE_INSTALLED),
                },
            ]

            with patch(
                "wolflauncher.workshop_subscription.find_steam_api_library",
                return_value=root / "libsteam_api.so",
            ), patch(
                "wolflauncher.workshop_subscription.SteamWorkshopClient",
                FakeWorkshopClient,
            ):
                result = subscribe_workshop_items(
                    ["111", "222", "111"], install, poll_seconds=0
                )

        self.assertTrue(result.ok)
        self.assertEqual(FakeWorkshopClient.subscribed, ["111", "222"])
        self.assertEqual(FakeWorkshopClient.downloads, ["111", "222"])

    def test_cancel_does_not_unsubscribe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workshop = root / "workshop"
            workshop.mkdir()
            install = install_for(root, workshop)
            FakeWorkshopClient.snapshots = [
                {"111": WorkshopItemProgress("111", ITEM_STATE_SUBSCRIBED)}
            ]
            cancelled = threading.Event()
            cancelled.set()

            with patch(
                "wolflauncher.workshop_subscription.find_steam_api_library",
                return_value=root / "libsteam_api.so",
            ), patch(
                "wolflauncher.workshop_subscription.SteamWorkshopClient",
                FakeWorkshopClient,
            ):
                result = subscribe_workshop_items(
                    ["111"], install, cancelled=cancelled, poll_seconds=0
                )

        self.assertTrue(result.cancelled)
        self.assertEqual(result.incomplete_ids, ("111",))

    def test_rejects_invalid_workshop_id_before_loading_steam(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            install = install_for(root, root / "workshop")
            with self.assertRaisesRegex(WorkshopSubscriptionError, "invalid Workshop ID"):
                subscribe_workshop_items(["not-an-id"], install)


if __name__ == "__main__":
    unittest.main()
