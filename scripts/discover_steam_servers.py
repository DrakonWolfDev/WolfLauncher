#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wolflauncher import server_cache
from wolflauncher.server_discovery import (
    discover_dayz_servers_battlemetrics,
    discover_dayz_servers,
    discover_dayz_servers_web_api,
    discover_dayz_servers_wolfapi,
    parse_master_address,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import DayZ candidates from configured discovery sources.")
    parser.add_argument("--batches", type=int, default=1, help="Maximum master-server batches to fetch.")
    parser.add_argument("--timeout", type=float, default=5.0, help="UDP timeout in seconds.")
    parser.add_argument("--web-api", action="store_true", help="Use Steam Web API instead of legacy UDP.")
    parser.add_argument("--battlemetrics", action="store_true", help="Use BattleMetrics instead of Steam.")
    parser.add_argument("--wolfapi", action="store_true", help="Use WolfAPI instead of Steam.")
    parser.add_argument("--web-api-key", default="", help="Steam Web API key. Defaults to environment.")
    parser.add_argument("--limit", type=int, default=500, help="Maximum discovery rows to fetch.")
    parser.add_argument("--filter", default="", help="Steam server filter. Defaults to DayZ appid.")
    parser.add_argument(
        "--master",
        action="append",
        default=[],
        help="Steam master endpoint as HOST[:PORT]. Can be passed more than once.",
    )
    parser.add_argument("--master-host", default="", help="Steam master host. Defaults to built-in fallbacks.")
    parser.add_argument("--master-port", type=int, default=27011, help="Steam master UDP port.")
    args = parser.parse_args()

    try:
        if args.wolfapi:
            source = "WolfAPI"
            servers = discover_dayz_servers_wolfapi(limit=args.limit, timeout=args.timeout)
        elif args.battlemetrics:
            source = "BattleMetrics"
            servers = discover_dayz_servers_battlemetrics(limit=args.limit, timeout=args.timeout)
        elif args.web_api:
            source = "Steam Web API"
            servers = discover_dayz_servers_web_api(
                api_key=args.web_api_key,
                limit=args.limit,
                timeout=args.timeout,
                filter_text=args.filter,
            )
        else:
            source = "Steam master"
            master_addresses = [parse_master_address(item, args.master_port) for item in args.master]
            servers = discover_dayz_servers(
                max_batches=args.batches,
                timeout=args.timeout,
                master_host=args.master_host,
                master_port=args.master_port,
                master_addresses=master_addresses,
                extra_filter=args.filter,
            )
    except Exception as exc:
        print(f"{source if 'source' in locals() else 'Server'} discovery failed: {exc}")
        return 1

    with server_cache.connect() as connection:
        count = server_cache.upsert_servers(connection, servers)
    print(f"Imported {count} {source} server candidate(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
