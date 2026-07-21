#!/usr/bin/env python3
"""Read-only diagnostic probe for a known DayZ server's required mods."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wolflauncher.dayz_mod_query import (  # noqa: E402
    DayzModQueryError,
    query_dayz_required_mods,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("query_port", type=int)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    if not 1 <= args.query_port <= 65535:
        parser.error("query_port must be between 1 and 65535")
    try:
        mods = query_dayz_required_mods(
            args.host, args.query_port, timeout=max(0.1, min(args.timeout, 30.0))
        )
    except DayzModQueryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Complete manifest: {len(mods)} required Workshop mod(s)")
    for mod in mods:
        print(f"{mod.workshop_id}\t{mod.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
