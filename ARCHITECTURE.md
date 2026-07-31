# Architecture

WolfLauncher is a Python + PySide6 Linux-first DayZ launcher. Its validated
native Python engine is the default, with a vendored external shell launcher
retained as a compatibility fallback during production hardening.

## Runtime Shape

```text
main.py
  -> wolflauncher.app.MainWindow
       -> Servers tab
       -> Server Browser tab
       -> Mods tab
       -> Settings tab
       -> guarded launch workflow
```

## Design Philosophy

WolfLauncher should make the Linux DayZ launch path feel calmer than the
underlying Steam, Proton, Workshop and server-query machinery. Prefer smooth,
low-noise flows that keep useful previous results visible while background work
runs, avoid unnecessary flicker, and reserve interruptions for decisions or
failures that genuinely need the user's attention.

Quiet should not mean dishonest. When WolfLauncher is checking, guessing,
falling back, handing off to Steam or lacking proof that DayZ actually started,
the UI, health checks, dialogs and diagnostics should say so clearly at the
right level of detail.

### GUI consistency contract

The v0.9 simplification pass uses progressive disclosure without feature loss.
Tabs should generally read from top to bottom as summary, common controls,
results and bottom actions. Frequent actions remain visible; specialist filters,
provider refresh, diagnostics, parity, copying and fallback tools may be placed
behind a compact direction-marked disclosure at the bottom. When the bottom row
also contains persistent primary actions, advanced tools align left and primary
actions align right.

Server Browser and Mods establish the approved reference layout. Both keep a
dense operational table on the left and use a draggable native inspector for
the current selection on the right. The Browser inspector owns endpoint,
truth/freshness, features, mod readiness and support diagnostics so Host and
ports do not consume its common scanning table; detailed columns and copied
details retain that data. Reuse `ui_sections.set_disclosure_state`, avoid
redundant labels and verify collapsed and expanded states at the default
1350x720 window size.

Moving directly from Server Browser to Mods carries the highlighted discovered
server into the same read-only active context used by **View mod details**.
Rows from a previous curated or discovered server are cleared before the new
mod check starts or queues, so Mods never labels stale content as the current
Browser selection.

## Module Map

```text
wolflauncher/
  app.py                 Main Qt GUI, tabs and launch workflow coordination
  connect_preflight.py   Qt coordination for Steam/Workshop connect preparation
  launch_execution.py    Qt command preparation, preview and launch handoff
  settings_health_controller.py
                         Qt Settings health refresh and table coordination
  workshop_resolution_controller.py
                         Qt Steam Workshop resolution-session coordination
  config.py              YAML server loading and default launcher candidates
  curated_server_presenter.py
                         Pure curated-row display construction
  diagnostics.py         Human-readable diagnostics report
  launcher.py            External dayz-launcher.sh command builder
  launch_dialogs.py      External/native handoff dialogs and process watching
  launch_preflight.py    Pure ordered launch-preflight policy
  launch_selection.py    Validated cached resolved-IP target selection
  models.py              Shared dataclasses
  mod_presenter.py       Pure Mods-tab summary and row presentation
  dayz_mod_query.py      strict direct DayZ A2S_RULES manifest decoder
  mods.py                direct server mod lookup and local Workshop comparison
  platform_detection.py  Shared Steam-library parsing, selection and readiness facade
  platforms/
    base.py              Platform capability and backend contracts
    linux.py             Validated Linux paths, commands and process detection
    windows.py           Windows paths, registry discovery and process detection
  native_launcher.py     Native launch engine, parity and failure-report details
  local_tools.py         Pure local profile parsing and DayZ Editor defaults
  local_tools_feature.py Editor/local-LAN development workspace
  server_discovery.py    WolfAPI, BattleMetrics, Steam Web API and legacy master server candidate discovery
  server_enrichment.py   Maps live status results onto discovered cache rows
  server_cache.py        SQLite cache for discovered public servers
  server_browser_controller.py
                         Discovered-server cache queries and filter options
  server_browser_presenter.py
                         Pure discovered-row and copied-details presentation
  server_browser_table.py
                         Qt discovered-row population
  server_map_atmosphere.py
                         Map-family selection and inspector atlas rendering
  settings.py            JSON settings and favourites under ~/.config/wolflauncher
  settings_health.py     Settings health snapshot construction
  status.py              gamedig server status and DNS resolution
  table_items.py         Data-aware Qt table sorting item
  ui_sections.py         Shared progressive-disclosure state helper
  workers.py             Background status, mod, discovery and enrichment threads
```

## External Tools

```text
gamedig             live DayZ server status
dig                 DNS lookup support
Steam               game ownership, Workshop downloads and Proton launch
dayz-launcher.sh    current launch engine
```

The native Python launcher is the default launch engine. A copy of the MIT-licensed upstream shell launcher is vendored at `external/dayz-linux-cli-launcher/` as the legacy reference engine and selectable fallback. WolfLauncher is responsible for preparing the user, validating the environment and generating the handoff command.

## Data Model

Current storage:

```text
example.servers.yaml              tracked, read-only curated server template
$XDG_CONFIG_HOME/wolflauncher/servers.yaml
                                  user-owned curated server list
$XDG_CONFIG_HOME/wolflauncher/settings.json
$XDG_CONFIG_HOME/wolflauncher/favourites.json
$XDG_DATA_HOME/wolflauncher/curated_status.json
$XDG_DATA_HOME/wolflauncher/last_launch_report.txt
$XDG_DATA_HOME/wolflauncher/server_cache.sqlite3
```

Recommended long-term split:

```text
servers.yaml      XDG-config curated, personal and import/export servers
SQLite            discovered/scraped server browser cache
settings.json     user preferences
favourites.json   favourite server keys
```

YAML should stay useful for hand-curated servers even after SQLite is introduced.

The v0.6 SQLite foundation stores discovered public servers separately from curated YAML entries. Cached rows retain endpoint keys for launch/connect behavior and non-WolfAPI providers, while also storing optional required-mod counts, status provenance, WolfAPI stable IDs and aliases, freshness/validation evidence and checked/seen timestamps. Provider status is advisory until local enrichment succeeds or fails: provider claims are amber, while local validation owns green/red status. A discovered row can become the active in-memory server context for mod inspection, Workshop resolution and guarded launch without changing `servers.yaml`; explicit promotion remains the optional path to user-owned persistence. Settings owns imports, provider choice, credentials, refresh limits, opt-in automatic HTTP refresh and health checks. Discovery includes WolfAPI v1 and its legacy fallback, BattleMetrics, Steam Web API and legacy Steam master paths. Full-snapshot providers replace only their own rows after success; bounded WolfAPI v1 pages and debounced remote searches merge by stable ID without deleting off-page entries. Failed refreshes and searches preserve cached rows. Explicit visible-row enrichment runs concurrently, applies results in browser order, preserves display names, required-mod counts, provider country metadata and locally measured game-time metadata, tries bounded query-port fallbacks and atomically replaces obsolete endpoint keys after live port correction. Discovered SQLite rows are not automatically UDP-probed. Schema v7 migrates earlier shapes in place and combines Workshop metadata with WolfAPI v1 identity, freshness fields, cached required-mod metadata provenance, advisory quality flags, nullable BattleMetrics country provenance and Launcher-owned game time/acceleration. Curated YAML rows can still be added, promoted, edited, removed and updated in-app.

WolfAPI should be treated as the companion hosted discovery service, not as the launcher source of truth. The bounded strict v1 path is the provider default for fresh installations after production and desktop canaries passed, while existing saved choices remain unchanged and `WolfAPI (legacy fallback)` stays selectable. V1 refreshes paginate in the background, and Server Browser search remains local-first before a debounced remote name search or exact `host:port` resolution merges additional matches. Exact resolution checks the supplied port as both game and query port, deduplicates stable IDs and preserves current/historical aliases. The browser carries `coverage.eligible` through those bounded responses and persists the last known value as the whole-directory count; SQLite totals remain explicitly local cache counts. SQLite schema v7 retains endpoint `cache_key` values for launch/connect behavior and non-WolfAPI providers while combining Workshop metadata with stable IDs, aliases, freshness/validation state, API required-mod evidence, advisory quality flags, nullable country provenance and local game-time metadata for WolfAPI rows; a corrected endpoint moves the stable row instead of creating a duplicate. The advanced quality-warning filter is enabled by default and filters cached rows plus remote v1 list/name-search calls without deleting flagged data or changing exact-resolution truth. As a conservative local safety net, WolfAPI ingestion flags three or more distinct endpoints advertising the same normalized provider name as a duplicate-name cluster; API-supplied quality classification remains the directory-wide source of truth. `/api/health` remains diagnostics/support data. Launcher features must stay resilient when WolfAPI is unavailable, preserve the local SQLite cache and curated YAML promotion flow, and keep selected-server/launch-time truth checks local after fixed startup polling is retired.

API freshness and validation are presentation evidence, not local reachability.
They appear in the existing Status tooltip and copied details without changing
the approved table hierarchy. When a cached `freshness_expires_at` has passed,
the launcher marks the stored label as expired/pending refresh rather than
inventing the next server state. Ping and selected/launch-time checks remain
local.

The planned transition from launcher polling to API-owned directory freshness is specified in `DISCOVERY_FRESHNESS_HANDOFF.md`. It preserves local selected-server/launch checks and offline cache use while moving shared validation age, provenance, canonical identity and scheduling responsibility into a stable WolfAPI contract.

## Server Status

Flow:

```text
Server row
  -> status.check_server
  -> gamedig query
  -> resolved IP, connect address and status fields
  -> GUI table update
```

Partial responses during server restarts should be treated as offline/restarting rather than online with unknown fields.

The GUI can refresh all curated rows or a selected curated row. Single-row
refreshes should reuse the same status path and table update behavior as full
refreshes so manual add/edit flows can validate one server without disturbing
the rest of the list.

Curated rows cache their last-known live status locally so startup can show
useful previous results while fresh checks run. Cached status is advisory only:
fresh status checks replace it, and offline/error results should overwrite
previous online values rather than preserving stale optimism.

## Mod Management

Flow:

```text
Selected server
  -> resolve host
  -> query DayZ SA Launcher style API
  -> read required Steam Workshop IDs
  -> scan local workshop/content/221100
  -> compare required vs installed
  -> display installed/missing mods and Workshop links
```

The ordinary mod check is read-only and advisory. When Steam is running, its
local-directory result is augmented by an isolated batch
`ISteamUGC::GetItemState` query so installed-but-outdated, pending and
downloading items do not count as launch-ready. After explicit confirmation, a
resolution path can pass those unready IDs to the signed-in Steam client.
`workshop_subscription.py` runs every Steamworks session in a spawned helper
process, dynamically loads the existing official `libsteam_api.so`, monitors
Steam state and treats both Steam state and Workshop directories as readiness
evidence. The helper exits before launch is re-enabled so Steam cannot retain
WolfLauncher's long-lived GUI process as the DayZ app-ID owner. On restart,
numeric folders in Steam's `workshop/downloads/221100` staging area provide a
conservative recovery signal only when they match the selected server's still-
unready required IDs. WolfLauncher does not download bytes itself, silently
unsubscribe or remove content; manual Workshop pages remain the fallback.
The Mods tab can copy a timestamped mod-check report with server target, required
mod counts, installed/missing state, Workshop URLs and missing Workshop IDs for
native parity testing and support. It can also copy only the missing Workshop
links for manual Steam subscription.

## Launching

WolfLauncher uses a guarded native launch workflow by default. The external
fallback preserves this command contract:

```text
bash dayz-launcher.sh -s resolved_ip:game_port -p query_port -n player_name --launch
```

On Windows, the native direct handoff adds `-useBE` before `-nolauncher` so the
BattlEye service is explicitly requested when the official DayZ launcher is bypassed.

Before launch, the GUI checks that:

- DayZ is detected.
- The DayZ Workshop folder is detected.
- Steam is running, or the user explicitly chooses to launch anyway.
- The latest mod check belongs to the selected server and its selected Steam
  install context. The native path requires every required Workshop directory
  and a fresh Steam item-state check before handoff; the external fallback
  retains its explicit warning boundary.

The launch dialog shows the generated command and captures launcher output. Exit code 0 means the command was successfully handed off to Steam; it does not prove that Proton or DayZ reached the main menu.

The vendored legacy launcher performs the lower-level launch work:

```text
DayZSA API query (legacy external launcher only)
  -> required Workshop IDs
  -> local Workshop folder checks
  -> shortened @base64modid symlinks in the DayZ directory
  -> -mod=... command line
  -> steam -applaunch 221100
```

This behavior is the reference contract for any future native Python launcher engine.

WolfLauncher's native engine and Mods screen no longer use that third-party
lookup. Their existing background `ModWorker` queries the selected game
server's binary `A2S_RULES` manifest directly, rejects incomplete or ambiguous
manifests atomically, and then uses Steam only for Workshop display metadata
and local install state. DNS, UDP reassembly, decoding and Steam metadata work
remain off the Qt UI thread on both Windows and Linux.

The native Python engine lives behind `wolflauncher.native_launcher`.
It currently prepares the shell launcher's shortened `@base64modid` symlinks,
checks installed Workshop mod directories and metadata, resolves the server host,
and generates the native Steam `-applaunch 221100` command line.
The GUI uses the native engine by default. Real-world native Steam handoffs
have reached DayZ process detection with Steam running and stopped,
including unmodded, fully modded and partially missing-mod server cases. The
external shell handoff remains selectable as a fallback.
The Mods tab native preview produces a copyable parity report with a validation
checklist and readiness comparison for selected Steam install setting, detected
Steam install, resolved connect target, query port, external command, native
command, required Workshop IDs, prepared mod links and missing Workshop
directories. The report calls out that the external launcher refetches server
requirements at launch while the native candidate uses the current WolfLauncher
mod check and prepared local Workshop links. When the native command is ready,
the preview dialog can copy only that command for terminal parity testing while
keeping the full report copy action.
Stale `@mod` symlink conflicts are reported with expected and actual targets so
native failure reports remain easy to compare with filesystem state.

When the native engine is selected, Settings can target Auto, Native Steam or
`STEAM_ROOT` for native-launch testing. Mod checks, preview and launch preflight
use that selected install so a secondary library cannot be confused with the
active native Steam installation.
The Mods summary and copied mod report include the Steam install context and
Workshop path checked so selected-mode mismatches are visible in support
snapshots.
Native command generation should fail before handoff when the selected Steam
mode does not have a detected launch command, so users get Steam-mode-specific
recovery guidance instead of a generic process-start failure.
Settings health and diagnostics should show the selected Steam mode alongside
the other detected install candidates and launch command details, making Auto
selection explainable when native Steam and `STEAM_ROOT` disagree.

Native Steam detection reads `steamapps/libraryfolders.vdf` from the detected
Steam root and scans secondary Steam libraries for DayZ and Workshop folders.
`STEAM_ROOT` remains an explicit single-library override for targeted testing.
Flatpak and Snap Steam are outside the current compatibility contract: neither
is offered in Settings or Auto detection, and stale Flatpak launch requests
fail before handoff.

## Editor / Local Tools

The Editor / Local Tools tab is an explicit advanced-development workspace,
separate from curated YAML and the discovered-server cache. Editor selections
are a separate locally installed-only checklist persisted as
`editor_extra_mod_ids` in `settings.json`; they are combined with DayZ Editor
(`2250764298`), CF (`1559212036`) and Dabs Framework (`2545327648`) for an
offline handoff without `-connect`. Local Development alone owns the saved
profile data: name, ordered client Workshop IDs and existing LAN
`host:game-port` endpoint, used to launch native DayZ into that test server.

Local Development can also manage a dedicated-server root accessible to the
running Launcher (same machine or mounted share). It starts/stops only its
owned process, asks the Windows Steam client to install its App ID 223350 tool
and detects completion from Steam library manifests; SteamCMD remains available
for an anonymous custom-path installation. It accepts explicit client/server local mod folders, and copies only
public `.bikey` files into the server `keys` directory after confirmation.
Private keys are never read or copied. Source-development mode enables
`-filePatching` and is deliberately not a release/signature test.

Steam remains the only Workshop subscription/download owner. When the Editor
action is selected, WolfLauncher explicitly asks Steam to subscribe/update its
three standard requirements, waits for the isolated helper to finish, rechecks
the local directories and only then launches. Its handoff dialog closes and the
main window minimizes once DayZ is detected. V1 does not start, stop, install,
configure, expose or monitor a dedicated server. Future hosting must use an
explicit configured server root (the dedicated-server app is separate from the
DayZ client), with bounded process control and logs; it must not infer
public-hosting scope from a local profile.

## Known External Issue

DayZ currently does not run when Steam launch options contain:

```text
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

This is a Steam/Proton/DayZ compatibility issue. It is an advisory FAQ item in
Settings, not a launcher readiness check. WolfLauncher must not read, write,
suggest or default Steam launch options; users should remove the option in
Steam and test DayZ directly there while investigating.

## Platform Support

Linux remains the primary supported and release-validation target. OS-owned
concerns enter through the small `platforms` backend boundary, while shared
Steam library parsing and readiness behavior remain behind
`platform_detection.py`.

Windows has an experimental runtime backend. It reads Valve registry locations,
reuses shared `libraryfolders.vdf` and app-manifest parsing, launches through
native `steam.exe`, inspects processes through `tasklist`, and stores config and
data under roaming and local AppData respectively. Windows passes absolute
Workshop item directories to DayZ's `-mod=` argument instead of creating links
inside the DayZ installation. The selected DayZ `steam_api64.dll` supplies the
same Steamworks exports used by the isolated Workshop helper.

Current Windows evidence covers detection, persistence, GUI construction,
native command preview and handoff, DLL exports, installed and missing-mod
Steamworks flows, a portable ZIP and a per-user installer on Windows 11.
Signing, update delivery and broader release-artifact desktop coverage remain
validation gates, so Windows is experimental rather than a supported release.

Update ownership is platform-native. Windows uses a signed evergreen
bootstrapper and prompted replacement through a verified signed installer;
Linux uses a signed APT repository and the system package manager. The running
launcher may check and explain availability but must not silently replace its
own executable or system-owned files. See `docs/UPDATE_STRATEGY.md`.

Primary target:

- Linux Mint
- Ubuntu/Debian family

The minimum validated functional Linux baseline is Ubuntu 24.04.4 LTS on an
Intel Core i5-8250U with 8 GB RAM and native Steam downloaded directly from
Steam. It completed the launch path with poor performance, so it is a
provisional floor rather than a recommended specification. Flatpak and Snap
Steam are not compatible.

The Windows functional baseline is Windows 10 on an Intel Core i5-8250U with
8 GB RAM using native Steam. It has completed the WolfLauncher DayZ handoff,
but Windows remains experimental until its signing, update and packaged-release
gates are complete.

Experimental target:

- Windows source runtime

Secondary future targets:

- Steam Deck
- Other Linux distributions
