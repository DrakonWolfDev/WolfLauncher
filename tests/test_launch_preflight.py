import unittest
from pathlib import Path

from wolflauncher.launch_preflight import (
    LaunchPreflightAction,
    LaunchPreflightState,
    build_launch_preflight_state,
    matching_mod_result,
    next_launch_preflight_action,
    usable_mod_result,
)
from wolflauncher.models import Server
from wolflauncher.mods import ModCheckResult, RequiredMod
from wolflauncher.platform_detection import SteamInstall


class LaunchPreflightTests(unittest.TestCase):
    def state(self, **overrides):
        values = {
            "has_install": True,
            "has_dayz": True,
            "has_workshop": True,
            "steam_running": True,
            "mods_checked": True,
            "missing_mod_count": 0,
            "native_engine": True,
        }
        values.update(overrides)
        return LaunchPreflightState(**values)

    def test_ready_when_environment_and_mods_are_ready(self):
        self.assertEqual(
            next_launch_preflight_action(self.state()),
            LaunchPreflightAction.READY,
        )

    def test_missing_install_or_dayz_blocks_before_other_checks(self):
        for overrides in ({"has_install": False}, {"has_dayz": False}):
            with self.subTest(overrides=overrides):
                self.assertEqual(
                    next_launch_preflight_action(
                        self.state(steam_running=False, mods_checked=False, **overrides)
                    ),
                    LaunchPreflightAction.BLOCK_MISSING_DAYZ,
                )

    def test_missing_workshop_blocks_before_steam_and_mod_checks(self):
        self.assertEqual(
            next_launch_preflight_action(
                self.state(has_workshop=False, steam_running=False, mods_checked=False)
            ),
            LaunchPreflightAction.BLOCK_MISSING_WORKSHOP,
        )

    def test_stopped_steam_requires_confirmation_then_continues(self):
        state = self.state(steam_running=False, mods_checked=False)
        self.assertEqual(
            next_launch_preflight_action(state),
            LaunchPreflightAction.CONFIRM_STEAM_STOPPED,
        )
        self.assertEqual(
            next_launch_preflight_action(state, steam_stopped_confirmed=True),
            LaunchPreflightAction.CONFIRM_MODS_UNCHECKED,
        )

    def test_unchecked_mods_require_confirmation(self):
        self.assertEqual(
            next_launch_preflight_action(self.state(mods_checked=False)),
            LaunchPreflightAction.CONFIRM_MODS_UNCHECKED,
        )

    def test_native_engine_blocks_missing_mods(self):
        self.assertEqual(
            next_launch_preflight_action(self.state(missing_mod_count=2)),
            LaunchPreflightAction.BLOCK_NATIVE_MISSING_MODS,
        )

    def test_external_engine_can_confirm_missing_mods(self):
        self.assertEqual(
            next_launch_preflight_action(self.state(native_engine=False, missing_mod_count=2)),
            LaunchPreflightAction.CONFIRM_EXTERNAL_MISSING_MODS,
        )

    def test_state_uses_successful_mod_check_for_selected_server(self):
        server = Server("Selected", "Tests", "dayz.test", 2302, 27016)
        result = ModCheckResult(
            ok=True,
            server=server,
            required_mods=[RequiredMod("123", installed=False)],
            workshop_dir=str(Path("/steam/workshop/content/221100")),
        )
        install = SteamInstall(
            mode="native",
            executable="steam",
            running=True,
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            dayz_dir=Path("/steam/DayZ"),
            workshop_dir=Path("/steam/workshop/content/221100"),
        )

        state = build_launch_preflight_state(install, server, result, native_engine=True)

        self.assertTrue(state.mods_checked)
        self.assertEqual(state.missing_mod_count, 1)
        self.assertTrue(state.has_dayz)
        self.assertTrue(state.has_workshop)

    def test_failed_mod_check_is_not_treated_as_checked(self):
        server = Server("Selected", "Tests", "dayz.test", 2302, 27016)
        failed = ModCheckResult(ok=False, server=server, required_mods=[], error="API unavailable")

        state = build_launch_preflight_state(None, server, failed, native_engine=True)

        self.assertFalse(state.mods_checked)
        self.assertEqual(state.missing_mod_count, 0)

    def test_stale_mod_check_for_another_server_is_not_reused(self):
        server = Server("Selected", "Tests", "dayz.test", 2302, 27016)
        other = Server("Other", "Tests", "other.test", 2302, 27016)
        stale = ModCheckResult(
            ok=True,
            server=other,
            required_mods=[RequiredMod("123", installed=False)],
        )

        state = build_launch_preflight_state(None, server, stale, native_engine=False)

        self.assertFalse(state.mods_checked)
        self.assertEqual(state.missing_mod_count, 0)

    def test_only_successful_matching_mod_result_is_usable_for_launch(self):
        server = Server("Selected", "Tests", "dayz.test", 2302, 27016)
        other = Server("Other", "Tests", "other.test", 2302, 27016)
        current = ModCheckResult(ok=True, server=server, required_mods=[])
        failed = ModCheckResult(ok=False, server=server, required_mods=[], error="failed")
        stale = ModCheckResult(ok=True, server=other, required_mods=[])

        self.assertIs(usable_mod_result(server, current), current)
        self.assertIsNone(usable_mod_result(server, failed))
        self.assertIsNone(usable_mod_result(server, stale))
        self.assertIsNone(usable_mod_result(server, None))

    def test_matching_failed_result_remains_available_for_support_report(self):
        server = Server("Selected", "Tests", "dayz.test", 2302, 27016)
        other = Server("Other", "Tests", "other.test", 2302, 27016)
        failed = ModCheckResult(ok=False, server=server, required_mods=[], error="failed")
        stale = ModCheckResult(ok=False, server=other, required_mods=[], error="stale")

        self.assertIs(matching_mod_result(server, failed), failed)
        self.assertIsNone(matching_mod_result(server, stale))

    def test_matching_result_requires_current_workshop_context_when_provided(self):
        server = Server("Selected", "Tests", "dayz.test", 2302, 27016)
        result = ModCheckResult(
            ok=True,
            server=server,
            required_mods=[],
            workshop_dir=str(Path("/steam-a/workshop/content/221100")),
        )

        self.assertIs(
            matching_mod_result(server, result, Path("/steam-a/workshop/content/221100")),
            result,
        )
        self.assertIsNone(
            matching_mod_result(server, result, Path("/steam-b/workshop/content/221100"))
        )
        self.assertIsNone(
            usable_mod_result(server, result, Path("/steam-b/workshop/content/221100"))
        )


if __name__ == "__main__":
    unittest.main()
