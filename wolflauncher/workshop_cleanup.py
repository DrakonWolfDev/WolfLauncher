"""Remove explicitly confirmed, unsubscribed local Workshop leftovers."""

import shutil
from pathlib import Path


def remove_local_workshop_mod(workshop_dir: Path, workshop_id: str) -> None:
    """Delete only a direct numeric child of the selected Workshop directory."""
    if not workshop_id.isascii() or not workshop_id.isdigit() or int(workshop_id) <= 0:
        raise ValueError("Invalid Workshop ID.")
    root = Path(workshop_dir).resolve(strict=True)
    target = root / workshop_id
    if target.is_symlink() or getattr(target, "is_junction", lambda: False)():
        raise ValueError("Refusing to delete a linked Workshop folder.")
    resolved = target.resolve(strict=True)
    if resolved.parent != root or resolved != target or not resolved.is_dir():
        raise ValueError("The mod folder is not inside the selected Workshop directory.")
    shutil.rmtree(resolved)
