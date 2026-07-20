# WolfLauncher Roadmap

Updated: 2026-07-20

This file records milestones, not individual engineering jobs. The single
ordered implementation backlog is `PRODUCTION_READINESS_REVIEW.md`.

## Completed foundations

### v0.5.2–v0.7

- Established the guarded external-launch workflow, diagnostics, settings
  health, curated server management and SQLite public-server browser.
- Added native/Flatpak Steam and secondary-library detection plus Linux desktop
  troubleshooting.

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
- a reproducible Linux artifact can install, upgrade and uninstall cleanly;
- CI and the supported native/Flatpak Steam desktop matrix pass for that
  artifact, or each exception has an explicit release waiver.

An experimental Windows source runtime now detects the local Steam/DayZ install
and prepares native commands without Linux links or shell tools. Before Windows
becomes a supported target, validate unmodded and modded DayZ handoffs,
Steamworks query/subscription lifecycle, then add a reproducible signed package
and Windows CI lane. These gates do not delay the Linux v1.0 boundary.

## v1.0 — supported native release

- Publish the first supported production artifact after all v0.9 gates pass.
- Keep the external fallback for the initial production release unless evidence
  supports a separate, deliberate removal decision.
- Publish checksums, installation/upgrade/uninstall instructions and a support
  policy.

## Post-v1 priorities

- Gradually extract feature ownership from `app.py` without a wholesale GUI
  rewrite.
- Continue the P1/P2 quality, accessibility, network, logging, cache and typing
  work in the production review.
- Define a signed update strategy and bounded data/log retention.
- Consider AppImage, Steam Deck layout and community submissions after the
  first supported Linux format is stable.
- Promote Windows from experimental to supported only after its handoff,
  Steamworks, packaging, signing and update gates pass.

## Known external investigation

Continue NVIDIA PRIME/Steam launch-option investigation only from reproducible
evidence. Do not bake the known problematic PRIME option into defaults.
