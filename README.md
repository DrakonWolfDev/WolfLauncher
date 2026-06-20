# WolfLauncher v0.5.3 prototype

A Linux-first DayZ launcher GUI prototype for Linux Mint / Ubuntu-family systems.

## What v0.5.3 adds

- Launch selected server through the existing `dayz-launcher.sh` script.
- Preflight checks for DayZ and Workshop detection.
- Warning when Steam is not currently running.
- Warning when the latest mod check shows missing required mods.
- Missing-mod flow: Open Workshop, Launch Anyway, or Cancel.
- Launch output dialog showing the generated command and launcher output.
- Clearer successful handoff message when Steam accepts the launch command.
- GUI hotfix for launch button text updates during startup.

## Current core features

- YAML server configuration with DNS hostnames or IP addresses.
- Live DayZ server status via `gamedig`.
- Native Steam and Flatpak Steam detection.
- DayZ install and Workshop folder detection.
- Required-vs-installed Workshop mod comparison.
- Missing mod detection with Steam Workshop links.
- Favourites, settings persistence, auto-refresh, diagnostics, context menus and copy actions.

## Install development dependencies

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip nodejs npm dnsutils libxcb-cursor0
sudo npm install -g gamedig
```

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Launching

Set the launcher script path to your existing `dayz-launcher.sh`, for example:

```text
/home/andi/dayz-launcher.sh
```

The generated command follows this shape:

```bash
bash /home/andi/dayz-launcher.sh -s "HOST:GAMEPORT" -p "QUERYPORT" -n "PLAYER" --launch
```

Recommended flow:

1. Select a server.
2. Check required mods in the Mods tab.
3. Subscribe to any missing Workshop mods.
4. Return to the Servers tab.
5. Launch the selected server.

## Server config

Edit `servers.yaml` to correct or add servers.

```yaml
servers:
  - name: Drakon Expansion
    group: Drakon
    host: drakonwolf.ddns.net
    game_port: 3302
    query_port: 3303
    favourite: true
```

`host` can be either a DNS name or an IP address.

## App locations

- Single-user scripts/apps: `~/.local/bin` and `~/.local/share/wolflauncher`
- User config: `~/.config/wolflauncher`
- Future system-wide app install: `/opt/wolflauncher` or a `.deb` package

## Project history files

- `CHANGELOG.md` records what changed in each prototype snapshot.
- `ROADMAP.md` tracks likely future milestones.
- `ARCHITECTURE.md` explains design decisions and data formats.
- `PROJECT_STATE.md` is a quick handoff summary for resuming development later.


## v0.5.2 hotfix notes
This build fixes launch-log scrolling on PySide6 and forces the launch command to use the resolved server IP where available.
