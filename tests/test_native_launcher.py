import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wolflauncher.models import Server
from wolflauncher.mods import RequiredMod
from wolflauncher.native_launcher import (
    NativeLaunchError,
    build_steam_launch_command,
    compact_mod_link_name,
    prepare_mod_links,
    prepare_native_launch,
    prepare_native_launch_parity_report,
    prepare_native_launch_preview,
)
from wolflauncher.platform_detection import FLATPAK_STEAM_ID, SteamInstall


def make_server(host: str = "dayz.example.test") -> Server:
    return Server(
        name="Example",
        group="Tests",
        host=host,
        game_port=2302,
        query_port=27016,
    )


def make_install(root: Path, mode: str = "native") -> SteamInstall:
    steamapps = root / "steamapps"
    dayz_dir = steamapps / "common" / "DayZ"
    workshop_dir = steamapps / "workshop" / "content" / "221100"
    dayz_dir.mkdir(parents=True)
    workshop_dir.mkdir(parents=True)
    return SteamInstall(
        mode=mode,
        executable=FLATPAK_STEAM_ID if mode == "flatpak" else "steam",
        running=True,
        root=root,
        steamapps=steamapps,
        dayz_dir=dayz_dir,
        workshop_dir=workshop_dir,
    )


class NativeLauncherTests(unittest.TestCase):
    def test_compact_mod_link_name_matches_legacy_little_endian_base64(self):
        self.assertEqual(compact_mod_link_name("1"), "@AQ")
        self.assertEqual(compact_mod_link_name("248"), "@_A")
        self.assertEqual(compact_mod_link_name("255"), "@-w")
        self.assertEqual(compact_mod_link_name("256"), "@AAE")
        self.assertEqual(compact_mod_link_name("4294967295"), "@-----w")

    def test_builds_native_steam_launch_command(self):
        install = SteamInstall(
            mode="native",
            executable="/usr/bin/steam",
            running=True,
            root=None,
            steamapps=None,
            dayz_dir=None,
            workshop_dir=None,
        )

        command = build_steam_launch_command(
            install,
            make_server("203.0.113.10"),
            "Wolf Player",
            ["@AQ", "@AAE"],
            ["-nosplash"],
        )

        self.assertEqual(
            command,
            [
                "/usr/bin/steam",
                "-applaunch",
                "221100",
                "-mod=@AQ;@AAE",
                "-connect=203.0.113.10:2302",
                "-nolauncher",
                "-world=empty",
                "-name=Wolf Player",
                "-nosplash",
            ],
        )

    def test_builds_flatpak_steam_launch_command(self):
        install = SteamInstall(
            mode="flatpak",
            executable=FLATPAK_STEAM_ID,
            running=True,
            root=None,
            steamapps=None,
            dayz_dir=None,
            workshop_dir=None,
        )

        command = build_steam_launch_command(install, make_server("203.0.113.10"), "", [])

        self.assertEqual(
            command,
            [
                "flatpak",
                "run",
                "--branch=stable",
                "--arch=x86_64",
                "--command=/app/bin/steam-wrapper",
                FLATPAK_STEAM_ID,
                "-applaunch",
                "221100",
                "-connect=203.0.113.10:2302",
                "-nolauncher",
                "-world=empty",
            ],
        )

    def test_build_native_command_requires_detected_steam_executable(self):
        install = SteamInstall(
            mode="native",
            executable="",
            running=False,
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            dayz_dir=None,
            workshop_dir=None,
        )

        with self.assertRaisesRegex(NativeLaunchError, "native Steam executable not detected") as raised:
            build_steam_launch_command(install, make_server("203.0.113.10"), "PlayerOne", [])

        self.assertEqual(raised.exception.stage, "Steam detection")
        self.assertIn("steam command available on PATH", raised.exception.user_message())

    def test_build_flatpak_command_requires_detected_flatpak_command(self):
        install = SteamInstall(
            mode="flatpak",
            executable="",
            running=False,
            root=Path("/flatpak/Steam"),
            steamapps=Path("/flatpak/Steam/steamapps"),
            dayz_dir=None,
            workshop_dir=None,
        )

        with self.assertRaisesRegex(NativeLaunchError, "Flatpak Steam command not detected") as raised:
            build_steam_launch_command(install, make_server("203.0.113.10"), "PlayerOne", [])

        self.assertEqual(raised.exception.stage, "Steam detection")
        self.assertIn("flatpak command is available", raised.exception.user_message())

    def test_build_steam_root_command_requires_native_steam_executable(self):
        install = SteamInstall(
            mode="STEAM_ROOT env",
            executable="",
            running=False,
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            dayz_dir=None,
            workshop_dir=None,
        )

        with self.assertRaisesRegex(NativeLaunchError, "STEAM_ROOT env Steam executable not detected") as raised:
            build_steam_launch_command(install, make_server("203.0.113.10"), "PlayerOne", [])

        self.assertEqual(raised.exception.stage, "Steam detection")
        self.assertIn("points WolfLauncher at a Steam library", raised.exception.user_message())

    def test_prepare_native_launch_creates_relative_mod_symlinks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            mod_dir = install.workshop_dir / "256"
            mod_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Example Mod";\n', encoding="utf-8")

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                prepared = prepare_native_launch(
                    install,
                    make_server(),
                    "PlayerOne",
                    [RequiredMod("256", "Example Mod")],
                )

            link_path = install.dayz_dir / "@AAE"
            self.assertTrue(link_path.is_symlink())
            self.assertEqual(Path(link_path.readlink()), Path("../../workshop/content/221100/256"))
            self.assertEqual(prepared.mod_links, ["@AAE"])
            self.assertEqual(prepared.prepared_mods[0].name, "Example Mod")
            self.assertTrue(prepared.prepared_mods[0].created)
            self.assertIn("-mod=@AAE", prepared.command)
            self.assertIn("-connect=203.0.113.10:2302", prepared.command)

    def test_prepare_mod_links_collects_missing_mods_without_aborting_installed_mods(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            mod_dir = install.workshop_dir / "256"
            mod_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Example Mod";\n', encoding="utf-8")

            setup = prepare_mod_links(
                install.dayz_dir,
                install.workshop_dir,
                [RequiredMod("111"), RequiredMod("256")],
            )

            self.assertEqual(setup.missing_mod_ids, ["111"])
            self.assertEqual(setup.mod_links, ["@AAE"])
            self.assertEqual(setup.prepared_mods[0].workshop_id, "256")
            self.assertEqual(setup.prepared_mods[0].link_path, install.dayz_dir / "@AAE")

    def test_prepare_mod_links_reports_existing_symlink_without_recreating_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            mod_dir = install.workshop_dir / "256"
            mod_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Example Mod";\n', encoding="utf-8")
            link_path = install.dayz_dir / "@AAE"
            link_path.symlink_to("../../workshop/content/221100/256")

            setup = prepare_mod_links(install.dayz_dir, install.workshop_dir, [RequiredMod("256")])

            self.assertFalse(setup.prepared_mods[0].created)
            self.assertEqual(Path(link_path.readlink()), Path("../../workshop/content/221100/256"))

    def test_prepare_native_launch_preview_reports_missing_mods_without_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            mod_dir = install.workshop_dir / "256"
            mod_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Example Mod";\n', encoding="utf-8")

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                preview = prepare_native_launch_preview(
                    install,
                    make_server(),
                    "PlayerOne",
                    [RequiredMod("111"), RequiredMod("256")],
                )

            self.assertFalse(preview.ready)
            self.assertEqual(preview.command, [])
            self.assertEqual(preview.server.host, "203.0.113.10")
            self.assertEqual(preview.mod_setup.missing_mod_ids, ["111"])
            self.assertEqual(preview.mod_setup.mod_links, ["@AAE"])

    def test_prepare_native_launch_preview_builds_command_when_ready(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            mod_dir = install.workshop_dir / "256"
            mod_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Example Mod";\n', encoding="utf-8")

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                preview = prepare_native_launch_preview(
                    install,
                    make_server(),
                    "PlayerOne",
                    [RequiredMod("256")],
                )

            self.assertTrue(preview.ready)
            self.assertIn("-mod=@AAE", preview.command)
            self.assertIn("-connect=203.0.113.10:2302", preview.command)

    def test_prepare_native_launch_parity_report_compares_external_and_native_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            launcher = Path(tmpdir) / "dayz-launcher.sh"
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")
            mod_dir = install.workshop_dir / "256"
            mod_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Example Mod";\n', encoding="utf-8")

            report = prepare_native_launch_parity_report(
                install,
                str(launcher),
                make_server("203.0.113.10"),
                "PlayerOne",
                [RequiredMod("256", "Example Mod")],
            )

            self.assertTrue(report.preview.ready)
            self.assertEqual(report.resolved_connect, "203.0.113.10:2302")
            self.assertEqual(report.required_mod_ids, ["256"])
            self.assertEqual(report.preview.mod_setup.mod_links, ["@AAE"])
            self.assertEqual(
                report.external_command,
                [
                    "bash",
                    str(launcher),
                    "-s",
                    "203.0.113.10:2302",
                    "-p",
                    "27016",
                    "-n",
                    "PlayerOne",
                    "--launch",
                ],
            )
            self.assertIn("-connect=203.0.113.10:2302", report.preview.command)

    def test_prepare_native_launch_parity_report_keeps_native_preview_when_external_path_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))

            report = prepare_native_launch_parity_report(
                install,
                str(Path(tmpdir) / "missing-launcher.sh"),
                make_server("203.0.113.10"),
                "PlayerOne",
                [],
            )

            self.assertTrue(report.preview.ready)
            self.assertEqual(report.external_command, [])
            self.assertIn("Launcher script not found", report.external_error)

    def test_prepare_native_launch_reports_missing_mods(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                with self.assertRaisesRegex(NativeLaunchError, "Missing mod directories for: 111") as raised:
                    prepare_native_launch(install, make_server(), "PlayerOne", [RequiredMod("111")])
        self.assertEqual(raised.exception.stage, "mod setup")
        self.assertIn("Open the missing Workshop pages", raised.exception.user_message())

    def test_prepare_native_launch_requires_mod_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            (install.workshop_dir / "111").mkdir()

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                with self.assertRaisesRegex(NativeLaunchError, "Missing mod metadata for: 111") as raised:
                    prepare_native_launch(install, make_server(), "PlayerOne", [RequiredMod("111")])
        self.assertEqual(raised.exception.stage, "mod setup")
        self.assertIn("redownload the Workshop item", raised.exception.user_message())

    def test_prepare_native_launch_requires_mod_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            mod_dir = install.workshop_dir / "111"
            mod_dir.mkdir()
            (mod_dir / "meta.cpp").write_text("// no display name\n", encoding="utf-8")

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                with self.assertRaisesRegex(NativeLaunchError, "Missing mod name for: 111"):
                    prepare_native_launch(install, make_server(), "PlayerOne", [RequiredMod("111")])

    def test_prepare_native_launch_wraps_dns_failures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))

            with patch("wolflauncher.native_launcher.resolve_host", side_effect=OSError("no host")):
                with self.assertRaisesRegex(NativeLaunchError, "Could not resolve server host") as raised:
                    prepare_native_launch(install, make_server(), "PlayerOne", [])
        self.assertEqual(raised.exception.stage, "server DNS")
        self.assertIn("network connection and DNS", raised.exception.user_message())


if __name__ == "__main__":
    unittest.main()
