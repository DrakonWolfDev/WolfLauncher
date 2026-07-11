# AGENTS.md

## Project Orientation

WolfLauncher is a Linux-first DayZ launcher GUI built with Python and PySide6. The current working baseline is v0.8 native-launch parity validated, with v0.9 native hardening in progress.

The app validates the local Steam/DayZ/Workshop setup, checks server status, compares required server mods with locally installed Workshop mods, then hands launch control to an external `dayz-launcher.sh` script.

The upstream shell launcher is vendored at `external/dayz-linux-cli-launcher/` as the legacy reference engine.

## Current Truth

- `PROJECT_STATE.md` is the handoff snapshot.
- `ARCHITECTURE.md` explains the module boundaries and launch contract.
- `ROADMAP.md` describes the next version targets.
- `CHANGELOG.md` records version history.
- `LICENSE` and `THIRD_PARTY_NOTICES.md` record licensing.

When these files disagree, update them as part of the same change.

## Known Bug

DayZ currently does not run when Steam launch options contain:

```text
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

Treat this as an external Steam/Proton/DayZ launch-option compatibility issue until reproduced. Do not bake this option into WolfLauncher defaults.

## Code Map

```text
main.py                         application entry point
wolflauncher/app.py             PySide6 GUI and launch workflow
wolflauncher/config.py          server YAML loading and launcher path candidates
wolflauncher/diagnostics.py     diagnostics report text
wolflauncher/launch_history.py  last launch report persistence
wolflauncher/launcher.py        external launcher command generation
wolflauncher/launch_dialogs.py  external/native handoff dialogs and process watching
wolflauncher/models.py          shared dataclasses
wolflauncher/mods.py            required mod lookup and Workshop scan
wolflauncher/platform_detection.py
                                native/Flatpak Steam, DayZ and Workshop detection
wolflauncher/native_launcher.py native Python launch engine
wolflauncher/server_cache.py    SQLite discovered-server cache
wolflauncher/server_discovery.py
                                public server discovery providers
wolflauncher/server_enrichment.py
                                live discovered-server status enrichment
wolflauncher/settings.py        JSON settings and favourites persistence
wolflauncher/settings_health.py Settings health snapshot construction
wolflauncher/status.py          gamedig status checks and DNS resolution
example.servers.yaml            tracked curated server template
servers.yaml                    local ignored curated server list
external/dayz-linux-cli-launcher/
                                vendored MIT legacy launcher reference
```

## Launch Contract

WolfLauncher currently builds this external command:

```text
bash dayz-launcher.sh -s resolved_ip:game_port -p query_port -n player_name --launch
```

Important details:

- Prefer the resolved IP for launch handoff when available.
- Keep the external launcher path configurable.
- Treat successful process exit as handoff to Steam, not proof that DayZ fully started.
- Preserve the guarded launch checks for DayZ detection, Workshop detection, Steam running state and missing mods.

The vendored script then:

- Queries the DayZSA API for required mods.
- Verifies local Workshop folders.
- Creates shortened `@base64modid` symlinks inside the DayZ install directory.
- Launches Steam with `-applaunch 221100`.

## Development Notes

- Prefer smooth, low-noise user experience: keep background checks quiet and preserve useful previous results while new work is running. Do not hide meaningful uncertainty, failures or launch boundaries; surface them honestly in status labels, health checks, dialogs or diagnostics when they matter.
- Keep validated v0.8 behaviour stable while working on v0.9 native-launch hardening.
- Keep local `servers.yaml` as the curated source even after adding SQLite for discovered servers; track `example.servers.yaml` as the repo template instead of committing personal server-list edits.
- WolfAPI is the companion service for hosted discovered-server data. Current WolfAPI truth: Redis remains the hot public `/api/servers` cache, Postgres is durable canonical/history storage, Steam/BattleMetrics/live validation update Redis, and Postgres-to-Redis publish is manual recovery only unless explicitly changed in WolfAPI.
- When building launcher features around WolfAPI, prefer additive client behavior: consume `/api/servers` for discovered rows, use `/api/health` only for diagnostics/status, keep remote data read-only, and preserve local curated YAML promotion as the user-owned path.
- Cross-project ideas should flow both ways: launcher UX needs can inform future WolfAPI fields or endpoints, while WolfAPI freshness/source/validation state can inform launcher filters, badges and diagnostics after the API contract is stable.
- Mod management is read-only and advisory; do not auto-subscribe or auto-download Workshop content without an explicit future design.
- User settings and favourites live under `~/.config/wolflauncher`.
- Prefer small, testable changes around launch command generation and platform detection.
- Keep native parity reports easy to compare with the external launcher: show readiness, shared connect/query targets, current required-mod counts and missing local Workshop directories.
- Keep the native launcher as the default and preserve the external launcher as a visible fallback.
- Keep the vendored launcher untouched unless deliberately updating the legacy reference; build replacement Python behavior behind WolfLauncher interfaces first.
- Preserve third-party license notices when moving or replacing vendored code.

## Local Run

```text
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
.venv/bin/python main.py
```

## Tests

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover
```
