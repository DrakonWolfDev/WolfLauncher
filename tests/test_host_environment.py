import os
import sys
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QUrl

from wolflauncher.host_environment import (
    configure_host_process,
    host_process_environment,
    open_host_url,
)


class HostEnvironmentTests(unittest.TestCase):
    def frozen(self):
        return patch.multiple(
            sys, platform="linux", frozen=True, _MEIPASS="/test/bundle", create=True
        )

    def test_source_and_other_platforms_keep_exact_environment_in_a_copy(self):
        original = {"LD_LIBRARY_PATH": "/host/lib", "PATH": "relative::/usr/bin", "CUSTOM": "value"}
        with patch.object(sys, "frozen", False, create=True):
            result = host_process_environment(original)
        self.assertEqual(result, original)
        self.assertIsNot(result, original)
        with self.frozen(), patch.object(sys, "platform", "win32"):
            self.assertEqual(host_process_environment(original), original)

    def test_frozen_linux_restores_host_paths_and_only_removes_bundle_entries(self):
        original = {
            "LD_LIBRARY_PATH": "/test/bundle:/host/lib",
            "LD_LIBRARY_PATH_ORIG": "/host/lib",
            "PATH": "/test/bundle/node-runtime:/usr/bin::relative:/test/bundle-other/bin",
            "QT_PLUGIN_PATH": "/test/bundle/plugins:/host/qt/plugins",
            "QT_QPA_PLATFORM_PLUGIN_PATH": "/test/bundle/platforms",
            "QT_QPA_FONTDIR": "/host/fonts",
            "DISPLAY": ":1",
            "QT_QPA_PLATFORM": "wayland",
            "STEAM_COMPAT_DATA_PATH": "/selected/library/prefix",
            "CUSTOM": "keep",
        }
        before = dict(original)
        with self.frozen():
            result = host_process_environment(original)
        self.assertEqual(original, before)
        self.assertEqual(result["LD_LIBRARY_PATH"], "/host/lib")
        self.assertNotIn("LD_LIBRARY_PATH_ORIG", result)
        self.assertEqual(result["PATH"], "/usr/bin::relative:/test/bundle-other/bin")
        self.assertEqual(result["QT_PLUGIN_PATH"], "/host/qt/plugins")
        self.assertNotIn("QT_QPA_PLATFORM_PLUGIN_PATH", result)
        for key in (
            "QT_QPA_FONTDIR",
            "DISPLAY",
            "QT_QPA_PLATFORM",
            "STEAM_COMPAT_DATA_PATH",
            "CUSTOM",
        ):
            self.assertEqual(result[key], original[key])

    def test_no_host_loader_override_clears_bundle_loader_path(self):
        for original in (
            {"LD_LIBRARY_PATH": "/test/bundle"},
            {"LD_LIBRARY_PATH": "/test/bundle", "LD_LIBRARY_PATH_ORIG": ""},
        ):
            with self.subTest(original=original), self.frozen():
                self.assertNotIn("LD_LIBRARY_PATH", host_process_environment(original))

    def test_qprocess_gets_child_copy_without_mutating_application_environment(self):
        process = Mock()
        with (
            self.frozen(),
            patch.dict(
                os.environ, {"LD_LIBRARY_PATH": "/test/bundle", "DISPLAY": ":1"}, clear=True
            ),
        ):
            configure_host_process(process)
            self.assertEqual(os.environ["LD_LIBRARY_PATH"], "/test/bundle")
        environment = process.setProcessEnvironment.call_args.args[0]
        self.assertFalse(environment.contains("LD_LIBRARY_PATH"))
        self.assertEqual(environment.value("DISPLAY"), ":1")

    def test_host_url_uses_explicit_sanitized_child_without_a_shell(self):
        opener = Mock()
        with (
            self.frozen(),
            patch("wolflauncher.host_environment.shutil.which", return_value="/usr/bin/xdg-open"),
            patch(
                "wolflauncher.host_environment.start_host_detached", return_value=(True, 123)
            ) as start,
            patch.dict(
                os.environ,
                {"PATH": "/test/bundle/bin:/usr/bin", "LD_LIBRARY_PATH": "/test/bundle"},
                clear=True,
            ),
        ):
            self.assertTrue(open_host_url(QUrl("steam://install/223350"), desktop_open=opener))
        opener.assert_not_called()
        self.assertEqual(start.call_args.args[0], ["/usr/bin/xdg-open", "steam://install/223350"])

    def test_host_url_errors_and_source_desktop_delegation(self):
        for executable in (None, "/usr/bin/xdg-open"):
            with (
                self.frozen(),
                patch("wolflauncher.host_environment.shutil.which", return_value=executable),
                patch(
                    "wolflauncher.host_environment.start_host_detached",
                    side_effect=OSError("failed"),
                ),
            ):
                self.assertFalse(open_host_url(QUrl("https://example.test")))
        desktop = Mock(return_value=True)
        with patch.object(sys, "frozen", False, create=True):
            self.assertTrue(open_host_url(QUrl("https://example.test"), desktop_open=desktop))
        desktop.assert_called_once()

    def test_detached_steam_handoff_uses_process_environment_in_frozen_linux(self):
        from wolflauncher.host_environment import start_host_detached

        process = Mock()
        process.startDetached.return_value = (True, 123)
        with (
            self.frozen(),
            patch("PySide6.QtCore.QProcess", return_value=process),
            patch.dict(
                os.environ, {"PATH": "/usr/bin", "LD_LIBRARY_PATH": "/test/bundle"}, clear=True
            ),
        ):
            self.assertEqual(start_host_detached(["/usr/bin/steam", "-silent"]), (True, 123))
        process.setProgram.assert_called_once_with("/usr/bin/steam")
        process.setArguments.assert_called_once_with(["-silent"])
        self.assertFalse(
            process.setProcessEnvironment.call_args.args[0].contains("LD_LIBRARY_PATH")
        )

    @unittest.skipUnless(sys.platform == "linux", "Linux child environment")
    def test_detached_host_child_receives_clean_environment_in_real_qprocess(self):
        import json
        import tempfile
        import time
        from pathlib import Path

        from wolflauncher.host_environment import start_host_detached

        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "child.json"
            code = "import json,os,sys;open(sys.argv[1]+'.tmp','w').write(json.dumps({'loader':os.environ.get('LD_LIBRARY_PATH'),'custom':os.environ.get('WOLF_TEST_HOST_VALUE')}));os.replace(sys.argv[1]+'.tmp',sys.argv[1])"
            with (
                self.frozen(),
                patch.dict(
                    os.environ,
                    {
                        "LD_LIBRARY_PATH": "/test/bundle",
                        "LD_LIBRARY_PATH_ORIG": "",
                        "WOLF_TEST_HOST_VALUE": "preserved",
                    },
                ),
            ):
                started, _pid = start_host_detached([sys.executable, "-c", code, str(report)])
            self.assertTrue(started)
            deadline = time.monotonic() + 2
            while not report.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(report.exists())
            self.assertEqual(
                json.loads(report.read_text()), {"loader": None, "custom": "preserved"}
            )
