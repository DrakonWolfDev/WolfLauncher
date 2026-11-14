# GameDig XML dependency audit — 14 November 2026

Follow-up: both private installers have now been rebuilt with this fix and
verified, superseding the unchanged-installer status recorded below. See
[fresh installer evidence](INSTALLER_REBUILD_NPM_FIX_2026-11-14.md).

The fresh npm audit reproduced two low-severity findings from one advisory:
[GHSA-474x-hrwr-fgx4](https://github.com/advisories/GHSA-474x-hrwr-fgx4).
GameDig 5.3.3 pins fast-xml-parser 5.8.0. Malformed XML can cause quadratic
CPU consumption when the non-default `stopNodes` option is enabled. The advisory
rates availability impact at 3.7, with no confidentiality/integrity impact;
5.12.0 is the patched version. npm suggested downgrading GameDig to 5.2.0.

## Reachability and fix

WolfLauncher invokes GameDig with `--type dayz` in `wolflauncher/status.py`.
GameDig's `dayz` protocol extends `valve` and parses binary A2S packets, without
XML parsing. The installed GameDig source imports fast-xml-parser only in its
Farming Simulator protocol, which uses `ignoreAttributes: false` and does not
enable `stopNodes`. No affected path was found in the DayZ query implementation.
This is source inspection plus local fixture evidence, not a live server test.

The npm manifest now overrides only GameDig's fast-xml-parser to exactly 5.12.0,
retaining GameDig 5.3.3. The regenerated lockfile updates the parser's required
transitive dependencies; unrelated runtime versions remain pinned. This avoids
the audit tool's suggested GameDig downgrade.

## Verification

- Clean `npm ci --ignore-scripts --prefix packaging/npm` succeeded.
- Fresh `npm audit --omit=dev --json --prefix packaging/npm`: **zero findings**.
- `npm ls` confirms GameDig 5.3.3 and overridden fast-xml-parser 5.12.0.
- `node --test scripts/test-gamedig-runtime.mjs`: **3 tests passed** on Windows:
  - Hostile stop-node XML with 100,000 fragments is rejected in a child process
    with a three-second limit.
  - GameDig's Farming Simulator consumer preserves attributes, entities and
    player parsing with the patched dependency.
  - The actual GameDig CLI queries a loopback UDP DayZ fixture and decodes server
    info, players/rules responses, first-person mode and queue count.
- Windows packaging CI now runs these checks after runtime installation/build.
- Workflow Ruff formatting/lint, core mypy and compilation passed in the existing
  Mint Python environment. Full regression result is recorded in the handoff.

Initial regression attempts could not use the checkout's broken virtual
environment; WSL system Python lacked project dependencies. The working existing
environment was located at `/opt/wolflauncher-mint-venv`; a redundant isolated
dependency-install attempt was stopped. Those setup failures are not application
regressions.

Existing private installers retain their original dependencies. They have not
been rebuilt or replaced. Final release packaging must consume this updated
manifest and lockfile. No live Steam/DayZ action, version bump, main merge, tag
or publication was performed.
