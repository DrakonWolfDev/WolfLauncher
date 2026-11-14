# WolfLauncher 0.9.4b — 14 November 2026

Release preparation was explicitly requested by the maintainer after the fresh
npm-patched Linux installer passed hands-on testing again. Earlier Windows
confirmation and native package evidence remain recorded separately in
[the installer rebuild record](INSTALLER_REBUILD_NPM_FIX_2026-11-14.md).

The public version advances from 0.9.3b (private test version 0.9.3.5b) to
**0.9.4b**. Windows numeric metadata becomes **0.9.4.0**. This remains a beta
prerelease under the existing unsigned pre-1.0 distribution policy.

## Changes since 0.9.3b

- Share compact server links through wolflauncher.co.uk, with address review,
  browser installation fallback and existing launch/Workshop confirmations.
- Choose existing DayZ profiles and use matching player-name controls on Windows
  and Linux. Profile discovery leaves the original game files unchanged.
- Improve LAN connection setup with separate game/query ports and visible
  server mod requirements.
- Await Steam download completion and retain manual requirements in mixed
  Workshop manifests. Explain unavailable Workshop items and recovery steps.
- Keep installed Workshop details stable during background server checks.
- Improve browser responsiveness, cache reuse and background work scheduling;
  show measured queue counts and preserve honest stale/offline states.
- Compare advertised mod hashes with local PBO evidence as advisory results.
- Isolate AppImage environment paths during external handoffs, add read-only
  Linux memory-map guidance, and record package source/input provenance.
- Patch the bundled XML parser while retaining GameDig 5.3.3; verify bundled
  DayZ query compatibility on Windows and Linux.

## Validation and publication boundaries

The maintainer reports that the new Linux installer passes again and explicitly
requests the main merge and release. Previous Windows confirmation and automated
install/reinstall/start/remove, checksum, inventory and clean-source provenance
checks are recorded in the linked rebuild evidence. These reports do not imply
that every older live Steam/DayZ, perspective-tag, accessibility or long-run
investigation has been completed.

Final source regression, lint/formatting, core type checks, compilation,
whitespace and locked dependency audit are run before the release push. The
existing tag workflow builds the complete Windows/Linux set from one clean
commit, checks checksums and matching provenance before publication, and requests
the shared website manifest update only after publishing all required platforms.
Terminal CI, asset and live download-feed evidence will be recorded in the
next-session handoff after publication. This document alone does not establish
that publication has completed.
