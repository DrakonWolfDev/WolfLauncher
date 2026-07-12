# Changelog

## Unreleased

- Fixed sequential discovered-server mod inspection stalling after several selections by handing the newest queued context forward when the current worker actually finishes, with visible queued feedback and direct navigation to Mods.
- Added a direct discovered-server journey: browser rows can become an in-memory active context for mod inspection, guarded Workshop resolution and launch, while promotion to curated YAML remains optional.
- Recorded the real-world experimental Workshop hardening roadmap: post-download launch readiness, honest stop-monitoring semantics, direct discovered-server checking/launching, update checks, size/progress presentation and discovery-status truth.
- Added an opt-in experimental Steam-native Workshop subscription flow for missing DayZ mods, with explicit account-change confirmation, per-item download monitoring, cancellation of waiting, local-directory verification and manual-link fallback.
- Added a minimal `ctypes` ISteamUGC adapter that dynamically loads Valve's existing 64-bit Steam API redistributable from the selected Steam installation; WolfLauncher does not vendor the proprietary library or create a persistent `steam_appid.txt`.
- Added an early selected-client warning when experimental Workshop subscription is requested while Steam is stopped, before opening the confirmation or progress flow.
- Changed experimental Workshop progress to show the required mod name instead of a numeric Workshop ID when server metadata provides one.
- Renamed the Workshop dialog action to **Stop monitoring**, blocked launch while the Steamworks worker is active, and added a short post-download settling boundary after the Steamworks context is released.
- Added **Install missing mods** to native and external missing-mod launch warnings when the experimental Steam-native subscription control is enabled.
- Moved the experimental Steamworks subscription session into a spawned helper process so the process that initialized as DayZ exits completely before WolfLauncher permits the real DayZ launch.
- Replaced **Stop monitoring** with **Hide monitor** so the original helper continues in the background, and made repeated install actions reopen that monitor instead of starting another Steamworks session.
- Made incomplete Workshop items retry Steam download requests at a bounded interval, identify still-incomplete IDs on timeout, ignore terminal interrupts inside the helper and cancel/join that helper during application shutdown.
- Removed the fixed 10-second post-download cooldown after real-world testing confirmed isolated-helper process exit is a sufficient launch-readiness boundary.
- Kept hidden Workshop monitors hidden by suppressing `QProgressDialog` updates until explicitly reopened, and simplified successful completion text to the downloaded mod count.
- Replaced the successful download dialog's generic confirmation with **Launch server**, deferred until the isolated helper exits and a forced mod recheck confirms the downloaded set.
- Added conservative restart/recovery detection for required items left in Steam's DayZ Workshop download staging area, with honest Mods guidance and guards against duplicate helper sessions or launch until a fresh check confirms readiness.
- Made native/external launch-engine changes invalidate and quietly recheck the selected server's mods using the newly authoritative Steam/Workshop context, matching Steam install mode changes.
- Made Steam install mode changes deterministically start or queue a quiet forced mod recheck, instead of leaving the Mods tab waiting when the previous lookup had already finished.
- Bound cached mod results to both the selected server and Workshop directory, preventing an in-flight check from an old Steam install mode being accepted after the mode changes and queuing a fresh check for the current context.
- Prevented Mods copy/open actions from using another server's stale result while a new selection is being checked; failed current-server reports remain copyable for support, while Workshop actions require a successful current result.
- Stopped failed cached mod checks from suppressing automatic retry when a curated server is selected again; only successful matching results are reused by the quiet selection refresh.
- Preserved launch argument boundaries in displayed and copied commands by using shell-aware formatting, so paths or player names containing spaces and shell characters remain unambiguous in support reports.
- Converted native fresh required-mod lookup failures into structured `mod lookup` launch errors with recovery guidance, instead of allowing raw API exceptions to escape the GUI launch workflow.
- Fixed native launch reusing an empty required-mod list from a failed cached check; failed or stale results now fall back to the native engine's fresh mod lookup after unchecked-launch confirmation.
- Fixed launches attempted during initial status refresh treating the `Checking...` resolved-IP placeholder as the server host; only valid resolved IPv4 values now replace the configured hostname.
- Fixed failed or stale cached mod checks being treated as authoritative during launch preflight; they now retain the existing explicit unchecked-mod confirmation boundary.
- Extracted ordered launch-preflight policy from the Qt window into `wolflauncher.launch_preflight`, with direct coverage for environment blockers, stopped-Steam continuation, unchecked mods and native/external missing-mod behavior.
- Extracted the automatic discovery-refresh timestamp policy from the Qt window into a pure module, with direct coverage for recent, expired, naive, invalid and UTC-normalized timestamps.
- Started the v0.9 GUI simplification pass by keeping common Server Browser filters and promotion visible while placing version/source/sort/limit and refresh/enrichment tools behind a compact, direction-marked disclosure control.
- Simplified the Mods tab by keeping recheck, missing-page and filter actions visible while retaining native preview, copy and selected-page actions in an advanced tools panel.
- Aligned the Server Browser and Mods hierarchy by placing their information summary first and moving advanced disclosures to the bottom of each tab.
- Aligned the Server Browser bottom actions on one row, with advanced tools on the left and Promote/Reset on the right.
- Simplified Settings with installation health first, persistent health/save actions and a bottom disclosure for discovery configuration, imports and copy-oriented support tools.
- Simplified Servers with status and common controls first, the curated table in the middle and persistent Add/Refresh/Launch actions at the bottom.
- Moved the external launcher path from Servers to an adaptive Settings row that appears beside the engine selector only when the external fallback is selected.
- Completed real-desktop review of the resulting Servers, Server Browser, Mods and Settings hierarchy.
- Added Steam-selection regressions for deterministic complete-install priority, explicit `STEAM_ROOT` selection and empty detection.
- Moved native launch failure-detail assembly into `wolflauncher.native_launcher`, with regression coverage for no-mod-check context, full parity output and secondary report-generation failures.
- Extracted Mods-tab summary and row presentation into `wolflauncher.mod_presenter`, with direct coverage for errors, no-mod servers, installed/missing counts and row metadata.
- Added an explicit v0.9 GUI simplification checkpoint that keeps common workflows calm while preserving advanced discovery, diagnostics, parity and fallback controls.
- Moved copied discovered-server detail formatting into the existing Server Browser presenter and added coverage for live names, flags, unseen dates and source text.
- Extracted curated-server row display construction into `wolflauncher.curated_server_presenter`, with direct tests for unchecked, online, offline and partial live-status states.
- Extracted discovered-server Qt row population into `wolflauncher.server_browser_table`, with focused tests for item roles, sort metadata, tooltips, status colours and row replacement.
- Clarified blank provider ping values in Server Browser tooltips and documentation, and made WolfAPI parsing accept a future additive `ping_ms`, `ping` or `latency` field.
- Moved discovered-server row display/sort metadata into the Server Browser presenter and fixed copied discovered-server details still calling the removed `_players_text` GUI helper.
- Fixed automatic discovery refresh crashing while evaluating its 24-hour throttle after the worker extraction dropped the main GUI's `timezone` import.
- Added a testable Server Browser controller boundary that owns cache queries, result counts, summary snapshots and filter-option loading.
- Extracted pure Server Browser presentation rules for style terms, player counts and cache-summary text into `wolflauncher.server_browser_presenter`, with direct edge-case tests.
- Extracted the Server Browser's data-aware Qt table item into `wolflauncher.table_items`, with direct numeric, text and empty-value sorting tests.
- Extracted curated-server promotion/edit dialogs from the main GUI module into `wolflauncher.curated_dialogs`, with direct field-normalization tests.
- Extracted status, mod-check, discovery and enrichment thread workers from the main GUI module into `wolflauncher.workers`, with focused error-handling and row-selection tests.
- Fixed the main-window startup failure caused by dropping its `QTimer` import during launch-dialog extraction.
- Recorded successful real-desktop smoke testing of Settings health/report copying, native preview actions and a known-working native server handoff after the v0.9 extractions.
- Extracted external and native launch dialogs and post-handoff process watching from the main GUI module into `wolflauncher.launch_dialogs` without changing the launch workflow.
- Added the Qt EGL runtime library to CI so GUI module import checks run on GitHub's headless Ubuntu workers.
- Extracted Settings health snapshot construction from the main GUI module and added direct readiness-row tests.

## v0.8.0 - 2026-07-11

- Added GitHub Actions unit-test coverage for Python 3.10, 3.11 and 3.12.
- Added a release checklist covering automated checks, desktop smoke tests, native and Flatpak Steam launch cases and the external fallback.
- Updated the package version from the stale `0.2.0` value to `0.8.0`.
- Made the validated native launcher the default for fresh installations while preserving existing saved launch-engine choices and retaining the external launcher as a selectable fallback.
- Recorded successful real-world native launch validation for native and Flatpak Steam, Steam running and stopped, and unmodded, fully modded and partially missing-mod servers.
- Preserved detailed native preview errors, including stale `@mod` symlink details, in the preview failure dialog.
- Added selected Steam/install/server context to native launch failure details when a full parity report cannot be built from a cached mod check.
- Added the selected Steam install setting to copied native parity reports so Auto, Native Steam, Flatpak Steam and `STEAM_ROOT` test runs are easier to compare.
- Expanded native missing-mod parity tests for no required mods, all missing mods, mixed installed/missing mods and missing selected-mode Workshop folders.
- Added selected Steam install context to Mods summaries and copied mod reports so native, Flatpak and `STEAM_ROOT` Workshop checks are easier to distinguish.
- Added a native preview **Copy native command** action that is enabled only when the experimental native command is ready.
- Clarified stale native `@mod` symlink failures with copyable expected-vs-actual target details in native failure reports.
- Added a Mods tab **Copy missing links** action for missing Workshop pages.
- Added a Mods tab **Copy mod report** action for timestamped required/missing Workshop ID snapshots.
- Added a Settings **Copy last launch** action backed by `~/.local/share/wolflauncher/last_launch_report.txt`.
- Added a clearer external-vs-native readiness comparison to copied native launch parity reports.
- Added a local last-known status cache for curated server rows so startup can show previous live data while fresh checks run.
- Added tracked `example.servers.yaml`, ignored local `servers.yaml`, and startup seeding for missing local server lists.
- Added curated add/edit handling for pasted `host:port` values, splitting the host and game port before saving YAML.
- Added selected-row curated status refresh, including an automatic one-row refresh after manually adding a curated server.
- Added a curated-server context action for saving a live status connect-port correction back to `servers.yaml`.
- Added a direct **Add curated server** flow on the Servers tab for saving manual YAML server entries without going through discovery first.
- Added Steam command details to selected and Auto Steam readiness text.
- Added Steam command details to the Settings health header summary.
- Documented command-aware Steam install summaries in README and handoff notes.
- Added Steam command details to Auto/selected Steam candidate summaries in Settings health and diagnostics.
- Added Steam command details to the Settings health configured-install summary.
- Clarified copied diagnostics and native parity reports to show Flatpak Steam as a `flatpak run` handoff command.
- Clarified native parity report result text when the external launcher comparison cannot be built.
- Changed native parity reports to build the external comparison from the same resolved server target as the native preview.
- Matched native launch player-name fallback to the external launcher handoff by using `Survivor` when the configured name is blank.
- Marked v0.7 health checks and Linux polish as the current documented baseline after successful real-world server testing.
- Added an explicit Auto Steam row to Settings health so selected Steam mode and automatic install selection can be compared at a glance.
- Added explicit Steam launch-options guidance to diagnostics, Settings health and post-handoff warnings, including a warning for the known bad NVIDIA PRIME option while keeping launch options external to WolfLauncher.
- Clarified diagnostics wording so copied reports show general DayZ process visibility rather than implying a launch handoff just happened.
- Clarified Settings and diagnostics labels for the selected Steam install mode so they are not confused with the selected launch engine.
- Softened copied troubleshooting next-step wording so diagnostics do not imply a launch handoff happened before the report was captured.
- Added generated-at metadata to copied Settings health reports.
- Added generated-at metadata to copied external launch output reports.
- Added generated-at metadata to native launch parity reports.
- Changed diagnostics generation to use a single environment snapshot for PRIME status and launch troubleshooting sections.
- Changed `STEAM_ROOT` detection to reuse the native Steam command and running state when available, and warn when a ready Steam library lacks a launchable Steam command.
- Made post-handoff DayZ process detection case-insensitive so Proton command lines with different executable casing are still recognized.
- Expanded DayZ install detection to read Steam `appmanifest_221100.acf` `installdir` values before falling back to the conventional `steamapps/common/DayZ` path.
- Clarified Proton compatdata diagnostics so missing prefixes are reported as first-run Steam/Proton state rather than a launch blocker, with matching Settings health, diagnostics and native parity report wording.
- Added a Copy button to the external launch output dialog so the generated command and handoff logs can be pasted into support reports.
- Added informational DayZ Proton compatdata detection to Settings health, diagnostics and native launch parity reports.
- Added generated-at and selected launch-engine metadata to copied diagnostics reports.
- Added a Settings diagnostics copy action that copies the full diagnostics report without opening a separate tab.
- Added a Settings health copy action and right-click menu so support snapshots can be copied from the health table.
- Added PRIME helper command visibility to diagnostics and Settings health, showing whether `prime-run` or `switcherooctl` are available without warning non-hybrid systems.
- Improved native launch Steam-library error guidance so missing DayZ installs and missing Workshop folders point to different recovery steps.
- Expanded the native launch preview into a copyable parity report with a validation checklist comparing the external launcher handoff with the experimental native command, selected Steam install, resolved connect target, required mod IDs, prepared mod links and missing Workshop directories.
- Added copyable parity-report details to native launch failures when a cached mod check is available.
- Changed the missing-mod launch prompt so the native experimental engine no longer offers an impossible "Launch anyway" path when required Workshop directories are missing.
- Added at-a-glance native parity report result text and included mod names in required-mod and missing-directory report sections when available.
- Added native parity report counts for created versus reused mod symlinks, and reject stale `@mod` symlinks that point at the wrong Workshop directory.
- Fixed Mods tab recovery when a cached mod result exists but the visible table is empty, and made missing Workshop detection visible during silent startup checks.
- Added a consolidated launch troubleshooting report to diagnostics and Settings health, covering selected Steam mode, detected command/paths, DayZ process visibility, PRIME status and suggested next steps.
- Fixed initial startup mod checks so the restored or default selected server is checked after the Mods tab is ready.
- Added Settings health and diagnostics summaries that show which Steam install Auto selects and what other detected install candidates report.
- Expanded native and Flatpak Steam detection to read Steam `libraryfolders.vdf`, so DayZ and Workshop can be found in secondary Steam libraries.
- Added diagnostics output for all detected Steam library folders.
- Added unit-tested Steam install selection helpers for Auto, Native Steam, Flatpak Steam and `STEAM_ROOT` launch modes.
- Confirmed real-world experimental native launch success through Flatpak Steam, with DayZ detected roughly 10 seconds after handoff.
- Added a native Steam install selector for Auto, Native Steam, Flatpak Steam and `STEAM_ROOT` so experimental native-launch testing can target a specific Steam install.
- Changed native-engine mod checks, launch preview and launch preflight to use the selected Steam install, clearing stale mod results when the selection changes.
- Changed native launch command generation to fail early with mode-specific guidance when native Steam, Flatpak Steam or `STEAM_ROOT` lacks a detected launch command.
- Moved packaging preparation later in the roadmap so native launcher parity and Steam/Proton reliability stay ahead of installer polish.
- Added a Settings health row for visible NVIDIA PRIME / DRI PRIME environment state.
- Expanded diagnostics with structured PRIME status and safer hybrid-GPU troubleshooting steps.
- Clarified that absent visible PRIME variables do not rule out Steam per-game launch options, and expanded no-process post-handoff guidance for the known NVIDIA PRIME option.
- Changed post-handoff DayZ process detection from a single early check to a 45-second watch window to account for slow Steam/Proton startup.
- Added clearer Linux Mint / Ubuntu development setup instructions to the README.
- Added post-handoff DayZ process checks to external and native launch dialogs.
- Added DayZ process visibility to diagnostics for Steam/Proton troubleshooting.
- Clarified launch dialog wording so successful handoff is not presented as proof that Proton or DayZ fully started.
- Added clearer native, Flatpak and `STEAM_ROOT` Steam readiness messages in Settings health and diagnostics.
- Added platform-detection tests for Steam install readiness and complete-install selection.
- Added structured native-launch failure stages with user-facing recovery guidance.
- Added launch dialog handling for command start failures.
- Added a diagnostics warning when WolfLauncher sees the known problematic NVIDIA PRIME offload environment combination.
- Added an experimental native launch action behind the Mods tab preview, with first real-world native Steam handoff confirmed.
- Added a saved launch-engine setting so the main Launch button can opt into the native experimental engine while keeping the external launcher as default.
- Added native launch preview output for prepared mod symlinks, missing Workshop directories and generated Steam commands.
- Added the first native Python launcher-engine foundation for legacy-compatible mod symlink preparation and Steam launch command generation.
- Added data-aware Server Browser sorting for numeric ports, players, ping, status and freshness columns.
- Added fuller NVIDIA PRIME and Steam launch-option troubleshooting guidance.
- Added Server Browser result-limit controls and clearer matching-vs-cached summary text.
- Added WolfAPI as a discovered-server cache provider, backed by `https://api.drakonwolf.ddns.net/api/servers`.
- Added name-derived Server Browser style filtering for PvE and PvP servers.
- Added Server Browser source filtering, reset controls and cache summary counts.
- Added Server Browser double-click promotion and a copy-host context action.
- Added tests that pin WolfLauncher's command generation to the vendored launcher handoff contract.
- Added PRIME-related environment values to diagnostics output for launch-option troubleshooting.
- Added bounded query-port fallback probing when enriching discovered server rows with uncertain port data.
- Added in-app editing for curated YAML server entries.
- Changed discovered-server enrichment to preserve display names while storing differing live names separately.
- Changed live enrichment to update a discovered server's game port from the queried connect address when available.
- Added Server Browser freshness/identity polish with Last Checked and non-duplicated Live Name display.
- Added SQLite cache schema-version checks and migration scaffolding.
- Changed failed provider refreshes to keep existing cached rows while still pruning stale rows after successful refreshes.
- Restored Server Browser map and version filters as cache-populated dropdowns.
- Reduced routine Server Browser completion popups by reporting successful refresh/enrichment results in the status bar.
- Replaced the separate Diagnostics tab with a Settings tab containing compact health checks.
- Moved discovery provider configuration, API key, refresh limit, endpoint overrides and server-list import into Settings.
- Simplified the Server Browser tab to a single configured-provider **Refresh database** button.
- Changed startup discovery refresh from hard-coded BattleMetrics to opt-in refresh for the selected provider.
- Added quiet rate-limited BattleMetrics startup refresh.
- Added BattleMetrics server discovery as a documented no-key discovery source.
- Added Steam Web API server-list discovery as the preferred HTTPS discovery path.
- Changed provider refreshes to sync discovered rows, clearing stale API-backed cache entries and inserting only new server keys.
- Added live enrichment for visible discovered server cache rows.
- Added an in-app Steam master endpoint override field.
- Added explicit Steam master endpoint-list overrides for discovery testing.
- Added fallback/error reporting for Steam master server discovery DNS failures.
- Added an in-app Steam master refresh button for discovered server candidates.
- Added Steam master server candidate discovery import support.
- Added editable promotion details and right-click copy actions for discovered servers.
- Added promotion from discovered cache rows into the curated YAML server list.
- Added YAML/JSON import for discovered server cache rows, including a sample import file.
- Added a read-only Server Browser tab backed by the SQLite discovered-server cache.
- Started v0.6 SQL foundations with a SQLite discovered-server cache module and tests.
- Added the MIT license for WolfLauncher and third-party notices for vendored code.
- Added `AGENTS.md` as the quick project orientation and coding-agent handoff file.
- Vendored the MIT-licensed `dayz-linux-cli-launcher` under `external/dayz-linux-cli-launcher/`.
- Added the vendored launcher as the final default launcher path fallback.
- Added a standard-library unit test suite for launch command generation, launcher path discovery and YAML server loading.
- Added offline unit tests for server status parsing and `gamedig` failure handling.
- Added offline unit tests for DayZSA mod parsing and local Workshop mod scanning.
- Removed tracked Python bytecode files and added `.gitignore` rules for generated caches.
- Expanded diagnostics and Linux Mint install dependencies for the external launcher tools.
- Reorganized project documentation around the end-of-v0.5.2 working baseline.
- Documented the known Steam launch-option issue with `__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%`.
- Clarified that successful external-launcher exit means handoff to Steam, not proof that DayZ fully started.

## v0.5.2
- Fixed launch output dialog QTextCursor crash on PySide6.
- Hardened launch path to pass the resolved IP address to dayz-launcher.sh.
- Reworded successful launch output so exit code 0 is shown as a successful handoff to Steam instead of an alarming finished message.
- Fixed early selection-change traceback by guarding launch button text updates until the button exists.
- Kept v0.5.1 offline/restart status handling fixes.


## v0.5.0 - Launch integration

- Added guarded launch workflow for selected servers.
- Added DayZ/Workshop preflight checks before launch.
- Added Steam-not-running warning with Launch Anyway / Cancel.
- Added missing-mod warning using the latest mod check for the selected server.
- Added Open Workshop / Launch Anyway / Cancel flow when required mods are missing.
- Added launch output dialog using the external `dayz-launcher.sh` command.
- Added launch command display for debugging and support.
- Kept the external MIT-licensed shell launcher as the launch engine.

## v0.4.2 - Mod management hotfix

- Fixed mod table sorting causing blank/incomplete rows.
- Fixed double-click/right-click Workshop page opening regression.

## v0.4.1 - Mod management polish

- Added double-click mod row to open its Steam Workshop page.
- Added right-click context menu on mods with open/copy actions.
- Added mod filter for All, Missing only, and Installed only.
- Added sortable mods table.
- Added copy Workshop ID, mod name, and Workshop URL actions.
- Added right-click server actions to copy connect address, copy server details, and toggle favourite.
- Missing/installed mod status is easier to scan.
- Kept v0.4 mod detection behaviour unchanged.

## v0.4.0 - Mod management foundation

- Added a dedicated Mods tab.
- Added selected-server mod checking through the DayZ SA Launcher style server API.
- Added local DayZ Workshop mod scanning from `steamapps/workshop/content/221100`.
- Added required-vs-installed mod comparison.
- Added missing mod detection.
- Added Steam Workshop links for required mods.
- Added buttons to open the selected Workshop page or all missing Workshop pages.
- Kept v0.3.1 Steam, DayZ, Workshop, diagnostics, favourites and settings behaviour.

## v0.3.1 - Diagnostics cleanup

- Improved diagnostics wording so optional install types do not appear as hard failures.
- Added last refresh timestamp to the server browser.
- Added subtle ONLINE/OFFLINE colour coding.
- Auto-refresh setting now applies and saves immediately.

## v0.3.0 - Local platform detection

- Added native Steam detection.
- Added Flatpak Steam detection.
- Added DayZ install detection.
- Added DayZ Workshop folder detection.
- Added improved Diagnostics tab.
- Added favourites click-to-toggle.
- Added settings persistence.
- Added last selected server persistence.

## v0.2.1 - Project state files

- Added `CHANGELOG.md`.
- Added `ROADMAP.md`.
- Added `ARCHITECTURE.md`.
- Added `PROJECT_STATE.md`.
- Updated README for handoff and continuation.

## v0.2.0 - Server browser refinement

- Added cleaner server table columns.
- Added saved settings.
- Added saved favourites.
- Added clickable favourites star.
- Added double-click server launch.
- Added auto-refresh setting.
- Added improved diagnostics tab.

## v0.1.x - First working GUI

- Added initial PySide6 GUI.
- Added YAML server configuration.
- Added DNS hostname support.
- Added live server status checks through `gamedig`.
- Added launch bridge to `dayz-launcher.sh`.

## v0.5.1
- Fixed launch integration for DNS-based servers by resolving hostnames before calling `dayz-launcher.sh`.
- Improved offline/restarting server detection so incomplete query responses are not shown as ONLINE.
