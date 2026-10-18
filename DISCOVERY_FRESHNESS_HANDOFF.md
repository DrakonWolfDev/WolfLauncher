# WolfAPI discovery handoff

## Windows HTTPS validation — 2026-10-17

WolfAPI's current public certificate and full server chain validate normally.
An affected Windows 10 installation contained the obsolete cross-signed
ISRG Root X2 certificate (SHA-1 thumbprint
`151682F5218C0A511C28F4060A73B9CA78CE9A53`, expired 2025-09-15).
Adding that public certificate to an isolated Python default SSL context
reproduced `CERTIFICATE_VERIFY_FAILED: certificate has expired`; a native
Windows truststore context with the same certificate validated successfully.

Launcher now uses Windows native verified chain building for provider HTTP
requests. Users need no certificate-store modifications. This does not permit
expired server certificates or bypass trust/hostname checks. Linux keeps its
existing system-trust backend. See `ARCHITECTURE.md` for implementation details.

No API deployment, endpoint/schema, identity, freshness, cache or rollout-default
change is required. This source fix needs a new published Launcher build before
downloaders receive it; GitHub's existing 0.9.0b2 installer is unchanged.
API-side record: `../WolfAPI/DISCOVERY_FRESHNESS_CONTRACT.md`.

Initial TLS validation on the Windows development machine (the later
[CI repair record](docs/CI_VALIDATION.md) supersedes the test/format limitations):

- All 23 focused TLS, HTTP, diagnostics and startup tests passed. Offline TLS
  tests prove that adding an expired intermediate changes legacy validation
  from success to the exact expiry error while native validation still succeeds.
- Live liveness and a one-row discovery request passed through the provider
  helper with the expired public ISRG Root X2 certificate loaded only in memory.
- Full UTF-8 discovery ran 768 tests: 700 passed, 55 skipped, 13 failed. An
  unchanged HEAD snapshot ran 760 tests with the exact same 13 failing test IDs
  (Linux shell installers, Windows SQLite cleanup and newline rollback checks).
  These failures predate this transport change; the full Windows suite is not green.
- Repository-wide lint and changed-file formatting passed. Repository-wide
  formatting still flags six unchanged files. Release dependency declarations
  and the hash-pinned truststore runtime were checked.

Build verification must use a clean terminal PATH: the initial tool-enriched
Codex environment caused PyInstaller to pick up Poppler's incompatible ICU DLL
and fail importing QtCore. That verification artifact must not be distributed.

The clean-PATH Windows PyInstaller build completed successfully. Its offscreen
startup smoke test exited 0 using disposable settings and initialized the native
TLS context. Archive inspection confirmed truststore._windows is bundled and
its MIT license is present. Existing published installers were not overwritten.


## Perspective filter ? 2026-10-18

The server browser advanced filters now offer Any perspective, First-person only,
Third-person enabled, and Unknown perspective. Perspective is parsed from Steam /
WolfAPI `gametype` keywords and local GameDig tags. `no3rd` means first-person only;
a recognizable DayZ keyword response without it means third-person enabled (both
views). Missing tags or classification-only values such as `mod` remain unknown.
Server names are not used as evidence. The selected-server diagnostics and copied
details include the advertised perspective.

Cache schema 9 adds the perspective field; existing rows migrate to unknown until
refreshed. No WolfAPI deployment is required. Filtering applies to the downloaded
local directory, like the existing modded filter. A new launcher build is required
for users to receive this change.

Validation: 193 focused discovery, cache, status, enrichment, perspective, browser
controller, presenter, table, and combined browser integration tests passed in the
repository virtual environment.


## Browser filter presentation ? 2026-10-18

Browser filtering now lives in a persistent Filters / Server side panel. Everyday
filters are visible first; game version, source and listing warning controls are
under More filters in that panel. Search and sort stay above the results. Active
filters appear above the list as removable links with Edit filters and Clear.
Selecting a different server opens Server; refreshing the same selection respects
the user's chosen tab. Technical server diagnostics and validation details are
collapsed under Details, leaving more room for the map atmosphere.

Advanced tools retain result limit, detailed columns, and Refresh server list.
The browser no longer uses a scroll wrapper around the whole workspace; the
results table and each side-panel page handle their own overflow.

Validation: 201 focused tests passed, including offscreen Qt checks for the panel,
selection changes, filter removal/reset, browser integration and startup. Changed
Python files pass lint and formatting checks. No installer was built or published.

Game version, source, and Hide listing data warnings have since moved back to
Advanced tools at user request; the empty More filters disclosure was removed.


## npm dependency audit ? 2026-10-18

Investigated GHSA-ch52-4w7c-c8xp (CVE-2026-93748), reported against
http-cache-semantics <=4.2.0 through GameDig -> got -> cacheable-request.
The advisory concerns cross-user disclosure through shared HTTP caches. The
launcher uses GameDig's DayZ/Valve UDP queries; GameDig's HTTP client also has no
cache enabled by default. No reachable instance of that shared-cache use was
identified in the launcher path inspected.

npm's dry run proposed only http-cache-semantics 4.2.0 -> 4.3.0. Applied that
compatible transitive update in packaging/npm/package-lock.json; GameDig remains
pinned at 5.3.3. A clean npm ci with scripts disabled installed 61 packages,
audited 62, and reported zero vulnerabilities. The separate event-to-promise
maintenance/deprecation warning remains.

Validation: 37 status, enrichment and packaging tests passed, GameDig's actual
Node runtime imports successfully, and a private/no-store response is rejected
by the cache storage policy. cacheable-request checks storable() before storage;
this is not a full advisory exploit regression test. No live-server query or
installer build was performed. Existing published installers are unchanged.
