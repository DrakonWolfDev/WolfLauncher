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
- Investigate Steam Workshop mod installation routes, with Steam-native subscription/download flows preferred over custom file management. An opt-in ISteamUGC experiment now delegates confirmed subscriptions/downloads to the running Steam client; native and Flatpak real-world hardening remains.
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

Status: in progress. Native hardening boundaries are established and the initial GUI simplification pass is complete. Server Browser, Mods, Settings and Servers now have user-approved information-first layouts with advanced or fallback controls kept available without competing with the primary path.

- Keep the validated native engine as the default and address real-world regressions as they are reported.
- Keep the external launcher path as a visible fallback during the transition.
- Run the automated unit suite in GitHub Actions across supported Python versions.
- Use the tracked release checklist for native/Flatpak Steam smoke testing.
- Continue small behavior-preserving extractions from `app.py`, with startup smoke checks after Qt import or initialization changes.
- Preserve the approved GUI hierarchy: keep common browsing and launching calm and obvious while retaining advanced discovery, diagnostics, parity and fallback controls through clearly labelled disclosures or context-sensitive settings.
- Improve structured launch errors and user-facing diagnostics.
- Add regression tests for launch command generation, host resolution and Steam mode detection.
  Current coverage includes resolved external/native targets, DNS failures, non-default ports, player-name argument safety, native/Flatpak/`STEAM_ROOT` selection and deterministic complete-install priority.

### Experimental Workshop and join-flow hardening

Real-world native-Steam testing confirmed subscription/download batches, isolated-helper cleanup and verified launch-after-download. Testing included a 34-mod subscription batch, a 61-mod lifecycle/stall investigation and successful post-fix multi-mod completion and launch. Flatpak and restart/recovery boundaries remain before the feature can leave experimental status.

Priority 1 — safe Steam handoff:

- Completed — reproduced the post-download launch failure where Steam claimed DayZ was running without starting a DayZ process, then resolved it by moving Steamworks ownership out of the GUI process.
- Completed — the Steamworks context now lives in an isolated helper process that must exit before launch is enabled; successful native-Steam launch-after-download is confirmed.
- Completed — isolated-helper process exit is the readiness boundary. Real-world retesting confirmed that the earlier fixed 10-second cooldown was unnecessary.
- Completed — launch is blocked while the subscription helper is active, and **Launch server** waits for helper exit plus a fresh all-installed mod check before handoff.
- Completed — on restart, relevant numeric items in Steam's DayZ Workshop download staging area are presented as possible outstanding activity; duplicate helper sessions and launch are guarded until Steam finishes and a fresh mod check clears the evidence.
- Completed — the unsafe **Stop monitoring** behavior was replaced with **Hide monitor**: the original helper keeps monitoring in the background, hidden progress updates cannot reopen the dialog, and the install action returns to that same session.

Priority 2 — direct discovered-server journey:

- Completed — a discovered Server Browser row can become the active in-memory server context for mod checking, subscription and launch without first writing it to curated YAML.
- Completed — direct **Inspect mods** and **Launch server** actions keep the selected discovered identity through background mod and Workshop work; double-click begins the inspect flow.
- Completed — **Promote to curated** remains an optional persistence action, not a prerequisite for trying or joining a server.
- Completed — local curated YAML remains the user-owned saved-server source while remote discovered rows stay read-only.

Priority 3 — Workshop readiness and information:

- Completed — missing mods can be requested from the Mods tab or launch warning after explicit confirmation, with bounded retry for incomplete Steam download requests.
- Completed — batch progress shows installed count, current mod name and percentage when Steam supplies it; successful completion offers the guarded **Launch server** continuation.
- Completed — if Steam stops reporting any state, byte or directory progress for two minutes, the isolated helper exits with an explicit incomplete result so AppID 221100 is released instead of leaving DayZ shown as running until the full operation timeout.
- In progress — normal experimental mod checks now query `ISteamUGC::GetItemState` through an isolated helper and launch preflight treats reported update/pending/downloading items as not ready; add a final fresh pre-handoff query so state cannot age between check and launch.
- Completed — when experimental Steam integration is enabled and Steam is running, the normal selected-server mod check performs a batch Workshop item-state check so **Installed**, **Update required**, **Download pending** and **Downloading** are represented honestly instead of treating directory presence as readiness.
- Completed — Mods rows provide **Check/update this mod** through the same isolated Steam helper for targeted recovery, while the ordinary server-level check remains the primary way to validate the complete required set.
- Completed — Mods rows and the Steam confirmation use Steam published-file metadata for pre-download sizes, switch to remaining transfer bytes once available, and label genuinely unavailable or partial totals explicitly.
- Add per-mod queued/downloading/installing progress to Mods rows, gradually filling green and ending in the verified **Installed** state, while retaining the batch-level dialog.
- Completed — progress UI uses mod names with numeric Workshop IDs only as fallback/support detail.
- Expose the required-mod count for a selected/discovered server where provider/API data permits it, without pretending an unknown count is zero.

Priority 4 — discovery truth and regression coverage:

- Investigate servers shown as online that fail a fresh live check; distinguish cached/provider claims from locally validated status and expose freshness honestly.
- Cover stopped Steam, Steam stopping mid-operation, partial completion, deleted/unavailable items, restart during downloads, secondary libraries, Flatpak Steam and launch-after-download in repeatable tests and the manual smoke checklist.

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
