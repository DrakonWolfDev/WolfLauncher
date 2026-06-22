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

## Module Map

```text
wolflauncher/
  app.py                 Main Qt GUI, workers, tables, dialogs and launch flow
  config.py              YAML server loading and default launcher candidates
  diagnostics.py         Human-readable diagnostics report
  launcher.py            External dayz-launcher.sh command builder
  models.py              Shared dataclasses
  mods.py                DayZSA API mod lookup and local Workshop comparison
  platform_detection.py  Native/Flatpak Steam, Steam library, DayZ and Workshop detection
  native_launcher.py     Native launch-engine foundation for mod links and Steam commands
  server_discovery.py    WolfAPI, BattleMetrics, Steam Web API and legacy master server candidate discovery
  server_enrichment.py   Maps live status results onto discovered cache rows
  server_cache.py        SQLite cache for discovered public servers
  settings.py            JSON settings and favourites under ~/.config/wolflauncher
  status.py              gamedig server status and DNS resolution
```

## External Tools

```text
gamedig             live DayZ server status
dig                 DNS lookup support
Steam               game ownership, Workshop downloads and Proton launch
dayz-launcher.sh    current launch engine
```

The external launcher remains the launch engine for now. A copy of the MIT-licensed upstream shell launcher is vendored at `external/dayz-linux-cli-launcher/` as the legacy reference engine. WolfLauncher is responsible for preparing the user, validating the environment and generating the handoff command.

## Data Model

Current storage:

```text
servers.yaml                      curated server list
~/.config/wolflauncher/settings.json
~/.config/wolflauncher/favourites.json
~/.local/share/wolflauncher/server_cache.sqlite3
```

Recommended long-term split:

```text
servers.yaml      curated, personal and import/export servers
SQLite            discovered/scraped server browser cache
settings.json     user preferences
favourites.json   favourite server keys
```

YAML should stay useful for hand-curated servers even after SQLite is introduced.

The v0.6 SQLite foundation stores discovered public servers separately from curated YAML entries. Cached rows are keyed by `host:game_port:query_port` and include browser-oriented fields such as display name, live server name, map, player counts, ping, version, mod/password flags and checked/seen timestamps. This keeps scraped or transient public browser data out of `servers.yaml` while still giving the GUI a searchable local cache. The Server Browser tab is read-only and focused on searching, filtering by map/version/source and name-derived style hints such as PvE/PvP, refreshing the local database from the configured Settings provider, enriching visible rows with live status data, copying server details, and explicitly promoting a discovered row into the curated YAML list with an editable name/group. Map, version and source filters are populated from cached/enriched values when present, with result-limit controls, cache summary counts and data-aware sorting for numeric and freshness fields. Settings owns YAML/JSON cache imports, provider choice, API keys, Steam master endpoint overrides, refresh limits, opt-in automatic refresh and compact health checks. Provider discovery includes the hosted WolfAPI cache, BattleMetrics, Steam Web API and legacy Steam master paths. Provider refreshes sync their own source rows after successful responses by removing entries no longer returned by the service and inserting only new cache keys, preserving existing enriched rows until the server disappears from the provider response. Failed provider refreshes preserve existing cache rows. Enrichment confirms live names, maps, player counts and status where query ports respond, preserves cached display names, tries a bounded set of likely query-port fallbacks for uncertain rows, and updates the cached game port from the queried connect address when available. Curated YAML rows can be added directly, promoted from discovery, edited and removed in-app, while the guarded launch workflow remains owned by curated servers.

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

The mod manager is advisory. It detects and opens Workshop pages, but does not subscribe, download or mutate Workshop content.

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

The native Python replacement has started behind `wolflauncher.native_launcher`.
It currently prepares the shell launcher's shortened `@base64modid` symlinks,
checks installed Workshop mod directories and metadata, resolves the server host,
and generates the native or Flatpak Steam `-applaunch 221100` command line. The
GUI still uses the external shell handoff by default until native launch parity
is proven with broader real-world testing. Real-world native Steam and Flatpak
Steam handoffs have both reached DayZ process detection through the experimental
path; broader multi-server and missing-mod parity still need coverage.
The Mods tab native preview produces a copyable parity report with a validation
checklist for selected Steam install, resolved connect target, external command,
native command, required Workshop IDs, prepared mod links and missing Workshop
directories.

When the native engine is selected, Settings can target Auto, Native Steam,
Flatpak Steam or `STEAM_ROOT` for native-launch testing. Mod checks, preview and
launch preflight should use that selected install so native and Flatpak parity
testing cannot accidentally read Workshop state from a different Steam library.
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
