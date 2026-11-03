"""Bounded, read-only discovery of existing DayZ player profile names."""

from __future__ import annotations

import os
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .dayz_product import STABLE

PROFILE_SUFFIX = ".dayzprofile"
MAX_ENTRIES = 4096
SCAN_SECONDS = 2.0


@dataclass(frozen=True)
class PlayerProfile:
    name: str
    files: tuple[Path, ...]
    modified_ns: int


@dataclass(frozen=True)
class ProfileDiscoveryResult:
    profiles: tuple[PlayerProfile, ...] = ()
    checked_folders: tuple[Path, ...] = ()
    note: str = ""


def profile_name_from_filename(filename: str) -> str | None:
    """Recognise primary files, excluding character/variable caches and backups.

    Encoded names are left for manual entry until the engine's filename escaping
    has been verified; decoding an ambiguous filename could select a new profile.
    """
    lower = filename.casefold()
    if not lower.endswith(PROFILE_SUFFIX):
        return None
    if lower in {"chars.dayzprofile", "vars.dayzprofile"} or lower.endswith(
        (".vars.dayzprofile", ".chars.dayzprofile")
    ):
        return None
    name = filename[: -len(PROFILE_SUFFIX)]
    if (
        not name
        or len(name) > 128
        or name.strip() != name
        or name in {".", ".."}
        or any(char in '%/\\:"<>|?*' or unicodedata.category(char).startswith("C") for char in name)
    ):
        return None
    return name


def profile_context_key(install) -> tuple:
    """Identify the selected edition and installation, not an unrelated library."""
    if install is None:
        return ()
    product = getattr(install, "product", STABLE)
    directory = getattr(install, "dayz_dir", None)
    try:
        library = str(Path(directory).parent.parent.resolve()) if directory else ""
        directory = str(Path(directory).resolve()) if directory else ""
    except (OSError, RuntimeError):
        return ()
    return (product.key, product.client_app_id, getattr(install, "mode", ""), library, directory)


def profile_documents_directories(
    install, *, platform_id: str, documents_dir=None
) -> tuple[Path, ...]:
    if not install or not getattr(install, "dayz_dir", None):
        return ()
    if platform_id == "windows":
        if documents_dir is None:
            from PySide6.QtCore import QStandardPaths

            # Qt uses FOLDERID_Documents / SHGetKnownFolderPath on Windows.
            documents_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        return (Path(documents_dir),) if documents_dir else ()
    if platform_id != "linux":
        return ()
    dayz = Path(install.dayz_dir)
    if dayz.parent.name.casefold() != "common":
        return ()
    product = getattr(install, "product", STABLE)
    # The game's actual library is authoritative. Older install snapshots can
    # contain Stable's compatdata_dir even for Experimental; never reuse it.
    prefix = dayz.parent.parent / "compatdata" / str(product.client_app_id)
    user = prefix / "pfx" / "drive_c" / "users" / "steamuser"
    return (user / "Documents", user / "My Documents")


class _Stopped(Exception):
    pass


def discover_player_profiles(
    install, *, platform_id: str, documents_dir=None, cancelled=lambda: False
) -> ProfileDiscoveryResult:
    """Scan recognised folders only; do not open, create, copy or edit profiles."""
    deadline = time.monotonic() + SCAN_SECONDS
    product = getattr(install, "product", STABLE)
    folder = "DayZ Exp" if product.experimental else "DayZ"
    checked = []
    found: dict[str, dict[Path, int]] = {}
    entries_seen = 0
    partial = False
    skipped_names = False

    def guard():
        if cancelled():
            raise _Stopped("Profile search cancelled.")
        if time.monotonic() >= deadline or entries_seen >= MAX_ENTRIES:
            raise _Stopped("The search reached its limit; some profiles may not be listed.")

    def scan(directory, *, subfolders=False, expected_name=None):
        nonlocal entries_seen, partial, skipped_names
        guard()
        try:
            entries = os.scandir(directory)
        except FileNotFoundError:
            # An absent default folder is normal before that edition is used.
            return
        except OSError:
            partial = True
            return
        try:
            with entries:
                for entry in entries:
                    guard()
                    entries_seen += 1
                    try:
                        if subfolders:
                            if entry.is_dir(follow_symlinks=False):
                                scan(Path(entry.path), expected_name=entry.name)
                            elif entry.is_symlink():
                                partial = True
                            continue
                        if not entry.name.casefold().endswith(PROFILE_SUFFIX):
                            continue
                        name = profile_name_from_filename(entry.name)
                        if name is None:
                            # Character and variable caches are normal, not errors.
                            if "%" in entry.name:
                                skipped_names = True
                            continue
                        if (
                            expected_name is not None
                            and name.casefold() != expected_name.casefold()
                        ):
                            continue
                        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                            partial = True
                            continue
                        info = entry.stat(follow_symlinks=False)
                        if info.st_size == 0:
                            continue
                        path = Path(entry.path).resolve()
                        found.setdefault(name, {})[path] = info.st_mtime_ns
                    except (OSError, RuntimeError):
                        partial = True
        except (OSError, RuntimeError):
            partial = True

    note = ""
    try:
        guard()
        documents = profile_documents_directories(
            install, platform_id=platform_id, documents_dir=documents_dir
        )
        for base in documents:
            for root, nested in ((base / folder, False), (base / f"{folder} Other Profiles", True)):
                guard()
                root = root.resolve()
                if root in checked:
                    continue
                checked.append(root)
                scan(root, subfolders=nested)
        if not documents:
            note = "The selected installation's profile location could not be determined."
        elif partial:
            note = "Some profile folders or files could not be checked."
        if skipped_names:
            note += " Encoded profile names need manual entry; they were not guessed."
    except _Stopped as exc:
        note = str(exc)
    except (OSError, RuntimeError):
        note = "Some profile folders could not be checked."
    profiles = [
        PlayerProfile(name, tuple(sorted(paths)), max(paths.values()))
        for name, paths in found.items()
    ]
    profiles.sort(key=lambda item: (-item.modified_ns, item.name.casefold(), item.name))
    return ProfileDiscoveryResult(tuple(profiles), tuple(checked), note.strip())


def profile_still_exists(profile: PlayerProfile) -> bool:
    """Recheck a selected primary file before applying its name, without opening it."""
    for path in profile.files:
        try:
            if (
                profile_name_from_filename(path.name) == profile.name
                and not path.is_symlink()
                and path.is_file()
                and path.stat().st_size > 0
            ):
                return True
        except OSError:
            continue
    return False
