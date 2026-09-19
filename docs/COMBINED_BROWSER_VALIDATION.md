# Combined browser implementation and validation

Updated 19 September 2026.

## Delivery status

| Phase | Implemented | Remaining release evidence |
| --- | --- | --- |
| 1: identity and saved data | Model/conversion metadata, schema 8, combined profile adapter, settings 10, history, rollback and migration tests | Upgrade/restore with a representative real user backup |
| 2: availability | Background scans of both products, manifest/executable checks, rescan and setup guidance | Real install/uninstall and first-run/BattlEye checks |
| 3: launch context | Fresh full game ID, immutable installation snapshot, request-bound mods/preflight/preview, stale-result rejection | Actual Linux and Windows Stable → EXP → Stable joins |
| 4: browser | Stable default, visible edition selector, scoped queries/counts, mixed saved-server tags | Interactive provider outage and rapid-selection checks |
| 5: integration | Global Settings mode removed, Stable-only local tools, user documentation | Manual matrix below; Experimental local tools are out of scope |

The browser choice scopes discovery. It never establishes the product to launch.
Live GameDig full IDs `221100` and `1024020` are accepted only for the exact endpoint
and request. Checks are reused for at most 30 seconds and refreshed before handoff
if expired. Installation/product changes require a new mod check. Names, versions,
short/truncated A2S IDs and legacy profile locations do not select a game.

Experimental always uses native launching. Stable retains its saved engine choice.
The legacy Linux external script requires the default `common/DayZ` directory and
Workshop content in that same library; unsupported layouts give guidance to choose
Native. Its `STEAM_ROOT` is set to the captured library explicitly.

## Automated evidence

Linux, Python 3.12, Qt offscreen; local temporary data and mocked network/process
boundaries. The full suite on 19 September ran **676 tests: OK, 5 skipped**.
The sandbox's local-socket restriction caused the single-instance test to fail;
the complete suite passed with local socket access. This is not a real game join.

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 venv/bin/python -m unittest discover -q
venv/bin/ruff format --check wolflauncher tests main.py scripts/render-windows-icon.py
venv/bin/ruff check wolflauncher tests main.py scripts/render-windows-icon.py
venv/bin/mypy wolflauncher/paths.py wolflauncher/persistence.py wolflauncher/redaction.py wolflauncher/secret_store.py
venv/bin/mypy --follow-imports=silent wolflauncher/server_identity.py wolflauncher/server_launch_context.py
```

Ruff 0.15.22 and mypy 2.3.0 match `requirements-quality.txt`. Lint and both type-check
commands pass. The targeted command checks the identity/context modules without
claiming imported legacy code is fully type-checked.

New tests cover both saved profiles, recoverable malformed rows, unknown fields,
rename-independent stars, alias conflicts, product-scoped provider IDs, interrupted
multi-file writes, journal recovery, schema versions 1–7, reopening migrated data,
unsupported live IDs, exact installation/engine selection, installation removal,
stale requests, worker failure, duplicate handoff, shutdown, browser switching and
editor isolation. Existing native-launcher tests cover Linux and Windows command
preparation. The full window was also constructed and switched Stable → Experimental
offscreen with background work suppressed; this checks construction, not live UI use.

### Browser timing

Budgets were chosen before measuring: query plus matching count under **250 ms**,
and 200 displayed rows under **1,000 ms**. The temporary cache had 20,000 rows,
split equally between products. Maximum of five query/count runs:

| Operation | Measured |
| --- | ---: |
| Unscoped baseline, 20,000 matches | 10.3 ms |
| Stable, 10,000 matches | 6.8 ms |
| Experimental, 10,000 matches | 7.1 ms |
| Populate 200 Qt table rows | 41.7 ms |

These are local measurements, not CI timing assertions or a network benchmark.
No Steam scan is performed per browser row. Identity and mod preparation workers
are bounded and obsolete results cannot authorize a launch.

## Saved data and restoration

The adapter reads `servers.yaml`, `servers-experimental.yaml`, `favourites.json`,
and `favourites-experimental.json` from the existing configuration directory.
Startup does not consolidate or delete those files. Profile location is only a
historical hint. Same-endpoint/aliased saved entries are displayed once, with stars
combined and contradictory identities retained for live resolution. Updates write
back to their original profile(s); new known EXP entries use the Experimental file.
Ordering is preserved within each profile; interleaving the two profiles is not a
persisted global order.

Writes preserve unknown fields and make a rolling `.bak` copy of each replaced
authoritative file. These backups represent the previous write, not a permanent
pre-upgrade snapshot. Before testing an upgrade, close WolfLauncher and copy the
whole configuration directory somewhere separate. Keep that snapshot when testing
multiple versions. History and settings also use atomic replacement and backups;
malformed history/settings are not silently overwritten on save. Damaged profile
files remain read-only, with recoverable entries visible and errors reported.

Multi-file profile/index changes use `saved-servers-transaction.json`, an undo
journal. A failed write restores originals; an interrupted process is recovered
on the next repository load. Do not delete an outstanding journal to bypass recovery.

To restore:

1. Close every WolfLauncher instance and copy the current configuration directory,
   including any journal and `.bak` files, for diagnosis.
2. Prefer restoring all authoritative files together from the separate snapshot.
   If using rolling `.bak` files, inspect dates and content first: independent
   previous writes need not represent one consistent point in time.
3. If restoring manually while an interrupted journal exists, retain it in the
   diagnostic copy and move it out of the live configuration directory before
   replacing files, so startup recovery cannot undo the intentional restore.
4. Start the launcher and confirm both profiles and stars. Unresolved historical
   identities are expected to need a new live query before joining.

The disposable server cache migrates transactionally to schema **8**. Older binaries
may refuse that schema. For a downgrade, close the launcher and move the cache and
its SQLite sidecars aside to rebuild with the older binary; restore the matching
pre-upgrade configuration snapshot as well, since older binaries do not understand
all product-scoped favourite keys. Never delete saved profiles to repair a cache.

Recent servers record **launch attempts at command handoff**, not confirmed joins.
Cancelled or failed preparation creates no recent entry. Legacy unknown and newly
identified history entries can remain distinct; history does not invent a product
for an old record.

## Editor compatibility

Editor and local profiles stay on Stable, including delayed Steam/Workshop callbacks.
The original interface is restored without an edition selector or compatibility notice.
Legacy Experimental local-tool preferences are ignored; Experimental tools are out of scope.
The [maintainer launch guide](https://github.com/InclementDab/DayZ-Editor/wiki/3.-Launching-Editor)
describes launching the client-side editor with its required mods. The
[main Editor item](https://steamcommunity.com/sharedfiles/filedetails/?id=2250764298)
and [separate Experimental item](https://steamcommunity.com/sharedfiles/filedetails/?id=2648049375)
have different dependency sets; the existence of an Experimental item does not
verify compatibility with the currently installed branch. No Experimental editor
runtime was exercised during this implementation.

If Experimental editor support is revisited in future, record the game build and matching
Editor/dependency item versions; verify offline startup, map loading, object
placement, save/reload and exit, then repeat with both games installed. Do not
substitute the standard Editor dependencies without testing them.

## Manual release matrix — pending

No new real-game join was performed for this refactor. Earlier Linux Experimental
launch evidence in the README predates this automatic-routing integration.

- Linux native Steam/Proton and Windows: Stable only, EXP only (with the required
  shared Workshop source), and both installations; Stable → EXP → Stable joins.
- Separate libraries/custom paths, vanilla and modded servers, incomplete install,
  uninstall/rescan and installation removal during preflight.
- Misfiled manual EXP favourite, offline/unknown/conflicting server, hostname and
  corrected query-port resolution, restart and preserved star/tag.
- Browser/favourite/recent/preview entry points; rapid selection/edition/filter
  changes during query, mods and Workshop work; cancellation and shutdown.
- Provider timeout/partial response, cached recovery, remote counts and map filters.
- Steam stopped, DayZ already running, first-run/BattlEye requirements and actual
  process handoff failure; verify the diagnostic report's edition and paths.
- Stable external launcher and local profiles after EXP joins; Stable Editor after
  changing the server browser edition while Workshop is preparing.

Record OS, commit, game builds, installation layout, redacted server identity and
launch report, expected/actual outcome, and whether the game actually joined.
