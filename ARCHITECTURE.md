# Architecture

WolfLauncher is a Python + PySide6 Linux-first DayZ launcher. At the end of v0.5.2 it is a working GUI wrapper around a proven external shell launcher, with pre-launch checks moved into the application.

## Runtime Shape

```text
main.py
  -> wolflauncher.app.MainWindow
       -> Servers tab
       -> Mods tab
       -> Diagnostics tab
       -> guarded launch workflow
```

## Module Map

```text
wolflauncher/
  app.py                 Main Qt GUI, workers, tables, dialogs and launch flow
  config.py              YAML server loading and default launcher candidates
  diagnostics.py         Human-readable diagnostics report
  launcher.py            External dayz-launcher.sh command builder
  models.py              Shared dataclasses
  mods.py                DayZSA API mod lookup and local Workshop comparison
  platform_detection.py  Native/Flatpak Steam, DayZ and Workshop detection
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

The v0.6 SQLite foundation stores discovered public servers separately from curated YAML entries. Cached rows are keyed by `host:game_port:query_port` and include browser-oriented fields such as display name, map, player counts, ping, version, mod/password flags and last-seen timestamps. This keeps scraped or transient public browser data out of `servers.yaml` while still giving the GUI a searchable local cache.

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

## Known Launch-Option Issue

DayZ currently does not run when Steam launch options contain:

```text
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

This is tracked as the only known bug at the end of v0.5.2. Keep it visible in docs and diagnostics planning, but do not make it the default launch recommendation until it is reproduced and a safe workaround is confirmed.

## Platform Support

Primary target:

- Linux Mint
- Ubuntu/Debian family

Secondary future targets:

- Steam Deck
- Other Linux distributions

Possible later target:

- Windows
