# WolfLauncher

A Linux-first DayZ launcher designed to remove the guesswork from joining modded servers.

DayZ runs surprisingly well on Linux. The problem is everything around it: Steam setup, Proton behaviour, Workshop content, server mod requirements, and paths that vary between native Steam and Flatpak Steam.

WolfLauncher checks those pieces before launch, then hands control to the existing `dayz-launcher.sh` workflow.

The upstream MIT-licensed shell launcher is vendored in `external/dayz-linux-cli-launcher/` as the current legacy launch engine and rewrite reference.

## Status

Current baseline: end of v0.5.2.

The server browser, settings health checks, mod checks and guarded launch handoff are working. The only known bug is that DayZ does not run when Steam launch options contain:

```text
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

That issue is tracked as a Steam/Proton/DayZ launch-option compatibility problem until it is reproduced and diagnosed.

## Features

### Server Management

- YAML-based server configuration.
- SQLite cache foundation for future discovered public servers.
- Read-only discovered server browser with search, filters and cache sorting.
- YAML/JSON import for discovered server cache rows.
- Promote discovered servers into the curated `servers.yaml` list with editable name/group.
- Copy discovered server connect addresses and details.
- Configurable discovered-server refresh provider for BattleMetrics, Steam Web API or Steam master candidates.
- Steam Web API server-list discovery with user-supplied API key.
- BattleMetrics server discovery.
- Enrich visible discovered servers with live status data.
- DNS hostname or IP address support.
- Favourites system.
- Server grouping support.
- Automatic refresh options.
- Persistent settings.

### Server Monitoring

- Live server status checks.
- Player counts and server information.
- Resolved IP and connect address display.
- Powered by `gamedig`.
- Quick settings health checks and troubleshooting indicators.

### Mod Validation

- Workshop folder detection.
- Required mod lookup via DayZ SA Launcher style API.
- Installed versus required mod comparison.
- Missing mod detection.
- Direct Steam Workshop links.
- Launch warnings when required mods are missing.

### Launch Integration

- Native Steam support.
- Flatpak Steam support.
- DayZ installation detection.
- Pre-launch validation checks.
- Launch diagnostics and output logging.
- External `dayz-launcher.sh` handoff using resolved IP addresses where available.

## Installation

Install system dependencies:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip nodejs npm dnsutils libxcb-cursor0 curl jq gawk
sudo npm install -g gamedig
```

Create a virtual environment and start the application:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Run the test suite:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover
```

## Launching

Configure the path to your existing launcher script, for example:

```text
~/dayz-launcher.sh
```

If no user-installed launcher is found, WolfLauncher can fall back to the vendored script at:

```text
external/dayz-linux-cli-launcher/dayz-launcher.sh
```

WolfLauncher generates launch commands in this shape:

```text
bash ~/dayz-launcher.sh -s "RESOLVED_IP:GAMEPORT" -p "QUERYPORT" -n "PLAYER" --launch
```

Recommended workflow:

1. Select a server.
2. Review required mods.
3. Subscribe to any missing Workshop content.
4. Return to the server list.
5. Launch.

## Server Configuration

Servers are stored in `servers.yaml`.

Example:

```yaml
servers:
  - name: Drakon Expansion
    group: Drakon
    host: drakonwolf.ddns.net
    game_port: 3302
    query_port: 3303
    favourite: true
```

The `host` field may contain either a DNS hostname or an IP address.

## Discovered Server Cache

The Server Browser tab reads from the SQLite cache at:

```text
~/.local/share/wolflauncher/server_cache.sqlite3
```

Use **Import server list** in Settings to load discovered server rows from YAML or JSON. A sample file is included at:

```text
examples/discovered_servers.sample.yaml
```

Imported rows stay separate from curated `servers.yaml`.

Select an imported/discovered row and use **Promote to curated** to add it to `servers.yaml`. Right-click a discovered row to promote it or copy its connect address/details.

Choose a server API provider in Settings, then use **Refresh database** in the Server Browser tab. BattleMetrics works without a key, Steam Web API uses the saved Steam API key, and Steam Master uses Valve's legacy UDP master server path.

Provider refreshes sync the provider-backed cache rather than accumulating old rows: servers no longer returned by a successful selected-service refresh are removed, a successful empty refresh clears that provider's discovered rows, and existing cache keys are left untouched so live enrichment is not repeated unnecessarily. Failed provider refreshes keep existing cached rows. Keep servers you care about in the curated `servers.yaml` list.

Settings also contains the refresh row limit, an opt-in automatic refresh toggle, and a comma-separated **Steam masters** endpoint list for cases where Valve's default DNS names do not resolve, for example `HOST:27011,HOST:27015`.

When automatic refresh is enabled, WolfLauncher waits after startup and refreshes the selected provider at most once every 24 hours.

The same discovery path is available from the command line:

```bash
.venv/bin/python scripts/discover_steam_servers.py --batches 1
```

The Web API path is also available from the command line:

```bash
.venv/bin/python scripts/discover_steam_servers.py --web-api --web-api-key YOUR_KEY --limit 5000
```

Use `--master HOST[:PORT]` to test specific Steam master endpoints if local DNS cannot resolve the built-in hostnames. Pass it more than once to try multiple candidates:

```bash
.venv/bin/python scripts/discover_steam_servers.py --master 203.0.113.10:27011 --master 203.0.113.20:27015
```

The app honors `WOLFLAUNCHER_STEAM_MASTER_ENDPOINTS` as a comma-separated endpoint list, plus the older `WOLFLAUNCHER_STEAM_MASTER_HOST` / `WOLFLAUNCHER_STEAM_MASTER_PORT` overrides. Steam discovery rows are treated as candidates until later status enrichment confirms display names, maps, player counts and port details.

Use **Enrich visible** in the Server Browser tab to query the currently visible cached rows and fill in live status fields such as server name, map, players, ping, version and online state. The Server Browser map and version filters are populated from cached/enriched values when those fields are available.

## Project Documentation

| File | Purpose |
| --- | --- |
| `AGENTS.md` | Quick orientation for future coding agents |
| `PROJECT_STATE.md` | Current development snapshot and handoff notes |
| `ARCHITECTURE.md` | Design decisions, module map and launch contract |
| `ROADMAP.md` | Planned features and future milestones |
| `CHANGELOG.md` | Version history and release notes |
| `external/dayz-linux-cli-launcher/` | Vendored MIT legacy launcher reference |
| `THIRD_PARTY_NOTICES.md` | Third-party license notices |

## Application Locations

User installation candidates:

```text
~/.local/bin
~/.local/share/wolflauncher
```

User configuration:

```text
~/.config/wolflauncher
```

User data cache:

```text
~/.local/share/wolflauncher/server_cache.sqlite3
```

Possible future system installation:

```text
/opt/wolflauncher
```

or via a native `.deb` package.

## Roadmap

Next active target: v0.6 server browser foundation.

Planned future work includes:

- SQLite-backed discovered server cache.
- Improved search, filtering and sorting.
- Hybrid-GPU/NVIDIA PRIME diagnostics.
- Improved Steam/Proton handoff diagnostics.
- Native packaging and installation.
- Eventual internal launcher engine investigation.

## License

WolfLauncher is licensed under the MIT License.

This repository includes the MIT-licensed `dayz-linux-cli-launcher` under `external/dayz-linux-cli-launcher/`. See `THIRD_PARTY_NOTICES.md` for details.
