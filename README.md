# WolfLauncher

A Linux-primary DayZ launcher designed to remove the guesswork from joining
modded servers, with an experimental portable Windows build.

DayZ runs surprisingly well on Linux. The problem is everything around it: Steam setup, Proton behaviour, Workshop content, server mod requirements, and paths that vary between native Steam and Flatpak Steam.

WolfLauncher checks those pieces before handing a native launch command to Steam. The existing `dayz-launcher.sh` workflow remains available as a fallback.

The upstream MIT-licensed shell launcher is vendored in `external/dayz-linux-cli-launcher/` as the current legacy launch engine and rewrite reference.

## Status

Current baseline: v0.8 Linux native-launch parity validated, with the native
launcher used by default and the external launcher retained as a Linux
fallback. Windows detection, native Steam/DayZ handoff, confirmed Workshop
resolution and portable packaging have been validated on Windows 11. The
Windows build remains experimental until signing, update delivery and broader
release-artifact desktop gates are exercised.

The server browser, settings health checks, diagnostics, mod checks and guarded launch handoff are working. The native engine has been validated with native and Flatpak Steam, Steam running and stopped, unmodded servers, fully installed mod sets and partially missing mod sets. Connect pre-flight asks the signed-in Steam client to subscribe, download or update required items and verifies them before launch; manual Workshop pages remain available as an advanced fallback. The external launcher remains available as a fallback. The only known bug is that DayZ does not run when Steam launch options contain:

```text
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

That issue is tracked as a Steam/Proton/DayZ launch-option compatibility problem until it is reproduced and diagnosed.

## NVIDIA PRIME / Steam Launch Options

WolfLauncher does not currently set or rewrite Steam launch options. Steam stores those per game, and WolfLauncher cannot reliably read them from the outside. The diagnostics report can show PRIME-related environment variables visible to WolfLauncher, but it cannot prove which launch options Steam applies when Proton starts DayZ.

Known-bad option while this issue is under investigation:

```text
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

For hybrid-GPU systems, prefer testing GPU offload outside WolfLauncher first:

```bash
prime-run glxinfo -B
prime-run steam
```

Then test DayZ directly from Steam with no WolfLauncher involvement. If DayZ only fails when the per-game Steam launch option above is present, remove that option and launch through WolfLauncher again. Do not add the known-bad option as a WolfLauncher default or recommended workaround.

Useful evidence for debugging:

- Whether Steam is native or Flatpak.
- GPU driver and PRIME helper in use, for example `prime-run`, `switcherooctl` or manual environment variables.
- Proton version selected for DayZ.
- Whether DayZ starts directly from Steam with no per-game launch option.
- WolfLauncher diagnostics output, especially the PRIME environment values and Steam/DayZ detection section.

## Features

### Server Management

- YAML-based server configuration.
- SQLite-backed cache for discovered public servers.
- Read-only discovered server browser with search, filters and cache sorting.
- YAML/JSON import for discovered server cache rows.
- Add, edit and remove Favourite Servers from the Servers tab.
- Add discovered servers to the Favourite Servers list with an editable name/group.
- Copy discovered server connect addresses and details.
- Configurable discovered-server refresh provider for WolfAPI, BattleMetrics, Steam Web API or Steam master candidates.
- WolfAPI hosted discovered-server cache provider.
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
- Last-known Favourite Server status cache for calmer startup display.
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
- Default Steam-native subscription, update and download monitoring.
- Launch warnings when required mods are missing.

### Launch Integration

- Native Steam support.
- Flatpak Steam support.
- Secondary Steam library detection for DayZ and Workshop folders.
- DayZ installation detection.
- Pre-launch validation checks.
- Launch diagnostics and output logging.
- External `dayz-launcher.sh` handoff using resolved IP addresses where available.
- Experimental native Windows Steam/DayZ detection and absolute Workshop mod
  handoff without symlinks or the external shell launcher.

## Installation

These instructions target Linux Mint 21/22 and Ubuntu 22.04/24.04 family systems.

Steam and DayZ should already be installed through native Steam or Flatpak Steam. WolfLauncher does not install DayZ or Proton. Workshop operations are delegated to the user's signed-in Steam client.

On Windows, Steam and DayZ should already be installed through native Steam.
The experimental Windows release produces both a per-user Setup executable and
a portable ZIP, each with the bundled status-query runtime. Setup does not need
administrator rights, creates a Start Menu shortcut and leaves settings and
cache data in the user profile when uninstalled. The artifacts are not yet
digitally signed.

Planned updates use a signed evergreen bootstrapper and prompted installer on
Windows, and a signed APT repository through the normal system update manager
on Linux. See [`docs/UPDATE_STRATEGY.md`](docs/UPDATE_STRATEGY.md).

At startup, WolfLauncher checks the selected Steam installation and warns once
if Steam is stopped or unavailable. Server browsing remains available, but
Workshop mod information, sizes and download operations may be incomplete until
Steam is running and signed in.

Missing or outdated mods are resolved automatically during Connect pre-flight and can also be requested from the Mods tab. Steam must run under the same user and be signed into an account that owns DayZ. **Hide monitor** only hides a manual batch's progress window: the helper continues monitoring in the background and launch remains blocked until it finishes. Use the install action again to reopen that live monitor; WolfLauncher will not start a second Steamworks session. Manual Workshop page actions remain under **Advanced mod tools** and on mod-row double-click/context actions.

After a successful batch, **Launch server** waits for the isolated Steamworks helper to exit and for a fresh mod check to confirm every required directory before starting the selected server. A failed or incomplete recheck returns control to the Mods tab instead of launching with stale readiness data.

### Quick Development Setup

#### Windows

From PowerShell in the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-quality.txt
.\.venv\Scripts\python.exe main.py
```

WolfLauncher reads Steam's registry location and library manifests. Windows
uses native `steam.exe`, direct absolute Workshop paths and the DayZ
`steam_api64.dll`; Flatpak, Proton/PRIME diagnostics and the external shell
launcher are intentionally absent. Use native launch preview first. Actual
Connect has been validated on Windows 11 24H2 with an unmodded handoff, a
58-mod installed server session and an explicitly confirmed 62-mod session that
subscribed to and downloaded three missing Workshop items before launch.
Workshop changes remain explicitly confirmed operations.

#### Linux

From the repository root:

```bash
./install-dev-linux-mint.sh
source .venv/bin/activate
python main.py
```

### Build artifacts

Install the pinned build tools and build the wheel/source archive:

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m build
```

Build the current-architecture Debian staging artifact with:

```bash
./scripts/build-deb.sh
```

The script bundles the exact Python dependency set from
`requirements-release.txt`, the npm-lock-pinned GameDig runtime, desktop entry,
icon, curated template, legacy fallback and license notices. It writes the
`.deb` and SHA-256 file under ignored `dist/`. Release artifacts must be built
and smoke-tested in the release CI environment; a developer-machine build is a
local validation artifact, not evidence for every supported distro.

On Windows, install the pinned release tools and build the portable ZIP from
PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-windows-release.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1 `
  -Python .\.venv\Scripts\python.exe
```

The script installs the lockfile-pinned GameDig tree, bundles the current Node
runtime, runs the packaged GUI and Windows Credential Manager smoke checks, and
writes a versioned ZIP plus SHA-256 file under `dist\windows`.

Build the per-user installer from that bundle with the hash-pinned Inno Setup
compiler:

```powershell
$iscc = powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\install-inno-setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\build-windows-installer.ps1 -Iscc $iscc `
  -Python .\.venv\Scripts\python.exe
```

`scripts\test-windows-installer.ps1` performs isolated install, packaged-start,
in-place reinstall and uninstall checks, and verifies that roaming configuration
and local application data survive. GitHub Actions repeats the portable and
installer builds and publishes their binaries and SHA-256 sidecars together.

### Manual Linux Mint / Ubuntu Setup

Install system dependencies:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip nodejs npm dnsutils libxcb-cursor0 curl jq gawk
sudo npm install -g gamedig
```

Dependency notes:

- `python3`, `python3-venv` and `python3-pip` run WolfLauncher in a local virtual environment.
- `nodejs`, `npm` and `gamedig` power live DayZ server status checks.
- `dnsutils` provides `dig` for DNS troubleshooting and the vendored legacy launcher.
- `curl`, `jq` and `gawk` are required by the vendored `dayz-launcher.sh` compatibility path.
- `libxcb-cursor0` is commonly needed for PySide6/Qt startup on Mint and Ubuntu desktops.

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

If the app starts but launch preflight fails, open **Settings** and press **Check health**. That table reports the selected Steam install, the install Auto would choose, other detected Steam candidates, their launch command details, DayZ, Workshop, required tools and visible PRIME/offload environment state. Use **Copy health** or the health-table right-click menu to copy a compact support snapshot, **Copy diagnostics** for the full diagnostics report, or **Copy last launch** to recover the most recent saved launch output report after closing the launch dialog. WolfLauncher reads Steam `libraryfolders.vdf` and DayZ's `appmanifest_221100.acf` for native and Flatpak Steam, so DayZ and Workshop can be detected from secondary Steam libraries as well as the primary Steam folder.

The health table and diagnostics also show whether common PRIME helper commands such as `prime-run` and `switcherooctl` are visible. Missing helper commands are informational only, because non-hybrid systems usually do not have them. The selected install's DayZ Proton compatdata folder is reported when visible; if it is missing, Steam may create it on first Proton launch. For a never-launched Steam install, start DayZ once directly from Steam so Proton can create the prefix and show first-run prompts.

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
3. Use **Copy mod report** for a timestamped required/missing Workshop ID snapshot, or **Copy missing links** for just the missing Workshop pages.
4. Subscribe to any missing Workshop content.
5. Return to the server list.
6. Launch.

The native engine is selected by default for fresh installations; the external
launcher remains selectable in **Settings** as a fallback. Use **Steam install
mode** to choose Auto, Native Steam, Flatpak Steam or a
`STEAM_ROOT` library explicitly. Mod checks, native preview and native launch
preflight use that selected install so Flatpak testing does not accidentally
read Workshop state from native Steam. The Mods summary and copied mod report
show the Steam install context and Workshop path checked, which makes native,
Flatpak and `STEAM_ROOT` parity snapshots easier to compare. `STEAM_ROOT` still
needs the native `steam` command on `PATH` for launch handoff; Settings health
reports when that command is missing. The native preview report includes a
readiness comparison between the external launcher handoff and the native
command, including the selected Steam install setting, detected install,
shared connect target, query port, current required-mod count and whether native
testing is blocked by missing local Workshop directories. When the native
command is ready, the preview dialog can copy only
that command for direct terminal parity tests. If a stale `@mod` symlink points
at a different Workshop directory, native failure details include the expected
and actual symlink targets so the conflict can be compared or pasted into a
support report. If a full parity report is unavailable, native failure details
still include the selected Steam mode, detected install, Steam command,
DayZ/Workshop paths and server target.

## Server Configuration

Servers are stored in local-only
`~/.config/wolflauncher/servers.yaml` (or `$XDG_CONFIG_HOME/wolflauncher/servers.yaml`).
The repository includes `example.servers.yaml` as the starting template. On the
first v0.9 run, an existing checkout-local `servers.yaml` is copied into the XDG
location without modifying the source; otherwise the example seeds the new file.

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

Use **Add a favourite server** on the Servers tab to add a server directly to
the curated server file. The dialog defaults to common DayZ ports, but both game and
query ports can be edited before saving. If you paste `host:port` into the host
field, WolfLauncher saves the host and game port separately. Newly added rows
are checked on their own after saving. Existing Favourite Servers can be edited,
removed or refreshed individually from the row context menu. If a live status
refresh reports a different connect port, use **Apply live connect port** from
the same context menu to save that game-port correction back to the curated file.

## Discovered Server Cache

The Server Browser tab reads from the SQLite cache at:

```text
~/.local/share/wolflauncher/server_cache.sqlite3
```

Favourite Server rows keep their last-known live status in:

```text
~/.local/share/wolflauncher/curated_status.json
```

Use **Import server list** in Settings to load discovered server rows from YAML or JSON. A sample file is included at:

```text
examples/discovered_servers.sample.yaml
```

Imported rows stay separate from curated server YAML.

Select an imported/discovered row and use **Add to Favourite Servers** to add it
to the curated YAML. Right-click a discovered row to add it or copy its connect
address/details.

WolfAPI is the normal Server Browser source. Cached rows render immediately and
the launcher refreshes the list quietly when it is due, including when the
Server Browser is opened. **Refresh server list** remains available under
advanced tools for an explicit refresh. The legacy WolfAPI, BattleMetrics,
Steam Web API and Steam Master providers remain advanced alternatives; failed
refreshes keep the existing SQLite rows.

Full-snapshot provider refreshes sync their own cache rows rather than accumulating old entries. Bounded WolfAPI v1 refreshes fetch 100-row pages in the background up to the configured limit and merge by stable ID without deleting off-page rows. With v1 selected, Server Browser search displays cached SQLite matches after typing pauses, then merges up to 100 remote matches from the full directory. An exact `host:port` search uses alias-aware resolution and checks the port as either game or query port. Failed refreshes and searches keep existing cached rows. Keep servers you care about in Favourite Servers.

Server Browser search begins at three characters. One- and two-character input
does not query the cache or rebuild the table; after the third character the
local refresh waits briefly for typing to pause, keeping the UI responsive.

Hover the Server Browser **Status** cell, or copy a server's details, to inspect
WolfAPI freshness, validation time and provider observation. These fields are
API-side directory evidence; local ping and final launch checks remain
separate. If cached freshness has expired, WolfLauncher says a refresh is
pending rather than asserting a new state.

Settings keeps the ordinary automatic-refresh choice visible. Provider,
refresh-limit, Steam-key and master-server controls are advanced; provider-only
fields stay hidden unless their provider is selected.

When automatic refresh is enabled, WolfLauncher waits after startup and refreshes the selected provider at most once every 24 hours.

The same discovery path is available from the command line:

```bash
.venv/bin/python scripts/discover_steam_servers.py --batches 1
```

The WolfAPI cache path is also available from the command line:

```bash
.venv/bin/python scripts/discover_steam_servers.py --wolfapi --limit 500
```

After the hosted service is deployed with the documented rollout metadata, the
bounded v1 path can be canaried without changing the GUI provider default:

```bash
.venv/bin/python scripts/discover_steam_servers.py --wolfapi-v1 --limit 100
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

Selecting a server automatically starts one debounced GameDig check on a
background worker. Only the selected row and inspector are updated; rapid
selection changes retain only the newest pending check. WolfAPI remains
browse-time truth and the guarded launch preflight performs the final live
check. An explicit **Refresh server list** action or a completed WolfAPI search
also checks all current matching rows in bounded batches of six. A newer
search cancels the obsolete batch and its GameDig processes, so repeated searches
do not build a work backlog. There is no unbounded visible-row enrichment workflow, and
no network work is performed on the Qt UI thread. These lightweight batches
follow the visible table from top to bottom and try only the provider's primary
query port. Selecting or launching a server still uses the fuller fallback-port
check when needed. Completed batches update their rows in place and report
completion without rebuilding the whole results table.

## Project Documentation

| File | Purpose |
| --- | --- |
| `AGENTS.md` | Quick orientation for future coding agents |
| `PROJECT_STATE.md` | Current development snapshot and handoff notes |
| `ARCHITECTURE.md` | Design decisions, module map and launch contract |
| `ROADMAP.md` | Planned features and future milestones |
| `DISCOVERY_FRESHNESS_HANDOFF.md` | WolfAPI v1 contract, rollout state and launcher adoption choices |
| `CHANGELOG.md` | Version history and release notes |
| `docs/RELEASE_CHECKLIST.md` | Automated and real-world release checks |
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

Settings and curated YAML are written atomically with owner-only permissions.
WolfLauncher prefers the desktop Secret Service for the optional Steam Web API
key when a usable keyring backend is available. Minimal/headless environments
fall back to the owner-only settings file and label that behavior as a local
fallback. Copyable support reports redact the home directory, Steam userdata
identifiers, credential-shaped fields and known API-key environment values.

User data cache:

```text
~/.local/share/wolflauncher/server_cache.sqlite3
~/.local/share/wolflauncher/curated_status.json
~/.local/share/wolflauncher/last_launch_report.txt
```

Possible future system installation:

```text
/opt/wolflauncher
```

or via a native `.deb` package.

## Roadmap

Next active target: v0.9 production hardening.

The authoritative ordered work list is in
`PRODUCTION_READINESS_REVIEW.md`; `ROADMAP.md` records release milestones.
Current gates cover XDG user-data placement, recoverable persistence, shutdown
lifecycle, credential/report security, reproducible packaging, expanded CI and
packaged-artifact desktop validation. NVIDIA PRIME investigation remains
evidence-driven.

## License

WolfLauncher is licensed under the MIT License.

This repository includes the MIT-licensed `dayz-linux-cli-launcher` under `external/dayz-linux-cli-launcher/`. See `THIRD_PARTY_NOTICES.md` for details.
