"""Read existing installed Workshop item states; never subscribe or request downloads."""

import argparse
import json
import multiprocessing
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# ruff: noqa: E402 - source root is added before application imports
from wolflauncher.platform_detection import detect_steam
from wolflauncher.workshop_subscription import query_workshop_item_states_isolated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.items <= 20 or not 1 <= args.repeats <= 5:
        parser.error("items must be 1–20 and repeats 1–5")
    installs = detect_steam()
    install = next(
        (i for i in installs if i.mode == "native" and i.dayz_dir and i.workshop_dir), None
    )
    if install is None:
        print(
            json.dumps(
                {
                    "passed": False,
                    "error": "No native DayZ Workshop installation detected",
                    "modes": [i.mode for i in installs],
                }
            )
        )
        return 1
    ids = tuple(
        sorted(
            (p.name for p in install.workshop_dir.iterdir() if p.is_dir() and p.name.isdigit()),
            key=int,
        )[: args.items]
    )
    samples = []
    for _ in range(args.repeats):
        start = time.monotonic()
        result = query_workshop_item_states_isolated(ids, install, timeout_seconds=15)
        samples.append(
            {
                "elapsed_ms": round((time.monotonic() - start) * 1000),
                "error": result.error,
                "items": len(result.items),
                "ready": sum(i.installed for i in result.items),
                "states": sorted(set(i.state for i in result.items)),
                "active_children_after_return": len(multiprocessing.active_children()),
            }
        )
    record = {
        "kind": "live_read_only_steam_workshop",
        "requested_items": len(ids),
        "steam_detected_running": install.running,
        "samples": samples,
        "passed": bool(ids)
        and all(
            not x["error"] and x["items"] == len(ids) and x["active_children_after_return"] == 0
            for x in samples
        ),
    }
    print(json.dumps(record, indent=2))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
