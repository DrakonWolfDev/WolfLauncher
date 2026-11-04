"""Keep frozen Linux loader settings out of host application handoffs."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Mapping


def _linux_bundle_root() -> Path | None:
    if sys.platform == "linux" and getattr(sys, "frozen", False):
        root = getattr(sys, "_MEIPASS", None)
        if root:
            return Path(root)
    return None


def host_process_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a child-only copy, preserving host overrides and unrelated variables."""
    environment = dict(os.environ if environ is None else environ)
    root = _linux_bundle_root()
    if root is None:
        return environment
    original_loader_path = environment.pop("LD_LIBRARY_PATH_ORIG", "")
    if original_loader_path:
        environment["LD_LIBRARY_PATH"] = original_loader_path
    else:
        environment.pop("LD_LIBRARY_PATH", None)

    def bundled(value: str) -> bool:
        # Do not treat relative/empty host search entries as paths in the bundle.
        path = Path(value)
        return path.is_absolute() and path.is_relative_to(root)

    if "PATH" in environment:
        environment["PATH"] = os.pathsep.join(
            value for value in environment["PATH"].split(os.pathsep) if not bundled(value)
        )
    for name in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QT_QPA_FONTDIR"):
        if name in environment:
            entries = environment[name].split(os.pathsep)
            retained = [entry for entry in entries if not bundled(entry)]
            if retained:
                environment[name] = os.pathsep.join(retained)
            else:
                environment.pop(name)
    return environment


def configure_host_process(process) -> None:
    """Set a QProcess's environment only for a frozen Linux host handoff."""
    if _linux_bundle_root() is None:
        return
    from PySide6.QtCore import QProcessEnvironment

    environment = QProcessEnvironment()
    for name, value in host_process_environment().items():
        environment.insert(name, value)
    process.setProcessEnvironment(environment)


def open_host_url(url, *, desktop_open=None) -> bool:
    """Use an explicit child environment when Qt would otherwise inherit ours."""
    if _linux_bundle_root() is None:
        if desktop_open is None:
            from PySide6.QtGui import QDesktopServices

            desktop_open = QDesktopServices.openUrl
        return desktop_open(url)
    environment = host_process_environment()
    opener = shutil.which("xdg-open", path=environment.get("PATH", os.defpath))
    if not opener:
        return False
    from PySide6.QtCore import QUrl

    try:
        started, _pid = start_host_detached([opener, url.toString(QUrl.FullyEncoded)])
    except OSError:
        return False
    return started


def start_host_detached(command: list[str], *, detached_start=None) -> tuple[bool, int]:
    if _linux_bundle_root() is None:
        if detached_start is None:
            from PySide6.QtCore import QProcess

            detached_start = QProcess.startDetached
        return detached_start(command[0], command[1:])
    from PySide6.QtCore import QProcess

    process = QProcess()
    configure_host_process(process)
    process.setProgram(command[0])
    process.setArguments(command[1:])
    result = process.startDetached()
    # PySide versions expose the instance overload as bool or (bool, pid).
    return result if isinstance(result, tuple) else (bool(result), 0)
