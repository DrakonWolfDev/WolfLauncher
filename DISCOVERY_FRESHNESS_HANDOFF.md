# WolfAPI Discovery Freshness Handoff

Last synchronized with WolfAPI development commit `ce0d1e6` on 2026-07-13.

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

## Current deployment boundary

WolfLauncher currently consumes the hosted legacy endpoint:

```text
GET https://api.drakonwolf.ddns.net/api/servers
```

Do not switch the default URL merely because v1 exists in the sibling source
tree. Confirm the production migration, contract fixture and rollout gates
below first. API failure means remote search is unavailable, not that cached
servers disappeared.

Post-fix probe on 2026-07-13: bounded list, dedicated search, exact resolution
and conditional ETag requests all pass. Migration `20260713_0006`, rollout
metadata, stable UUIDs and endpoint aliases are live; list/search/resolve agree
on identity. The strict Launcher client imported 100 v1 rows into an isolated
SQLite cache. Keep the legacy default while the load gate remains open: two
1,000-request/100-concurrency external mixes produced 1 and 13 timeouts with
multi-second p95/p99 latency. Host/container and reverse-proxy evidence is
required before GUI orchestration or provider-default changes.

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

The current WolfAPI development branch provides:

```text
GET /api/v1/servers
GET /api/v1/servers/search?q=&map=&version=&limit=&offset=
GET /api/v1/servers/resolve?host=&game_port=&query_port=
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

Legacy `/api/servers` remains compatibility-only and endpoint-keyed.

## Launcher implementation choices

Foundation implemented locally on 2026-07-13:

- SQLite schema v2 migrates existing v1 caches in place and stores stable IDs,
  aliases, freshness and validation state;
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
  legacy provider remains an explicit fallback.

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
6. Use API freshness/validation as browsing truth. Keep local ping blank until
   measured locally; API-host latency is not player latency.
7. Retain selected-server and launch-time reachability/mod checks. V1 removes
   the need for fixed startup polling, not final join validation.

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
- Required-mod count/manifest metadata remains a separate future bounded job.
- Production proxy/CDN behavior and sustained-load peak RSS still need final
  deployment evidence.
