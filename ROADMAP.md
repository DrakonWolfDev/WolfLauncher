# WolfLauncher Roadmap

## Linux installer coverage

The newer user-local installer works across Ubuntu 22.04/24.04/26.04,
Debian 12+, Linux Mint 21+, Pop!_OS, Fedora 40+, Nobara, Arch Linux,
Manjaro/EndeavourOS, openSUSE Tumbleweed/Leap, NixOS, Alpine 3.20+
(non-musl environment) and SteamOS 3/HoloISO. This distro coverage is confirmed
by the maintainer. See [Installing on Linux](docs/INSTALL_LINUX.md).

The distro-neutral installer is available now. Future distribution work covers
additional package formats and desktop integration.

Updated: 2026-08-05

This file records milestones, not individual engineering jobs. The single
ordered implementation backlog is `PRODUCTION_READINESS_REVIEW.md`.

## Completed foundations

### v0.5.2–v0.7

- Established the guarded external-launch workflow, diagnostics, settings
  health, curated server management and SQLite public-server browser.
- Added native/Flatpak Steam and secondary-library detection plus Linux desktop
  troubleshooting. Flatpak was later retired from the current compatibility
  contract after packaged validation failed.

### v0.8

- Validated native Python launch parity and made it the fresh-settings default.
- Retained the vendored external shell launcher as a visible fallback.
- Added tested native/Flatpak launch selection, mod-link preparation, structured
  failures and parity reports.

### v0.8.x discovery and Workshop work

- Adopted WolfAPI v1 as the fresh-install default with bounded pagination,
  local-first search, exact resolution, stable IDs, aliases and offline cache.
- Added explicit Steam-managed Workshop subscription/update resolution through
  an isolated helper, including progress, stall handling and final readiness
  verification.
- Added direct inspect/resolve/launch flow for discovered servers without
  requiring curated promotion.

## v0.9 — production hardening

Status: in progress.

The GUI hierarchy, native launch flow, Workshop journey and discovery contract
are functionally established. Complete every P0 item in
`PRODUCTION_READINESS_REVIEW.md`, then execute
`docs/RELEASE_CHECKLIST.md` against the packaged release candidate.

Completion means:

- version and truth documents agree;
- mutable user data works with application resources mounted read-only;
- persistence and shutdown are recoverable and race-safe;
- credentials and support reports have an explicit secure policy;
- a focused release-readiness audit confirms that the source tree, build
  inputs, generated artifacts and user-facing workflow remain purposeful,
  documented and free of obsolete or misleading paths;
- a reproducible Linux artifact can install, upgrade and uninstall cleanly;
- CI and the supported native-Steam desktop matrix pass for that artifact, or
  each exception has an explicit release waiver.

The experimental Windows lane now has validated unmodded and modded DayZ
handoffs, confirmed Steamworks query/subscription lifecycle, a reproducible
portable ZIP, a per-user installer with data-preserving uninstall and a Windows
CI packaging lane. Before Windows becomes a supported target, add signing and
update behavior, then exercise the release artifact on the intended desktop
matrix. These gates do not delay the Linux v1.0 boundary.

The approved delivery direction is documented in `docs/UPDATE_STRATEGY.md`:
signed prompted installer updates on Windows and signed repository-managed
updates on Linux, sharing one release-channel manifest and policy.

## v1.0 — supported native release

- Publish the first supported production artifact after all v0.9 gates pass.
- Keep the external fallback for the initial production release unless evidence
  supports a separate, deliberate removal decision.
- Publish checksums, installation/upgrade/uninstall instructions and a support
  policy.

## Post-v1 priorities

- Gradually extract feature ownership from `app.py` without a wholesale GUI
  rewrite.
- Add a Mods-screen sort selector: keep **Action needed** as the default,
  and offer the selected server's reported load order and alphabetical name
  order. Make the load-order view visibly numbered so it is clear that it
  reflects the server's DayZ `A2S_RULES` manifest.
- Add safe server deep links that resolve a stable server ID or explicit
  endpoint into WolfLauncher's normal inspect, mod-validation and guarded
  launch journey; links must never inject launch parameters or mod lists.
- Conduct a deliberate calmness pass over every visible action, option and
  message: retain only what supports choosing, preparing or joining a server;
  keep meaningful uncertainty honest; and move secondary detail behind the
  established compact disclosures rather than removing capability.
- Continue the P1/P2 quality, accessibility, network, logging, cache and typing
  work in the production review.
- Extend the initial signed update channels only from release evidence, and
  define bounded data/log retention.
- Consider AppImage, Steam Deck layout and community submissions after the
  first supported Linux format is stable.
- Promote Windows from experimental to supported only after its handoff,
  Steamworks, packaging, signing and update gates pass.
- Validate the Linux DayZ Experimental handoff before enabling its native
  launcher. The Windows Experimental profile is intentionally distinct from
  Stable: it uses Steam app ID 1024020, local mod sources and BattlEye's direct
  launcher path. Experimental's explicitly confirmed install/update actions
  resolve its required items through the Stable DayZ Workshop context.
- Evolve **Editor / Local Tools** for advanced mod development in stages:
  v1 saved local client-mod profiles, offline DayZ Editor and joining existing
  LAN/test servers; v2 explicitly configured local dedicated-server start/stop
  and external-editor project opening; v3 bounded server/client log viewing and
  export. This remains local development tooling, not public-server hosting.

## Known external issue

Keep the NVIDIA PRIME/Steam launch-option note as an advisory Settings FAQ item.
Investigate only from reproducible evidence; do not inspect, modify or default
the known problematic option.
