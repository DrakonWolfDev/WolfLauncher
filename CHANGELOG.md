# Changelog

## Unreleased
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
