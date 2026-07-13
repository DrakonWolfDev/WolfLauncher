# WolfAPI Discovery Freshness Handoff

Last synchronized with WolfAPI development commit `69480db` on 2026-07-13.

## Purpose

This file is the launcher-side companion to
`../WolfAPI/DISCOVERY_FRESHNESS_CONTRACT.md`. Update both documents whenever a
launcher-facing endpoint, field, identity rule, freshness policy or rollout
gate changes.

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
  has switched yet.

1. Migrate SQLite additively. Keep the existing endpoint `cache_key` for
   non-WolfAPI providers and launch/connect behavior, but add nullable
   `stable_server_id`, freshness/validation fields and an alias mapping for
   WolfAPI rows.
2. Upsert WolfAPI rows by stable ID. When the current endpoint changes, update
   the existing cached row and retain aliases instead of inserting a duplicate.
3. Render SQLite results immediately. Fetch a bounded initial v1 page in the
   background, then merge returned rows into SQLite.
4. Search in two stages: local SQLite first, followed by a debounced remote
   `/search`; merge remote matches into SQLite. A successful empty response is
   distinct from service failure.
5. Use `/resolve` for exact host/port additions and alias-aware lookups. Never
   make search or resolution synchronously trigger UDP validation.
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
