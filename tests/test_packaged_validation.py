import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from wolflauncher.app import configure_packaged_smoke_test
from wolflauncher.packaged_validation import PackagedValidation, isolated_root


class PackagedValidationTests(unittest.TestCase):
    def test_extended_checks_require_both_smoke_flags(self):
        with (
            patch("wolflauncher.packaged_validation.schedule_validation") as schedule,
            patch("wolflauncher.app.QTimer.singleShot"),
        ):
            self.assertFalse(
                configure_packaged_smoke_test(
                    Mock(), Mock(), {"WOLFLAUNCHER_SMOKE_VALIDATE_UI": "1"}
                )
            )
            schedule.assert_not_called()
            app, window = Mock(), Mock()
            environment = {"WOLFLAUNCHER_SMOKE_TEST": "1", "WOLFLAUNCHER_SMOKE_VALIDATE_UI": "1"}
            self.assertTrue(configure_packaged_smoke_test(app, window, environment))
            schedule.assert_called_once_with(app, window, environment)

    def test_validation_rejects_default_and_nonisolated_paths(self):
        window = Mock()
        with self.assertRaises(ValueError):
            isolated_root({}, window)
        with tempfile.TemporaryDirectory(prefix="wolf-validation-test-") as directory:
            root = Path(directory)
            window.server_cache.execute.return_value.fetchone.return_value = (
                0,
                "main",
                str(root / "db.sqlite3"),
            )
            with (
                patch(
                    "wolflauncher.packaged_validation.user_config_dir", return_value=root / "config"
                ),
                patch("wolflauncher.packaged_validation.user_data_dir", return_value=root / "data"),
            ):
                self.assertEqual(
                    isolated_root({"WOLFLAUNCHER_SMOKE_ROOT": directory}, window), root
                )
            with (
                patch(
                    "wolflauncher.packaged_validation.user_config_dir",
                    return_value=Path("/outside"),
                ),
                patch("wolflauncher.packaged_validation.user_data_dir", return_value=root / "data"),
            ):
                with self.assertRaises(ValueError):
                    isolated_root({"WOLFLAUNCHER_SMOKE_ROOT": directory}, window)

    def test_failure_marks_exit_status_and_requests_normal_shutdown(self):
        validation = object.__new__(PackagedValidation)
        validation.started = validation.last_tick = 1
        validation.max_tick_gap_ms = 0
        validation.phase = 2
        validation.timer, validation.app, validation.window = Mock(), Mock(), Mock()
        validation.step = Mock(side_effect=AssertionError("wrong rows"))
        with (
            patch("wolflauncher.packaged_validation.time.monotonic", return_value=2),
            patch("builtins.print") as output,
        ):
            validation.tick()
        validation.timer.stop.assert_called_once()
        validation.app.setProperty.assert_called_once_with("packagedValidationFailed", True)
        validation.window.close.assert_called_once()
        self.assertIn('"packaged_validation": "failed"', output.call_args.args[0])
