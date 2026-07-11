import unittest

from wolflauncher.launch_preflight import (
    LaunchPreflightAction,
    LaunchPreflightState,
    next_launch_preflight_action,
)


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
            next_launch_preflight_action(
                self.state(native_engine=False, missing_mod_count=2)
            ),
            LaunchPreflightAction.CONFIRM_EXTERNAL_MISSING_MODS,
        )


if __name__ == "__main__":
    unittest.main()
