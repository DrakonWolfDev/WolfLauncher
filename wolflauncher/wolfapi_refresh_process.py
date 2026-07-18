"""Process-isolated WolfAPI refresh used to keep the Qt event loop responsive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import server_cache
from .server_discovery import discover_dayz_servers_wolfapi
from .workers import discover_wolfapi_v1_pages


def refresh_cache(
    cache_path: Path,
    limit: int,
    use_v1: bool,
    unflagged_only: bool,
) -> dict[str, object]:
    connection = None
    try:
        if use_v1:
            servers = discover_wolfapi_v1_pages(limit, unflagged_only=unflagged_only)
        else:
            servers = discover_dayz_servers_wolfapi(limit=limit)
        connection = server_cache.connect(cache_path)
        if use_v1:
            inserted = server_cache.merge_source_servers(connection, "wolfapi", servers)
            removed = 0
        else:
            inserted, removed = server_cache.sync_source_servers(connection, "wolfapi", servers)
        return {"inserted": inserted, "removed": removed, "error": ""}
    except Exception as exc:
        return {"inserted": 0, "removed": 0, "error": str(exc)}
    finally:
        if connection is not None:
            connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--limit", type=int, required=True)
    parser.add_argument("--v1", action="store_true")
    parser.add_argument("--unflagged-only", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            refresh_cache(
                args.cache,
                max(1, args.limit),
                args.v1,
                args.unflagged_only,
            )
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
