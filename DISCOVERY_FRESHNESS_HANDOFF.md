# Discovery Freshness Cross-Project Handoff

Status: design checkpoint for coordinated WolfAPI and WolfLauncher work.

## Why this is now a priority

Server discovery is the least settled part of WolfLauncher. The launcher currently receives provider-cached rows, cannot reliably tell whether a row is still reachable, and compensates by querying servers from the user's computer. The latest bounded first-30 enrichment is safer than polling every visible row, but it remains a workaround:

- startup performs network work unrelated to the user's immediate action;
- fixed batches spend time on off-screen or unwanted rows;
- slow query ports make progress feel clunky;
- corrected ports can change row identity and require deduplication;
- every launcher repeats work WolfAPI could perform once for all users;
- provider timestamps, successful live validation and failed live attempts are too easy to conflate.

WolfAPI already has most of the backend foundation: Redis public serving, Postgres history, source observations, validation attempts, bounded A2S validation, freshness fields and health metrics. The next step is to harden that data into a stable public contract and make WolfLauncher consume it.

## Target ownership model

### WolfAPI owns shared directory truth

WolfAPI should own:

- provider observations from Steam and BattleMetrics;
- canonical identity and alias/port correction history;
- scheduled live A2S validation;
- validation success/failure history and retry policy;
- server-side freshness classification and ranking;
- stable public fields describing exactly what was observed, by whom and when;
- aggregate validation coverage and lag metrics.

### WolfLauncher owns user-local truth

WolfLauncher should own:

- curated YAML servers and favourites;
- its offline SQLite snapshot of the last API response;
- selected-server checks needed for joining, mod resolution and launch;
- optional explicit **Check now** actions;
- local ping, because API-host latency is not the player's latency;
- honest presentation when remote truth is old or unavailable.

The launcher should not continuously recreate WolfAPI's global validation job.

## Required WolfAPI public contract

Add the fields below additively to `/api/servers`, then freeze them in a versioned `/api/v1/servers` contract. Existing fields must remain for older launchers.

| Field | Type | Meaning |
|---|---:|---|
| `server_id` | string | Stable canonical ID; not silently changed by display-field corrections. |
| `provider_online` | bool/null | Latest upstream provider claim, or null when no provider makes one. |
| `provider_last_checked` | timestamp/null | Latest provider observation attempt represented by the row. |
| `provider_last_seen` | timestamp/null | Latest provider observation that considered the server present/online. |
| `validation_status` | enum | `online`, `offline`, `failed`, `unverified`; result of the latest direct validation attempt. |
| `validation_checked_at` | timestamp/null | Latest direct validation attempt, successful or failed. |
| `validation_seen_at` | timestamp/null | Latest successful direct validation. |
| `validation_error_code` | string/null | Stable category such as `timeout`, `dns`, `refused`, `invalid_response`; avoid exposing unstable raw exception text as contract. |
| `freshness` | enum | `live`, `recent`, `stale`, `offline`, `unverified`, computed at publish/request time from explicit aging rules. |
| `freshness_expires_at` | timestamp/null | When the current class will age if no new observation arrives. |
| `data_updated_at` | timestamp | Latest material change to the merged public row. |
| `sources` | list/string | Upstreams contributing to the canonical row. |
| `required_mod_count` | integer/null | Known count only; null is unknown and must never become zero by coercion. |
| `quality_flags` | list/string | Stable advisory flags. |
| `ranking_score` | integer | Server-side ordering input, documented as advisory rather than truth. |

Response metadata should include:

```json
{
  "contract_version": 1,
  "generated_at": "2026-07-12T12:00:00Z",
  "validation_policy": {
    "live_for_seconds": 1800,
    "recent_for_seconds": 21600
  },
  "coverage": {
    "eligible": 40000,
    "validated_live": 2500,
    "validated_recent": 9000,
    "unverified": 22000,
    "oldest_ready_candidate_age_seconds": 7200
  }
}
```

## Freshness semantics

The current WolfAPI implementation treats any non-empty `live_last_seen` as `live` indefinitely. That must be corrected before WolfLauncher relies on it.

Recommended deterministic policy:

1. `offline` when the latest completed direct validation confidently reports offline according to a defined failure threshold/policy.
2. `live` when `validation_seen_at` is within `LIVE_FRESHNESS_SECONDS`.
3. `recent` when a provider or successful validation observation is within `RECENT_FRESHNESS_SECONDS`.
4. `stale` when an observation exists but exceeds the recent window and remains inside retention.
5. `unverified` when no meaningful observation timestamp exists.

A timeout is not automatically proof of offline. Keep `validation_status="failed"`, retain the last successful `validation_seen_at`, expose the failed `validation_checked_at`, and let freshness age normally.

## Identity and deduplication contract

The existing `ip:game_port:query_port` key is useful but corrections can produce a second identity. WolfAPI should provide one of:

- a stable database-generated `server_id` plus current endpoint fields and endpoint aliases; or
- a canonical-ID redirect/alias map when ports are corrected.

WolfLauncher must key favourites/cache promotion against the stable ID when available while retaining endpoint fallback for old API rows. API publish and provider merge tests must prove that a live port correction updates one canonical server instead of creating two public rows.

## WolfAPI implementation breakdown

### Required-mod metadata

WolfAPI should run a separate bounded metadata job for required-mod information instead of forcing every launcher to query every server. List rows need nullable `required_mod_count` plus metadata status/checked/expiry fields; a versioned server-mod detail endpoint can return Workshop IDs and names. Unknown must remain null, while zero is accepted only from a successful explicit empty manifest.

Prioritize live/recent modded and recently requested servers, cache successes, retain the last success as stale after a failed refresh, and apply cooldown/global budgets. Do not synchronously fetch manifests inside `/api/servers` and do not sweep the full retained directory every cycle. WolfLauncher retains direct lookup for selected-server and final join truth.

The matching detailed backend design and full launcher-facing enrichment inventory are in WolfAPI `DISCOVERY_FRESHNESS_CONTRACT.md`.

### Phase A — contract correctness

- Add failing tests demonstrating that old `live_last_seen` values age out of `live`.
- Split provider observation fields from validation fields.
- Add `validation_status` and stable error categories.
- Compute `freshness_expires_at` and response `generated_at`.
- Ensure Redis ingestion, Postgres persistence, backfill and Postgres-to-Redis recovery preserve every contract field.
- Add golden JSON contract fixtures for legacy `/api/servers` and `/api/v1/servers`.

### Phase B — validation scheduler quality

- Move validation out of the FastAPI request process before materially increasing throughput.
- Use bounded concurrency; current validation iterates candidates sequentially.
- Maintain separate queues/budgets for never validated, previously live, recently failed and stale rows.
- Prevent one large retained directory from taking days to revisit popular/recent rows.
- Record queue lag, candidate age, duration and outcome categories.
- Keep cooldown/backoff for failures and global probe budgets.

### Phase C — public serving

- Add `/api/v1/servers` with pagination, stable sort and filters for freshness/quality/source.
- Add ETag/`If-None-Match` or `Last-Modified` so unchanged launcher refreshes are cheap.
- Default ordering should favour unflagged live/recent rows without hiding inspectable stale rows.
- Keep `/api/servers` backward compatible.

### Phase D — optional demand signals

Only after the scheduler is stable, consider a heavily rate-limited validation-request endpoint for selected servers. It must deduplicate requests, enqueue rather than probe inline, prevent arbitrary UDP scanning, and never be required for launch.

## WolfLauncher implementation breakdown

### Two-stage search is a core requirement

The initial API page is only the default view; it must not limit what players can find.

1. Search SQLite immediately on every edit for responsive offline/local results.
2. After a 300–500 ms debounce and a sensible minimum query length, search WolfAPI's complete canonical directory.
3. Ignore/cancel superseded requests and limit remote results to roughly 25–50.
4. Merge returned rows into SQLite by stable `server_id`, then endpoint fallback for legacy rows.
5. Label/handle three outcomes separately: found locally, found remotely, and not found remotely.
6. Distinguish “not found” from “remote search unavailable”; API failure must not imply the server does not exist.
7. Support exact host/game-port/query-port resolution for advertised servers and keep **Add server manually** as the final fallback.

Required API shapes:

```text
GET /api/v1/servers/search?q=&limit=&cursor=
GET /api/v1/servers/resolve?host=&game_port=&query_port=
```

Remote search must be indexed in Postgres or a dedicated search index. Scanning/deserializing the complete Redis JSON payload per keystroke is not acceptable. Cache repeated queries, apply public rate limits and use ETags where useful.

### Phase 1 — additive parsing

- Extend `DiscoveredServer` and SQLite with the stable ID, provider timestamps, validation status/timestamps, freshness expiry, quality flags and data update timestamp.
- Accept absent fields from old WolfAPI without changing current behaviour.
- Preserve unknown/null distinctly from false/zero/empty.
- Add fixtures covering legacy, partial v1 and complete v1 rows.

### Phase 2 — honest presentation

- Replace the coarse `PROVIDER ONLINE` label with compact status derived from the contract: `Live`, `Recent`, `Stale`, `Offline`, `Unverified`.
- Show “validated X ago” and provider-source detail in tooltips/details.
- Keep ping blank until locally measured; API validation does not equal player latency.
- Add freshness filters only after contract fixtures are stable.

### Phase 3 — stop fixed startup polling

- Put the current automatic first-30 enrichment behind a temporary compatibility setting/feature flag.
- When a response has a supported contract version and usable freshness coverage, do not start the fixed batch.
- Retain local checks for **Inspect mods**, **Launch**, explicit **Check now**, and possibly the currently selected row.
- Continue serving the SQLite snapshot when WolfAPI is unavailable.

### Phase 4 — remove compatibility polling

- Remove the fixed startup batch after one release cycle of production contract validation.
- Keep bounded manual enrichment as diagnostics/fallback, not the normal browsing path.
- Document the external distinction: WolfAPI reachability/freshness is directory truth; local launch checks are join truth.

## Acceptance criteria

### API

- A successful validation older than the live window is no longer classified `live`.
- A timeout records a failed attempt without erasing the last success or falsely declaring offline.
- Port correction does not produce duplicate canonical rows.
- Redis, Postgres and recovery publish produce contract-equivalent rows.
- `/api/health` exposes validation coverage, queue lag and outcome counts.
- Validation jobs remain bounded and the HTTP API stays responsive.
- Required-mod metadata distinguishes unknown, confirmed zero, stale and failed states and never blocks list serving.

### Launcher

- With a healthy v1 response, opening Server Browser performs no automatic per-server UDP polling.
- Rows remain useful offline from SQLite with their captured timestamps.
- Old API responses still load and retain the current compatibility path.
- A server outside the initial page can be found through remote name search or exact endpoint resolution and cached locally.
- “No remote result” and “remote search unavailable” are distinct tested states.
- Unknown freshness/mod counts remain visibly unknown.
- Selecting or launching a server still performs the safety-critical local work already required by those flows.
- No provider/API outage blocks curated servers or launcher startup.

## Rollout and test checkpoint

1. Implement and deploy WolfAPI contract correctness with legacy compatibility.
2. Observe production freshness aging and validation coverage for at least several scheduler intervals.
3. Capture real `/api/v1/servers` fixtures in WolfLauncher tests.
4. Enable contract-driven presentation while retaining startup polling as fallback.
5. Disable fixed polling only for supported/healthy contract responses.
6. Run desktop/offline/slow-API tests.
7. Remove fixed polling after the fallback has proven unnecessary.

This sequence is intentionally additive. WolfLauncher must never require a simultaneous WolfAPI deployment to remain usable.
