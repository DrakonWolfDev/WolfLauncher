#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wolflauncher import server_cache
from wolflauncher.server_discovery import discover_dayz_servers


def main() -> int:
    parser = argparse.ArgumentParser(description="Import DayZ candidates from the Steam master server.")
    parser.add_argument("--batches", type=int, default=1, help="Maximum master-server batches to fetch.")
    parser.add_argument("--timeout", type=float, default=5.0, help="UDP timeout in seconds.")
    parser.add_argument("--master-host", default="hl2master.steampowered.com", help="Steam master host.")
    parser.add_argument("--master-port", type=int, default=27011, help="Steam master UDP port.")
    args = parser.parse_args()

    try:
        servers = discover_dayz_servers(
            max_batches=args.batches,
            timeout=args.timeout,
            master_host=args.master_host,
            master_port=args.master_port,
        )
    except OSError as exc:
        print(f"Steam discovery failed: {exc}")
        return 1
    except ValueError as exc:
        print(f"Steam discovery failed: {exc}")
        return 1

    with server_cache.connect() as connection:
        count = server_cache.upsert_servers(connection, servers)
    print(f"Imported {count} Steam master server candidate(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
