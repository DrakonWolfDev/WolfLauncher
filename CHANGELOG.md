# Changelog

## Unreleased
- Added Steam Web API server-list discovery as the preferred HTTPS discovery path.
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
