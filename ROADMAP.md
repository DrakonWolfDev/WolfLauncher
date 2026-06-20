# Roadmap

## v0.5.x - Launch polishing and validation

- Test launch flow on Andrew's Linux Mint system.
- Confirm missing-mod guard behaviour with a real missing Workshop item.
- Confirm launcher output dialog captures useful shell launcher messages.
- Continue small hotfixes after real launch testing.
- Investigate optional hybrid-GPU/NVIDIA PRIME diagnostics later.

## v0.6 - Server browser foundation

- Add SQLite cache for discovered servers.
- Keep YAML as curated/import/export format.
- Add search and filtering.
- Add sort by player count, ping, map and version.

## v0.7 - Packaging preparation

- Add Linux Mint/Ubuntu install instructions.
- Explore AppImage.
- Explore `.deb` packaging.
- Add desktop file and icon.

## v0.8 - Native launcher engine investigation

- Document the current handoff contract with `dayz-linux-cli-launcher`.
- Build an internal launcher-engine module behind the existing GUI workflow.
- Reproduce the current external launcher command behaviour with test coverage.
- Investigate direct Steam/Proton launch handling for native and Flatpak Steam.
- Keep the external launcher path as a fallback until native launch parity is proven.

## v0.9 - Native launcher engine replacement

- Move server launch flow from shell-script handoff to the internal engine.
- Improve structured launch errors and user-facing diagnostics.
- Add regression tests for launch command generation, host resolution and Steam mode detection.
- Remove the external launcher dependency once real-world launch testing is stable.

## Later

- Steam Deck-focused layout.
- Community-maintained server lists.
- Windows support investigation.
