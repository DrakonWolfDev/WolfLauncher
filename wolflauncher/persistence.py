from __future__ import annotations

import os
import tempfile
from pathlib import Path

PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIRECTORY_MODE)
    try:
        path.chmod(PRIVATE_DIRECTORY_MODE)
    except OSError:
        # Some mounted filesystems do not implement POSIX permissions. The
        # subsequent file operation remains authoritative for success/failure.
        pass


def ensure_private_file(path: Path) -> None:
    if not path.is_file():
        return
    try:
        path.chmod(PRIVATE_FILE_MODE)
    except OSError:
        pass


def atomic_write_text(
    path: Path,
    text: str,
    *,
    mode: int = PRIVATE_FILE_MODE,
    backup: bool = False,
) -> None:
    """Durably replace a text file without exposing a partial destination."""
    ensure_private_directory(path.parent)
    if backup and path.is_file():
        atomic_write_bytes(path.with_suffix(path.suffix + ".bak"), path.read_bytes(), mode=mode)
    atomic_write_bytes(path, text.encode("utf-8"), mode=mode)


def atomic_write_bytes(path: Path, content: bytes, *, mode: int = PRIVATE_FILE_MODE) -> None:
    ensure_private_directory(path.parent)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(file_descriptor, mode)
        with os.fdopen(file_descriptor, "wb") as handle:
            file_descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    except BaseException:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        # Windows flushes the replaced file above but does not support opening
        # a directory with os.open for the POSIX directory-fsync pattern.
        return
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    directory_descriptor = os.open(path, flags)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)
