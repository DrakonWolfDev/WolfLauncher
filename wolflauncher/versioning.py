"""Native Windows version fields for the launcher's PEP 440 release version."""

from packaging.version import Version


def windows_version_tuple(value: str) -> tuple[int, int, int, int]:
    release = Version(value).release
    if len(release) > 4 or any(part > 65535 for part in release):
        raise ValueError("Windows versions require at most four 16-bit release components")
    return tuple((*release, 0, 0, 0, 0)[:4])
