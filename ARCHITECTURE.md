# Architecture

WolfLauncher is currently a Python + PySide6 Linux-first DayZ launcher.

## Current layers

```text
PySide6 GUI
  ├─ Server browser
  ├─ Mods tab
  ├─ Diagnostics tab
  └─ Settings/favourites

Core modules
  ├─ status.py             DayZ server querying through gamedig
  ├─ mods.py               required mod lookup and Workshop scanning
  ├─ platform_detection.py Steam/DayZ/Workshop detection
  ├─ launcher.py           external bash launcher invocation
  ├─ settings.py           JSON settings and favourites
  └─ config.py             YAML server loading

External tools
  ├─ gamedig
  ├─ dig
  ├─ Steam
  └─ dayz-launcher.sh
```

## Server data

Current curated servers live in `servers.yaml`.

YAML is useful for:

- hand-curated servers,
- personal favourites,
- simple sharing,
- early testing.

Later, scraped/community server data should move to SQLite.

Recommended long-term split:

```text
servers.yaml  -> curated/import-export servers
SQLite        -> scraped server browser cache
settings.json -> user settings
favourites.json -> favourites
```

## Mod management

v0.4 introduced advisory mod management. v0.4.1/v0.4.2 polished the mod workflow with filters, sorting, double-click Workshop opening, right-click copy actions and hotfixes.

Flow:

```text
Selected server
  ↓
Resolve host
  ↓
Query DayZ SA Launcher style API
  ↓
Read required Steam Workshop IDs
  ↓
Scan local workshop/content/221100
  ↓
Compare required vs installed
  ↓
Display installed/missing mods and Workshop links
```

The mod manager intentionally does not try to download Workshop content automatically. Steam Workshop subscription and download behaviour is left to Steam.

## Launching

WolfLauncher v0.5 calls the external launcher script through a guarded launch workflow:

```text
dayz-launcher.sh -s host:game_port -p query_port -n player_name --launch
```

Before launch, the GUI checks that DayZ and the Workshop folder are detected, warns if Steam is not running, and warns if the latest mod check for the selected server shows missing required mods. The launch dialog shows the generated command and captures launcher output for debugging.

This keeps v0.x releases close to the proven shell workflow while the GUI matures.

## Platform support

Primary target:

- Linux Mint
- Ubuntu/Debian family

Secondary future targets:

- Steam Deck
- Other Linux distributions

Possible later target:

- Windows
