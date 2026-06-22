import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from wolflauncher.models import Server
from wolflauncher.mods import RequiredMod
from wolflauncher.native_launcher import (
    NativeLaunchError,
    build_steam_launch_command,
    compact_mod_link_name,
    format_native_launch_parity_report,
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
    compatdata_dir = steamapps / "compatdata" / "221100"
    dayz_dir.mkdir(parents=True)
    workshop_dir.mkdir(parents=True)
    compatdata_dir.mkdir(parents=True)
    return SteamInstall(
        mode=mode,
        executable=FLATPAK_STEAM_ID if mode == "flatpak" else "steam",
        running=True,
        root=root,
        steamapps=steamapps,
        dayz_dir=dayz_dir,
        workshop_dir=workshop_dir,
        compatdata_dir=compatdata_dir,
    )


class NativeLauncherTests(unittest.TestCase):
    def test_native_launch_error_can_carry_copyable_details(self):
        error = NativeLaunchError(
            "Missing mod directories for: 111",
            stage="mod setup",
            guidance="Open the missing Workshop pages.",
        )

        detailed = error.with_details("Native launch parity report\n- Missing Workshop directories: 1")

        self.assertIsNot(detailed, error)
        self.assertEqual(detailed.stage, "mod setup")
        self.assertEqual(detailed.user_message(), error.user_message())
        self.assertIn("Native launch parity report", detailed.details)
        self.assertEqual(error.details, "")

    def test_native_launch_error_ignores_empty_details(self):
        error = NativeLaunchError("Steam not detected")

        self.assertIs(error.with_details(""), error)

    def test_native_launch_error_preserves_existing_details_when_wrapping(self):
        error = NativeLaunchError("Mod setup failed", details="Expected target: good")

        detailed = error.with_details("Native launch parity report unavailable.")

        self.assertIn("Expected target: good", detailed.details)
        self.assertIn("Native launch parity report unavailable.", detailed.details)

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
                "-name=Survivor",
            ],
        )

    def test_build_native_command_defaults_blank_player_name_to_external_launcher_default(self):
        install = SteamInstall(
            mode="native",
            executable="/usr/bin/steam",
            running=True,
            root=None,
            steamapps=None,
            dayz_dir=None,
            workshop_dir=None,
        )

        command = build_steam_launch_command(install, make_server("203.0.113.10"), "  ", [])

        self.assertIn("-name=Survivor", command)

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

    def test_build_steam_root_command_uses_detected_native_steam_executable(self):
        install = SteamInstall(
            mode="STEAM_ROOT env",
            executable="/usr/bin/steam",
            running=False,
            root=Path("/steam-library"),
            steamapps=Path("/steam-library/steamapps"),
            dayz_dir=None,
            workshop_dir=None,
        )

        command = build_steam_launch_command(install, make_server("203.0.113.10"), "PlayerOne", [])

        self.assertEqual(command[0], "/usr/bin/steam")
        self.assertIn("-applaunch", command)
        self.assertIn("-connect=203.0.113.10:2302", command)

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

    def test_prepare_mod_links_reuses_symlink_created_by_previous_preview(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            mod_dir = install.workshop_dir / "256"
            mod_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Example Mod";\n', encoding="utf-8")

            first = prepare_mod_links(install.dayz_dir, install.workshop_dir, [RequiredMod("256")])
            second = prepare_mod_links(install.dayz_dir, install.workshop_dir, [RequiredMod("256")])

            self.assertTrue(first.prepared_mods[0].created)
            self.assertFalse(second.prepared_mods[0].created)
            self.assertEqual(first.mod_links, second.mod_links)
            self.assertEqual(Path((install.dayz_dir / "@AAE").readlink()), Path("../../workshop/content/221100/256"))

    def test_prepare_mod_links_rejects_stale_mod_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            mod_dir = install.workshop_dir / "256"
            stale_dir = install.workshop_dir / "999"
            mod_dir.mkdir()
            stale_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Example Mod";\n', encoding="utf-8")
            link_path = install.dayz_dir / "@AAE"
            link_path.symlink_to("../../workshop/content/221100/999")

            with self.assertRaisesRegex(NativeLaunchError, "points somewhere else") as raised:
                prepare_mod_links(install.dayz_dir, install.workshop_dir, [RequiredMod("256")])

            self.assertEqual(raised.exception.stage, "mod setup")
            self.assertIn("Remove the stale @mod symlink", raised.exception.user_message())
            self.assertIn("Stale @mod symlink conflict:", raised.exception.details)
            self.assertIn(f"- Link: {link_path}", raised.exception.details)
            self.assertIn("- Expected target: ../../workshop/content/221100/256", raised.exception.details)
            self.assertIn("- Actual target: ../../workshop/content/221100/999", raised.exception.details)
            self.assertIn(f"- Expected resolved path: {mod_dir}", raised.exception.details)
            self.assertIn(f"- Actual resolved path: {stale_dir}", raised.exception.details)

    def test_prepare_native_launch_wraps_stale_symlink_details_with_failure_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            mod_dir = install.workshop_dir / "256"
            stale_dir = install.workshop_dir / "999"
            mod_dir.mkdir()
            stale_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Example Mod";\n', encoding="utf-8")
            link_path = install.dayz_dir / "@AAE"
            link_path.symlink_to("../../workshop/content/221100/999")

            with self.assertRaisesRegex(NativeLaunchError, "points somewhere else") as raised:
                try:
                    prepare_native_launch(
                        install,
                        make_server("203.0.113.10"),
                        "PlayerOne",
                        [RequiredMod("256", "Example Mod")],
                    )
                except NativeLaunchError as exc:
                    raise exc.with_details(
                        "Native launch parity report unavailable.\n\n"
                        f"Report generation failed during {exc.stage}: {exc.user_message()}"
                    )

            self.assertIn("Stale @mod symlink conflict:", raised.exception.details)
            self.assertIn("- Expected target: ../../workshop/content/221100/256", raised.exception.details)
            self.assertIn("- Actual target: ../../workshop/content/221100/999", raised.exception.details)
            self.assertIn(f"- Expected resolved path: {mod_dir}", raised.exception.details)
            self.assertIn(f"- Actual resolved path: {stale_dir}", raised.exception.details)
            self.assertIn("Native launch parity report unavailable.", raised.exception.details)

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

    def test_prepare_native_launch_preview_handles_no_required_mods_as_ready(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                preview = prepare_native_launch_preview(
                    install,
                    make_server(),
                    "PlayerOne",
                    [],
                )

            self.assertTrue(preview.ready)
            self.assertEqual(preview.mod_setup.missing_mod_ids, [])
            self.assertEqual(preview.mod_setup.prepared_mods, [])
            self.assertNotIn("-mod=", " ".join(preview.command))
            self.assertIn("-connect=203.0.113.10:2302", preview.command)

    def test_prepare_native_launch_preview_blocks_when_all_mods_are_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                preview = prepare_native_launch_preview(
                    install,
                    make_server(),
                    "PlayerOne",
                    [RequiredMod("111", "First Missing"), RequiredMod("222", "Second Missing")],
                )

            self.assertFalse(preview.ready)
            self.assertEqual(preview.command, [])
            self.assertEqual(preview.mod_setup.mod_links, [])
            self.assertEqual(preview.mod_setup.missing_mod_ids, ["111", "222"])

    def test_prepare_native_launch_preview_keeps_installed_links_when_some_mods_are_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            mod_dir = install.workshop_dir / "256"
            mod_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Installed Mod";\n', encoding="utf-8")

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                preview = prepare_native_launch_preview(
                    install,
                    make_server(),
                    "PlayerOne",
                    [RequiredMod("111", "Missing Mod"), RequiredMod("256", "Installed Mod")],
                )

            self.assertFalse(preview.ready)
            self.assertEqual(preview.command, [])
            self.assertEqual(preview.mod_setup.missing_mod_ids, ["111"])
            self.assertEqual(preview.mod_setup.mod_links, ["@AAE"])
            self.assertEqual(preview.mod_setup.prepared_mods[0].workshop_id, "256")

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

    def test_prepare_native_launch_preview_reports_selected_mode_missing_workshop_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dayz_dir = root / "steamapps" / "common" / "DayZ"
            dayz_dir.mkdir(parents=True)
            install = SteamInstall(
                mode="flatpak",
                executable=FLATPAK_STEAM_ID,
                running=True,
                root=root,
                steamapps=root / "steamapps",
                dayz_dir=dayz_dir,
                workshop_dir=None,
            )

            with self.assertRaisesRegex(NativeLaunchError, "DayZ Workshop directory not detected") as raised:
                prepare_native_launch_preview(
                    install,
                    make_server("203.0.113.10"),
                    "PlayerOne",
                    [RequiredMod("111")],
                )

        self.assertEqual(raised.exception.stage, "Steam library detection")
        self.assertIn("selected Steam library", raised.exception.user_message())
        self.assertIn("Workshop folder is visible", raised.exception.user_message())

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
                selected_steam_mode="flatpak",
            )

            self.assertTrue(report.preview.ready)
            self.assertEqual(report.selected_steam_mode, "flatpak")
            self.assertEqual(report.resolved_connect, "203.0.113.10:2302")
            self.assertEqual(report.required_mod_ids, ["256"])
            self.assertEqual(report.required_mod_labels, ["Example Mod (256)"])
            self.assertEqual(report.missing_mod_labels, [])
            self.assertEqual(report.preview.mod_setup.mod_links, ["@AAE"])
            self.assertIn("-connect=203.0.113.10:2302", report.native_command_text)
            self.assertIn("-s 203.0.113.10:2302", report.external_command_text)
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

    def test_prepare_native_launch_parity_report_reuses_resolved_preview_target_for_external_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            launcher = Path(tmpdir) / "dayz-launcher.sh"
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                with patch("wolflauncher.launcher.resolve_host", side_effect=lambda host: host) as external_resolve:
                    report = prepare_native_launch_parity_report(
                        install,
                        str(launcher),
                        make_server(),
                        "PlayerOne",
                        [],
                    )

            self.assertEqual(report.resolved_connect, "203.0.113.10:2302")
            self.assertIn("-s 203.0.113.10:2302", report.external_command_text)
            external_resolve.assert_called_once_with("203.0.113.10")

    def test_format_native_launch_parity_report_includes_copyable_validation_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir), mode="flatpak")
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
                selected_steam_mode="auto",
            )

            text = format_native_launch_parity_report(
                report,
                generated_at=datetime(2026, 6, 21, 15, 16, 59, tzinfo=timezone.utc),
            )

            self.assertIn("Native launch parity report", text)
            self.assertIn("Generated at: 2026-06-21T15:16:59+00:00", text)
            self.assertIn("- Steam install setting: Auto", text)
            self.assertIn("- Steam mode: Flatpak Steam", text)
            self.assertIn("- Steam command: flatpak run com.valvesoftware.Steam", text)
            self.assertIn(f"- Proton compatdata: {install.compatdata_dir}", text)
            self.assertIn(f"- DayZ path: {install.dayz_dir}", text)
            self.assertIn("- Required mod count: 1", text)
            self.assertIn("- Prepared native mod links: 1", text)
            self.assertIn("- Created native mod links: 1", text)
            self.assertIn("- Reused native mod links: 0", text)
            self.assertIn("- Missing Workshop directories: 0", text)
            self.assertIn("- Native ready: yes", text)
            self.assertIn("Readiness comparison:", text)
            self.assertIn(
                "- External launcher: ready; command can be handed to the configured external launcher",
                text,
            )
            self.assertIn("- Native launcher: ready; 1 local Workshop link(s) prepared", text)
            self.assertIn("- Connect target: 203.0.113.10:2302", text)
            self.assertIn("- Query port: 27016", text)
            self.assertIn("- Required mods from current check: 1", text)
            self.assertIn(
                "- External mod source: external launcher refetches server requirements at launch",
                text,
            )
            self.assertIn(
                "- Native mod source: current WolfLauncher mod check and prepared local Workshop links",
                text,
            )
            self.assertIn("External launcher handoff:\n- Ready: yes", text)
            self.assertIn("Native command is ready for 203.0.113.10:2302 with 1 prepared mod link(s).", text)
            self.assertIn("Required Workshop mods:\n- Example Mod (256)", text)
            self.assertIn("Example Mod (256) -> @AAE", text)
            self.assertIn("-connect=203.0.113.10:2302", text)
            self.assertIn("-s 203.0.113.10:2302", text)

    def test_format_native_launch_parity_report_counts_reused_mod_links(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            launcher = Path(tmpdir) / "dayz-launcher.sh"
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")
            mod_dir = install.workshop_dir / "256"
            mod_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Example Mod";\n', encoding="utf-8")
            prepare_mod_links(install.dayz_dir, install.workshop_dir, [RequiredMod("256")])

            report = prepare_native_launch_parity_report(
                install,
                str(launcher),
                make_server("203.0.113.10"),
                "PlayerOne",
                [RequiredMod("256", "Example Mod")],
            )

            text = format_native_launch_parity_report(report)

            self.assertIn("- Created native mod links: 0", text)
            self.assertIn("- Reused native mod links: 1", text)
            self.assertIn("Example Mod (256) -> @AAE [already existed]", text)

    def test_format_native_launch_parity_report_explains_missing_compatdata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            steamapps = root / "steamapps"
            dayz_dir = steamapps / "common" / "DayZ"
            workshop_dir = steamapps / "workshop" / "content" / "221100"
            dayz_dir.mkdir(parents=True)
            workshop_dir.mkdir(parents=True)
            launcher = root / "dayz-launcher.sh"
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")
            install = SteamInstall(
                mode="native",
                executable="steam",
                running=False,
                root=root,
                steamapps=steamapps,
                dayz_dir=dayz_dir,
                workshop_dir=workshop_dir,
            )

            report = prepare_native_launch_parity_report(
                install,
                str(launcher),
                make_server("203.0.113.10"),
                "PlayerOne",
                [],
            )

            text = format_native_launch_parity_report(report)

            self.assertIn(
                "- Proton compatdata: not detected yet; Steam may create it on first Proton launch",
                text,
            )

    def test_format_native_launch_parity_report_keeps_missing_mod_preview_copyable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            launcher = Path(tmpdir) / "dayz-launcher.sh"
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")

            report = prepare_native_launch_parity_report(
                install,
                str(launcher),
                make_server("203.0.113.10"),
                "PlayerOne",
                [RequiredMod("111", "Missing Mod")],
            )

            text = format_native_launch_parity_report(report)

            self.assertFalse(report.preview.ready)
            self.assertEqual(report.native_command_text, "")
            self.assertEqual(report.required_mod_labels, ["Missing Mod (111)"])
            self.assertEqual(report.missing_mod_labels, ["Missing Mod (111)"])
            self.assertIn("- Missing Workshop directories: 1", text)
            self.assertIn("- Native ready: no", text)
            self.assertIn("- Native launcher: blocked; 1 required Workshop directory is missing", text)
            self.assertIn("Native command is not ready because 1 Workshop directory is missing.", text)
            self.assertIn("Missing Workshop mod directories:\n- Missing Mod (111)", text)
            self.assertIn("Native Steam command: not ready until all required mods are installed.", text)

    def test_format_native_launch_parity_report_handles_all_missing_mods(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            launcher = Path(tmpdir) / "dayz-launcher.sh"
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")

            report = prepare_native_launch_parity_report(
                install,
                str(launcher),
                make_server("203.0.113.10"),
                "PlayerOne",
                [RequiredMod("111", "First Missing"), RequiredMod("222", "Second Missing")],
            )

            text = format_native_launch_parity_report(report)

            self.assertFalse(report.preview.ready)
            self.assertEqual(report.preview.mod_setup.prepared_mods, [])
            self.assertEqual(report.preview.mod_setup.missing_mod_ids, ["111", "222"])
            self.assertEqual(report.missing_mod_labels, ["First Missing (111)", "Second Missing (222)"])
            self.assertIn("- Required mod count: 2", text)
            self.assertIn("- Prepared native mod links: 0", text)
            self.assertIn("- Missing Workshop directories: 2", text)
            self.assertIn("- Native launcher: blocked; 2 required Workshop directories are missing", text)
            self.assertIn("Native command is not ready because 2 Workshop directories are missing.", text)
            self.assertIn("Missing Workshop mod directories:\n- First Missing (111)\n- Second Missing (222)", text)
            self.assertIn("Native Steam command: not ready until all required mods are installed.", text)

    def test_format_native_launch_parity_report_handles_mixed_installed_and_missing_mods(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))
            launcher = Path(tmpdir) / "dayz-launcher.sh"
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")
            mod_dir = install.workshop_dir / "256"
            mod_dir.mkdir()
            (mod_dir / "meta.cpp").write_text('name = "Installed Mod";\n', encoding="utf-8")

            report = prepare_native_launch_parity_report(
                install,
                str(launcher),
                make_server("203.0.113.10"),
                "PlayerOne",
                [RequiredMod("111", "Missing Mod"), RequiredMod("256", "Installed Mod")],
            )

            text = format_native_launch_parity_report(report)

            self.assertFalse(report.preview.ready)
            self.assertEqual(report.preview.mod_setup.missing_mod_ids, ["111"])
            self.assertEqual(report.preview.mod_setup.mod_links, ["@AAE"])
            self.assertEqual(report.missing_mod_labels, ["Missing Mod (111)"])
            self.assertIn("- Required mod count: 2", text)
            self.assertIn("- Prepared native mod links: 1", text)
            self.assertIn("- Missing Workshop directories: 1", text)
            self.assertIn("Native prepared mod links:\n- Installed Mod (256) -> @AAE [created]", text)
            self.assertIn("Missing Workshop mod directories:\n- Missing Mod (111)", text)
            self.assertIn("Native Steam command: not ready until all required mods are installed.", text)

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

            text = format_native_launch_parity_report(report)
            self.assertIn("External launcher comparison is unavailable: Launcher script not found", text)
            self.assertIn("- External launcher: unavailable; Launcher script not found", text)
            self.assertIn("External launcher handoff:\n- Ready: no", text)
            self.assertIn("- Command: not available", text)

    def test_prepare_native_launch_reports_missing_mods(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                with self.assertRaisesRegex(NativeLaunchError, "Missing mod directories for: 111") as raised:
                    prepare_native_launch(install, make_server(), "PlayerOne", [RequiredMod("111")])
        self.assertEqual(raised.exception.stage, "mod setup")
        self.assertIn("Open the missing Workshop pages", raised.exception.user_message())

    def test_prepare_native_launch_guides_missing_dayz_install(self):
        install = SteamInstall(
            mode="native",
            executable="steam",
            running=True,
            root=Path("/steam"),
            steamapps=Path("/steam/steamapps"),
            dayz_dir=None,
            workshop_dir=Path("/steam/steamapps/workshop/content/221100"),
        )

        with self.assertRaisesRegex(NativeLaunchError, "DayZ install directory not detected") as raised:
            prepare_native_launch(install, make_server(), "PlayerOne", [])

        self.assertEqual(raised.exception.stage, "Steam library detection")
        self.assertIn("confirm DayZ is installed", raised.exception.user_message())

    def test_prepare_native_launch_guides_missing_workshop_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dayz_dir = root / "steamapps" / "common" / "DayZ"
            dayz_dir.mkdir(parents=True)
            install = SteamInstall(
                mode="native",
                executable="steam",
                running=True,
                root=root,
                steamapps=root / "steamapps",
                dayz_dir=dayz_dir,
                workshop_dir=None,
            )

            with self.assertRaisesRegex(NativeLaunchError, "DayZ Workshop directory not detected") as raised:
                prepare_native_launch(install, make_server(), "PlayerOne", [])

        self.assertEqual(raised.exception.stage, "Steam library detection")
        self.assertIn("Workshop folder is visible", raised.exception.user_message())
        self.assertIn("subscribe to at least one DayZ Workshop item", raised.exception.user_message())

    def test_prepare_native_launch_reports_missing_mod_names_when_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install = make_install(Path(tmpdir))

            with patch("wolflauncher.native_launcher.resolve_host", return_value="203.0.113.10"):
                with self.assertRaisesRegex(NativeLaunchError, r"Missing Mod \(111\)") as raised:
                    prepare_native_launch(
                        install,
                        make_server(),
                        "PlayerOne",
                        [RequiredMod("111", "Missing Mod")],
                    )
        self.assertIn("Missing Mod (111)", str(raised.exception))

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
