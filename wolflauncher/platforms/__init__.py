from __future__ import annotations

import sys

from .base import PlatformBackend, PlatformCapabilities


def _select_platform() -> PlatformBackend:
    if sys.platform.startswith("linux"):
        from .linux import LinuxPlatformBackend

        return LinuxPlatformBackend()
    if sys.platform == "win32":
        from .windows import WindowsPlatformBackend

        return WindowsPlatformBackend()
    raise RuntimeError(f"WolfLauncher does not yet support platform {sys.platform!r}")


_BACKEND = _select_platform()


def current_platform() -> PlatformBackend:
    """Return the validated runtime backend.

    Unsupported platforms fail explicitly rather than silently inheriting
    misleading Steam paths, launch behavior or diagnostics.
    """
    return _BACKEND


__all__ = ["PlatformBackend", "PlatformCapabilities", "current_platform"]
