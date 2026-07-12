# Architecture

WolfLauncher is a Python + PySide6 Linux-first DayZ launcher. At the end of v0.5.2 it is a working GUI wrapper around a proven external shell launcher, with pre-launch checks moved into the application.

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

Server Browser and Mods establish the approved reference layout. Reuse
`ui_sections.set_disclosure_state`, avoid redundant labels and verify both
collapsed and expanded states at the default 1350x720 window size. Theme,
typography and branding follow after structural hierarchy is settled.

## Module Map

```text
wolflauncher/
  app.py                 Main Qt GUI, tabs and launch workflow coordination
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
  mods.py                DayZSA API mod lookup and local Workshop comparison
  platform_detection.py  Native/Flatpak Steam, Steam library, DayZ and Workshop detection
  native_launcher.py     Native launch engine, parity and failure-report details
  server_discovery.py    WolfAPI, BattleMetrics, Steam Web API and legacy master server candidate discovery
  server_enrichment.py   Maps live status results onto discovered cache rows
  server_cache.py        SQLite cache for discovered public servers
  server_browser_controller.py
                         Discovered-server cache queries and filter options
  server_browser_presenter.py
                         Pure discovered-row and copied-details presentation
  server_browser_table.py
                         Qt discovered-row population
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
example.servers.yaml              tracked curated server template
servers.yaml                      local ignored curated server list
~/.config/wolflauncher/settings.json
~/.config/wolflauncher/favourites.json
~/.local/share/wolflauncher/curated_status.json
~/.local/share/wolflauncher/last_launch_report.txt
~/.local/share/wolflauncher/server_cache.sqlite3
```

Recommended long-term split:

```text
servers.yaml      local curated, personal and import/export servers
SQLite            discovered/scraped server browser cache
settings.json     user preferences
favourites.json   favourite server keys
```

YAML should stay useful for hand-curated servers even after SQLite is introduced.

The v0.6 SQLite foundation stores discovered public servers separately from curated YAML entries. Cached rows are keyed by `host:game_port:query_port` and include browser-oriented fields such as display name, live server name, map, player counts, ping, version, optional required-mod count, mod/password flags, status provenance and checked/seen timestamps. Provider status is explicitly advisory until local enrichment succeeds or fails; provider claims are amber while local validation owns green/red status. This keeps scraped or transient public browser data out of `servers.yaml` while still giving the GUI a searchable local cache. A discovered row can become the active in-memory server context for mod inspection, Workshop resolution and guarded launch without changing `servers.yaml`; a successful inspection can add its known required-mod count to the cache, while explicit promotion remains the optional path to user-owned persistence. Map, version and source filters are populated from cached/enriched values when present, with result-limit controls, cache summary counts and data-aware sorting for numeric and freshness fields. Settings owns YAML/JSON cache imports, provider choice, API keys, Steam master endpoint overrides, refresh limits, opt-in automatic refresh and compact health checks. Provider discovery includes the hosted WolfAPI cache, BattleMetrics, Steam Web API and legacy Steam master paths. Provider refreshes sync their own source rows after successful responses by removing entries no longer returned by the service and inserting only new cache keys. Failed provider refreshes preserve existing cache rows. Enrichment confirms live names, maps, player counts and status where query ports respond, preserves cached display names and required-mod counts, and tries a bounded set of likely query-port fallbacks. Checks run concurrently but results are applied in current top-to-bottom browser order; the first 30 filtered/sorted rows are enriched quietly at most once per day. When a live connect-port correction changes `host:game_port:query_port`, the corrected row atomically replaces the obsolete key instead of creating a duplicate. Schema v2 adds required-mod count and status-provenance columns through an in-place migration. Curated YAML rows can be added directly, promoted from discovery, edited, removed and updated from live connect-port results in-app.

WolfAPI should be treated as the companion hosted discovery service, not as the launcher source of truth. Its public contract for WolfLauncher is `/api/servers`; `/api/health` is useful for diagnostics and support snapshots. As of the current WolfAPI work, Redis remains the hot public cache, Postgres stores durable canonical/history tables, scheduled Steam/BattleMetrics/live-validation jobs update Redis, and Postgres-to-Redis publishing remains a manual recovery operation. Launcher-side features should stay resilient when WolfAPI is unavailable, preserve the local SQLite cache and curated YAML promotion flow, and request explicit stable API fields before depending on source freshness, validation, quality or future submission metadata.

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

The normal mod-manager path remains read-only and advisory. When experimental Steam integration is enabled and Steam is running, its local-directory result is augmented by an isolated batch `ISteamUGC::GetItemState` query so installed-but-outdated, pending and downloading items do not count as launch-ready. An explicitly confirmed resolution path can pass those unready IDs to the signed-in Steam client. `workshop_subscription.py` runs every Steamworks session in a spawned helper process, dynamically loads the existing official `libsteam_api.so`, monitors Steam state and treats both Steam state and Workshop directories as readiness evidence. The helper exits before launch is re-enabled so Steam cannot retain WolfLauncher's long-lived GUI process as the DayZ app-ID owner. On restart, numeric folders in Steam's `workshop/downloads/221100` staging area provide a conservative recovery signal only when they match the selected server's still-unready required IDs; WolfLauncher reports possible Steam activity and requires a fresh mod check rather than treating the Workshop catalogue as a reliable live queue. WolfLauncher does not download bytes itself, silently unsubscribe, or remove content; manual Workshop pages remain the fallback.
The Mods tab can copy a timestamped mod-check report with server target, required
mod counts, installed/missing state, Workshop URLs and missing Workshop IDs for
native parity testing and support. It can also copy only the missing Workshop
links for manual Steam subscription.

## Launching

WolfLauncher v0.5.2 calls the external launcher script through a guarded launch workflow:

```text
bash dayz-launcher.sh -s resolved_ip:game_port -p query_port -n player_name --launch
```

Before launch, the GUI checks that:

- DayZ is detected.
- The DayZ Workshop folder is detected.
- Steam is running, or the user explicitly chooses to launch anyway.
- The latest mod check for the selected server has no missing required mods, or the user explicitly chooses to launch anyway.

The launch dialog shows the generated command and captures launcher output. Exit code 0 means the command was successfully handed off to Steam; it does not prove that Proton or DayZ reached the main menu.

The vendored legacy launcher performs the lower-level launch work:

```text
DayZSA API query
  -> required Workshop IDs
  -> local Workshop folder checks
  -> shortened @base64modid symlinks in the DayZ directory
  -> -mod=... command line
  -> steam -applaunch 221100
```

This behavior is the reference contract for any future native Python launcher engine.

The native Python engine lives behind `wolflauncher.native_launcher`.
It currently prepares the shell launcher's shortened `@base64modid` symlinks,
checks installed Workshop mod directories and metadata, resolves the server host,
and generates the native or Flatpak Steam `-applaunch 221100` command line. The
The GUI uses the native engine by default. Real-world native Steam and Flatpak
Steam handoffs have reached DayZ process detection with Steam running and stopped,
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

When the native engine is selected, Settings can target Auto, Native Steam,
Flatpak Steam or `STEAM_ROOT` for native-launch testing. Mod checks, preview and
launch preflight should use that selected install so native and Flatpak parity
testing cannot accidentally read Workshop state from a different Steam library.
The Mods summary and copied mod report include the Steam install context and
Workshop path checked so selected-mode mismatches are visible in support
snapshots.
Native command generation should fail before handoff when the selected Steam
mode does not have a detected launch command, so users get Steam-mode-specific
recovery guidance instead of a generic process-start failure.
Settings health and diagnostics should show the selected Steam mode alongside
the other detected install candidates and launch command details, making Auto
selection explainable when native Steam, Flatpak Steam and `STEAM_ROOT`
disagree.

Native and Flatpak Steam detection reads `steamapps/libraryfolders.vdf` from the
detected Steam root and scans secondary Steam libraries for DayZ and Workshop
folders. `STEAM_ROOT` remains an explicit single-library override for targeted
testing.

## Known Launch-Option Issue

DayZ currently does not run when Steam launch options contain:

```text
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

This remains tracked as the only known bug after v0.7 health-check polish. Keep it visible in docs and diagnostics planning, but do not make it the default launch recommendation until it is reproduced and a safe workaround is confirmed.

WolfLauncher should continue to treat Steam launch options as external state. The app may surface diagnostics that help users reason about PRIME, such as visible `__NV_PRIME_RENDER_OFFLOAD`, `__GLX_VENDOR_LIBRARY_NAME` and `DRI_PRIME` environment values, but it should not infer the effective per-game Steam launch option unless a future implementation has a reliable source of truth.

Recommended investigation flow:

- Confirm whether the user is running native Steam or Flatpak Steam.
- Confirm GPU driver, PRIME helper and Proton version.
- Test GPU offload outside WolfLauncher, for example `prime-run glxinfo -B` and `prime-run steam`.
- Test DayZ directly from Steam with no per-game launch option.
- Compare that direct-Steam result with the WolfLauncher handoff command and diagnostics report.

Until the issue is reproduced, the app should avoid writing, suggesting or defaulting to the known-bad `__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%` launch option.

## Platform Support

Primary target:

- Linux Mint
- Ubuntu/Debian family

Secondary future targets:

- Steam Deck
- Other Linux distributions

Possible later target:

- Windows
