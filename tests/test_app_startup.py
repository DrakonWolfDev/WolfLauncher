import unittest
from unittest.mock import Mock, patch

from wolflauncher.app import configure_packaged_smoke_test


class PackagedSmokeTestConfigurationTests(unittest.TestCase):
    @patch("wolflauncher.app.QTimer.singleShot")
    def test_smoke_mode_closes_window_and_sets_failure_watchdog(self, single_shot):
        app = Mock()
        window = Mock()

        enabled = configure_packaged_smoke_test(app, window, {"WOLFLAUNCHER_SMOKE_TEST": "1"})

        self.assertTrue(enabled)
        self.assertEqual(single_shot.call_args_list[0].args, (1000, window.close))
        self.assertEqual(single_shot.call_args_list[1].args, (5000, window.close))
        self.assertEqual(single_shot.call_args_list[2].args, (10000, window.close))
        self.assertEqual(single_shot.call_args_list[3].args[0], 30000)
        single_shot.call_args_list[3].args[1]()
        app.exit.assert_called_once_with(124)

    @patch("wolflauncher.app.QTimer.singleShot")
    def test_normal_startup_does_not_schedule_smoke_shutdown(self, single_shot):
        enabled = configure_packaged_smoke_test(Mock(), Mock(), {})

        self.assertFalse(enabled)
        single_shot.assert_not_called()

    @patch("wolflauncher.app.QTimer.singleShot")
    def test_smoke_mode_can_require_a_usable_keyring(self, single_shot):
        app = Mock()
        window = Mock()
        window.secret_store.available.return_value = False

        enabled = configure_packaged_smoke_test(
            app,
            window,
            {
                "WOLFLAUNCHER_SMOKE_TEST": "1",
                "WOLFLAUNCHER_SMOKE_REQUIRE_KEYRING": "1",
            },
        )

        self.assertTrue(enabled)
        single_shot.assert_called_once()
        single_shot.call_args.args[1]()
        app.exit.assert_called_once_with(125)
