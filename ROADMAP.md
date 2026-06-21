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

- Improve hybrid-GPU/NVIDIA PRIME diagnostics; initial structured diagnostics and Settings health visibility are in place.
- Add safer user-facing guidance for Steam launch options; initial diagnostics guidance is in place.
- Expand native Steam and Flatpak Steam checks.
- Continue improving Proton/Steam handoff failure states; launch dialogs now clarify the handoff boundary and probe for known DayZ processes after successful command exit.
- Add Linux Mint/Ubuntu install instructions; development setup notes are in the README, packaged install notes still need future work.
- Start carving native Python equivalents from the vendored legacy launcher behavior. Experimental native Steam handoff now has an initial native-Steam success and an opt-in launch-engine setting, while Flatpak and broader server parity still need testing.

## v0.8 - Packaging preparation

- Explore AppImage.
- Explore `.deb` packaging.
- Add desktop file and icon.
- Document user config and data directories.

## v0.9 - Native launcher engine investigation

- Document the current handoff contract with `dayz-linux-cli-launcher`.
- Build an internal launcher-engine module behind the existing GUI workflow. Initial foundation is in place for compact mod symlink names, mod link preparation, launch previews, experimental native handoff and Steam command generation.
- Reproduce the current external launcher command behaviour with test coverage.
- Investigate direct Steam/Proton launch handling for native and Flatpak Steam.
- Investigate Steam Workshop mod installation routes, with Steam-native subscription/download flows preferred over custom file management.
- Keep the external launcher path as a fallback until native launch parity is proven.

## v1.0 - Native launcher engine replacement

- Move server launch flow from shell-script handoff to the internal engine.
- Improve structured launch errors and user-facing diagnostics.
- Add regression tests for launch command generation, host resolution and Steam mode detection.
- Remove the external launcher dependency once real-world launch testing is stable.

## Later

- Steam Deck-focused layout.
- Community-maintained server lists.
- Optional guided missing-mod installation flow after explicit user confirmation.
- Windows support investigation.
