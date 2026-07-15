# WolfLauncher Project State

Cross-repository handoff: read the **Future Codex resume note** in
`DISCOVERY_FRESHNESS_HANDOFF.md` and its authoritative API companion in
`../WolfAPI/DISCOVERY_FRESHNESS_CONTRACT.md`. Discovery development remains
bidirectional regardless of which repository a request originates in. The next
shared task has a locally implemented WolfAPI balance between new, expired and
retryable required-mod metadata candidates. Observe initial production cycles,
then raise the global budget progressively; Launcher direct inspection remains
final truth.

Current snapshot: v0.8 native-launch parity validated; v0.9 native hardening is in progress and the initial GUI simplification pass is complete. Native launch is the default with the external launcher retained as a fallback.

WolfLauncher is a Linux-first DayZ launcher GUI built with Python and PySide6. Its validated native Python engine is the default, with the existing MIT-licensed `dayz-linux-cli-launcher` style shell launcher retained as a fallback.

The upstream shell launcher is now vendored under `external/dayz-linux-cli-launcher/` so the current working behavior can be inspected and replaced gradually.

## Current status

The v0.8 launch, status, settings health checks, diagnostics, mod-checking, discovered-server browser and native Linux handoff are considered functional. The application can be used as the working project base for the native-launch hardening cycle.

## Latest handoff

Handoff recorded: 2026-07-11 after commit `05d0ce5` on `main`.

- Release `v0.8.0` is tagged at `b7883a2` and pushed to GitHub.
- Native launch is the default for fresh settings; an existing saved external-launcher choice is preserved.
- GitHub Actions runs the unit suite on Python 3.10, 3.11 and 3.12. The matrix passed for `05d0ce5` in run `29168383905`.
- The local suite contains 323 passing tests.
- Real desktop smoke testing passed after the v0.9 refactors: Settings health refresh/population, Copy health, Copy diagnostics, native preview copy actions, dialog close behavior, a known-working native server handoff, Server Browser filters/limits/sorting, curated promotion/editing, discovered-row display metadata and discovered-server **Copy details** all worked.
- `wolflauncher/launch_dialogs.py` now owns external/native launch dialogs and post-handoff DayZ process watching.
- `wolflauncher/settings_health.py` now owns testable Settings health snapshot construction.
- `wolflauncher/discovery_refresh.py` now owns automatic provider-refresh timestamp parsing, UTC normalization and the 24-hour throttle policy.
- `wolflauncher/launch_preflight.py` now owns the ordered launch-preflight policy, separating environment, Steam and mod decisions from their Qt dialogs.
- Failed or stale cached mod results no longer count as a completed launch preflight check; only a successful result for the selected server suppresses the explicit unchecked-mod confirmation.
- Native command preparation also reuses only a successful matching cached mod result; after an unchecked-launch confirmation, failed or stale results fall back to the native engine's fresh required-mod lookup.
- Native fresh required-mod lookup failures are reported as structured `mod lookup` errors with recovery and external-fallback guidance instead of escaping the GUI as raw API exceptions.
- Failed cached mod checks no longer suppress the automatic quiet retry when a curated server is selected again; only successful matching results are reused.
- Mods copy/open actions are gated to the selected server so a previous server's result cannot be used while a new check is running; failed selected-server reports remain copyable, while Workshop link/page actions require a successful result.
- Cached and in-flight mod results are also bound to the Workshop directory that was checked, so changing Steam install context cannot make an old worker result authoritative; mismatched completions queue a fresh check for the current selection.
- Changing Steam install mode now deterministically starts a quiet forced mod recheck, or queues it behind an in-flight lookup, so the replacement check no longer depends on switch timing.
- Changing between native and external launch engines now uses the same invalidation and quiet forced recheck path so the Mods view follows the newly authoritative Steam/Workshop context.
- Launch dialogs use shell-aware command formatting for display and copied reports, preserving argument boundaries for paths and player names containing spaces or shell characters while execution continues to use a safe argument vector.
- Cached resolved-IP launch selection now accepts only valid IPv4 values, so launching during initial status refresh preserves the configured hostname instead of trying to resolve the `Checking...` table placeholder.
- `wolflauncher/workers.py` now owns status, mod-check, discovery and enrichment background threads, with focused tests for row selection and error containment.
- `wolflauncher/curated_dialogs.py` now owns curated-server promotion and editing forms, with direct normalization tests.
- `wolflauncher/curated_server_presenter.py` now owns unchecked/online/offline curated-row display construction.
- `wolflauncher/mod_presenter.py` now owns Mods-tab summary text and installed/missing row presentation.
- `wolflauncher/native_launcher.py` now owns native failure-detail assembly for full parity, unavailable context and secondary report failures.
- Steam selection regression coverage now locks down complete-install priority, explicit `STEAM_ROOT` selection and empty detection.
- The initial v0.9 GUI simplification pass is complete. Server Browser keeps common filters, promotion and reset visible while secondary filters and database/enrichment tools remain available through a direction-marked collapsed disclosure panel.
- The same progressive-disclosure pattern now keeps common Mods actions visible while retaining native preview, copy and selected-page controls in an advanced panel.
- Desktop feedback aligned both browser-style tabs: Server Browser information now precedes search/common filters, and advanced disclosures sit at the bottom of both Server Browser and Mods.
- The Server Browser bottom row aligns its advanced disclosure on the left with Promote/Reset on the right; the approved Mods layout remains unchanged.
- User desktop review approved the current Server Browser and Mods direction. Do not undo their hierarchy or move advanced controls back above the results without new review.
- User desktop review approved the simplified Settings hierarchy: installation summary and launch choices remain visible above health results, Check health and Save settings remain persistent, and discovery/import/copy support controls remain available through a bottom disclosure.
- User desktop review approved the Servers consistency pass: refresh status and common player controls precede the curated table, while Add/Refresh/Launch remain persistent at the bottom. The external launcher path moved to Settings and appears beside a half-width engine selector only when the external fallback is selected; native mode restores the selector to full width.
- A final real-desktop review passed across all four tabs after the Settings and Servers consistency changes.
- `wolflauncher/table_items.py` now owns the Server Browser's data-aware Qt sorting item, with direct numeric, text and empty-value tests.
- `wolflauncher/server_browser_presenter.py` now owns style-filter, player-count, cache-summary, discovered-row metadata and copied discovered-server details.
- `wolflauncher/server_browser_controller.py` now owns testable cache queries, match counts, summary snapshots and filter-option loading for the Server Browser.
- `wolflauncher/server_browser_table.py` now owns Qt row population, including sortable items, cache-key roles, tooltips and status colours.
- `wolflauncher/app.py` is currently 2,227 lines, down from 2,889 at the v0.8 restart point after the approved GUI consistency work and subsequent hardening boundaries.
- The worker, curated-dialog, sortable-table-item, Server Browser presenter/controller and row-presentation slices were pushed as `3ac6483`, `95e57e6`, `77213b3`, `0c695b9`, `5b3dfb9` and `4853dfe`; each pushed slice passed its hosted test matrix.
- Commit `772e450` restored the automatic-refresh `timezone` dependency after real-desktop testing exposed the missing import; timezone-aware and legacy naive timestamps now have regression coverage.
- Commit `3868fe1` documented that WolfAPI does not currently supply ping, added explanatory blank-ping tooltips and made the launcher accept future additive `ping_ms`, `ping` or `latency` fields.
- A launch-dialog extraction briefly removed the main window's `QTimer` import and caused startup to fail. Commit `63d014c` restored it, added a regression test and passed both a clean temporary-profile GUI startup check and hosted CI.
- GitHub CLI authentication is restored for `DrakonWolfDev` with repository access; normal Git continues to use the SSH `origin` remote.
- Commits `e541b5c`, `2fde7f9` and `a443310` completed, approved and documented the Settings/Servers/four-tab GUI pass. Commit `9ed18bf` extracted the discovery refresh policy; all four commits are pushed to `origin/main`.
- Commits `957bb8c`, `d7094ea`, `13f2087`, `92c2174`, `c995c14`, `af98eb1`, `7ced984`, `8cd8385` and `05d0ce5` hardened launch preflight, target selection, mod lookup/reporting and stale mod-result handling; each pushed slice passed its hosted matrix through the final run `29168383905`.
- The working tree was clean and synchronized with `origin/main` before this handoff documentation refresh.

The user confirmed the Flatpak Workshop/restart path and the advanced quality-
warning control work on the real desktop on 2026-07-14. Real-world native-Steam
testing had already confirmed successful subscription/download batches, safe
hidden monitoring, bounded incomplete-item retries and launch after isolated-
helper exit plus a fresh all-installed mod check. Continue treating Workshop
management as experimental while responding to real-world failures; preserve
the approved four-tab hierarchy and the settled clean-profile startup smoke
check for import/startup changes.

## v0.9 GUI consistency handoff

The native visual theme is implemented with shared tokens, a complete Qt palette and application-level QSS for the existing widgets and dialogs. It uses restrained charcoal surfaces, amber action hierarchy, semantic status colours, portable technical fonts and visible keyboard focus without changing the approved tab structure. The user confirmed the foundation at different resolutions; final real-desktop interaction review and later icon/branding work remain separate from this solid theme baseline.

Server Browser and curated Servers now apply their HTML redesign references as native Qt layouts. Server Browser uses bounded common filters, a concise summary and balanced Name/Host allocation while retaining every operational field through **Show detailed columns**. Curated Servers uses native card rows with status edges, two-line metadata, player/ping blocks, favourite and per-row Connect actions; **Show detailed table** preserves the original editable table, complete data, selection, context-menu and launch workflows.

The Server Browser wide-screen policy caps Name at 600 logical pixels, scales it to 30% of the viewport with a 300-pixel floor and assigns remaining table width to Host. Common filters remain contiguous instead of spreading across 1920×1080, and checkboxes use an explicit theme indicator rather than relying on an invisible dark desktop-style box.

- Use this vertical hierarchy where a tab has comparable content: information/summary, common controls, results, then a bottom action row.
- Keep the frequent path visible. For Server Browser this means search/common filters and Promote/Reset. For Mods this means recheck, open missing pages and filter.
- Put secondary filters, refresh/enrichment, parity, copying and specialist tools behind a compact direction-marked disclosure at the bottom.
- On a shared bottom row, align the disclosure left and primary persistent actions right. Avoid adjacent controls on separate rows when they visually belong together.
- Use `wolflauncher.ui_sections.set_disclosure_state` so collapsed/expanded wording and markers remain consistent.
- Preserve every advanced feature unless removal is explicitly agreed. Progressive disclosure is an organisation tool, not permission to delete diagnostics, parity, fallback or provider controls.
- Avoid redundant labels when a combo box already communicates its purpose clearly, as with `Any map`.
- Keep summaries above filters/results, matching the approved Server Browser, Mods and Settings information-first rhythm.
- Validate visible layout changes with the 1350x720 offscreen render, the full unit suite and a real desktop review. Check both collapsed and expanded states and ensure bottom controls remain visible.
- Current approved commits: `c5c1110` initial Server Browser disclosure, `2c0161a` disclosure refinement, `d74a4b6` Mods disclosure, `c65d707` shared hierarchy, `f42e732` Server Browser bottom-row alignment, `e541b5c` Settings simplification, `2fde7f9` Servers/adaptive fallback settings and `a443310` final desktop-review record.

Working:

- PySide6 desktop GUI.
- YAML curated server list.
- Direct in-app addition of curated YAML server rows.
- Selected curated server rows can be status-refreshed individually.
- Last-known curated server status is cached locally for calmer startup rows.
- Curated server rows can persist a live status connect-port correction back to YAML.
- Read-only SQLite-backed discovered server browser tab.
- YAML/JSON import for discovered server cache rows.
- Promotion from discovered cache rows into the curated YAML server list with editable name/group.
- In-app editing/removal of curated YAML server rows.
- Copy actions for discovered server connect addresses and details.
- Steam master server candidate discovery import script.
- Single in-app discovered-server database refresh using the provider selected in Settings.
- Explicit staged WolfAPI v1 provider using bounded strict responses, with the
  legacy `/api/servers` provider preserved as a separately selectable fallback
  and for existing saved settings.
- WolfAPI rows currently require local **Enrich visible** queries for ping because the hosted API contract does not supply it; WolfLauncher accepts a future additive `ping_ms`, `ping` or `latency` field and explains blank provider ping cells in a tooltip.
- Steam Web API server-list discovery with user-supplied API key.
- BattleMetrics server discovery.
- Optional quiet rate-limited startup refresh for the selected discovery provider, throttled to once per day.
- Enrichment of visible discovered servers with live status data.
- Live enrichment preserves cached display names, stores differing live server names separately and updates game ports from queried connect addresses when available.
- Live enrichment probes a bounded set of likely query ports when discovered rows have uncertain port data.
- Failed provider refreshes preserve existing discovered-server cache rows.
- Server Browser map and version filters populated from cached/enriched values.
- Server Browser source/style filtering, result-limit controls, reset controls and cache summary counts.
- Server Browser advanced filtering includes an off-by-default **Hide quality
  warnings** option. WolfAPI advisory flags persist in SQLite schema v5, remain
  visible with explanatory detail by default, and filter cached plus remote v1
  list/search results consistently when selected.
- Server Browser data-aware sorting for cached rows, including numeric player/ping values and checked/seen timestamps.
- Server Browser double-click promotion and context actions for connect/host/detail copying.
- DNS hostname and direct IP support.
- Live DayZ server querying through `gamedig`.
- Partial `gamedig` restart responses are treated as offline/restarting rather than as healthy online rows.
- Server status table with map, players, time, ping, version, flags and connect address.
- Native Steam detection.
- Flatpak Steam detection.
- DayZ install detection, including Steam `appmanifest_221100.acf` `installdir` parsing when available.
- DayZ Workshop folder detection.
- Secondary Steam library detection through `steamapps/libraryfolders.vdf` for native and Flatpak Steam installs.
- Settings tab with compact green/yellow/red health checks.
- Settings health rows can be copied as a support snapshot with generated-at metadata.
- Full diagnostics reports can be copied from Settings for support and bug reports.
- Copied diagnostics reports include generated-at and selected launch-engine metadata.
- Native launch parity reports include an external-vs-native readiness comparison for the shared connect target, query port, current required-mod count and missing local Workshop directories.
- Launch dialogs save the latest copyable launch output report locally so Settings can copy it again after the dialog is closed.
- Settings health, diagnostics and native parity reports show the selected install's DayZ Proton compatdata folder when visible; this is informational and does not gate launch.
- Missing Proton compatdata is reported as a possible first-run Steam/Proton state, with guidance to launch DayZ directly from Steam once so Proton can create the prefix and show prompts.
- Steam health reporting distinguishes native, Flatpak and `STEAM_ROOT` installs and explains partial detection states.
- Settings health and diagnostics explain the selected Steam install and list detected Steam candidates so Auto selection is easier to troubleshoot.
- Settings health and diagnostics include Steam command details in selected, Auto and candidate summaries, including the `flatpak run com.valvesoftware.Steam` handoff form for Flatpak Steam.
- Settings health includes a dedicated Auto Steam row so users can compare the selected Steam install mode with the install WolfLauncher would choose automatically.
- Discovery provider, API key, endpoint and refresh-limit settings persistence.
- Favourites persistence.
- Last selected server persistence.
- Mods tab.
- Required mod lookup via DayZ SA Launcher style API.
- Local Workshop folder scan.
- Required-vs-installed mod comparison.
- Missing mod list and Steam Workshop links.
- Mods tab repopulates from the cached selected-server mod result if the visible table is empty, and silent startup checks show a clear Workshop-folder message when detection blocks mod checking.
- Mods table double-click and right-click actions.
- Mods filtering for all/missing/installed.
- Copy Workshop ID, mod name, Workshop URL, connect address and server details.
- Guarded native launch workflow with the external `dayz-launcher.sh` script retained as a fallback.
- Launch commands pass the resolved server IP to the external launcher when available.
- Missing-mod warning with Open Workshop / Launch Anyway / Cancel.
- Steam-not-running warning.
- Launch output dialog with generated command and launcher output.
- External and native launch output can be copied from the launch dialog for timestamped support reports, and the most recent closed launch dialog is saved at `~/.local/share/wolflauncher/last_launch_report.txt`.
- Successful external-launcher exit code is presented as a handoff to Steam.
- Launch dialogs clarify that a successful handoff does not prove Proton initialized or DayZ reached the menu.
- Launch dialogs watch for known DayZ processes for up to 45 seconds after handoff, because Steam/Proton can take tens of seconds before DayZ appears.
- Mods tab can copy a timestamped mod-check report with required mod counts, installed/missing state, Workshop URLs and missing Workshop IDs for parity testing and support, or copy only missing Workshop links for manual subscription.
- Mods summaries and copied mod reports include the Steam install context and Workshop path checked so native, Flatpak and `STEAM_ROOT` parity snapshots are easier to compare.
- Native launch parity report from the Mods tab, with generated-at metadata and a copyable validation checklist comparing the external launcher handoff with the native command, selected Steam install setting, detected Steam install, resolved connect target, required mod IDs, prepared mod links and missing Workshop directories. When the native command is ready, the preview dialog can copy only that command for direct terminal parity testing.
- Native launch failures include copyable parity-report details when a cached mod check is available, so failed launches and preview reports can be compared. If a full parity report is unavailable, failure details still include the selected Steam install setting, detected install, Steam command, DayZ/Workshop paths and server target.
- Native preview failures preserve detailed native-engine text, including stale symlink expected-vs-actual targets when available.
- Native parity reports show created versus reused mod symlink counts, and existing `@mod` symlinks are reused only when they point to the expected Workshop directory. Stale `@mod` symlink conflicts report expected versus actual targets in copyable failure details.
- The native engine does not offer "Launch anyway" when required Workshop directories are missing, because it cannot build a valid native mod command until the missing mods are installed.
- Native Steam handoff with real-world native Steam and Flatpak Steam launch success confirmed across Steam running/stopped and unmodded, fully modded and partially missing-mod server cases.
- Saved launch-engine setting in Settings. `Native launcher` is the default for fresh installations, while `External launcher` remains available as a fallback. Existing saved choices are preserved.
- Saved native Steam install selection in Settings, with Auto, Native Steam, Flatpak Steam and `STEAM_ROOT` options so parity testing can target a specific detected install.
- Settings and diagnostics label this as the Steam install mode so it is not confused with the external/native launch-engine selector.
- Structured native-launch failure stages with user-facing recovery guidance for Steam detection, library detection, DNS and mod setup failures.
- README Linux Mint / Ubuntu development setup instructions with dependency notes and Settings health fallback guidance.

Planned WolfAPI follow-up:

- `DISCOVERY_FRESHNESS_HANDOFF.md` records the cross-repository contract and
  rollout state; `ROADMAP.md` tracks the launcher adoption work.
- The current launcher working tree contains the additive adoption foundation:
  SQLite schema v5 preserves earlier layouts while combining stable IDs,
  endpoint aliases, freshness/validation fields and API required-mod metadata;
  WolfAPI rows merge port corrections
  by stable ID; opt-in v1 list/search/resolve clients enforce rollout metadata.
  Settings exposes v1 as an explicit staged provider while existing saved
  `wolfapi` selections remain on the separately labelled legacy fallback.
  V1 refreshes paginate in bounded 100-row background requests and use
  merge-only cache updates. Advisory API quality flags are retained for the
  explicit off-by-default advanced hide control. Server Browser search is
  local-first with a 450 ms
  debounced remote v1 search that merges stable-ID matches, preserves unrelated
  rows and does not let stale completions replace the current query view.
  Exact `host:port` input uses alias-aware resolution for either port role.
  Fresh installations now select v1 by default; existing saved provider choices
  remain unchanged and the legacy endpoint remains selectable.
  Existing Status tooltips and copied details expose API freshness, validation
  and provider observation without changing the approved table hierarchy;
  locally expired labels are marked refresh-pending rather than reclassified.
  A startup audit confirms discovered SQLite rows are not automatically
  UDP-probed: startup status checks are curated-YAML-only, v1 refresh is
  HTTP-only and **Enrich visible** remains explicit.
- WolfAPI v1 required-mod count/status/timestamps/error/hash now persist in
  SQLite and appear as ready/stale/failed browsing evidence in tooltips and
  copied details. Direct **Inspect mods** and launch-time lookup remain final
  truth. The API job remains disabled by default in source but is persistently
  enabled in the local deployment; its first scheduled 10/10 cycle passed with
  no stale or failed rows.
- A post-fix hosted probe on 2026-07-13 confirmed bounded list, dedicated
  search, exact resolution, ETags, rollout metadata, stable identity and aliases
  are live. The strict client imported 100 rows into isolated SQLite. Two
  public-hostname 1,000-request/100-concurrency mixes initially produced 1 and
  13 timeouts with high tail latency, prompting host/container and
  reverse-proxy isolation.
  The host-local origin comparison subsequently passed 1,000 requests at about
  680 requests/second with zero errors and p99 181 ms, narrowing the remaining
  gate to OpenResty/TLS/public routing rather than WolfAPI capacity.
  A TLS/SNI-preserving direct-LAN OpenResty run then passed at about 482
  requests/second with zero errors and p99 246 ms, identifying the earlier
  external timeout pattern as local router NAT-loopback/hairpin behavior.
  Origin and proxy capacity are cleared for staged adoption with telemetry.
- WolfAPI commit `552b9cf` implements and repairs bounded
  `/api/v1/servers`, `/search` and `/resolve` flows, ETags, request-time
  freshness coverage, validation queue lag, normalized provider/validation
  fields, stable UUID server IDs and endpoint aliases. The hosted deployment
  passed the documented rollout gates and v1 is now the fresh-install default;
  saved choices and the legacy fallback remain available.
- SQLite schema v5 preserves earlier layouts, storing Workshop metadata,
  stable server IDs, endpoint aliases and API mod-metadata provenance;
  corrected endpoints merge
  into one cached row without weakening offline behavior or curated YAML
  ownership.
- WolfAPI `/api/health` remains operator/support data. Normal browsing should
  consume only the public v1 contract and continue from SQLite during API
  failure.
- Current WolfLauncher behavior remains read-only for remote WolfAPI data; users can already promote discovered rows or add their own servers to the local curated YAML list.
- Cross-project planning rule: launcher features should ask WolfAPI for stable fields/endpoints when they need source freshness, validation state or submission workflows; WolfAPI changes should consider how the Server Browser, diagnostics and promotion flow can use the data without harming offline/local operation.

## Known bug

- DayZ currently does not run when the Steam launch options contain `__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%`.

Current handling:

- Treat this as an external Steam/Proton/DayZ launch-option compatibility issue, not a WolfLauncher command-generation failure.
- Do not recommend that option as the default workaround.
- WolfLauncher does not set, rewrite or reliably read per-game Steam launch options.
- Diagnostics report PRIME-related environment variables visible to WolfLauncher, but Steam launch options must be checked in Steam itself; confirmed testing showed Steam can have the known option set while WolfLauncher sees no PRIME variables in its own environment.
- Diagnostics use a single environment snapshot for the visible PRIME values and launch troubleshooting summary so copied reports stay internally consistent.
- Diagnostics classify visible PRIME/DRI environment state and warn when WolfLauncher itself is running with the known problematic NVIDIA PRIME offload environment combination.
- Diagnostics, Settings health and post-handoff warnings include explicit Steam launch-options guidance that points users to Steam's DayZ Properties page, while preserving the rule that WolfLauncher does not read, write or default per-game launch options.
- Settings health includes a PRIME environment row so the known problematic environment is visible without opening a full diagnostics report.
- Diagnostics and Settings health report whether common PRIME helper commands such as `prime-run` and `switcherooctl` are visible, without treating their absence as a problem on non-hybrid systems.
- Diagnostics include per-install Steam readiness and command summaries for native, Flatpak and `STEAM_ROOT` library detection.
- Diagnostics include Auto Steam selection and command-aware candidate summaries for native, Flatpak and `STEAM_ROOT` troubleshooting.
- Diagnostics list detected Steam library folders for each configured install.
- Diagnostics include known DayZ process visibility for Steam/Proton handoff troubleshooting.
- Copied diagnostics label known DayZ process visibility as general process state, while launch dialogs keep the more specific post-handoff process-check wording.
- Copied diagnostics use conditional handoff troubleshooting wording so reports captured before launch still make sense.
- Diagnostics and Settings health include a consolidated launch troubleshooting report covering selected Steam mode, detected Steam command and paths, DayZ process visibility, PRIME status and suggested next steps.
- Known DayZ process checks are case-insensitive so Proton command lines with different executable casing still count as visible.
- Post-handoff process checks should avoid warning too early; observed native launches can report no DayZ process initially, then show DayZ roughly 10 seconds later, matching the slower behavior seen with the original CLI launcher.
- Hybrid-GPU testing should start outside WolfLauncher, for example with `prime-run glxinfo -B`, `prime-run steam` and direct DayZ launch from Steam before testing the WolfLauncher handoff.
- Useful bug reports should capture native-vs-Flatpak Steam, GPU driver/PRIME helper, Proton version, whether DayZ starts directly from Steam without per-game launch options, and WolfLauncher diagnostics output.
- Future work should improve hybrid-GPU/NVIDIA PRIME diagnostics and safer launch-option guidance.

## Key files

- `AGENTS.md` - quick project orientation for future coding agents.
- `main.py` - entry point.
- `wolflauncher/app.py` - main Qt GUI, tabs, table actions and launch workflow.
- `wolflauncher/status.py` - `gamedig` server querying and host resolution.
- `wolflauncher/mods.py` - required mod lookup and local Workshop scanning.
- `wolflauncher/mod_presenter.py` - pure Mods-tab summary and row presentation.
- `wolflauncher/platform_detection.py` - Steam, DayZ and Workshop detection.
- `wolflauncher/launcher.py` - external launcher command building.
- `wolflauncher/launch_dialogs.py` - external/native handoff dialogs and post-handoff process watching.
- `wolflauncher/launch_preflight.py` - pure ordered environment, Steam and mod preflight policy.
- `wolflauncher/launch_selection.py` - validated cached resolved-IP launch target selection.
- `wolflauncher/native_launcher.py` - native launch engine, parity reports and failure-detail construction.
- `wolflauncher/server_cache.py` - SQLite cache for discovered public servers.
- `wolflauncher/settings.py` - user settings and favourites.
- `wolflauncher/settings_health.py` - testable Settings health summary and row construction.
- `wolflauncher/discovery_refresh.py` - pure automatic provider-refresh timestamp policy.
- `wolflauncher/workers.py` - background status, mod-check, discovery and enrichment threads.
- `wolflauncher/curated_dialogs.py` - curated-server promotion and editing dialogs.
- `wolflauncher/curated_server_presenter.py` - pure curated-row display construction.
- `wolflauncher/table_items.py` - data-aware Qt item sorting for cached server rows.
- `wolflauncher/server_browser_presenter.py` - pure Server Browser row/detail formatting and style-filter rules.
- `wolflauncher/server_browser_controller.py` - testable cache query and filter-option boundary.
- `wolflauncher/server_browser_table.py` - Qt discovered-row population and item metadata.
- `wolflauncher/config.py` - YAML server loading and default launcher path candidates.
- `tests/` - standard-library unit tests for launcher commands, vendored launcher handoff contract, path discovery, YAML loading, status parsing and mod parsing.
- `example.servers.yaml` - tracked curated server template.
- `servers.yaml` - local ignored curated server registry.
- `external/dayz-linux-cli-launcher/dayz-launcher.sh` - vendored MIT legacy launch engine.
- `LICENSE` - WolfLauncher MIT license.
- `THIRD_PARTY_NOTICES.md` - third-party license notices.
- `CHANGELOG.md` - version history.
- `docs/RELEASE_CHECKLIST.md` - automated and Steam/Proton release validation checklist.
- `ROADMAP.md` - planned milestones.
- `ARCHITECTURE.md` - architecture and design notes.

## Important design decisions

- YAML is the curated server/source-of-truth format for early versions.
- SQLite is now introduced as the discovered public server browser cache.
- v0.6 provides a standalone SQLite server cache foundation and read-only browser tab for discovered public servers.
- Provider refreshes sync their discovered rows after successful responses by removing stale provider-backed entries and adding only new cache keys; failed refreshes preserve existing cache rows. Curated YAML remains the place for saved servers.
- JSON is used for user settings and favourites under `~/.config/wolflauncher`.
- The native Python launcher is the default; the external shell launcher remains a selectable fallback and reference contract.
- The vendored shell launcher is the reference contract for future native launcher work.
- Native launcher replacement work is implemented behind a separate Python interface, with tests covering compact mod symlink names, relative symlink creation, no-mod/all-missing/mixed missing-mod preview handling, missing selected-mode Workshop folders, Steam launch command generation and external-vs-native parity report formatting.
- The native engine has confirmed real-world native Steam and Flatpak Steam handoff success, including starting Steam when it was not already running and a Flatpak DayZ launch reaching process detection in roughly 10 seconds.
- The main Launch button uses the native engine by default after successful real-world parity testing; Settings can select the external fallback.
- When the native engine is selected, mod checks, native launch preview and launch preflight use the selected Steam install rather than always using automatic best-install detection.
- Auto Steam selection is reported from the same detection snapshot as the candidate list so users can see why native or Flatpak Steam was chosen.
- Native launch command generation now fails before handoff when the selected Steam mode lacks a detected command, with mode-specific guidance for native Steam, Flatpak Steam and `STEAM_ROOT`.
- `STEAM_ROOT` detection reuses the native Steam command and running state when available, while Settings health warns if the selected library is complete but no launchable Steam command is detected.
- Mod management remains read-only and advisory by default. An opt-in experimental control now uses the official Steam API redistributable already present in the selected Steam installation to confirm and request missing-item subscriptions through `ISteamUGC`, monitor progress, and verify local directories. Its Steamworks context is isolated in a spawned helper process that must exit before launch is re-enabled. It never vendors Valve's binary, downloads Workshop bytes itself, or removes subscriptions; manual Workshop links remain the fallback. Native Steam and the Flatpak Workshop/restart path passed real-world testing.
- Launch remains guarded: WolfLauncher warns about missing mods and Steam state before native handoff or calling the external fallback.
- Hostnames are resolved before launch where possible to mirror the original terminal menu behaviour and avoid DayZSA API issues with DNS-based servers.
- Python bytecode caches are ignored and should not be tracked as source.
- WolfLauncher is MIT licensed; vendored third-party MIT notices are preserved separately.

## Next step

Use v0.9 native-launch hardening as the next active development target:

- Keep native launch as the default and retain the external launcher as a fallback.
- Preserve the completed launch-dialog, Settings-health, worker, curated-dialog and Server Browser query/presentation boundaries while continuing small `app.py` extractions.
- Run an offscreen clean-profile startup smoke check after changes to Qt imports or `MainWindow` initialization.
- Continue native and Flatpak Steam regression testing when real-world failures are reported.
- Before v0.9 is considered complete, explicitly pause for a GUI simplification pass that preserves advanced discovery, diagnostics, parity and fallback features behind calmer, clearly labelled secondary controls.
- Continue refining hybrid-GPU/NVIDIA PRIME guidance after reproducible data is available.
- Keep refining Proton/Steam handoff failure states from real-world failures.
- Continue refining Linux Mint/Ubuntu install instructions toward packaged installs.
- Defer packaging work until late pre-1.0 polish; launcher parity and Steam/Proton reliability should come first.
- Continue improving curated server organisation beyond basic edit/remove flows.
- Keep local `servers.yaml` for curated, personal and import/export server lists, seeded from tracked `example.servers.yaml` when missing.
- Continue carving native Python equivalents from the vendored launcher's behavior while expanding the new native launcher engine behind WolfLauncher interfaces.
- Keep mod management read-only by default while hardening the opt-in Steam-native experiment through the ordered Workshop/join-flow roadmap. Do not graduate it until the post-download launch race and monitoring semantics are resolved.
- Keep the NVIDIA PRIME Steam launch-option issue visible as the only known bug until it is reproduced and diagnosed.
