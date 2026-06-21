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
    prepare_native_launch,
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
            self.assertIn("-mod=@AAE", prepared.command)
            self.assertIn("-connect=203.0.113.10:2302", prepared.command)

    def test_prepare_native_launch_reports_missing_mods(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                with self.assertRaisesRegex(NativeLaunchError, "Missing mod directories for: 111"):
                    prepare_native_launch(install, make_server(), "PlayerOne", [RequiredMod("111")])

    def test_prepare_native_launch_requires_mod_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            (install.workshop_dir / "111").mkdir()

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                with self.assertRaisesRegex(NativeLaunchError, "Missing mod metadata for: 111"):
                    prepare_native_launch(install, make_server(), "PlayerOne", [RequiredMod("111")])

    def test_prepare_native_launch_wraps_dns_failures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))

            with patch("wolflauncher.native_launcher.resolve_host", side_effect=OSError("no host")):
                with self.assertRaisesRegex(NativeLaunchError, "Could not resolve server host"):
                    prepare_native_launch(install, make_server(), "PlayerOne", [])


if __name__ == "__main__":
    unittest.main()
