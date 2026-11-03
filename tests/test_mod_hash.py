import base64
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wolflauncher.dayz_mod_query import decode_dayz_mod_rules
from wolflauncher.mod_hash import (
    ModHashComparison,
    apply_mod_hash_comparisons,
    calculate_mod_hash,
    compare_mod_hash,
)
from wolflauncher.mod_presenter import mod_detail_status, mod_row, mod_summary_text
from wolflauncher.models import Server
from wolflauncher.mods import (
    ModCheckResult,
    RequiredMod,
    apply_workshop_item_states,
    format_mod_check_report,
)
from wolflauncher.mods_feature import ModsFeatureMixin
from wolflauncher.server_launch_coordinator import ServerLaunchCoordinator
from wolflauncher.workers import ModWorker


class ModHashTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.library = self.root / "workshop"
        self.mod_dir = self.library / "111"
        self.pbo = self.mod_dir / "Addons" / "example.PBO"
        self.write_pbo(self.pbo, bytes(range(20)))
        self.server_hash = calculate_mod_hash([bytes(range(20))])
        self.server = Server("Test", "Group", "203.0.113.1", 2302, 2303)

    def write_pbo(self, path, trailer):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic PBO body\0" + trailer)

    def result(self, **kwargs):
        mod = RequiredMod("111", installed=True, server_hash=self.server_hash, **kwargs)
        return ModCheckResult(True, self.server, [mod], workshop_dir=str(self.library))

    def test_real_capture_matches_decoded_server_hashes_and_local_trailers(self):
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/mod_hash_capture_2026-11-03.json").read_text()
        )
        rules = {
            bytes.fromhex(key): base64.b64decode(value)
            for key, value in fixture["binary_rules"].items()
        }
        advertised = {mod.workshop_id: mod.server_hash for mod in decode_dayz_mod_rules(rules)}
        for mod in fixture["local_mods"]:
            with self.subTest(mod=mod["name"]):
                trailers = [bytes.fromhex(value) for value in mod["pbo_trailers"]]
                self.assertEqual(calculate_mod_hash(trailers), advertised[mod["workshop_id"]])
                for index, trailer in enumerate(trailers):
                    self.write_pbo(self.root / "captured" / "addons" / f"{index}.pbo", trailer)
                self.assertEqual(
                    compare_mod_hash(self.root / "captured", mod["server_hash"]).status, "match"
                )
                for path in (self.root / "captured" / "addons").iterdir():
                    path.unlink()

    def test_aggregation_preserves_duplicates_and_is_order_independent(self):
        a, b = bytes(20), bytes([1]) * 20
        self.assertEqual(calculate_mod_hash([a, b]), 0x33E437AE)
        self.assertEqual(calculate_mod_hash([a, b]), calculate_mod_hash([b, a]))
        self.assertNotEqual(calculate_mod_hash([a, b]), calculate_mod_hash([a, b, b]))
        self.assertEqual(calculate_mod_hash([]), 0x11FDD19C)
        with self.assertRaises(ValueError):
            calculate_mod_hash([b"short"])

    def test_only_top_level_data_pbos_are_counted(self):
        self.write_pbo(self.mod_dir / "keys" / "ignored.pbo", bytes(20))
        self.write_pbo(self.mod_dir / "Addons" / "nested" / "ignored.pbo", bytes(20))
        (self.pbo.parent / "example.PBO.author.bisign").write_bytes(bytes(100))
        self.assertEqual(compare_mod_hash(self.mod_dir, self.server_hash).status, "match")

    def test_changed_files_are_reread_instead_of_reusing_a_cached_match(self):
        self.assertEqual(compare_mod_hash(self.mod_dir, self.server_hash).status, "match")
        self.write_pbo(self.pbo, bytes([9]) * 20)
        changed = compare_mod_hash(self.mod_dir, self.server_hash)
        self.assertEqual(changed.status, "different")
        self.assertIn("does not show which copy is newer", changed.detail)

    def test_duplicate_server_pbo_allowance_is_explicit_and_bounded(self):
        trailer = bytes(range(20))
        duplicate_hash = calculate_mod_hash([trailer, trailer])
        compared = compare_mod_hash(self.mod_dir, duplicate_hash)
        self.assertEqual(compared.status, "match")
        self.assertIn("duplicate PBOs", compared.detail)
        with patch("wolflauncher.mod_hash.MAX_DUPLICATE_SEARCH_PBOS", 0):
            self.assertEqual(compare_mod_hash(self.mod_dir, duplicate_hash).status, "unknown")

    def test_missing_empty_short_unreadable_and_unadvertised_remain_unknown(self):
        self.assertEqual(compare_mod_hash(self.mod_dir, None).status, "unknown")
        self.assertEqual(
            compare_mod_hash(self.root / "missing", self.server_hash).status, "unknown"
        )
        for contents in (b"short", b"X" * 21, b""):
            self.pbo.write_bytes(contents)
            self.assertEqual(compare_mod_hash(self.mod_dir, self.server_hash).status, "unknown")
        self.pbo.unlink()
        self.assertEqual(compare_mod_hash(self.mod_dir, self.server_hash).status, "unknown")
        self.write_pbo(self.pbo, bytes(20))
        with patch("pathlib.Path.open", side_effect=PermissionError):
            self.assertEqual(compare_mod_hash(self.mod_dir, self.server_hash).status, "unknown")

    def test_zero_server_hash_is_compared_rather_than_treated_as_missing(self):
        self.assertEqual(compare_mod_hash(self.mod_dir, 0).status, "different")

    def test_cancellation_and_work_limits_never_produce_a_match_or_difference(self):
        self.assertEqual(
            compare_mod_hash(self.mod_dir, self.server_hash, cancelled=lambda: True).status,
            "unknown",
        )
        self.assertEqual(
            compare_mod_hash(self.mod_dir, self.server_hash, deadline=time.monotonic() - 1).status,
            "unknown",
        )
        for limit in ("MAX_PBOS", "MAX_DIRECTORY_ENTRIES"):
            with patch("wolflauncher.mod_hash." + limit, 0):
                self.assertEqual(compare_mod_hash(self.mod_dir, self.server_hash).status, "unknown")

    def test_cancellation_during_file_enumeration_stops_before_hashing(self):
        checks = iter([False, False, True])
        with patch("wolflauncher.mod_hash.calculate_mod_hash") as aggregate:
            compared = compare_mod_hash(
                self.mod_dir, self.server_hash, cancelled=lambda: next(checks)
            )
        self.assertEqual(compared.status, "unknown")
        self.assertIn("cancelled", compared.detail)
        aggregate.assert_not_called()

    def test_updates_during_comparison_invalidate_the_result(self):
        def changed(trailers):
            self.write_pbo(self.pbo, bytes([3]) * 20)
            return self.server_hash

        with patch("wolflauncher.mod_hash.calculate_mod_hash", side_effect=changed):
            compared = compare_mod_hash(self.mod_dir, self.server_hash)
        self.assertEqual(compared.status, "unknown")
        self.assertIn("changed during comparison", compared.detail)

    def test_new_pbo_during_comparison_invalidates_the_result(self):
        def changed(trailers):
            self.write_pbo(self.pbo.parent / "new.pbo", bytes(20))
            return self.server_hash

        with patch("wolflauncher.mod_hash.calculate_mod_hash", side_effect=changed):
            self.assertEqual(compare_mod_hash(self.mod_dir, self.server_hash).status, "unknown")

    def test_linked_pbos_cannot_bless_content_outside_the_selected_mod(self):
        self.pbo.unlink()
        outside = self.root / "outside.pbo"
        self.write_pbo(outside, bytes(range(20)))
        try:
            self.pbo.symlink_to(outside)
        except OSError:
            self.skipTest("Creating symlinks is unavailable")
        self.assertEqual(compare_mod_hash(self.mod_dir, self.server_hash).status, "unknown")

    def test_selected_library_and_steam_activity_are_respected(self):
        first = self.result()
        apply_mod_hash_comparisons(first, None)
        self.assertEqual(first.required_mods[0].hash_comparison.status, "match")
        alternate = self.root / "other-library"
        self.write_pbo(alternate / "111" / "addons" / "other.pbo", bytes(20))
        install = SimpleNamespace(workshop_dir=alternate)
        apply_mod_hash_comparisons(first, install)
        self.assertEqual(first.required_mods[0].hash_comparison.status, "different")
        active = self.result(workshop_state=16)  # DOWNLOADING
        apply_mod_hash_comparisons(active, None)
        self.assertEqual(active.required_mods[0].hash_comparison.status, "unknown")
        self.assertFalse(active.required_mods[0].ready)

    def test_new_steam_state_invalidates_an_earlier_comparison(self):
        result = self.result()
        apply_mod_hash_comparisons(result, None)
        self.assertEqual(result.required_mods[0].hash_comparison.status, "match")
        apply_workshop_item_states(
            result, [SimpleNamespace(workshop_id="111", state=16, downloaded=1, total=100)]
        )
        self.assertIsNone(result.required_mods[0].hash_comparison)
        self.assertFalse(result.required_mods[0].ready)

    def test_experimental_uses_the_actual_official_launcher_mod_path(self):
        alternate = self.root / "other-library" / "111"
        self.write_pbo(alternate / "addons" / "other.pbo", bytes(20))
        dayz_dir = self.root / "common" / "DayZ Exp"
        source = dayz_dir.parent / "DayZ" / "!Workshop"
        source.mkdir(parents=True)
        try:
            (source / "@Example").symlink_to(alternate, target_is_directory=True)
        except OSError:
            self.skipTest("Creating directory symlinks is unavailable")
        result = self.result()
        result.required_mods[0].server_hash = calculate_mod_hash([bytes(20)])
        install = SimpleNamespace(
            workshop_dir=self.library,
            dayz_dir=dayz_dir,
            product=SimpleNamespace(experimental=True),
        )
        apply_mod_hash_comparisons(result, install)
        self.assertEqual(result.required_mods[0].hash_comparison.status, "match")

    def test_unavailable_experimental_paths_do_not_fail_the_mod_check(self):
        install = SimpleNamespace(
            workshop_dir=self.library,
            dayz_dir=self.root,
            product=SimpleNamespace(experimental=True),
        )
        result = self.result()
        with patch("wolflauncher.native_launcher._experimental_mod_paths", side_effect=OSError):
            apply_mod_hash_comparisons(result, install)
        self.assertTrue(result.ok)
        self.assertTrue(result.required_mods[0].ready)
        self.assertEqual(result.required_mods[0].hash_comparison.status, "unknown")

    def test_advisory_does_not_trigger_a_download_or_block_an_installed_mod(self):
        result = self.result()
        mod = result.required_mods[0]
        mod.hash_comparison = ModHashComparison("different", "Different trailers", 123)
        self.assertTrue(mod.ready)
        self.assertEqual(result.missing_mods, [])
        self.assertEqual(result.update_mods, [])
        self.assertIn("different from server", mod_row(mod).values[0])
        self.assertEqual(mod_detail_status(mod), "warning")
        self.assertIn("1 different", mod_summary_text(result))
        self.assertIn("does not", compare_mod_hash(self.mod_dir, 0).detail)
        self.assertIn("Not a full integrity check", format_mod_check_report(result))

    def test_unknown_evidence_is_visible_and_not_reported_as_a_match(self):
        result = self.result()
        result.required_mods[0].hash_comparison = ModHashComparison()
        self.assertIn("server hash unavailable", mod_row(result.required_mods[0]).values[0])
        self.assertIn("0 matching, 0 different, 1 unavailable", mod_summary_text(result))

    def test_worker_runs_comparisons_and_suppresses_cancelled_results(self):
        result = self.result()
        worker = ModWorker(self.server, self.library, include_metadata=False, include_hashes=True)
        results = []
        worker.mods_ready.connect(results.append)
        with patch("wolflauncher.workers.check_server_mods", return_value=result):
            worker.run()
        self.assertEqual(results[0].required_mods[0].hash_comparison.status, "match")
        with (
            patch.object(worker, "isInterruptionRequested", return_value=True),
            patch("wolflauncher.workers.check_server_mods") as check,
        ):
            worker.run()
        check.assert_not_called()
        self.assertEqual(len(results), 1)

    def test_cheap_browser_previews_do_not_read_pbos(self):
        worker = ModWorker(self.server, self.library, include_metadata=False, include_hashes=False)
        with (
            patch("wolflauncher.workers.check_server_mods", return_value=self.result()),
            patch("wolflauncher.workers.apply_mod_hash_comparisons") as compare,
        ):
            worker._check()
        compare.assert_not_called()

    def coordinator(self):
        install = SimpleNamespace(workshop_dir=self.library, dayz_dir=self.root)
        context = SimpleNamespace(
            request_id="current",
            mod_context_key=("stable", str(self.library)),
            server=self.server,
            install=install,
            product=SimpleNamespace(label="DayZ Stable"),
            matches=lambda server: server == self.server,
            fresh=lambda: True,
        )
        window = SimpleNamespace(
            active_server_context=lambda: self.server,
            last_mod_result=None,
            display_mods_result=Mock(),
        )
        coordinator = ServerLaunchCoordinator(window)
        coordinator.request_id = context.request_id
        return coordinator, window, context

    def tagged_result(self, context):
        result = self.result()
        result.request_id = context.request_id
        result.launch_context_key = context.mod_context_key
        return result

    def test_inspector_enables_hashes_through_the_real_launch_coordinator_path(self):
        coordinator, window, context = self.coordinator()
        window.server_launch = coordinator
        window.workshop_recovery_ids = ()
        for name in (
            "mod_server_title",
            "mod_readiness",
            "mod_summary",
            "mods_table",
            "subscribe_missing_button",
            "force_update_button",
            "update_mod_detail_card",
        ):
            setattr(window, name, Mock())
        with (
            patch.object(
                coordinator, "prepare", side_effect=lambda s, callback, **kw: callback(context)
            ),
            patch("wolflauncher.workers.ModWorker") as worker,
        ):
            ModsFeatureMixin.check_server_mods(window, self.server)
        self.assertTrue(worker.call_args.kwargs["include_hashes"])
        self.assertIs(worker.call_args.kwargs["launch_context"], context)

    def test_launch_checks_skip_hashes_and_ignore_a_replaced_request(self):
        coordinator, window, context = self.coordinator()
        continuation = Mock()
        with patch("wolflauncher.workers.ModWorker") as worker:
            coordinator.check_mods(context, continuation)
            self.assertFalse(worker.call_args.kwargs["include_hashes"])
            ready = worker.return_value.mods_ready.connect.call_args.args[0]
            coordinator.request_id = "replacement"
            ready(self.tagged_result(context))
        window.display_mods_result.assert_not_called()
        continuation.assert_not_called()

    def test_requested_hash_read_is_queued_after_a_readiness_only_check(self):
        coordinator, window, context = self.coordinator()
        continuation = Mock()
        with patch("wolflauncher.workers.ModWorker") as worker:
            worker.return_value.include_hashes = False
            coordinator.check_mods(context, continuation)
            coordinator.check_mods(context, Mock(), include_hashes=True)
            self.assertEqual(worker.call_count, 1)
            ready = worker.return_value.mods_ready.connect.call_args.args[0]
            ready(self.tagged_result(context))
            continuation.assert_called_once()
            coordinator._mod_finished(context.request_id)
            self.assertEqual(worker.call_count, 2)
            self.assertTrue(worker.call_args.kwargs["include_hashes"])

    def test_new_hash_request_rereads_while_launch_can_reuse_readiness(self):
        coordinator, window, context = self.coordinator()
        window.last_mod_result = self.tagged_result(context)
        window.last_mod_result.required_mods[0].hash_comparison = ModHashComparison("match")
        continuation = Mock()
        with patch("wolflauncher.workers.ModWorker") as worker:
            coordinator.check_mods(context, continuation)
            continuation.assert_called_once_with(window.last_mod_result)
            worker.assert_not_called()
            coordinator.check_mods(context, Mock(), include_hashes=True)
            self.assertTrue(worker.call_args.kwargs["include_hashes"])
