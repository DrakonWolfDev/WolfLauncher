# WolfLauncher Project State

Current snapshot: end of v0.5.2.

WolfLauncher is a Linux-first DayZ launcher GUI built with Python and PySide6. It currently wraps the existing MIT-licensed `dayz-linux-cli-launcher` style shell launcher instead of replacing it.

The upstream shell launcher is now vendored under `external/dayz-linux-cli-launcher/` so the current working behavior can be inspected and replaced gradually.

## Current status

The v0.5.2 launch, status, settings health checks and mod-checking work is considered functional. The application can be used as the working project base for the next improvement cycle.

Working:

- PySide6 desktop GUI.
- YAML curated server list.
- Read-only SQLite-backed discovered server browser tab.
- YAML/JSON import for discovered server cache rows.
- Promotion from discovered cache rows into the curated YAML server list with editable name/group.
- In-app editing/removal of curated YAML server rows.
- Copy actions for discovered server connect addresses and details.
- Steam master server candidate discovery import script.
- Single in-app discovered-server database refresh using the provider selected in Settings.
- Steam Web API server-list discovery with user-supplied API key.
- BattleMetrics server discovery.
- Optional quiet rate-limited startup refresh for the selected discovery provider, throttled to once per day.
- Enrichment of visible discovered servers with live status data.
- Live enrichment preserves cached display names, stores differing live server names separately and updates game ports from queried connect addresses when available.
- Live enrichment probes a bounded set of likely query ports when discovered rows have uncertain port data.
- Failed provider refreshes preserve existing discovered-server cache rows.
- Server Browser map and version filters populated from cached/enriched values.
- DNS hostname and direct IP support.
- Live DayZ server querying through `gamedig`.
- Partial `gamedig` restart responses are treated as offline/restarting rather than as healthy online rows.
- Server status table with map, players, time, ping, version, flags and connect address.
- Native Steam detection.
- Flatpak Steam detection.
- DayZ install detection.
- DayZ Workshop folder detection.
- Settings tab with compact green/yellow/red health checks.
- Discovery provider, API key, endpoint and refresh-limit settings persistence.
- Favourites persistence.
- Last selected server persistence.
- Mods tab.
- Required mod lookup via DayZ SA Launcher style API.
- Local Workshop folder scan.
- Required-vs-installed mod comparison.
- Missing mod list and Steam Workshop links.
- Mods table double-click and right-click actions.
- Mods filtering for all/missing/installed.
- Copy Workshop ID, mod name, Workshop URL, connect address and server details.
- Guarded launch workflow through the external `dayz-launcher.sh` script.
- Launch commands pass the resolved server IP to the external launcher when available.
- Missing-mod warning with Open Workshop / Launch Anyway / Cancel.
- Steam-not-running warning.
- Launch output dialog with generated command and launcher output.
- Successful external-launcher exit code is presented as a handoff to Steam.

## Known bug

- DayZ currently does not run when the Steam launch options contain `__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%`.

Current handling:

- Treat this as an external Steam/Proton/DayZ launch-option compatibility issue, not a WolfLauncher command-generation failure.
- Do not recommend that option as the default workaround.
- Future work should investigate hybrid-GPU/NVIDIA PRIME diagnostics and safer launch-option guidance.

## Key files

- `AGENTS.md` - quick project orientation for future coding agents.
- `main.py` - entry point.
- `wolflauncher/app.py` - main Qt GUI, tabs, table actions and launch workflow.
- `wolflauncher/status.py` - `gamedig` server querying and host resolution.
- `wolflauncher/mods.py` - required mod lookup and local Workshop scanning.
- `wolflauncher/platform_detection.py` - Steam, DayZ and Workshop detection.
- `wolflauncher/launcher.py` - external launcher command building.
- `wolflauncher/server_cache.py` - SQLite cache for discovered public servers.
- `wolflauncher/settings.py` - user settings and favourites.
- `wolflauncher/config.py` - YAML server loading and default launcher path candidates.
- `tests/` - standard-library unit tests for launcher commands, vendored launcher handoff contract, path discovery, YAML loading, status parsing and mod parsing.
- `servers.yaml` - curated server registry.
- `external/dayz-linux-cli-launcher/dayz-launcher.sh` - vendored MIT legacy launch engine.
- `LICENSE` - WolfLauncher MIT license.
- `THIRD_PARTY_NOTICES.md` - third-party license notices.
- `CHANGELOG.md` - version history.
- `ROADMAP.md` - planned milestones.
- `ARCHITECTURE.md` - architecture and design notes.

## Important design decisions

- YAML is the curated server/source-of-truth format for early versions.
- SQLite is now introduced as the discovered public server browser cache.
- v0.6 has started with a standalone SQLite server cache foundation and read-only browser tab for discovered public servers.
- Provider refreshes sync their discovered rows after successful responses by removing stale provider-backed entries and adding only new cache keys; failed refreshes preserve existing cache rows. Curated YAML remains the place for saved servers.
- JSON is used for user settings and favourites under `~/.config/wolflauncher`.
- The external shell launcher remains the launch engine for now.
- The vendored shell launcher is the reference contract for future native launcher work.
- Mod management is read-only and advisory: it detects installed/missing mods and opens Workshop pages, but does not attempt automatic downloads.
- Launch remains guarded: WolfLauncher warns about missing mods and Steam state before calling the external launcher.
- Hostnames are resolved before launch where possible to mirror the original terminal menu behaviour and avoid DayZSA API issues with DNS-based servers.
- Python bytecode caches are ignored and should not be tracked as source.
- WolfLauncher is MIT licensed; vendored third-party MIT notices are preserved separately.

## Next step

Use v0.6 as the next active development target:

- Keep BattleMetrics as the default no-key discovery source while allowing users to choose Steam Web API or UDP master discovery in Settings.
- Improve bulk enrichment controls and keep refining candidate port probing from real-world server data.
- Continue improving curated server organisation beyond basic edit/remove flows.
- Keep `servers.yaml` for curated, personal and import/export server lists.
- Improve filtering, sorting and settings health checks around the existing stable launch flow.
- Continue extracting tests and documentation from the vendored launcher's behavior before rewriting it.
- Keep the NVIDIA PRIME Steam launch-option issue visible as the only known bug until it is reproduced and diagnosed.
