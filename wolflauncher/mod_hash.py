"""Read-only, bounded DayZ PBO-trailer comparisons, never an integrity check.

The aggregation format is described in docs/MOD_HASH_COMPARISON.md. No PBO body
is hashed and a difference cannot establish which copy is newer.
"""

from __future__ import annotations

import hashlib
import os
import stat
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

DATA_DIRECTORIES = {"addons", "dta", "bin"}
MAX_DIRECTORY_ENTRIES = 8192
MAX_PBOS = 2048
MAX_DUPLICATE_SEARCH_PBOS = 12
CHECK_BUDGET_SECONDS = 3.0


@dataclass(frozen=True)
class ModHashComparison:
    status: str = "unknown"
    detail: str = "Server hash comparison unavailable."
    local_hash: int | None = None


class _Unavailable(Exception):
    pass


def calculate_mod_hash(trailers: Iterable[bytes]) -> int:
    """Aggregate SHA-1 trailers into DayZ's advertised unsigned 32-bit value."""
    ordered = sorted(trailers)
    if any(len(trailer) != 20 for trailer in ordered):
        raise ValueError("PBO SHA-1 trailers must contain 20 bytes")
    digest = hashlib.sha1(
        "".join(value.hex() for value in ordered).encode("ascii"), usedforsecurity=False
    ).hexdigest()
    result = 0
    factor = 378551
    for value in bytes([len(digest)]) + digest.encode("ascii"):
        result = (result * factor + value) & 0xFFFFFFFF
        factor = factor * 63689 & 0xFFFFFFFF
    return result


def compare_mod_hash(
    mod_dir: Path,
    server_hash: int | None,
    *,
    cancelled: Callable[[], bool] = lambda: False,
    deadline: float | None = None,
) -> ModHashComparison:
    """Return a snapshot; reread on every check rather than caching by item ID.

    Directory/file identities are checked again before accepting any outcome.
    Unknown covers partial reads, concurrent updates, cancellation and limits.
    The deadline is shared across a worker's required mods.
    """
    if type(server_hash) is not int or not 0 <= server_hash <= 0xFFFFFFFF:
        return ModHashComparison(detail="The server supplied no usable mod hash.")
    if deadline is None:
        deadline = time.monotonic() + CHECK_BUDGET_SECONDS

    def guard():
        if cancelled():
            raise _Unavailable("Server hash comparison cancelled.")
        if time.monotonic() >= deadline:
            raise _Unavailable("Server hash comparison reached its time limit. Recheck to retry.")

    def identity(path):
        info = path.stat()
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    try:
        guard()
        root = Path(mod_dir).resolve(strict=True)
        directories = {root: identity(root), Path(mod_dir): identity(Path(mod_dir))}
        files = {}
        trailers = []
        count = 0
        # Only the top level of DayZ's data directories contributes to its hash.
        with os.scandir(root) as entries:
            for entry in entries:
                guard()
                count += 1
                if count > MAX_DIRECTORY_ENTRIES:
                    raise _Unavailable("Too many directory entries to compare safely.")
                if entry.name.casefold() not in DATA_DIRECTORIES:
                    continue
                if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                    raise _Unavailable("A mod data directory is unavailable or linked elsewhere.")
                directory = Path(entry.path)
                directories[directory] = identity(directory)
                with os.scandir(directory) as children:
                    for child in children:
                        guard()
                        count += 1
                        if count > MAX_DIRECTORY_ENTRIES:
                            raise _Unavailable("Too many directory entries to compare safely.")
                        if Path(child.name).suffix.casefold() != ".pbo":
                            continue
                        if child.is_symlink() or not child.is_file(follow_symlinks=False):
                            raise _Unavailable("A PBO is unavailable or linked elsewhere.")
                        if len(trailers) >= MAX_PBOS:
                            raise _Unavailable("Too many PBOs to compare safely.")
                        path = Path(child.path)
                        before = identity(path)
                        with path.open("rb") as handle:
                            info = os.fstat(handle.fileno())
                            if not stat.S_ISREG(info.st_mode) or info.st_size < 21:
                                raise _Unavailable("A PBO has no complete SHA-1 trailer.")
                            handle.seek(-21, os.SEEK_END)
                            trailer = handle.read(21)
                        if len(trailer) != 21 or trailer[0] != 0:
                            raise _Unavailable("A PBO has no supported SHA-1 trailer.")
                        if identity(path) != before:
                            raise _Unavailable(
                                "Mod files changed during comparison. Recheck to retry."
                            )
                        files[path] = before
                        trailers.append(trailer[1:])
        # Empty data could mean an incomplete install, even though the empty-set
        # aggregation is defined. Do not claim compatibility from absent files.
        if not trailers:
            raise _Unavailable("No readable PBO trailers were found in this mod.")
        local_hash = calculate_mod_hash(trailers)
        status = "match" if local_hash == server_hash else "different"
        detail = "PBO trailer hash matches the server."
        if status == "different":
            detail = (
                "PBO trailer hash differs from the server; this does not show which copy is newer."
            )
            if len(trailers) > MAX_DUPLICATE_SEARCH_PBOS:
                status = "unknown"
                detail = (
                    "Hashes differ, but the duplicate-PBO compatibility search exceeds its limit."
                )
            else:
                # Some Linux servers retain case-renamed copies of PBOs. Test
                # that possibility only within a strict exponential-work bound.
                for mask in range(1, 1 << len(trailers)):
                    guard()
                    extras = [value for i, value in enumerate(trailers) if mask & (1 << i)]
                    if calculate_mod_hash([*trailers, *extras]) == server_hash:
                        status = "match"
                        detail = "Server hash matches when allowing duplicate PBOs on the server."
                        break
        for path, before in {**directories, **files}.items():
            guard()
            if identity(path) != before:
                raise _Unavailable("Mod files changed during comparison. Recheck to retry.")
        return ModHashComparison(status, detail, local_hash)
    except _Unavailable as exc:
        return ModHashComparison(detail=str(exc))
    except (OSError, RuntimeError):
        return ModHashComparison(
            detail="Mod files could not be read consistently. Recheck to retry."
        )


def _comparison_paths(result, install):
    directory = getattr(install, "workshop_dir", None) if install else result.workshop_dir
    mods = [mod for mod in result.required_mods if mod.downloadable]
    try:
        if directory:
            if install and getattr(getattr(install, "product", None), "experimental", False):
                # Use exactly the same official-launcher paths as native EXP launch.
                from .native_launcher import _experimental_mod_paths

                if getattr(install, "dayz_dir", None):
                    return dict(
                        zip(
                            (mod.workshop_id for mod in mods),
                            _experimental_mod_paths(Path(install.dayz_dir), Path(directory), mods),
                        )
                    )
            else:
                return {mod.workshop_id: Path(directory) / mod.workshop_id for mod in mods}
    except (OSError, RuntimeError):
        pass
    return {}


def apply_mod_hash_comparisons(result, install, *, cancelled=lambda: False):
    """Enrich only this worker's server/library/edition result; never update Steam."""
    if not result.ok:
        return
    paths = _comparison_paths(result, install)
    deadline = time.monotonic() + CHECK_BUDGET_SECONDS
    for mod in result.required_mods:
        if cancelled():
            return
        path = paths.get(mod.workshop_id)
        # Skip files while Steam can be rewriting them. This advisory never
        # changes readiness or the list of items eligible for Steam updates.
        if not mod.ready or path is None:
            mod.hash_comparison = ModHashComparison(
                detail="An installed, idle mod in the selected library is needed for comparison."
            )
        else:
            mod.hash_comparison = compare_mod_hash(
                path, mod.server_hash, cancelled=cancelled, deadline=deadline
            )
