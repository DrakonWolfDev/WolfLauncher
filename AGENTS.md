# AGENTS.md

## Project Orientation

WolfLauncher is a Linux-primary DayZ launcher GUI built with Python and PySide6,
with experimental portable and installed Windows builds. The current working
baseline is v0.8 Linux native-launch parity validated, with v0.9 native hardening
in progress.

The app validates the local Steam/DayZ/Workshop setup, checks server status,
compares required server mods with locally installed Workshop mods, then hands
launch control to Steam through the native Python engine. The external
`dayz-launcher.sh` is a Linux-only fallback.

## Branch Policy

All completed changes must be committed and pushed directly to `main`. Do not
create, push, or maintain feature, agent, or other long-lived branches unless
the user explicitly overrides this policy for a specific task.

The upstream shell launcher is vendored at `external/dayz-linux-cli-launcher/` as the legacy reference engine.

## Current Deployment Scope

WolfLauncher currently runs only on the user's own systems; there is no
external installed user base to preserve. Prefer the clearest coordinated
API/Launcher implementation and direct, tested migrations over speculative
third-party compatibility. Still preserve the user's settings, curated YAML,
SQLite data and unrelated work unless a deliberate migration covers them.

## Cross-Repository Workflow

WolfAPI is cloned at `../WolfAPI`. The two repositories form one product
boundary for public server discovery. Work may originate in either repository;
when a task materially affects the shared feature, inspect and update both
repositories as needed in the same work session. The user has explicitly
authorized this coordinated workflow.

- Read this file, `DISCOVERY_FRESHNESS_HANDOFF.md` and the sibling
  `../WolfAPI/AGENTS.md` and `../WolfAPI/DISCOVERY_FRESHNESS_CONTRACT.md` before
  changing shared endpoints, fields, identity, search/resolve behavior,
  freshness and validation semantics, caching, polling or rollout gates.
- Treat a necessary companion change as part of the in-scope task regardless
  of which repository the request started in. Do not wait for a separate
  prompt merely because the implementation crosses the repository boundary.
- Keep the API contract and launcher handoff/truth documents synchronized.
  Test each affected repository independently and commit changes separately so
  each can be reviewed and pushed on its own.
- Preserve unrelated and user-owned changes in both worktrees. Source
  completion is not proof of deployment readiness. WolfAPI v1 is the
  fresh-install default after its gates passed; retain the explicit legacy
  fallback until deliberately removed.

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
wolflauncher/discovery_refresh.py
                                automatic provider refresh timestamp policy
wolflauncher/launch_history.py  last launch report persistence
wolflauncher/launcher.py        external launcher command generation
wolflauncher/launch_dialogs.py  external/native handoff dialogs and process watching
wolflauncher/models.py          shared dataclasses
wolflauncher/mod_presenter.py   Mods-tab summary and row presentation
wolflauncher/mods.py            required mod lookup and Workshop scan
wolflauncher/platform_detection.py
                                native/Flatpak Steam, DayZ and Workshop detection
wolflauncher/platforms/         Linux and experimental Windows platform backends
wolflauncher/native_launcher.py native Python launch engine
wolflauncher/server_cache.py    SQLite discovered-server cache
wolflauncher/server_discovery.py
                                public server discovery providers
wolflauncher/server_enrichment.py
                                live discovered-server status enrichment
wolflauncher/server_browser_controller.py
                                cache queries and filter options
wolflauncher/server_browser_presenter.py
                                discovered row/detail presentation
wolflauncher/server_browser_table.py
                                Qt discovered-row population
wolflauncher/settings.py        JSON settings and favourites persistence
wolflauncher/settings_health.py Settings health snapshot construction
wolflauncher/status.py          gamedig status checks and DNS resolution
wolflauncher/ui_sections.py     shared progressive-disclosure state
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

- Keep Linux as WolfLauncher's primary development, runtime and validation
  target unless a task explicitly includes another platform. Do not delay
  ordinary Linux work to build speculative cross-platform support. When new or
  changed code touches genuinely platform-sensitive concerns—such as Steam and
  process detection, filesystem links and permissions, user-data locations,
  launch commands, diagnostics or packaging—keep the shared behavior separate
  from each backend and preserve a clear platform boundary. Introduce only the
  abstractions justified by the current change: preserve validated Linux
  behavior, avoid scattered platform conditionals, and keep Windows marked
  experimental until handoff, Workshop lifecycle and packaging are validated.
- Prefer smooth, low-noise user experience: keep background checks quiet and preserve useful previous results while new work is running. Do not hide meaningful uncertainty, failures or launch boundaries; surface them honestly in status labels, health checks, dialogs or diagnostics when they matter.
- Preserve the approved v0.9 GUI rhythm: information/summary first, common controls next, results in the middle and secondary/advanced tools at the bottom.
- Keep frequent actions visible and advanced discovery, diagnostics, parity, copying and fallback controls available through compact direction-marked disclosures. Do not treat simplification as permission to remove advanced features.
- Use `ui_sections.set_disclosure_state` for consistent disclosure markers/text. When primary actions share the bottom area, align advanced tools left and persistent primary actions right on one row.
- Server Browser and Mods have passed initial desktop review. Continue the pattern into Settings and then Servers, but request new review before materially changing the approved Server Browser/Mods hierarchy.
- Treat fonts, theme, colours and branding as a later visual-polish pass after layout hierarchy is settled.
- Keep validated v0.8 behaviour stable while working on v0.9 native-launch hardening.
- Keep local `servers.yaml` as the curated source even after adding SQLite for discovered servers; track `example.servers.yaml` as the repo template instead of committing personal server-list edits.
- WolfAPI is the companion hosted discovery service. Read
  `DISCOVERY_FRESHNESS_HANDOFF.md` and the sibling
  `../WolfAPI/DISCOVERY_FRESHNESS_CONTRACT.md` before making discovery contract,
  cache identity or startup-polling choices.
- WolfAPI v1 is implemented locally with bounded Postgres pages, indexed
  search/exact resolution, freshness/validation metadata, stable UUID server
  IDs and endpoint aliases. Keep the deployed legacy `/api/servers` path until
  the v1 deployment/rollout gates in the handoff are confirmed.
- Prefer additive client behavior: keep remote data read-only, preserve offline
  SQLite and local curated YAML promotion, and use `/api/health` only for
  diagnostics/status. When adopting v1, persist stable IDs separately from
  endpoint keys so port corrections merge rather than duplicate rows.
- If shared discovery behavior changes, update `DISCOVERY_FRESHNESS_HANDOFF.md`,
  `PROJECT_STATE.md`, `ARCHITECTURE.md` and `ROADMAP.md` as applicable, and
  record launcher constraints back in WolfAPI's contract.
- Workshop mutation is always an explicitly confirmed, Steam-managed operation.
  Do not subscribe, download or update without confirmation, and never remove
  subscriptions.
- User settings and favourites live under `~/.config/wolflauncher` on Linux
  and `%APPDATA%\wolflauncher` on Windows; cache data uses the corresponding
  platform data directory.
- Prefer small, testable changes around launch command generation and platform detection.
- Keep native parity reports easy to compare with the external launcher: show readiness, shared connect/query targets, current required-mod counts and missing local Workshop directories.
- Keep the native launcher as the default and preserve the external launcher as
  a visible Linux fallback; Windows must not expose the shell launcher.
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
