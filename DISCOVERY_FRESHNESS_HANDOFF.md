# WolfAPI Discovery Freshness Handoff

Last synchronized with WolfAPI migration `20260713_0007` on 2026-07-13.

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
- WolfLauncher SQLite schema v4 persists count/status/timestamps/error/hash and
  presents API metadata only as browsing evidence; direct **Inspect mods** and
  launch-time lookup remain final truth;
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

Quality filtering is a separate Launcher product decision. The API already
demotes flagged rows without hiding them. Evaluate an explicit optional filter
against real browsing behavior; do not silently change the default or remove
flagged servers.

## Current deployment boundary

WolfLauncher uses the hosted v1 endpoints for fresh-install default discovery:

```text
GET https://api.drakonwolf.ddns.net/api/v1/servers
GET https://api.drakonwolf.ddns.net/api/v1/servers/search
GET https://api.drakonwolf.ddns.net/api/v1/servers/resolve
```

V1 is the default provider for fresh installations after the production
migration, contract fixture, origin load and proxy load gates passed. Existing
saved choices remain unchanged and the explicit legacy fallback stays
available at `GET /api/servers`. API failure means remote search is unavailable,
not that cached servers disappeared.

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

- SQLite schema v4 migrates earlier layouts in place and
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

## Rollout gates

- Production reports `contract_version >= 1`, `generated_at`, validation
  policy, coverage and queue-lag metadata.
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

- WolfAPI has a transactional port-correction operation, but automatic use
  still needs trustworthy corrected-port evidence; A2S reachability alone does
  not provide it.
- Required-mod metadata is implemented behind WolfAPI's committed
  disabled-by-default job. The local production `.env` enables it persistently.
  Its original ten-row canary completed 40/40 across four cycles, then exposed
  strict unknown-first refresh starvation. The local fair-lane fix reserves
  new/refresh/retry capacity without changing the hard budget or Launcher
  truth boundary; observe it in production before increasing coverage.

The earlier development snapshot contained no flagged rows, but the
2026-07-14 production snapshot contained 1,810 flagged and 50,492 unflagged
rows. Keep the current ranking behavior while an explicit optional Launcher
filter is evaluated from real browsing behavior; do not silently hide rows.
- Production proxy/CDN behavior and sustained-load peak RSS still need final
  deployment evidence.
