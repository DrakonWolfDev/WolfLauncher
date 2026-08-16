# WolfAPI Discovery Freshness Handoff

Last synchronized with WolfAPI migration `20260713_0007` on 2026-07-13.

## Supplemental map sweep (2026-08-14)

WolfAPI can supplement its bounded global Steam directory query with a slow,
durable, case-normalized map sweep. This is ingestion-only coverage work: it
does not change WolfLauncher endpoints, fields, stable IDs, pagination or
freshness semantics. Launcher should continue to treat WolfAPI directory
counts as observed coverage rather than a full Steam census.

## WolfAPI post-canary scheduling update (2026-08-16)

WolfAPI now gives advisory-flagged rows a bounded validation share, supports
bounded concurrency in its separately budgeted direct-mod job, avoids
rewriting unchanged per-server Redis hashes after live-validation batches and
publishes queue wait/runtime plus cache-write telemetry. This improves hosted
freshness throughput without changing v1 fields, quality-warning semantics or
Launcher behavior. Flagged rows remain discoverable by exact resolution and a
warning is still advisory rather than proof that a server is unsafe. Launcher
selected-server and launch-time checks remain local final truth.

## Purpose

This file is the launcher-side companion to
`../WolfAPI/DISCOVERY_FRESHNESS_CONTRACT.md`. Update both documents whenever a
launcher-facing endpoint, field, identity rule, freshness policy or rollout
gate changes. This coordination is bidirectional: regardless of which
repository a task originates in, inspect and update both sides when the shared
feature materially requires it.

WolfLauncher remains offline-first: cached SQLite rows render immediately,
remote discovery is read-only, curated YAML remains user-owned, and selected
server/launch-time checks remain local truth.

Production-hardening synchronization on 2026-07-19: WolfAPI v1 retains the
required `generated_at` field, but its strong ETag now hashes the exact
serialized response bytes (including that timestamp). A cached representation
still returns `304`; a rebuilt byte-different representation receives a new
validator. No Launcher parser, cache schema or UI change is required.

Experimental-directory routing update on 2026-08-03: WolfAPI has a
disabled-by-default Steam collection using DayZ Experimental client App ID
`1024020`. Its v1 list, search and resolve rows are product-filtered as
`experimental`; the Launcher keeps them in the separate `wolfapi_experimental`
source namespace and rejects a mixed response before cache writes. Experimental
`A2S_RULES` metadata also uses an independent, opt-in 50-per-six-hours API
lane, so it cannot consume Stable's existing budget. Steam Master remains an
explicit manual fallback; enable hosted Experimental discovery only after
deployment and product-isolation verification.

Live-validation scheduling update on 2026-07-19: WolfAPI now suppresses only
automatic A2S re-probes for seven days after three consecutive failures since a
server's last successful validation. A success resets that durable history.
This does not hide provider rows, change freshness/validation fields, or alter
Launcher behavior; local selected-server and launch-time checks remain final
truth.

Current-scope close-out on 2026-07-21: WolfAPI's operating model is now fixed
at Steam discovery plus bounded rolling A2S validation, with capacity for a
24-hour eligible-directory revisit. BattleMetrics and scheduled DZSA metadata
are disabled in the hosted API. GameDig remains authoritative for a selected
server and at launch time. Any future BattleMetrics, DZSA or other directory
subscription is a disabled-by-default, locally configured Launcher power-user
integration; its credentials and failures must never become a WolfAPI
dependency or contaminate the shared cache.

Launcher direct-mod transition on 2026-07-21: native selected-server inspection
and launch preflight now obtain the required Workshop manifest directly from
the game server's binary `A2S_RULES` response on the existing background
worker. The owned decoder is bounded and fail-closed for overflow, truncation,
duplicates and structural ambiguity; it never accepts a partial prefix. Live
DayZ responses may append an undocumented opaque extension after the declared
signature records. The decoder permits that suffix only after every declared
mod and signature has parsed completely and limits it to 2 KiB; its content is
never interpreted or exposed. Steam
remains responsible for Workshop display metadata and local item state. DZSA
remains only in the explicitly labelled legacy Linux shell-launcher fallback,
not in the native Windows/Linux path. WolfAPI cached counts remain browse-time
evidence and are not made authoritative by this launcher-only change.

Direct-mod preview operating plan on 2026-07-26: WolfAPI will retain direct
`A2S_RULES` manifests as advisory browse evidence on a target fourteen-day
freshness window. The job will remain separately scheduled every six hours,
with a staged target of 1,200 sequential known-reachable probes per run and
phase-specific capacity: approximately 90% new coverage during the initial
pass, then approximately 90% due refreshes after coverage is established.
The live 100-server canary remains a checkpoint, not the final setting. This
does not change Launcher parsing, UI semantics, or selected-server/launch-time
truth: direct local inspection remains authoritative.

Directory-count correction on 2026-07-21: WolfLauncher now carries
`coverage.eligible` from every successful WolfAPI v1 list/search/resolve
response through its background workers and persists the last known value for
offline startup. The Server Browser uses that value for the whole WolfAPI
directory total; its SQLite row count is labelled as local cache state and is
never presented as the directory size. This is shared Windows/Linux behavior.

Manual-refresh scheduling correction on 2026-07-21: provider refresh and local
GameDig freshness are serialized. **Refresh server list** waits for the
provider/cache update to finish before starting local freshness, and repeated
same-search requests coalesce without cancelling a live worker. A genuinely
changed search still cancels obsolete checks. This removes the Linux native
worker/cache overlap while preserving a fluid UI on both platforms.
If the user clicks refresh during an existing GameDig batch, Launcher cancels
that batch and defers provider startup until the worker's `finished` signal;
it never blocks the Qt thread or overlaps the two SQLite writers.

## Future Codex resume note — 2026-07-14

Treat WolfLauncher and `../WolfAPI` as one discovery product with two separately
tested and committed repositories. The direction of the next request does not
define the implementation boundary: a Launcher-originated task may require API
work, and an API-originated task may require Launcher fields, persistence,
presentation or truth-boundary changes. Read both `AGENTS.md` files, this file
and `../WolfAPI/DISCOVERY_FRESHNESS_CONTRACT.md`; make necessary companion
changes in the same session and keep both handoffs synchronized. Never wait for
the user to repeat a shared request in the other repository.

Current shared baseline:

- WolfAPI migration `20260713_0007` is deployed with its bounded metadata job
  persistently enabled in the production host's ignored `.env`;
- WolfLauncher SQLite schema v7 persists count/status/timestamps/error/hash,
  advisory quality flags and nullable country provenance. API metadata remains browsing evidence; direct
  **Inspect mods** and launch-time lookup remain final truth. The advanced,
  default-on quality hide control filters cached rows and remote v1 list/name-search
  calls without deleting data or changing exact-resolution truth;
- four production metadata cycles completed 40/40 lookups without failure, but
  the six-hour TTL and strict unknown-first ordering yielded 10 ready and 30
  stale manifests among roughly 49,000 unknown eligible rows;
- web memory remained about 75 MiB and the active worker about 709 MiB inside
  the 4 GiB deployment limit, with no OOM or restart;
- the real production directory contained 1,810 flagged and 50,492 unflagged
  rows. This supersedes the earlier development-only zero-flag snapshot.

Implemented locally in WolfAPI on 2026-07-14: the ten-row global budget now
uses bounded 60/30/10 new-coverage, expired-success refresh and retry lanes,
with unused capacity spilling between lanes. The API health response exposes
the latest lane counts. No Launcher schema, parser or UI change is required;
failure cooldown, confirmed zero versus unknown, last-success retention,
cached-only detail responses and the direct-Launcher-final-truth boundary are
unchanged. Observe initial production cycles at ten, then raise the global
budget progressively using duration, upstream-error and worker-RSS evidence.
The first production fair-lane cycle completed 10/10 without error on
2026-07-14: seven new candidates and three expired successful manifests, with
the unused retry slot spilling to new coverage. The queue returned to zero and
worker health remained healthy. Keep the ten-row budget for additional cycles
before increasing it.
WolfAPI now also exposes latest-run duration, full ready backlog counts by lane
and stable error-category counts in `mod_metadata` health. Promotion remains
sequential: observe at least three healthy queue-draining cycles at 10 before
50, then apply the same failure, duration and worker-RSS gates before 100.
Measure sequential 100-row behavior before adding request concurrency.

Production quality-filter evaluation on 2026-07-14 found 1,383 flagged rows in
the current directory. Samples coherently showed impossible `bots=255`
telemetry and dense same-host populations, while some names could still be
legitimate communities with bad provider data. WolfLauncher therefore adds an
explicit advanced **Hide listing data warnings** filter, on by default. SQLite
schema v7 persists the advisory flags so cached/offline filtering agrees with
v1 list and name-search requests. Exact resolution remains available, but the
local visibility filter still applies. Visible flagged rows say the warning is
advisory, not proof that a server is unsafe.

Launcher safety-net update on 2026-07-28: while WolfAPI remains responsible for
directory-wide quality classification, the Launcher additionally marks three or
more distinct endpoints with the same whitespace-normalized, case-insensitive
provider name as `duplicate_name_cluster` during WolfAPI ingestion. This
conservative local flag flows through the existing advisory filter and is not a
claim about server safety. WolfAPI should add an equivalent directory-wide rule
with operator-visible telemetry and fixtures so it catches clusters outside a
bounded Launcher response page.
The user confirmed the advanced control works on the real desktop on
2026-07-14.

## Current deployment boundary

### WolfAPI product-identity hotfix (2026-08-14)

WolfAPI normalized legacy raw Steam product labels across global and map-sweep
ingestion and repaired duplicated Experimental endpoint identities internally.
The existing v1 `product` filter,
opaque `server_id` and legacy endpoint compatibility remain unchanged; no
WolfLauncher code, SQLite migration or user-setting change is required.

WolfLauncher uses the hosted v1 endpoints for fresh-install default discovery:

```text
GET https://api.wolfcontrol.co.uk/api/v1/servers
GET https://api.wolfcontrol.co.uk/api/v1/servers/search
GET https://api.wolfcontrol.co.uk/api/v1/servers/resolve
```

V1 is the default provider for fresh installations after the production
migration, contract fixture, origin load and proxy load gates passed. Existing
saved choices remain unchanged and the explicit legacy fallback stays
available at `GET /api/servers`. API failure means remote search is unavailable,
not that cached servers disappeared.

WolfAPI's additive `/api/health` operator telemetry now breaks advisory quality
warnings down by stable reason and reports the configured direct-validation
capacity plus map-sweep cycle yield. This does not change v1 row parsing,
visibility, SQLite storage or Launcher behavior. The API's 900-row,
concurrency-10 production canary passed three scheduled cycles on 2026-08-16
with zero queue residue, dead letters, restarts or service errors; continue to
treat provider/validation state as browsing evidence and selected-server checks
as local truth.

Post-fix probe on 2026-07-13: bounded list, dedicated search, exact resolution
and conditional ETag requests all pass. Migration `20260713_0006`, rollout
metadata, stable UUIDs and endpoint aliases are live; list/search/resolve agree
on identity. The strict Launcher client imported 100 v1 rows into an isolated
SQLite cache. Two public-hostname tests from the same LAN initially showed
timeouts and high tail latency, prompting the origin/proxy isolation below.

The identical host-local origin mix then passed all 1,000 requests with zero
errors at about 680 requests/second, p95 173 ms and p99 181 ms while web RSS
remained near 78 MiB. WolfAPI origin capacity is therefore sufficient; direct
OpenResty/LAN testing must isolate proxy behavior from public routing before
the external load gate can close.

The hostname-preserving direct-LAN OpenResty mix also passed all 1,000 requests
with zero errors at about 482 requests/second, p95 234 ms and p99 246 ms. Since
the test client is on the same LAN, the slow public-hostname run was a router
NAT-loopback/hairpin artifact. Origin and proxy capacity gates now pass;
preserve the legacy fallback and watch normal external telemetry during staged
Launcher adoption.

## Implemented WolfAPI v1 contract

WolfAPI `main` provides:

```text
GET /api/v1/servers
GET /api/v1/servers/search?q=&map=&version=&limit=&offset=
GET /api/v1/servers/resolve?host=&game_port=&query_port=
GET /api/v1/servers/{server_id}/mods
```

- bounded Postgres-backed pages that do not decode the full Redis directory;
- stable ordering, pagination, ETags and shared-cache policy;
- indexed name search with exact-name priority plus exact endpoint resolution;
- source, freshness, quality, map, version and endpoint filters;
- request-time `live`, `recent`, `stale`, `offline` and `unverified` aging;
- normalized provider and validation timestamps/status/error categories;
- response validation policy, coverage counts and validation queue lag;
- opaque stable UUID `server_id` values;
- `legacy_endpoint_id` for the current endpoint-derived identity;
- `endpoint_aliases` containing current and corrected endpoint identities.
- nullable required-mod count/status/timestamps/error/hash fields in list rows,
  plus a cached-only full-manifest detail endpoint.

Legacy `/api/servers` remains compatibility-only and endpoint-keyed.

## Launcher implementation choices

Foundation implemented locally on 2026-07-13:

- SQLite schema v7 migrates earlier layouts in place and
  combines Workshop metadata with stable IDs, aliases, freshness and
  validation state, while retaining WolfAPI mod-metadata provenance;
- WolfAPI rows are merged by stable ID so corrected ports move one row;
- opt-in bounded list, remote search and exact-resolution clients exist;
- v1 responses are rejected unless contract version, generation time,
  validation policy, coverage and queue metadata are present;
- the hosted legacy endpoint remains the default and no GUI/startup behavior
  has switched for existing saved settings;
- Settings now offers an explicit `WolfAPI v1 (staged)` provider alongside
  `WolfAPI (legacy fallback)`. The staged worker uses only the bounded strict
  v1 client, retains cached SQLite rows on failure and has its own 24-hour
  automatic-refresh timestamp;
- staged refreshes fetch 100-row pages in the background up to the configured
  limit and merge them without deleting cached rows outside the bounded pages;
- Server Browser renders local SQLite matches immediately, then debounces v1
  remote search for 450 ms, merges stable-ID results without deleting unrelated
  rows and ignores stale completions for the visible query;
- Observed UI issue for joint Launcher/API investigation: entering the third
  search character can briefly freeze the Server Browser before subsequent
  input becomes responsive. This coincides with the minimum-length remote
  search transition, but whether the pause is in the client query/merge path,
  the HTTP request, or the API remains unproven and must be profiled.
- exact `host:port` searches use `/resolve` with the port checked as both game
  and query port, deduplicate by stable ID and make historical endpoint aliases
  searchable locally;
- v1 is the provider default for fresh installations after production and
  desktop canaries passed. Existing saved choices remain unchanged and the
  legacy provider remains an explicit fallback;
- the existing Status-cell tooltip and copied server details expose API
  freshness, validation and provider observation without adding a table column.
  Cached labels past `freshness_expires_at` say `expired; refresh pending`
  rather than guessing a new API state.
- discovered rows persist WolfAPI's required-mod metadata status, timestamps,
  error and manifest hash. Ready/stale/failed tooltips describe it as browsing
  evidence and direct **Inspect mods** remains final selected-server truth.

1. Migrate SQLite additively. Keep the existing endpoint `cache_key` for
   non-WolfAPI providers and launch/connect behavior, but add nullable
   `stable_server_id`, freshness/validation fields and an alias mapping for
   WolfAPI rows.
2. Upsert WolfAPI rows by stable ID. When the current endpoint changes, update
   the existing cached row and retain aliases instead of inserting a duplicate.
3. Implemented: render SQLite results immediately, fetch bounded 100-row v1
   pages in the background and merge them into SQLite.
4. Implemented: search local SQLite first, then debounce remote `/search` and
   merge matches. Successful empty responses remain distinct from failures,
   which quietly retain and display cached results.
5. Implemented: exact `host:port` searches use `/resolve` for game/query-port
   and alias-aware lookups. Search and resolution never synchronously trigger
   UDP validation.
6. Implemented: use API freshness/validation as browsing truth in existing
   status tooltips and copied details. Keep local ping blank until measured
   locally; API-host latency is not player latency.
7. Retain selected-server and launch-time reachability/mod checks. V1 removes
   the need for fixed startup polling, not final join validation.

Startup audit completed on 2026-07-13: WolfLauncher does not automatically
UDP-probe discovered SQLite rows. Startup status refresh covers curated YAML
servers only, v1 automatic refresh is HTTP-only and discovered-row live probing
remains the explicit **Enrich visible** action. No probing removal is required;
curated, selected-server and launch-time checks remain intentionally local.

## Implemented Server Browser location and game-time fields

The completed Server Browser data pass keeps stable discovery metadata separate
from rapidly changing live server state:

- **Game Time** is Launcher-owned live state. SQLite schema v7 now retains
  `ServerStatus.time` plus GameDig's DayZ day/night acceleration values through
  explicit local enrichment. The compact table uses a 24-hour value, broad
  sun/moon cue and effective multiplier, while unknown remains explicit until
  measured. Provider merges preserve the local observation. Do not publish
  game time through WolfAPI because a cached directory value would age quickly
  and could look live when it is not.
- **Region** in the user interface means a trustworthy geographical country,
  not WolfAPI's existing integer `region` field. That existing value is the
  Steam master-server region code and is frequently `-1`; preserve it for
  compatibility but never present it as a country.
- Add a nullable `country_code` field to the WolfAPI v1 contract only when it
  can be normalized from a known source to an ISO 3166-1 alpha-2 code. Null
  explicitly means unknown. Record provider provenance, avoid guessing from an
  IP address, and measure real coverage before considering a separate IP
  geolocation source.
- WolfLauncher should parse and cache `country_code` additively, preserve it
  across stable-ID merges and local enrichment, and display a compact country
  label or flag with an unknown fallback.
- Refactor discovered-server enrichment to preserve fields it did not measure
  (prefer `dataclasses.replace` over reconstructing a partial object). This is
  required before adding either field because the current reconstruction can
  drop newer API metadata.

Implementation order: first retain and present locally measured `game_time`;
then add the shared nullable `country_code` contract and persistence in both
repositories; finally evaluate country coverage before selecting any additional
data source. Update this handoff and the API contract together when the fields
are implemented.

### Country implementation record — 2026-07-18

The Server Browser visual pass is approved as the stable presentation target. The
selected-server inspector uses a dense table/master-detail split, grouped
selectable metadata and an original map-family atmosphere in otherwise-unused
lower space. Do not reopen that hierarchy when adding the fields; populate the
existing Region and Game Time positions.

Country work is complete across both repositories:

1. A live public BattleMetrics DayZ response confirmed the exact path as
   `data[].attributes.country`; the sanitized fixture value is `US`.
2. WolfAPI normalizes trustworthy BattleMetrics country values to nullable
   ISO 3166-1 alpha-2 `country_code`, retain explicit provider provenance, add
   an additive Alembic migration and preserve the values through ingestion,
   canonical merging, recovery publishing and port correction.
3. `country_code` and its provenance are exposed consistently from v1 list, search
   and resolve rows. Null remains unknown; the existing integer `region` stays
   a separate Steam compatibility field. Measure coverage before considering
   any IP-geolocation fallback.
4. WolfLauncher has the matching nullable model and SQLite schema-v7 fields,
   parse all v1 response shapes, preserve country across stable-ID merges and
   local enrichment, and populate the inspector's existing Region value.
5. WolfLauncher now retains locally measured game time and GameDig's published
   day/night acceleration values through enrichment and SQLite, and populates
   the existing Game Time value. The sun/moon cue uses 06:00/18:00 display
   boundaries; night acceleration is the documented day multiplier times night
   factor. This rapidly changing state remains Launcher-only.

Test and commit WolfAPI and WolfLauncher separately. Deployment and migration
readiness remain distinct from source completion; keep the legacy API fallback
until a deliberate later removal.

## Rollout gates

- On 2026-07-21 WolfAPI proved concurrency 10 over 160 scheduled 100-row
  cycles, but measured a roughly six-day eligible-directory revisit. API
  selection now reserves bounded capacity for provider-fresh new, active
  revisit, cooled retry and long-tail background lanes and publishes 24-hour
  provider-fresh first-check and six-hour active-revisit objectives. Batch 250
  and 500 mixed-load production canaries remain required. No Launcher code
  change is needed: API freshness remains browse-time truth, while selected
  server and launch-time checks remain authoritative.
- Enabled WolfAPI source failures now degrade top-level operator health. The
  Launcher should continue treating `/api/health` as diagnostics and retain
  cached SQLite results on provider failure.
- BattleMetrics now returns an explicit subscription-required HTTP 403 even
  for page one, so its scheduled WolfAPI source is disabled unless the
  operator deliberately provisions paid API access. Retained observations are
  preserved; Launcher behavior remains unchanged and Steam/direct A2S are the
  active discovery-freshness path.
- WolfAPI final production canary uses batch 600/concurrency 10. It completed
  in 96.685 seconds during 20,000 mixed v1 requests with zero HTTP errors and
  projects a 24-hour full revisit for 57,411 eligible rows. Launcher behavior
  remains unchanged; observe one real full window before closing the coverage
  objective.

- Production reports `contract_version >= 1`, `generated_at`, validation
  policy, coverage and queue-lag metadata. WolfAPI now also exposes ready and
  cooling-down candidate counts, oldest-ready age, and configured-capacity
  estimates for ready-queue drain and full eligible-population revisit in v1
  responses and operator health. These are scheduling projections rather than
  promises that an A2S probe will succeed; Launcher behavior does not depend on
  them.
- Migration `20260713_0006` is applied and old/new endpoint resolution returns
  one stable server ID.
- Freshness ages correctly across several production expiry cycles.
- Bounded pages, indexed search, exact resolution and conditional ETags pass a
  sanitized production fixture test.
- Cold/warm mixed-client load and scheduled worker jobs stay inside the agreed
  memory/latency envelope without web-process restarts.
- The launcher SQLite migration, stable-ID merge behavior, offline fallback and
  legacy response parser tests pass before changing the default URL.

## Known follow-up dependencies

- Native direct DayZ `A2S_RULES` inspection is implemented and confirmed on
  Windows canaries plus the user's real Linux desktop across every server tried.
  It is noticeably faster than the former DZSA lookup. Keep it authoritative
  for the selected server and launch preflight, and keep it off browser
  freshness batches so search/scroll responsiveness cannot be held behind
  split-packet manifest work.
- Next shared direction: WolfAPI may gradually populate the existing cached
  required-mod count/manifest fields from direct `A2S_RULES` as advisory
  browse-time evidence. Implement this as a disabled-by-default, separately
  budgeted lane after successful reachability—not as part of public HTTP
  requests and not as a condition of reachability success. Preserve the last
  successful count on later rules failure. The browser count answers roughly
  “lightly or heavily modded”; Launcher direct inspection remains final truth.

- WolfAPI has a transactional port-correction operation, but automatic use
  still needs trustworthy corrected-port evidence; A2S reachability alone does
  not provide it.
- Required-mod persistence and cached-only API fields already exist. The old
  DZSA-backed scheduled job remains disabled and must not be revived. Reuse the
  tested direct decoder for a new canary lane only after its separate budget,
  provenance, stale-retention and health/error telemetry are covered by tests.

The earlier development snapshot contained no flagged rows, but the
2026-07-14 production snapshot contained 1,810 flagged and 50,492 unflagged
rows. Keep the current ranking behavior while an explicit optional Launcher
filter is evaluated from real browsing behavior; do not silently hide rows.
- Production proxy/CDN behavior and sustained-load peak RSS still need final
  deployment evidence.
