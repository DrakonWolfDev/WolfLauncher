from __future__ import annotations

import sys

from .base import PlatformBackend, PlatformCapabilities
from .linux import LinuxPlatformBackend


def _select_platform() -> PlatformBackend:
    if sys.platform.startswith("linux"):
        return LinuxPlatformBackend()
    raise RuntimeError(f"WolfLauncher does not yet support platform {sys.platform!r}")


_BACKEND = _select_platform()


def current_platform() -> PlatformBackend:
    """Return the validated runtime backend.

    Linux remains the only supported backend. A future Windows implementation
    should be selected here only after it has its own tests and runtime
    validation; silently treating an unknown platform as Linux would make the
    launch diagnostics misleading.
    """
    return _BACKEND


__all__ = ["PlatformBackend", "PlatformCapabilities", "current_platform"]
