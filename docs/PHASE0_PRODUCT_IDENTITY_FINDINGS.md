# Phase 0: can implementation proceed without changing WolfAPI?

Observed: 15 September 2026, approximately 16:19–16:25 UTC.

## Decision

**Yes: proceed with launcher implementation using the existing API and direct
server identity checks. A WolfAPI endpoint/schema change is not a prerequisite.**

**Do not ship automatic selection based only on WolfAPI's `product` field.** A live
endpoint was returned under both products. The direct A2S full game ID resolved it
to Experimental, and the launcher's existing GameDig dependency already exposes
that ID. Carry it through the launcher instead of discarding it.

Phase 0 is complete: live feasibility evidence, a pure executable identity contract,
regression tests, and the freshness/retry rules below are recorded. This does not
integrate automatic joining or verify the next Experimental release. The sample is
small; one of six direct probes timed out. Unknown/unreachable cases remain explicit.

## Live results

The checked endpoints are the public `https://api.wolfcontrol.co.uk/api/v1/servers`
list, `/search`, and `/resolve`. Bounded requests used at most three HTTP requests
in parallel. No authentication, backend changes, deployments, or game launches
were involved.

| Check | Observed result | Consequence |
| --- | --- | --- |
| Experimental list, 100 rows | All sampled rows explicitly labelled `experimental`; filtered total 640 | Existing list contract supplies identity |
| Stable live list, 50 rows | All sampled rows explicitly labelled `stable` | Same contract works for Stable |
| List with `product=all` | Accepted; total 224,433; first five ranked rows happened to be Stable | Unified pagination is already exposed; first-page composition is not evidence that every product appears on each page |
| Search with `product=all` | Found the sampled Stable endpoint and both records for the conflicting endpoint | Combined search is deployed |
| Resolve with `product=all` | Returned one sampled Stable record and two conflicting records for the sampled Experimental endpoint | Resolve can search both editions in one request, but callers must handle multiple records |
| Resolve sampled Stable endpoint as Experimental | Empty result | Product filtering works for this control |
| Resolve `192.0.2.1:2302` | Empty result | An unlisted address remains unknown; this is not active probing |
| Direct A2S queries | Three Stable responses had full game ID `221100`; two Experimental responses had `1024020`; one timeout | Version-independent client-side identity is practical |
| Short A2S AppID field | `0` in all five responding samples | Do not classify using that field alone |
| Existing GameDig CLI, one server per edition | `raw.appId=221100` and `raw.appId=1024020`, both successful | No new query dependency is needed for the observed cases |

The complete reduced observation set is in
[the evidence JSON](evidence/phase0-product-identity-2026-09-15.json). It contains
public server endpoints and returned identity information, not credentials. These
are dated observations; server availability and directory counts will change.

### A concrete duplicate/conflict

`5.101.164.234`, game port `11100`, query port `11101`, appeared twice in
`/resolve?host=5.101.164.234&game_port=11100&product=all`:

- Experimental public ID: `78ac3434-53f3-466d-8ab3-332a38703c01`.
- Stable public ID: `0a60b2fa-4930-4bd0-8ff3-3901cb29854e`.
- Both rows advertised version `1.29.163401` and had recent freshness.
- Both named `steam_web_api_experimental` as their source. The Stable record had
  an older provider observation but a same-day successful validation timestamp.
- A direct query to that endpoint returned full game ID **1024020**. GameDig also
  returned **1024020**.

Therefore neither matching version nor general server freshness settles product
identity. A successful status validation should not be treated as evidence that
the API's product label was independently revalidated. Source code inspection
suggests legacy identity overlap is relevant, but this investigation does not
establish the production root cause or full extent of the duplication.

WolfAPI cleanup/reconciliation would improve directory accuracy. It is a worthwhile
separate follow-up, but the launcher can resolve this case today using live identity.

## Why the next release need not require a code change

The sibling WolfAPI implementation collects Experimental with Steam application
ID `1024020` and assigns the Experimental product to that collection. It does not
choose the product by comparing the DayZ version string in that ingestion path.
The launcher's product definitions already contain Stable `221100` and
Experimental `1024020`.

Today's Experimental page contained both `1.29.163401` and `1.30.163975` rows. The
latter sampled endpoint was stale and timed out when queried directly; its presence
does **not** verify the announced release, its date, or its readiness.

Provided the next release continues using the same Steam application, these identity
rules need no release-number update. Repeat the direct-query canary after release:
pick a freshly validated Experimental server, compare its API record with GameDig's
`raw.appId`, then perform the existing installation/launch checks on an updated
client. Directory ingestion and server restarts can delay visibility during rollout.

## Launcher changes required

1. Preserve WolfAPI `product` as discovery evidence in models/cache/saved records.
   Validate supported values for both products; invalid/missing values are unknown.
2. Preserve GameDig `raw.appId` in `ServerStatus`. The installed
   `packaging/npm/node_modules/gamedig/protocols/valve.js` extracts the low 24 bits
   of the full 64-bit game ID and exposes the corrected value as `raw.appId`.
   `wolflauncher/status.py` currently discards it.
3. Use a bounded direct identity check before automatic launch/mod preparation.
   Matching supported live ID selects the product. A successful live ID can supersede
   contradictory directory labels for the same exact endpoint. Invalidate any old
   mod/launch context when the resolved product changes.
4. If the direct query times out, lacks a supported ID, or is incomplete, do not
   resolve a known conflict by taking the first API row. Keep the saved record and
   offer retry; do not silently launch Stable. Initially require a successful identity
   check for automatic joining; any future cached-identity grace period needs its
   own explicit policy and tests. Server self-report is operational routing evidence,
   not cryptographic authentication.
5. Use `product=all` for combined WolfAPI browsing/search/resolution, and `stable`
   when Experimental is excluded. Keep individual-product fetching for other
   providers/fallbacks where necessary. Do not send a global profile switch.
6. Reconcile duplicate physical endpoints for display. Keep API IDs and evidence
   attached until identity is resolved; do not merge incompatible records merely
   because their names match. Resolve hostnames locally before API lookup: the
   inspected API resolver performs exact IP/alias matching, not DNS resolution.
7. Separate filtered totals from whole-directory coverage. For the Experimental
   sample, `total_count` was 640 while `coverage.eligible` was 224,433. Current
   `parse_wolfapi_v1_servers()` uses coverage for its directory-wide count. Preserve
   that meaning and introduce a separate filtered total for combined pagination/UI.

## Required test additions before accepting automatic routing

- Recorded GameDig Stable and Experimental results classify using `raw.appId`,
  regardless of misleading names or equal version strings.
- Missing ID, ID `0`, malformed ID, unsupported ID, timeout, and partial response
  remain unknown. Include challenge-response and missing extended-ID query fixtures
  if adding a custom A2S path; prefer the existing dependency.
- Exact same host/game/query ports in two API products produce one unresolved
  conflict; live `1024020` resolves it to Experimental. Reverse the labels/live ID
  to test the Stable resolution too.
- Recent API timestamps do not override a contradictory live identity. Older
  callbacks cannot overwrite a newer identity decision or launch the prior product.
- An unlisted manually added server can still resolve through a successful direct
  query; directory miss plus query timeout produces retry guidance, not a default.
- Hostname lookup uses resolved IP while preserving the user's saved hostname and
  distinct game/query ports. Ambiguous single-port input must not query the game
  port as though it were confirmed to be the query port.
- `product=all` survives list/search/resolve parsing, including mixed rows,
  duplicates, empty results, and malformed values. Counts preserve both filtered
  total and global coverage; offset pagination uses filtered total.
- Product changes invalidate cached mod results before any launch; the user's
  Stable external-engine preference remains unchanged when launching Experimental.

The list above spans the complete feature. Phase 0 now tests the pure identity
decision and existing API request contract. Persistence, callback wiring, count/UI
changes and actual launch integration remain the Phase 1–5 gates, rather than being
claimed as delivered by these tests.

## Final identity, freshness and retry contract

The executable decision boundary is `wolflauncher/server_identity.py`. It is not
yet connected to polling or launching. Integrating it is a subsequent phase.

1. **Identity:** use GameDig's corrected integer `raw.appId`: `221100` means Stable,
   `1024020` means Experimental. Missing, malformed, unsupported, short ID `0`, and
   dedicated-server app IDs are unknown. Never use names, versions, or a default
   product to resolve unknown. Incomplete/failed GameDig responses are not evidence.
2. **Precedence:** directory `product` is provisional display/discovery evidence.
   Only supported explicit labels are accepted; absent/malformed labels are unknown.
   Opposing labels for one endpoint are a conflict. A successful supported live ID
   for that exact endpoint supersedes either label, even when API timestamps are
   recent. Live timeout does not break a conflict in favour of either API record.
3. **Freshness:** reuse a successful live observation for at most **30 seconds**,
   inclusive, measured with a monotonic clock. Negative/nonfinite ages are invalid.
   Record observation time on successful completion, never on request start or cache
   access. This is a conservative initial product policy, not a Steam guarantee.
4. **Context:** bind evidence to resolved IP, distinct game/query ports, and the
   current selection/request generation. Replacing selection, installation or mod
   context invalidates it. Only the latest applicable check may publish its result;
   a cancelled request or late result cannot restore invalidated evidence. An existing
   poll can supply evidence if bound to that same current context.
5. **Failure:** a newer failed/incomplete check invalidates launch authority. Keep
   last-known identity separately for the saved badge, with a stale/unavailable state.
   Never restore launch authority from persisted wall-clock timestamps after restart.
6. **Join:** require valid live identity before mod preparation and again before
   handoff if more than 30 seconds has passed. If identity changed, invalidate mods
   and rebuild context. If unchanged, valid matching mod work can remain usable.
   A refresh failure blocks handoff and offers Retry, without guessing another edition.
7. **Bounded work:** reuse the current status-check timeout budget (one GameDig
   attempt, 1.5-second socket timeout, 5-second process deadline). Normal background
   polling may retry on its existing cadence. Join gets one bounded refresh; on
   failure return control to the user rather than silently looping. No new polling
   loop or new packet decoder is required.
8. **Manual endpoints:** resolve hostname to IP locally, retain the saved hostname,
   and query confirmed query ports. WolfAPI `product=all` handles both directories.
   A known game port and query port are never interchanged. If only an ambiguous
   port is supplied, bounded API lookup may try it separately as game and query port;
   unresolved query-port ambiguity needs correction before direct querying. Directory
   miss plus a valid direct response is supported; miss plus failed direct query is
   unknown. Multiple IP/alias matches must not be silently collapsed into one target.

The caller obligations above (polling, invalidation, preflight ordering and timeout
enforcement) are explicit integration requirements for Phases 1–4. The pure resolver
tests freshness and exact context without pretending that UI integration exists.

## Phase 0 completion evidence

- Nine new tests in `tests/test_server_identity.py` cover captured live IDs and
  directory conflicts, malformed/unsupported IDs, misleading names/equal versions,
  directory misses, both conflict-resolution directions, freshness boundaries,
  incomplete results, old request IDs, changed endpoints/ports, combined API request
  encoding, and transport failure versus an empty response.
- Focused regression command: `python -m unittest tests.test_server_identity
  tests.test_server_discovery tests.test_status -q` — **73 tests passed**. Existing
  status tests also exercise DNS resolution and incomplete/failed query handling.
- New files pass Ruff lint/format checks. Mypy passes for the new contract module
  and the existing four hardened core modules.
- Full suite under temporary Python 3.12 / PySide6 6.11.2, Qt offscreen: **632 tests,
  two failures, five skips**. Both failures reproduce from unchanged commit `87db479`
  in the same environment: browser column width (38 versus 32) and local-socket
  second-instance notification. They are not Phase 0 regressions.
- Whole-tree Ruff is not clean: seven existing lint errors also reproduce on the
  unchanged commit, alongside existing formatting issues. Only the new code was
  formatted; unrelated files were not rewritten.
- Follow-up: the single-instance test passes outside the socket-restricted sandbox.
  The column-width failure was fixed by explicitly allowing the 32-pixel password
  column instead of inheriting Qt's larger style minimum; its test now forces a
  larger initial minimum. After that fix, the full suite outside the sandbox passes:
  **632 tests, five skips, no failures**. Lint and whitespace checks pass for the fix.
- Validation environment was created under `/tmp`; no dependency or lockfile changes.
- Live checks are dated observations. The new-release canary remains a release-time
  validation task; it cannot be completed before that release is available.

**Gate: passed for Phase 0.** No WolfAPI implementation/deployment change is required
to begin Phase 1. Full automatic launch and browser acceptance remains outstanding.

## Source locations inspected

- WolfLauncher: `wolflauncher/server_discovery.py` (v1 requests, row conversion,
  directory counts), `wolflauncher/status.py` (GameDig conversion),
  `wolflauncher/dayz_product.py` (Steam identities).
- Sibling WolfAPI: `main.py`, `fetch_and_cache_experimental_servers()` near line
  5145; v1 list/search/resolve near lines 7677–7888; product-aware SQL filtering
  near line 3230; `DISCOVERY_FRESHNESS_CONTRACT.md`, product-identity hotfix section.
- Installed GameDig: `protocols/valve.js`, full game-ID parsing near lines 109–112.

The sibling source establishes implementation intent; the live probes establish
which relevant public behaviours were actually observed. No WolfAPI files changed.
