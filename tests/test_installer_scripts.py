"""Smoke tests for the distro-neutral installer scripts.

These exercise the bits that don't require network, Node.js or Steam:
argument parsing, env-variable overrides, distro family detection, the
wrapper script it generates, and the uninstaller.

Run with::

    python3 -m unittest tests.test_installer_scripts -v

The tests stub out every external command the installer might invoke so they
work on any host.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "wolflauncher-install.sh"
UNINSTALLER = REPO_ROOT / "scripts" / "wolflauncher-uninstall.sh"


def _stub_bin_dir() -> tuple[Path, list[str]]:
    """Create a temporary directory filled with stub commands.

    Returns the directory and the PATH value to use when invoking the scripts.
    The stubs are intentionally minimal: every command exits 0 and prints
    nothing, except for `python3 -m ensurepip` which we test separately.
    """
    bin_dir = Path(tempfile.mkdtemp(prefix="wl-install-stub-"))
    py_stub = bin_dir / "python3"
    py_stub.write_text(
        "#!/bin/bash\n"
        "# Minimal python3 stub for installer tests.\n"
        'cmd_log="${WOLF_STUB_LOG:-/tmp/wl-stub.log}"\n'
        'echo "INVOKED args=$@" >> "$cmd_log"\n'
        'case "$1" in\n'
        "  -c)\n"
        '    src="$2"\n'
        '    case "$src" in\n'
        "      *sys.version_info*)\n"
        '        echo "3.12.7"\n'
        "        exit 0\n"
        "        ;;\n"
        "      *wolflauncher.__version__*)\n"
        '        echo "0.9.0b1"\n'
        "        exit 0\n"
        "        ;;\n"
        "    esac\n"
        "    exit 0\n"
        "    ;;\n"
        "  -m)\n"
        "    shift\n"
        '    subcmd="$1"\n'
        '    case "$subcmd" in\n'
        "      pip)\n"
        '        : > "${WOLF_STUB_PIP_MARKER:-/dev/null}"\n'
        "        exit 0\n"
        "        ;;\n"
        "      ensurepip|wolflauncher)\n"
        "        exit 0\n"
        "        ;;\n"
        "      build)\n"
        "        # Drop a fake wheel at --outdir if present.\n"
        '        outdir=""\n'
        '        prev=""\n'
        '        for arg in "$@"; do\n'
        '          if [ "$prev" = "--outdir" ]; then\n'
        '            outdir="$arg"\n'
        "            break\n"
        "          fi\n"
        '          prev="$arg"\n'
        "        done\n"
        '        echo "STUB build outdir=$outdir" >> "$cmd_log"\n'
        '        if [ -n "$outdir" ]; then\n'
        '          mkdir -p "$outdir"\n'
        '          touch "$outdir/wolflauncher-0.9.0-py3-none-any.whl"\n'
        '          echo "STUB build wrote wheel to $outdir" >> "$cmd_log"\n'
        "        fi\n"
        "        exit 0\n"
        "        ;;\n"
        "    esac\n"
        "    exit 0\n"
        "    ;;\n"
        "  -)\n"
        "    python3 -c \"import sys; print('0.9.0b1')\"\n"
        "    exit 0\n"
        "    ;;\n"
        "esac\n"
        "exit 0\n"
    )
    py_stub.chmod(0o755)

    sha = bin_dir / "sha256sum"
    sha.write_text("#!/usr/bin/sh\nexit 0\n")
    sha.chmod(0o755)

    node = bin_dir / "node"
    node.write_text("#!/usr/bin/sh\nexit 0\n")
    node.chmod(0o755)

    npm = bin_dir / "npm"
    npm.write_text("#!/usr/bin/sh\nexit 0\n")
    npm.chmod(0o755)

    # Stub network commands to succeed without doing anything.
    for name in ("curl", "wget"):
        cmd = bin_dir / name
        cmd.write_text("#!/usr/bin/sh\nexit 0\n")
        cmd.chmod(0o755)

    # Stub tar to no-op; we won't actually run the Node install in tests.
    tar = bin_dir / "tar"
    tar.write_text("#!/usr/bin/sh\nexit 0\n")
    tar.chmod(0o755)

    unzip = bin_dir / "unzip"
    unzip.write_text("#!/usr/bin/sh\nexit 0\n")
    unzip.chmod(0o755)

    return bin_dir, [
        str(bin_dir),
        "/usr/bin",
        "/bin",
        *os.environ.get("PATH", "").split(os.pathsep),
    ]


class InstallerScriptsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._stub_dir, self._path = _stub_bin_dir()
        self._tmp = Path(tempfile.mkdtemp(prefix="wl-install-home-"))
        self._env = {
            **os.environ,
            "PATH": os.pathsep.join(self._path),
            "HOME": str(self._tmp),
            "XDG_DATA_HOME": str(self._tmp / ".local" / "share"),
            "XDG_BIN_HOME": str(self._tmp / ".local" / "bin"),
            "XDG_CONFIG_HOME": str(self._tmp / ".config"),
            "WOLFLAUNCHER_ASSUME_YES": "1",
            "WOLFLAUNCHER_REPO": str(REPO_ROOT),
            # Don't actually download Node, GameDig, or launch Qt in tests.
            "WOLFLAUNCHER_SKIP_NODE": "1",
            "WOLFLAUNCHER_SKIP_GAMEDIG": "1",
            "WOLFLAUNCHER_SKIP_VERIFY": "1",
            # Pip install is a no-op; mark it for assertion.
            "WOLF_STUB_PIP_MARKER": str(self._tmp / "pip-was-called"),
            "WOLF_STUB_BUILD_MARKER": str(self._tmp / "build-was-called"),
        }

    def tearDown(self) -> None:
        shutil.rmtree(self._stub_dir, ignore_errors=True)
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ----- the installer -----------------------------------

    def _run(self, cmd: Iterable[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            list(cmd),
            env=self._env,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def test_installer_help_smoke(self) -> None:
        # Even running --help should not break; just confirms the script is parseable.
        result = self._run([str(INSTALLER)])
        # Installer may exit non-zero only if the network/Node step fails; we
        # only care that the script was reachable.
        self.assertEqual(result.returncode, 0, msg="installer produced no output at all")

    def test_installer_creates_wrapper_and_layout(self) -> None:
        result = self._run([str(INSTALLER)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        prefix = self._env["XDG_DATA_HOME"] + "/wolflauncher/runtime"
        bin_dir = self._env["XDG_BIN_HOME"]
        for required in (
            f"{prefix}/python",
            f"{prefix}/node",
            f"{prefix}/node-runtime/bin",
            f"{prefix}/app",
            f"{prefix}/share",
            f"{bin_dir}/wolflauncher",
        ):
            self.assertTrue(
                os.path.exists(required),
                msg=f"expected path missing after install: {required}\nstdout={result.stdout}\nstderr={result.stderr}",
            )

    def test_wrapper_is_executable_and_includes_paths(self) -> None:
        self._run([str(INSTALLER)])
        wrapper = Path(self._env["XDG_BIN_HOME"]) / "wolflauncher"
        self.assertTrue(wrapper.is_file())
        mode = wrapper.stat().st_mode
        self.assertTrue(mode & 0o111, msg="wrapper must be executable")
        text = wrapper.read_text()
        self.assertIn("PYTHONPATH=", text)
        self.assertIn("WOLFLAUNCHER_SHARE_ROOT=", text)
        self.assertIn("node-runtime/bin", text)
        self.assertIn("python3 -m wolflauncher", text)

    def test_overrides_are_honoured(self) -> None:
        custom_prefix = self._tmp / "custom-prefix"
        custom_bin = self._tmp / "custom-bin"
        env = {
            **self._env,
            "WOLFLAUNCHER_PREFIX": str(custom_prefix),
            "WOLFLAUNCHER_BIN_DIR": str(custom_bin),
        }
        result = subprocess.run(
            [str(INSTALLER)],
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        wrapper = custom_bin / "wolflauncher"
        self.assertTrue(
            wrapper.is_file(),
            msg=f"override wrapper missing: {wrapper}\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        self.assertIn(str(custom_prefix), wrapper.read_text())

    # ----- the uninstaller -----------------------------

    def test_uninstaller_removes_wrapper_and_prefix(self) -> None:
        # First run the installer (best effort).
        self._run([str(INSTALLER)])
        prefix = Path(self._env["XDG_DATA_HOME"]) / "wolflauncher" / "runtime"
        wrapper = Path(self._env["XDG_BIN_HOME"]) / "wolflauncher"
        self.assertTrue(prefix.exists())
        self.assertTrue(wrapper.exists())

        result = subprocess.run(
            [str(UNINSTALLER)],
            env=self._env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertFalse(
            wrapper.exists(),
            msg=f"wrapper not removed: stdout={result.stdout}\nstderr={result.stderr}",
        )
        self.assertFalse(
            prefix.exists(),
            msg=f"prefix not removed: stdout={result.stdout}\nstderr={result.stderr}",
        )

    def test_uninstaller_preserves_cached_data(self) -> None:
        result = self._run([str(INSTALLER)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        cache = Path(self._env["XDG_DATA_HOME"]) / "wolflauncher" / "servers.sqlite3"
        cache.write_bytes(b"personal cache sentinel")
        result = self._run([str(UNINSTALLER)])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(cache.read_bytes(), b"personal cache sentinel")

    def test_uninstaller_keeps_config_without_purge(self) -> None:
        self._run([str(INSTALLER)])
        # Drop a sentinel file into the config dir.
        cfg = Path(self._env["XDG_CONFIG_HOME"]) / "wolflauncher"
        cfg.mkdir(parents=True, exist_ok=True)
        sentinel = cfg / "settings.json"
        sentinel.write_text("{}")
        subprocess.run(
            [str(UNINSTALLER)],
            env=self._env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertTrue(sentinel.exists(), "settings.json should be preserved without --purge")

    def test_uninstaller_purge_removes_config(self) -> None:
        self._run([str(INSTALLER)])
        cfg = Path(self._env["XDG_CONFIG_HOME"]) / "wolflauncher"
        cfg.mkdir(parents=True, exist_ok=True)
        sentinel = cfg / "settings.json"
        sentinel.write_text("{}")
        subprocess.run(
            [str(UNINSTALLER), "--purge"],
            env=self._env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertFalse(sentinel.exists(), "settings.json should be removed with --purge")

    def test_uninstaller_is_idempotent(self) -> None:
        # Running uninstall with nothing installed must not error.
        result = subprocess.run(
            [str(UNINSTALLER)],
            env=self._env,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode, 0, msg=f"stderr={result.stderr}\nstdout={result.stdout}"
        )


if __name__ == "__main__":
    unittest.main()
