# Roadmap

## v0.5.2 - Stable working base

Status: complete, with one known external launch-option issue.

- Launch handoff through `dayz-launcher.sh` works.
- DNS-based servers launch through resolved IP addresses when available.
- Server status, settings health checks, favourites and mod checks are working.
- Launch output dialog no longer crashes while reading PySide6 process output.
- Known bug: DayZ does not run with the Steam launch option `__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%`.

## v0.6 - Server browser foundation

Status: complete.

- Add SQLite cache for discovered public servers.
- Keep YAML as the curated, personal and import/export format.
- Add search, filtering and sorting for cached public server rows.
- Add data-aware sorting for numeric player/ping fields and checked/seen timestamps.
- Add documented no-key BattleMetrics discovery as the preferred public-list fallback.
- Keep Steam Web API and legacy UDP master discovery as optional paths.
- Add quiet, bounded and rate-limited background refresh for discovery data.
- Add live enrichment for visible discovered rows.
- Refine discovered-row query-port fallback probing from real-world server data.
- Improve Server Browser source/style filtering, result limits, reset flow and cache visibility.
- Preserve promotion into the current curated server workflow.
- Expand tests around launch-engine compatibility.
- Document the vendored shell launcher's behavior as the compatibility contract.

## v0.7 - Health checks and Linux polish

Status: complete, with the NVIDIA PRIME Steam launch-option issue still tracked as external until reproduced.

- Improve hybrid-GPU/NVIDIA PRIME diagnostics; initial structured diagnostics and Settings health visibility are in place.
- Add safer user-facing guidance for Steam launch options; initial diagnostics guidance is in place.
- Expand native Steam and Flatpak Steam checks; secondary Steam library detection is now in place.
- Continue improving Proton/Steam handoff failure states; launch dialogs now clarify the handoff boundary and probe for known DayZ processes after successful command exit.
- Add Linux Mint/Ubuntu install instructions; development setup notes are in the README, packaged install notes still need future work.
- Start carving native Python equivalents from the vendored legacy launcher behavior. This work progressed into the validated v0.8 native engine with explicit Steam-install selection.

## v0.8 - Native launcher engine investigation

Status: complete. Native launch parity has been validated in real-world use and the native engine is now the default for fresh installations. The external launcher remains available as a fallback.

- Document the current handoff contract with `dayz-linux-cli-launcher`.
- Build an internal launcher-engine module behind the existing GUI workflow. Completed for compact mod symlink names, mod link preparation, launch previews, native handoff and Steam command generation.
- Reproduce the current external launcher command behaviour with test coverage.
- Direct Steam/Proton launch handling has been validated for native and Flatpak Steam, with Steam running and stopped, and with unmodded, fully modded and partially missing-mod servers.
- Investigate Steam Workshop mod installation routes, with Steam-native subscription/download flows preferred over custom file management.
- Keep the external launcher path as a visible fallback during native hardening.

## v0.8.x - WolfAPI discovery quality and submissions

Goal: turn WolfAPI from a Steam-capped cache into a resilient community server directory while keeping WolfLauncher usable offline and with curated local rows.

- Keep WolfAPI as the preferred read-only discovered-server provider in WolfLauncher.
- Treat Steam's 10,000-row server-list cap as a fast baseline rather than the complete directory.
- Add slow, rate-limited BattleMetrics ingestion on the API side so WolfAPI can fill gaps without hammering public services.
- Track source freshness per server, including `last_seen`, `last_checked`, and which upstream source last confirmed the row.
- Mark servers as stale/offline when they disappear from a refresh instead of deleting them immediately.
- Keep stale rows for roughly 30 days before deletion so temporary downtime, refresh gaps and upstream quirks do not erase valid servers.
- Give user-submitted or locally curated servers stronger retention than discovered-only rows.
- Add an in-app "Add your server to WolfLauncher" flow that saves locally first, then submits to a dedicated WolfAPI endpoint.
- Design the submission contract before implementation: host, game port, query port, optional display name, duplicate handling, validation status, rate limiting and abuse prevention.
- Have WolfAPI validate or enrich submitted servers before promoting them into the public cache.
- Later expose freshness/source state in the Server Browser so players can tell live, stale, API-cached and user-added rows apart.
- Use WolfAPI `/api/health` as an operator/support signal for diagnostics, not as the primary server-list contract.
- Keep feature design bidirectional: launcher UX should drive explicit WolfAPI contract requests, and WolfAPI source freshness, validation and quality signals should eventually become launcher filters/badges only after they are stable.

## v0.9 - Native launcher engine hardening

Status: in progress. Launch dialogs, curated-server dialogs, Settings health snapshots, background workers and testable Server Browser query/presentation boundaries have been extracted from the main GUI module, with local desktop smoke testing and the hosted Python 3.10-3.12 test matrix passing for the previously pushed slices.

- Keep the validated native engine as the default and address real-world regressions as they are reported.
- Keep the external launcher path as a visible fallback during the transition.
- Run the automated unit suite in GitHub Actions across supported Python versions.
- Use the tracked release checklist for native/Flatpak Steam smoke testing.
- Continue small behavior-preserving extractions from `app.py`, with startup smoke checks after Qt import or initialization changes.
- After the current behavior boundaries are stable, run a GUI simplification pass: keep common server browsing and launching calm and obvious by default while retaining advanced discovery, diagnostics, parity and fallback controls in clearly labelled secondary areas.
- Improve structured launch errors and user-facing diagnostics.
- Add regression tests for launch command generation, host resolution and Steam mode detection.

## v0.9.9 - Packaging preparation

- Explore AppImage.
- Explore `.deb` packaging.
- Add desktop file and icon.
- Document user config and data directories.

## v1.0 - Native launcher engine replacement

- Move server launch flow from shell-script handoff to the internal engine.
- Remove the external launcher dependency once real-world launch testing is stable.

## Later

- Steam Deck-focused layout.
- Community-maintained server lists.
- Optional guided missing-mod installation flow after explicit user confirmation.
- Windows support investigation.
