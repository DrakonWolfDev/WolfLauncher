# Mint installer rebuild and quick release readiness — 14 November 2026

## Result

The requested private Linux Mint 22.3 amd64 Debian installer was rebuilt.
Version stays **0.9.3.5b**. It includes the Player name / Set name /
Existing profile… Settings row and the earlier Servers-toolbar server-link move.

- Artifact: [Mint test installer](../dist/wolflauncher_0.9.3.5b_mint22-profile-test-20261114_amd64.deb)
- SHA256: `5acda4f331e825d86d538264c8ea570dd8dedd00b7fbc5878481af231bd007b7`
- Adjacent `.sha256` and `.provenance.json` sidecars retained.
- Source: `980a6328189f592dae5846c5410fab0d0698349b` plus the existing
  uncommitted toolbar move. Provenance honestly records a dirty snapshot.
- Python 3.12 build, dependency range >=3.12 and <3.13; libegl1 required.
- Built in a temporary native Linux checkout; previous installers preserved.

## Verification

- Artifact checksum passed.
- Full independently extracted payload and Debian control/hook inventory matched
  the recorded provenance, including file modes.
- Unpatched packaged entry-point startup and shutdown passed with temporary
  config/data/cache/runtime directories and local IPC access. The restricted
  sandbox attempt could not complete; the isolated unrestricted rerun exited 0.
- An isolated extracted-package UI smoke confirmed the visible single name row,
  both directions of Servers/Settings name synchronisation, saving by button and
  Enter, delegation to the existing profile picker, and the server-link button
  on Servers rather than Settings. Screenshot visually inspected.
- Full local source regression suite from this UI change: **1,038 tests, OK,
  7 skipped**. Workflow Ruff formatting/lint, core mypy, compilation and whitespace
  checks pass.
- Current Python locked release dependency audit: no known vulnerabilities.
- npm audit: two low-severity package findings, one underlying
  [fast-xml-parser advisory](https://github.com/advisories/GHSA-474x-hrwr-fgx4)
  propagated through GameDig. No moderate/high/critical findings. Pinned
  dependencies were preserved; npm's suggested GameDig downgrade was not applied.
- [Tests CI for 980a632](https://github.com/DrakonWolfDev/WolfLauncher/actions/runs/43608855175):
  all eight jobs passed, including Windows package, Ubuntu 22/24 packages,
  RPM/AppImage, Python 3.10/3.11/3.12 unit suites and quality.
- [Installer CI for 980a632](https://github.com/DrakonWolfDev/WolfLauncher/actions/runs/43608855189):
  branch checks passed. Tag-only release builds/publication were not run.

## Release readiness

**Ready for private installer testing; not yet a fully verified public release.**

Before release:

1. Commit the already-authorised toolbar changes and intended release records,
   then obtain CI/build evidence for that exact clean source. Current Windows
   CI packages contain the committed name row, but not the uncommitted toolbar move.
2. Confirm the release version and notes, then build the complete Windows/Linux
   release set from the same final clean tagged commit. The current dated,
   same-version private installer is not a public release artifact.
3. Deploy and verify the matching website HTTPS server-link fallback.
   A read-only request to `https://wolf-forge.co.uk/join/` returned **HTTP 404**
   in this check. No deployment was attempted.
4. Confirm native installer install/upgrade/remove behaviour and live Steam/DayZ
   profile reuse, an actual server join, and browser-to-protocol handoff on the
   intended Windows/Linux release packages. Existing records do not establish
   all these checks for the final source.
5. Resolve or explicitly assess the low-severity npm advisory before publication.

Older investigation/evidence gaps remain recorded in NEXT_SESSION_HANDOFF:
verified camera settings for REL-02, the exact remembered API/PHP alert identity,
and broader changed-content/bulk Workshop, accessibility/older-distro and long-run
evidence. These are not newly reproduced failures. Optional LAN discovery,
localisation and signed automatic updates are backlog decisions; unsigned
packages are already an explicit pre-1.0 project policy, not a new release blocker.

No installation on the host, version bump, main merge, tag, publication, public
download-link change, Windows rebuild or API/website deployment was performed.
