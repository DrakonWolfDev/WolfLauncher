"""Run an AppImage's synthetic UI checks with private data, IPC, PIDs and network."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--scale", choices=("1", "1.5", "2"), default="1")
    parser.add_argument("--platform", choices=("offscreen", "xcb"), default="offscreen")
    args = parser.parse_args()
    artifact = args.artifact.resolve(strict=True)
    if not artifact.is_file() or not os.access(artifact, os.X_OK):
        parser.error("artifact must be an executable AppImage")
    if shutil.which("bwrap") is None:
        parser.error("bubblewrap is required for isolated Linux validation")
    if args.platform == "xcb" and (
        not os.environ.get("DISPLAY", "").startswith(":") or not Path("/tmp/.X11-unix").is_dir()
    ):
        parser.error("xcb validation requires a local X11 display and its socket directory")
    root = Path(tempfile.mkdtemp(prefix="wolflauncher-package-ui-"))
    (root / "config/wolflauncher").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "runtime").mkdir(mode=0o700)
    (root / "config/wolflauncher/servers.yaml").write_text("servers: []\n")
    (root / "config/wolflauncher/settings.json").write_text(
        json.dumps(
            {
                "schema_version": 10,
                "discovery_auto_refresh": False,
                "refresh_seconds": 0,
            }
        )
    )
    command = [
        "bwrap",
        "--die-with-parent",
        "--unshare-pid",
        "--ro-bind",
        "/",
        "/",
        "--tmpfs",
        "/tmp",
        "--bind",
        str(root),
        str(root),
        "--ro-bind",
        str(artifact),
        str(artifact),
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--unshare-net",
    ]
    if args.platform == "xcb":
        command.extend(("--ro-bind", "/tmp/.X11-unix", "/tmp/.X11-unix"))
    for name, value in {
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "XDG_RUNTIME_DIR": str(root / "runtime"),
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent-wolf-validation",
        "QT_QPA_PLATFORM": args.platform,
        "QT_SCALE_FACTOR": args.scale,
        "WOLFLAUNCHER_SMOKE_TEST": "1",
        "WOLFLAUNCHER_SMOKE_VALIDATE_UI": "1",
        "WOLFLAUNCHER_SMOKE_ROOT": str(root),
    }.items():
        command.extend(("--setenv", name, value))
    command.extend(("--", str(artifact), "--appimage-extract-and-run"))
    started = time.monotonic()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired as exc:
        result = subprocess.CompletedProcess(
            command,
            124,
            (exc.stdout or b"").decode(errors="replace"),
            (exc.stderr or b"").decode(errors="replace"),
        )
    (root / "stdout.txt").write_text(result.stdout)
    (root / "stderr.txt").write_text(result.stderr)
    validations = []
    for line in result.stdout.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and "packaged_validation" in record:
            validations.append(record)
    passed = (
        result.returncode == 0
        and len(validations) == 1
        and validations[0]["packaged_validation"] == "passed"
    )
    summary = {
        "artifact": artifact.name,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "exit_code": result.returncode,
        "passed": passed,
        "scale": args.scale,
        "platform": args.platform,
        "launch_mode": "extract-and-run",
        "wall_ms": round((time.monotonic() - started) * 1000),
        "validation": validations,
    }
    (root / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"output_root": str(root), **summary}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
