"""Evidence-scoped acknowledgements for successful metadata-only Steam checks."""

import hashlib
import json
import re
from pathlib import Path

from .paths import user_data_dir
from .persistence import atomic_write_text


def installed_manifest(install):
    """Read only the ACF belonging to the selected Workshop content directory."""
    directory = getattr(install, "workshop_dir", None)
    if not directory:
        return {}
    path = Path(directory).parent.parent / "appworkshop_221100.acf"
    try:
        if path.stat().st_size > 8 * 1024 * 1024:
            return {}
        tokens = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"|([{}])', path.read_text())
        offset = 0

        def section(depth=0):
            nonlocal offset
            if depth > 8:
                raise ValueError("ACF nesting limit")
            result = {}
            while offset < len(tokens):
                key, symbol = tokens[offset]
                offset += 1
                if symbol == "}":
                    return result
                if symbol or offset >= len(tokens):
                    raise ValueError("Invalid ACF")
                value, symbol = tokens[offset]
                offset += 1
                result[key] = section(depth + 1) if symbol == "{" else value
            if depth:
                raise ValueError("Truncated ACF")
            return result

        root = section()
        root = root.get("AppWorkshop", root)
        entries = root.get("WorkshopItemsInstalled", {})
        return entries if isinstance(entries, dict) else {}
    except (OSError, UnicodeError, ValueError, AttributeError):
        return {}


def content_evidence(install, workshop_id, manifests=None):
    """Manifest plus bounded file-stat evidence; this is not a file integrity hash."""
    if not workshop_id.isdigit() or not getattr(install, "workshop_dir", None):
        return None
    directory = Path(install.workshop_dir) / workshop_id
    manifests = installed_manifest(install) if manifests is None else manifests
    entry = manifests.get(workshop_id, {})
    if not isinstance(entry, dict) or not entry.get("manifest") or not entry.get("timeupdated"):
        return None
    try:
        root = directory.stat()
        files = []
        for count, path in enumerate(directory.rglob("*")):
            if count >= 10000 or path.is_symlink():
                return None
            if path.is_file():
                stat = path.stat()
                files.append((str(path.relative_to(directory)), stat.st_size, stat.st_mtime_ns))
        if not files:
            return None
        return hashlib.sha256(
            json.dumps(
                [
                    str(directory.resolve()),
                    root.st_dev,
                    root.st_ino,
                    root.st_mtime_ns,
                    entry,
                    sorted(files),
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()
    except OSError:
        return None


def _record_path(install, workshop_id):
    namespace = str(Path(install.workshop_dir).resolve())
    product = getattr(getattr(install, "product", None), "key", "stable")
    key = hashlib.sha256(f"{namespace}|{product}|{workshop_id}".encode()).hexdigest()
    return user_data_dir() / "workshop-checks" / f"{key}.json"


def capture_update_targets(install, workshop_ids, metadata):
    manifests = installed_manifest(install)
    targets = {}
    for item in workshop_ids:
        detail = metadata.get(item, {})
        stamp = detail.get("time_updated", 0)
        evidence = content_evidence(install, item, manifests)
        if detail.get("result") == 1 and stamp and evidence:
            targets[item] = {
                "updated": stamp,
                "size": detail.get("file_size", 0),
                "evidence": evidence,
            }
    return targets


def record_completed_checks(install, result, targets):
    if not result.ok:
        return
    manifests = installed_manifest(install)
    for item in result.installed_ids:
        target = targets.get(item)
        if not target or content_evidence(install, item, manifests) != target["evidence"]:
            continue
        try:
            atomic_write_text(_record_path(install, item), json.dumps(target))
        except OSError:
            # A cache write failure must leave the revision mismatch unresolved.
            continue


def apply_completed_checks(install, mods):
    manifests = installed_manifest(install)
    for mod in mods:
        mod.workshop_acknowledged_at = 0
        # Never use historical completion evidence instead of a live idle state.
        if not mod.workshop_id or not mod.installed or mod.workshop_state is None:
            continue
        if not mod.workshop_state & 4 or mod.workshop_state & (8 | 16 | 32):
            continue
        evidence = content_evidence(install, mod.workshop_id, manifests)
        if not evidence:
            continue
        try:
            path = _record_path(install, mod.workshop_id)
            if path.stat().st_size > 4096:
                continue
            record = json.loads(path.read_text())
            if (
                record.get("updated") == mod.workshop_updated_at
                and record.get("size") == mod.workshop_file_size
                and record.get("evidence") == evidence
            ):
                mod.workshop_acknowledged_at = mod.workshop_updated_at
        except (OSError, ValueError, AttributeError):
            continue
