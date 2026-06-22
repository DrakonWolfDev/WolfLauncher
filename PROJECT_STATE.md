# WolfLauncher Project State

Current snapshot: v0.7 health checks and Linux polish complete.

WolfLauncher is a Linux-first DayZ launcher GUI built with Python and PySide6. It currently wraps the existing MIT-licensed `dayz-linux-cli-launcher` style shell launcher instead of replacing it.

The upstream shell launcher is now vendored under `external/dayz-linux-cli-launcher/` so the current working behavior can be inspected and replaced gradually.

## Current status

The v0.7 launch, status, settings health checks, diagnostics, mod-checking, discovered-server browser and Linux handoff polish are considered functional. The application can be used as the working project base for the native-launch parity improvement cycle.

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
- WolfAPI discovered-server cache provider using `https://api.drakonwolf.ddns.net/api/servers`.
- Steam Web API server-list discovery with user-supplied API key.
- BattleMetrics server discovery.
- Optional quiet rate-limited startup refresh for the selected discovery provider, throttled to once per day.
- Enrichment of visible discovered servers with live status data.
- Live enrichment preserves cached display names, stores differing live server names separately and updates game ports from queried connect addresses when available.
- Live enrichment probes a bounded set of likely query ports when discovered rows have uncertain port data.
- Failed provider refreshes preserve existing discovered-server cache rows.
- Server Browser map and version filters populated from cached/enriched values.
- Server Browser source/style filtering, result-limit controls, reset controls and cache summary counts.
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
- Guarded launch workflow through the external `dayz-launcher.sh` script.
- Launch commands pass the resolved server IP to the external launcher when available.
- Missing-mod warning with Open Workshop / Launch Anyway / Cancel.
- Steam-not-running warning.
- Launch output dialog with generated command and launcher output.
- External launch output can be copied from the launch dialog for timestamped support reports.
- Successful external-launcher exit code is presented as a handoff to Steam.
- Launch dialogs clarify that a successful handoff does not prove Proton initialized or DayZ reached the menu.
- Launch dialogs watch for known DayZ processes for up to 45 seconds after handoff, because Steam/Proton can take tens of seconds before DayZ appears.
- Experimental native launch parity report from the Mods tab, with generated-at metadata and a copyable validation checklist comparing the external launcher handoff with the native command, selected Steam install, resolved connect target, required mod IDs, prepared mod links and missing Workshop directories.
- Native launch failures include copyable parity-report details when a cached mod check is available, so failed launches and preview reports can be compared.
- Native parity reports show created versus reused mod symlink counts, and existing `@mod` symlinks are reused only when they point to the expected Workshop directory.
- The native experimental engine does not offer "Launch anyway" when required Workshop directories are missing, because it cannot build a valid native mod command until the missing mods are installed.
- Experimental native Steam handoff from the preview dialog, with real-world native Steam and Flatpak Steam launch success confirmed. The external launcher remains the default launch path while parity testing continues.
- Saved launch-engine setting in Settings. `External launcher` remains the default, while `Native experimental` routes the main Launch button through the Python native engine.
- Saved native Steam install selection in Settings, with Auto, Native Steam, Flatpak Steam and `STEAM_ROOT` options so parity testing can target a specific detected install.
- Settings and diagnostics label this as the Steam install mode so it is not confused with the external/native launch-engine selector.
- Structured native-launch failure stages with user-facing recovery guidance for Steam detection, library detection, DNS and mod setup failures.
- README Linux Mint / Ubuntu development setup instructions with dependency notes and Settings health fallback guidance.

Planned WolfAPI follow-up:

- `ROADMAP.md` tracks a v0.8.x WolfAPI discovery-quality and submission side-track.
- The intent is to combine Steam's capped list with slow BattleMetrics ingestion, freshness/stale tracking, roughly 30-day stale retention, stronger retention for user-submitted rows, and a future in-app "Add your server to WolfLauncher" submission flow.
- Current WolfLauncher behavior remains read-only for remote WolfAPI data; users can already promote discovered rows or add their own servers to the local curated YAML list.

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
- `wolflauncher/platform_detection.py` - Steam, DayZ and Workshop detection.
- `wolflauncher/launcher.py` - external launcher command building.
- `wolflauncher/native_launcher.py` - native Python launch-engine foundation for tested Steam command and mod-link preparation.
- `wolflauncher/server_cache.py` - SQLite cache for discovered public servers.
- `wolflauncher/settings.py` - user settings and favourites.
- `wolflauncher/config.py` - YAML server loading and default launcher path candidates.
- `tests/` - standard-library unit tests for launcher commands, vendored launcher handoff contract, path discovery, YAML loading, status parsing and mod parsing.
- `example.servers.yaml` - tracked curated server template.
- `servers.yaml` - local ignored curated server registry.
- `external/dayz-linux-cli-launcher/dayz-launcher.sh` - vendored MIT legacy launch engine.
- `LICENSE` - WolfLauncher MIT license.
- `THIRD_PARTY_NOTICES.md` - third-party license notices.
- `CHANGELOG.md` - version history.
- `ROADMAP.md` - planned milestones.
- `ARCHITECTURE.md` - architecture and design notes.

## Important design decisions

- YAML is the curated server/source-of-truth format for early versions.
- SQLite is now introduced as the discovered public server browser cache.
- v0.6 provides a standalone SQLite server cache foundation and read-only browser tab for discovered public servers.
- Provider refreshes sync their discovered rows after successful responses by removing stale provider-backed entries and adding only new cache keys; failed refreshes preserve existing cache rows. Curated YAML remains the place for saved servers.
- JSON is used for user settings and favourites under `~/.config/wolflauncher`.
- The external shell launcher remains the launch engine for now.
- The vendored shell launcher is the reference contract for future native launcher work.
- Native launcher replacement work has started behind a separate Python interface, with tests covering compact mod symlink names, relative symlink creation, missing-mod preview handling, Steam launch command generation and external-vs-native parity report formatting.
- The native engine has confirmed real-world native Steam and Flatpak Steam handoff success, including starting Steam when it was not already running and a Flatpak DayZ launch reaching process detection in roughly 10 seconds.
- The main Launch button can opt into the native engine through Settings, but this should remain experimental until more servers and missing-mod cases are tested.
- When the native engine is selected, mod checks, native launch preview and launch preflight use the selected Steam install rather than always using automatic best-install detection.
- Auto Steam selection is reported from the same detection snapshot as the candidate list so users can see why native or Flatpak Steam was chosen.
- Native launch command generation now fails before handoff when the selected Steam mode lacks a detected command, with mode-specific guidance for native Steam, Flatpak Steam and `STEAM_ROOT`.
- `STEAM_ROOT` detection reuses the native Steam command and running state when available, while Settings health warns if the selected library is complete but no launchable Steam command is detected.
- Mod management is read-only and advisory: it detects installed/missing mods and opens Workshop pages, but does not attempt automatic downloads. Future mod installation work should investigate Steam-native subscription/download routes first and require explicit user confirmation.
- Launch remains guarded: WolfLauncher warns about missing mods and Steam state before calling the external launcher.
- Hostnames are resolved before launch where possible to mirror the original terminal menu behaviour and avoid DayZSA API issues with DNS-based servers.
- Python bytecode caches are ignored and should not be tracked as source.
- WolfLauncher is MIT licensed; vendored third-party MIT notices are preserved separately.

## Next step

Use v0.8 as the next active development target:

- Broaden native and Flatpak Steam parity testing across more servers, Steam install modes and missing-mod cases.
- Keep the external launcher as the default launch path until native parity is proven with broader real-world testing.
- Continue refining hybrid-GPU/NVIDIA PRIME guidance after reproducible data is available.
- Keep refining Proton/Steam handoff failure states from real-world failures.
- Continue refining Linux Mint/Ubuntu install instructions toward packaged installs.
- Defer packaging work until late pre-1.0 polish; launcher parity and Steam/Proton reliability should come first.
- Continue improving curated server organisation beyond basic edit/remove flows.
- Keep local `servers.yaml` for curated, personal and import/export server lists, seeded from tracked `example.servers.yaml` when missing.
- Continue carving native Python equivalents from the vendored launcher's behavior while expanding the new native launcher engine behind WolfLauncher interfaces.
- Keep mod installation as a future investigated design, not part of the current read-only mod-management contract.
- Keep the NVIDIA PRIME Steam launch-option issue visible as the only known bug until it is reproduced and diagnosed.
