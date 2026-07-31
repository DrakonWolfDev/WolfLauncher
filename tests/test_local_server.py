import tempfile
import unittest
from pathlib import Path

from wolflauncher.local_server import (
    LocalServerLaunch,
    build_local_server_command,
    build_steamcmd_install_command,
    public_key_files,
)


class LocalServerTests(unittest.TestCase):
    def test_builds_server_command_with_local_mod_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            executable = root / "DayZServer"
            config = root / "serverDZ.cfg"
            executable.touch()
            config.touch()
            command = build_local_server_command(
                LocalServerLaunch(
                    root, executable, config, root / "profiles", 2302,
                    (root / "@Client",), (root / "@Server",), True,
                )
            )
        self.assertIn(f"-mod={root / '@Client'}", command)
        self.assertIn(f"-serverMod={root / '@Server'}", command)
        self.assertIn("-filePatching", command)

    def test_collects_only_public_bikey_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mod = Path(tmpdir) / "@Test"
            keys = mod / "Keys"
            keys.mkdir(parents=True)
            (keys / "Test.bikey").touch()
            (keys / "private.biprivatekey").touch()
            self.assertEqual(public_key_files((mod,)), (keys / "Test.bikey",))

    def test_steamcmd_command_requires_existing_program(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            steamcmd = root / "steamcmd"
            steamcmd.touch()
            command = build_steamcmd_install_command(steamcmd, root / "server")
        self.assertIn("223350", command)
        self.assertIn("+login", command)


if __name__ == "__main__":
    unittest.main()
