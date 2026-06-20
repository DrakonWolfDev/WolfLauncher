# WolfLauncher Project State

Current snapshot: v0.5.3 alpha prototype.

WolfLauncher is a Linux-first DayZ launcher GUI built with Python and PySide6. It currently wraps the existing MIT-licensed `dayz-linux-cli-launcher` style shell launcher rather than replacing it.

## Current status

Working:

- Launch command handoff to Steam via the external shell launcher has been validated.
- Launch output now reports successful Steam handoff more clearly.

- PySide6 desktop GUI.
- YAML curated server list.
- DNS hostname and direct IP support.
- Live DayZ server querying through `gamedig`.
- Server status table with map, players, time, ping, version, flags and connect address.
- Native Steam detection.
- Flatpak Steam detection.
- DayZ install detection.
- DayZ Workshop folder detection.
- Diagnostics tab.
- Settings persistence.
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
- Missing-mod warning with Open Workshop / Launch Anyway / Cancel.
- Steam-not-running warning.
- Launch output dialog with generated command and launcher output.

## Key files

- `main.py` - entry point.
- `wolflauncher/app.py` - main Qt GUI and launch workflow.
- `wolflauncher/status.py` - `gamedig` server querying.
- `wolflauncher/mods.py` - required mod lookup and local Workshop scanning.
- `wolflauncher/platform_detection.py` - Steam, DayZ and Workshop detection.
- `wolflauncher/launcher.py` - external launcher command building.
- `wolflauncher/settings.py` - user settings and favourites.
- `servers.yaml` - curated server registry.
- `CHANGELOG.md` - version history.
- `ROADMAP.md` - planned milestones.
- `ARCHITECTURE.md` - design notes.

## Important design decisions

- YAML is the curated server/source-of-truth format for early versions.
- SQLite should be introduced later for scraped public server browser cache.
- JSON is used for user settings and favourites under `~/.config/wolflauncher`.
- The external shell launcher remains the launch engine for now.
- Mod management is read-only and advisory: it detects installed/missing mods and opens Workshop pages, but does not attempt automatic downloads.
- v0.5 launch is guarded: WolfLauncher warns about missing mods and Steam state before calling the external launcher.

## Suggested next version

v0.5.x should focus on real launch validation and hotfixes only:

- Confirm successful launch into a selected DayZ server.
- Confirm behaviour when Steam is already running vs not running.
- Confirm behaviour when missing mods are detected.
- Improve launch output/error messages based on real terminal output.

After launch is stable, v0.6 can move toward a searchable server browser backed by SQLite.

## v0.5.2 Hotfix Notes
- Launch commands now mirror the original terminal menu behaviour by passing the resolved IP address to the external launcher.
- This fixes DayZSA API failures such as `Missing mods data from API response` when launching DNS-based servers.
- Partial `gamedig` responses during restarts are now treated as offline/restarting rather than ONLINE with unknown fields.


## v0.5.2 hotfix
- Launch dialog output no longer crashes while reading launcher output.
- Launch command now explicitly uses the resolved IP from the server table when available.
