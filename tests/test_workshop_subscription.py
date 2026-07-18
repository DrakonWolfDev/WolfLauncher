import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher.platform_detection import SteamInstall
from wolflauncher.workshop_subscription import (
    ITEM_STATE_DOWNLOAD_PENDING,
    ITEM_STATE_DOWNLOADING,
    ITEM_STATE_INSTALLED,
    ITEM_STATE_NEEDS_UPDATE,
    ITEM_STATE_SUBSCRIBED,
    WorkshopItemProgress,
    WorkshopStateResult,
    WorkshopSubscriptionError,
    current_workshop_item,
    find_steam_api_library,
    query_workshop_item_states,
    silence_helper_output,
    steam_api_library_candidates,
    subscribe_workshop_items,
    subscribe_workshop_items_isolated,
    workshop_recovery_state,
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

    def test_needs_update_is_not_ready_even_with_installed_flag(self):
        progress = WorkshopItemProgress("123", ITEM_STATE_INSTALLED | ITEM_STATE_NEEDS_UPDATE)

        self.assertFalse(progress.installed)

    def test_current_item_prefers_downloading_over_first_unresolved(self):
        snapshots = [
            WorkshopItemProgress("stalled", ITEM_STATE_SUBSCRIBED),
            WorkshopItemProgress("active", ITEM_STATE_DOWNLOADING, 25, 100),
            WorkshopItemProgress("pending", ITEM_STATE_DOWNLOAD_PENDING),
        ]

        self.assertEqual(current_workshop_item(snapshots).workshop_id, "active")

    def test_current_item_does_not_claim_arbitrary_unresolved_item(self):
        snapshots = [WorkshopItemProgress("stalled", ITEM_STATE_SUBSCRIBED)]

        self.assertIsNone(current_workshop_item(snapshots))


class SteamApiLibraryTests(unittest.TestCase):
    def test_helper_output_redirects_native_stdout_and_stderr(self):
        with (
            patch("wolflauncher.workshop_subscription.os.open", return_value=9) as open_mock,
            patch("wolflauncher.workshop_subscription.os.dup2") as dup_mock,
            patch("wolflauncher.workshop_subscription.os.close") as close_mock,
        ):
            silence_helper_output()

        open_mock.assert_called_once_with(os.devnull, os.O_WRONLY)
        self.assertEqual(dup_mock.call_args_list[0].args, (9, 1))
        self.assertEqual(dup_mock.call_args_list[1].args, (9, 2))
        close_mock.assert_called_once_with(9)

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


class WorkshopRecoveryStateTests(unittest.TestCase):
    def test_reports_only_relevant_numeric_staged_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            steamapps = Path(temp_dir) / "steamapps"
            staging = steamapps / "workshop/downloads/221100"
            staging.mkdir(parents=True)
            for name in ("111", "222", "not-an-item"):
                (staging / name).mkdir()
            install = install_for(Path(temp_dir), Path(temp_dir) / "workshop")
            install.steamapps = steamapps
            install.library_steamapps = [steamapps]

            state = workshop_recovery_state(install, ["222", "333"])

        self.assertTrue(state.active)
        self.assertEqual(state.item_ids, ("222",))
        self.assertEqual(state.staging_dirs, (str(staging),))

    def test_missing_staging_area_is_not_reported_as_activity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            install = install_for(Path(temp_dir), Path(temp_dir) / "workshop")

            state = workshop_recovery_state(install, ["111"])

        self.assertFalse(state.active)


class FakeWorkshopClient:
    snapshots = []
    subscribed = []
    downloads = []
    download_results = []

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
        if self.download_results:
            return self.download_results.pop(0)
        return True


class SubscribeWorkshopItemsTests(unittest.TestCase):
    def setUp(self):
        FakeWorkshopClient.snapshots = []
        FakeWorkshopClient.subscribed = []
        FakeWorkshopClient.downloads = []
        FakeWorkshopClient.download_results = []

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

            with (
                patch(
                    "wolflauncher.workshop_subscription.find_steam_api_library",
                    return_value=root / "libsteam_api.so",
                ),
                patch(
                    "wolflauncher.workshop_subscription.SteamWorkshopClient",
                    FakeWorkshopClient,
                ),
            ):
                result = subscribe_workshop_items(["111", "222", "111"], install, poll_seconds=0)

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

            with (
                patch(
                    "wolflauncher.workshop_subscription.find_steam_api_library",
                    return_value=root / "libsteam_api.so",
                ),
                patch(
                    "wolflauncher.workshop_subscription.SteamWorkshopClient",
                    FakeWorkshopClient,
                ),
            ):
                result = subscribe_workshop_items(
                    ["111"], install, cancelled=cancelled, poll_seconds=0
                )

        self.assertTrue(result.cancelled)
        self.assertEqual(result.incomplete_ids, ("111",))

    def test_retries_rejected_download_request_while_item_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workshop = root / "workshop"
            workshop.mkdir()
            install = install_for(root, workshop)
            FakeWorkshopClient.snapshots = [
                {"111": WorkshopItemProgress("111", ITEM_STATE_SUBSCRIBED)}
            ]
            FakeWorkshopClient.download_results = [False, True]
            cancelled = threading.Event()
            progress_calls = 0

            def stop_after_two_requests(_snapshots):
                nonlocal progress_calls
                progress_calls += 1
                if progress_calls >= 3:
                    cancelled.set()

            with (
                patch(
                    "wolflauncher.workshop_subscription.find_steam_api_library",
                    return_value=root / "libsteam_api.so",
                ),
                patch(
                    "wolflauncher.workshop_subscription.SteamWorkshopClient",
                    FakeWorkshopClient,
                ),
                patch(
                    "wolflauncher.workshop_subscription.DOWNLOAD_REQUEST_RETRY_SECONDS",
                    0,
                ),
            ):
                result = subscribe_workshop_items(
                    ["111"],
                    install,
                    progress_callback=stop_after_two_requests,
                    cancelled=cancelled,
                    poll_seconds=0,
                )

        self.assertTrue(result.cancelled)
        self.assertEqual(FakeWorkshopClient.downloads, ["111", "111"])

    def test_stalled_items_release_helper_with_incomplete_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workshop = root / "workshop"
            workshop.mkdir()
            install = install_for(root, workshop)
            FakeWorkshopClient.snapshots = [
                {"111": WorkshopItemProgress("111", ITEM_STATE_SUBSCRIBED)}
            ]
            with (
                patch(
                    "wolflauncher.workshop_subscription.find_steam_api_library",
                    return_value=root / "libsteam_api.so",
                ),
                patch(
                    "wolflauncher.workshop_subscription.SteamWorkshopClient",
                    FakeWorkshopClient,
                ),
            ):
                result = subscribe_workshop_items(
                    ["111"], install, stall_timeout_seconds=0, poll_seconds=0
                )

        self.assertFalse(result.ok)
        self.assertEqual(result.incomplete_ids, ("111",))
        self.assertIn("released the Steam helper", result.error)
        self.assertIn("Recheck mods", result.error)

    def test_rejects_invalid_workshop_id_before_loading_steam(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            install = install_for(root, root / "workshop")
            with self.assertRaisesRegex(WorkshopSubscriptionError, "invalid Workshop ID"):
                subscribe_workshop_items(["not-an-id"], install)

    def test_isolated_helper_returns_child_error_after_process_exit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            install = install_for(root, root / "workshop")

            result = subscribe_workshop_items_isolated(["not-an-id"], install, poll_seconds=0)

        self.assertIn("invalid Workshop ID", result.error)
        self.assertEqual(result.incomplete_ids, ("not-an-id",))

    def test_state_query_reads_items_without_changing_subscriptions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            install = install_for(root, root / "workshop")
            FakeWorkshopClient.snapshots = [
                {
                    "111": WorkshopItemProgress("111", ITEM_STATE_INSTALLED),
                    "222": WorkshopItemProgress("222", ITEM_STATE_DOWNLOADING, 5, 10),
                }
            ]
            with (
                patch(
                    "wolflauncher.workshop_subscription.find_steam_api_library",
                    return_value=root / "libsteam_api.so",
                ),
                patch(
                    "wolflauncher.workshop_subscription.SteamWorkshopClient",
                    FakeWorkshopClient,
                ),
            ):
                result = query_workshop_item_states(["111", "222"], install)

        self.assertIsInstance(result, WorkshopStateResult)
        self.assertEqual([item.workshop_id for item in result.items], ["111", "222"])
        self.assertEqual(FakeWorkshopClient.subscribed, [])
        self.assertEqual(FakeWorkshopClient.downloads, [])


if __name__ == "__main__":
    unittest.main()
