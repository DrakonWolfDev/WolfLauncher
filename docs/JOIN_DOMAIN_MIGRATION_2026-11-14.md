# wolflauncher.co.uk migration — 14 November 2026

Both implementation parts are complete and pushed.

- Launcher source: `4815172d31e254f8d199b70c63a8966c4c74beeb` on
  `dev/release-preparation`.
- Website source: `6f4716ff11d31bbfb67499dfb51020bc927024ae` on website `main`.
- Production: **https://wolflauncher.co.uk/join/**. The maintainer confirmed
  Coolify automatically deploys website main. Deployment was verified after push.

## Behaviour

Copied launcher HTTPS links now use wolflauncher.co.uk. The launcher's About
website and View Update destinations also use the new domain. Input still accepts
the previous exact wolf-forge.co.uk origin. Strict parsing, endpoint identity,
edition/library boundaries, IPC and launch/Workshop confirmations remain intact.

The standalone website serves both /join and /join/. Its review page shows the
address and separate game/query ports, offers a user-clicked launcher action,
links to the existing homepage downloads and provides a manual copy fallback.
Invalid or unsupported links cannot enable launcher opening. There is no automatic
protocol opening, download, server lookup or inserted HTML from query values.
No-JavaScript installation guidance, no-referrer policy and noindex are included.
Manual opening instructions now refer to the Servers tab.

The website remains on its existing Docker/Coolify hosting and shared release
feed. The old Wolf Forge site was not changed. Legacy-origin input compatibility
does not imply that the old site's missing /join/ route has been restored.

## Verification

- Launcher: **1,038 tests, OK / 7 skipped**, plus Ruff formatting/lint, core mypy,
  compilation and whitespace checks.
- Website: **58 tests passed**, including shared parser vectors, valid/invalid
  page states, clipboard denial fallback, public routes and module MIME types.
- Launcher and website vectors are byte-identical: 5 valid / 40 invalid cases,
  including old-domain compatibility and new-domain authority/path attacks.
- Docker build passed. The production image passed /health, /join, /join/ and
  asset/MIME checks using loopback inside the container.
- Headless Chrome desktop/mobile and invalid-link checks passed; screenshots
  were visually inspected. Opera connector was unavailable, so isolated Chrome
  profiles were used.
- Live /join and /join/ return 200. Page HTML and all three join assets match
  the committed source byte-for-byte, with expected MIME/referrer headers.
  [Recorded path/hash evidence](evidence/2026-11-14-join-live-verification.json).
- An isolated browser verified that the deployed page runs its modules, displays
  the supplied target and enables the expected wolflauncher:// protocol link.
- [Migration CI](https://github.com/DrakonWolfDev/WolfLauncher/actions/runs/43610250906)
  was still running at the final check; the branch
  [Installer checks](https://github.com/DrakonWolfDev/WolfLauncher/actions/runs/43610251026)
  passed. See GitHub for terminal CI status. Local evidence above uses the exact
  integrated launcher code.

## Matching private Mint installer

[Download the refreshed Mint installer](../dist/wolflauncher_0.9.3.5b_mint22-join-test-20261114_amd64.deb)

- Version stays **0.9.3.5b**; this is a private test build.
- Built from clean commit `4815172`; provenance records `dirty: false`.
- SHA256: `aed1ad405e7a2b26c9585347ec57284d4a4b355cfc537218a93a71cea868aa2a`.
- Adjacent checksum/provenance sidecars retained.
- Checksum and independent complete extracted payload/control inventory pass,
  including the expected-commit and require-clean provenance gates.
- Extracted UI smoke verifies new-domain link generation, old-domain input,
  the new View Update destination, shared name row/synchronisation/save actions,
  existing-profile delegation and the moved Servers link action.
- Unpatched packaged entry-point startup/shutdown passes with isolated settings
  and runtime directories. Real user settings/profile files were not changed.
- Earlier private installers and Windows artifacts are preserved. Windows was
  not rebuilt locally for this follow-up. Python 3.12 and libegl1 are required.

## Remaining release evidence

The missing join-page deployment and uncommitted toolbar blockers from the earlier
readiness review are resolved. Final matching Windows/Linux release packages,
current terminal native CI, native install/upgrade/remove checks, real browser
protocol-handler prompts and Steam/DayZ profile reuse/server joining still need
release-time confirmation. No real game or Workshop action was performed here.

The earlier Python audit was clear. Locked npm dependencies still carry the two
low-severity package findings from one XML-parser advisory; no dependency pins
were silently changed. Older REL-02/API-01 and broader manual-evidence notes remain
in NEXT_SESSION_HANDOFF and are separate from these completed changes.

No version bump, main merge in the launcher repository, desktop release/tag,
public installer upload, public download-manifest change or WolfAPI deployment.
Only the requested website change was deployed publicly.
