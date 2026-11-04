"""Local build evidence; hashes provide traceability, not signatures or reproducibility."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1


def file_record(path: Path) -> dict:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ino,
    ):
        raise ValueError(f"File changed while hashing: {path.name}")
    return {"size": after.st_size, "sha256": digest.hexdigest()}


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, timeout=30
    ).stdout


def source_state(root: Path) -> dict:
    commit = git(root, "rev-parse", "HEAD").decode("ascii").strip()
    names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    records = []
    for name in sorted(set(os.fsdecode(item) for item in names.split(b"\0") if item)):
        path = root / name
        if path.is_symlink():
            record = {"symlink": os.readlink(path)}
        elif path.is_file():
            record = {"mode": stat.S_IMODE(path.stat().st_mode), **file_record(path)}
        elif not path.exists():
            record = {"missing": True}
        else:
            raise ValueError(f"Unsupported source entry: {name}")
        records.append({"path": name, **record})
    serialized = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return {
        "commit": commit,
        "dirty": bool(git(root, "status", "--porcelain", "--untracked-files=normal")),
        "snapshot_sha256": hashlib.sha256(serialized).hexdigest(),
        "files": records,
    }


def bundle_inventory(root: Path) -> list[dict]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Bundle root must be a directory")
    records = []
    # Path.rglob does not follow directory symlinks; record and validate those links.
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            if not path.resolve(strict=True).is_relative_to(root):
                raise ValueError(f"Bundle symlink escapes package: {name}")
            target = os.readlink(path)
            if Path(target).is_absolute():
                raise ValueError(f"Packaged symlink must be relative: {name}")
            records.append({"path": name, "symlink": target})
        elif path.is_file():
            records.append(
                {"path": name, "mode": stat.S_IMODE(path.stat().st_mode), **file_record(path)}
            )
        elif not path.is_dir():
            raise ValueError(f"Unsupported packaged file: {name}")
    if not records:
        raise ValueError("Bundle inventory is empty")
    return records


def write_json(path: Path, data: dict) -> None:
    # Build output lives outside the source snapshot. Never truncate an existing source file.
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path) -> dict:
    with path.open("rb") as stream:
        body = stream.read(20 * 1024 * 1024 + 1)
    if len(body) > 20 * 1024 * 1024:
        raise ValueError("Provenance document exceeds size limit")
    data = json.loads(body)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("Unsupported provenance schema")
    return data


def begin(root: Path, output: Path, tools: list[str]) -> None:
    packages = {}
    for name in ("PyInstaller", "PySide6", "shiboken6"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    tool_records = {}
    for specification in tools:
        name, separator, value = specification.partition("=")
        if not separator or not name or name in tool_records:
            raise ValueError("Tools must have unique name=path specifications")
        tool_records[name] = {"file": Path(value).name, **file_record(Path(value))}
    state = source_state(root)
    write_json(
        output,
        {
            "schema": SCHEMA,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "source": state,
            "toolchain": {
                "python": platform.python_version(),
                "platform": platform.system(),
                "architecture": platform.machine(),
                "packages": packages,
                "tools": tool_records,
            },
        },
    )


def finish(root: Path, inputs: Path, bundle: Path, artifact: Path) -> Path:
    evidence = read_json(inputs)
    if evidence["source"] != source_state(root):
        raise ValueError("Source changed during build; rebuild from one consistent snapshot")
    evidence.update(
        {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "artifact": {"file": artifact.name, **file_record(artifact)},
            "bundle": bundle_inventory(bundle),
            "assurance": "Unsigned build evidence; not an independent signature or reproducible-build claim.",
        }
    )
    if evidence["source"] != source_state(root):
        raise ValueError("Source changed while recording output; rebuild")
    output = artifact.with_name(artifact.name + ".provenance.json")
    write_json(output, evidence)
    return output


def verify(
    manifest: Path,
    artifact: Path,
    bundle: Path | None = None,
    *,
    expected_commit: str = "",
    require_clean: bool = False,
) -> None:
    data = read_json(manifest)
    if expected_commit and data.get("source", {}).get("commit") != expected_commit:
        raise ValueError("Provenance source commit does not match the expected build")
    if require_clean and data.get("source", {}).get("dirty") is not False:
        raise ValueError("Release provenance must come from a clean source checkout")
    expected = data.get("artifact", {})
    if expected != {"file": artifact.name, **file_record(artifact)}:
        raise ValueError("Artifact does not match its provenance record")
    if bundle is not None and data.get("bundle") != bundle_inventory(bundle):
        raise ValueError("Packaged files do not match their provenance inventory")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("begin")
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--tool", action="append", default=[])
    complete = commands.add_parser("finish")
    complete.add_argument("--inputs", type=Path, required=True)
    complete.add_argument("--bundle-root", type=Path, required=True)
    complete.add_argument("artifact", type=Path)
    check = commands.add_parser("verify")
    check.add_argument("--manifest", type=Path, required=True)
    check.add_argument("--bundle-root", type=Path)
    check.add_argument("artifact", type=Path)
    check.add_argument("--commit", default="")
    check.add_argument("--require-clean", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "begin":
            begin(args.root, args.output, args.tool)
        elif args.command == "finish":
            print(finish(args.root, args.inputs, args.bundle_root, args.artifact))
        else:
            verify(
                args.manifest,
                args.artifact,
                args.bundle_root,
                expected_commit=args.commit,
                require_clean=args.require_clean,
            )
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Build provenance failed: {exc}\n")


if __name__ == "__main__":
    main()
