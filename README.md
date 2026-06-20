# WolfLauncher

A Linux-first DayZ launcher designed to remove the guesswork from joining modded servers.

DayZ runs surprisingly well on Linux. The problem is everything around it: Steam setup, Proton behaviour, Workshop content, server mod requirements, and paths that vary between native Steam and Flatpak Steam.

WolfLauncher checks those pieces before launch, then hands control to the existing `dayz-launcher.sh` workflow.

The upstream MIT-licensed shell launcher is vendored in `external/dayz-linux-cli-launcher/` as the current legacy launch engine and rewrite reference.

## Status

Current baseline: end of v0.5.2.

The server browser, diagnostics, mod checks and guarded launch handoff are working. The only known bug is that DayZ does not run when Steam launch options contain:

```text
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

That issue is tracked as a Steam/Proton/DayZ launch-option compatibility problem until it is reproduced and diagnosed.

## Features

### Server Management

- YAML-based server configuration.
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
- Quick diagnostics and troubleshooting tools.

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

## Launching

Configure the path to your existing launcher script, for example:

```text
/home/andi/dayz-launcher.sh
```

If no user-installed launcher is found, WolfLauncher can fall back to the vendored script at:

```text
external/dayz-linux-cli-launcher/dayz-launcher.sh
```

WolfLauncher generates launch commands in this shape:

```text
bash /home/andi/dayz-launcher.sh -s "RESOLVED_IP:GAMEPORT" -p "QUERYPORT" -n "PLAYER" --launch
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

## Project Documentation

| File | Purpose |
| --- | --- |
| `AGENTS.md` | Quick orientation for future coding agents |
| `PROJECT_STATE.md` | Current development snapshot and handoff notes |
| `ARCHITECTURE.md` | Design decisions, module map and launch contract |
| `ROADMAP.md` | Planned features and future milestones |
| `CHANGELOG.md` | Version history and release notes |
| `external/dayz-linux-cli-launcher/` | Vendored MIT legacy launcher reference |

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

License information to be added before first public release.
