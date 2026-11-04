# Further launcher performance opportunities — 4 November 2026

Review of development source at `aed2fa4` on `dev/release-preparation`.
This records the assessment before implementation, not a release claim.
Priorities 1–3 were subsequently approved and implemented; see
[the follow-up evidence](DEVELOPMENT_FOLLOWUP_2026-11-04.md#further-performance-work-review-priorities-13-implemented). The remaining four areas subsequently received source improvements as well;
see [their implementation and measurements](DEVELOPMENT_FOLLOWUP_2026-11-04.md#remaining-performance-review-areas--4-november-2026).
Existing PERF-01,
PERF-02 and gzip improvements documented in DEVELOPMENT_FOLLOWUP_2026-11-04.md
remain complete. No Steam/game action or public network request was performed.

## Recommended order

### 1. Deliver completed browser checks immediately

`workers.py:683` uses `executor.map()` and consumes results in input order.
Queries run concurrently, but a slow early query delays delivery of later,
already completed results. The optional browser freshness path uses this worker.
`StatusWorker` already demonstrates completion-order delivery with `as_completed`.

A local probe through the actual `ServerEnrichmentWorker.run()` patched only
`check_server`: the first check took 200 ms and the second 5 ms. The second
completed at 6.2 ms, but both progress signals arrived at 201.2 ms.
This reproduces delivery delay; it is not a measurement of real server latency.

Use a bounded future-to-original-server mapping and deliver completed futures.
Keep original cache-key association, cancellation, edition/filter generation
guards and accurate completed counts. Preserve final collection ordering if any
consumer relies on it. Verify a fast second result arrives while the first is
still blocked, and cancellation cannot apply late results.

### 2. Show required mods before their optional enrichment finishes

`ModWorker._check()` in `workers.py:164` serially performs local/server checks,
Workshop metadata, isolated live Steam state and optional PBO comparisons. Its
only result signal is emitted after that sequence. Unlike this path, the installed
library worker already provides a local snapshot before enrichment.

Publish an immutable initial snapshot of requirements/local presence with an
explicit checking state. Then deliver authoritative freshness/state results and
advisory hashes separately. Hash comparisons have a shared three-second budget;
that is a limit, not evidence that ordinary checks take three seconds.

Descriptions and images can arrive later. Published revision and live state
contribute to freshness and must retain their launch-readiness role. An early
local-presence snapshot must never enable Connect or imply that installed means
current. Do not make optional advisory hashing delay an otherwise verified join.
Preserve request ID, library, edition and endpoint ownership at every stage.

### 3. Share repeated Workshop metadata work and cancel superseded work

`fetch_workshop_metadata()` in `mods.py:210` batches IDs within one request, but
does not share metadata requests between server checks, installed-library loads
and dependency resolution. Existing library and dependency caches should be
preserved; this proposal addresses the common HTTP metadata layer.

Use a bounded cache for display metadata and coalesce overlapping in-flight
requests. Keep children/dependency completeness explicit. Cache eviction, failures
and refresh behaviour need tests. A cached description is suitable for immediate
display; an old published revision must not become current launch evidence.
Explicit rechecks and post-download verification still need fresh evidence.

The metadata wrapper also does not forward cancellation, although
`post_form_json()` accepts it. ModWorker checks interruption between phases,
so a superseded request can occupy one of its bounded worker slots while the
metadata call finishes. Carry cancellation/deadlines through the complete chain.
The existing HTTP cancellation hook does not itself interrupt every blocking
socket read; describe and measure the resulting cancellation latency honestly.

### 4. Reduce mod-table and download-progress presentation work

Both `_display_mod_rows()` (`mods_feature.py:438`) and `display_mods_result()`
(`:670`) rebuild cells and call `resizeColumnsToContents()`. The browser already
avoids that repeated content sizing. Apply stable sizing to short fixed-format
columns, retain the stretch name column and user resizing, and update changed
cells rather than rebuilding an unchanged library after metadata arrives.
Batch painting with exception-safe restoration and preserve selection, sorting,
keyboard access, scaling and scroll position.

`update_mod_progress_rows()` (`:1320`) scans every row each snapshot and performs
a linear search of the snapshots for every matching mod. Index snapshots by ID,
update changed visible values, and coalesce intermediate presentation updates
when the UI is busy. Always process terminal state, callbacks and cancellation
promptly. Keep monitoring active while hidden. A delegate for progress is a
possible later refinement if profiling justifies replacing progress widgets.

This improves responsiveness during downloads. Steam remains responsible for
content transfer. The source already requests priority downloads for forced
updates; this review establishes no further transfer-rate improvement. Retain
isolated helpers, single-session ownership, completion callbacks and revalidation.

### 5. Keep browser queries and unnecessary refreshes off the interaction path

`refresh_server_browser()` (`server_browser_feature.py:1662`) synchronously
rebuilds filter options, loads a snapshot and rebuilds the table. Filter options
issue three DISTINCT queries. The snapshot additionally retrieves rows, counts
matches and computes summary aggregates (`server_browser_controller.py:33`).

Cache filter options and summaries by actual relevant mutations and edition.
Use a worker-owned SQLite connection for search/snapshot work if end-to-end
profiling supports it. Apply only the latest query/filter/edition generation,
retain the displayed snapshot while waiting, and keep count/row consistency.
Diff unchanged result rows before repopulating. Preserve substring/alias matching;
changing search semantics merely to use a faster index would reduce quality.

The current browser table improvements already have strong benchmark evidence.
A complete model/view replacement should remain conditional on packaged scrolling,
large-result and accessibility measurements.

### 6. Reuse thumbnail previews

`update_mod_detail_card()` calls `load_mod_thumbnail()` on each update.
`mods_feature.py:795` aborts the previous reply, clears the image and starts a GET,
including when the same URL is requested again. No explicit image cache is
configured in this path.

Keep a small byte-bounded cache of validated scaled previews and reuse an active
same-URL request. Preserve the current URL/content/size checks and revision or
expiry refresh rules. Probe decoding/scaling on the GUI thread before deciding
whether it also needs worker-side image decoding. Expected gain: less flicker
and faster revisiting of mods; no measured network savings are claimed here.

### 7. Avoid rescanning the entire library for every selected server

`check_server_mods()` (`mods.py:558`) calls `scan_installed_mods()` before querying
the server, unless provided a scan. That enumerates every numeric Workshop
directory and reads each `meta.cpp`. Experimental adds its official-launcher
junction mapping. This work repeats across checks even when servers share mods.

Consider a library-scoped name/index cache for presentation, with a required-ID
check on the authoritative launch path. Invalidate for Steam activity, changed
manifests, explicit rechecks and library/edition changes. Recheck required paths
at launch. Preserve Experimental path precedence and installed-count meaning.
Measure cold/warm disks before choosing the complexity of incremental scanning.

## Local measurement scope

Additional probes used the existing `.venv`, Linux offscreen Qt, the application
theme and a 1200×600 table. Five-sample medians, synthetic records only:

| Installed mods | Populate table and process events | Separate content-resize call |
| --- | --- | --- |
| 200 | 12.10 ms | 2.93 ms |
| 500 | 25.82 ms | 7.24 ms |
| 1,000 | 49.57 ms | 14.32 ms |

The harness called the real `_display_mod_rows()` with filtering and the detail
card stubbed out. Population includes its existing resize; the separate resize
column is a second standalone call and cannot be subtracted as an exact predicted
speedup. It does not include real thumbnail/network or full-window layout work.

A temporary SQLite database held 10,000 synthetic Stable rows using the normal
schema/upsert path. Five-sample warm-cache medians with a 1,000-row result cap:

| Search | Filter options | Snapshot: rows, match count and summary |
| --- | --- | --- |
| Empty | 5.18 ms | 30.71 ms |
| `Server 050` | 5.04 ms | 30.02 ms |
| `not found` | 4.93 ms | 25.70 ms |

These identify GUI-thread work, not a claim of visible freezing in ordinary use.
Temporary probes were kept outside the repository. No production implementation
was changed and no full regression-suite result is claimed for this review.

## Evidence needed for implementation

Start with completion-order results, then staged mod presentation and shared
metadata work. Record time to first useful result and time to verified readiness
separately. Follow with end-to-end filter latency, event-loop stalls, metadata
request counts, cancellation latency and download-progress presentation cost.
Use cold/warm runs and realistic library sizes; retain slow-provider and failure
cases. Report median and tail latency without treating advisory display as
verified readiness. Native Windows and current packaged Linux measurements remain
required before claiming consistent improvement across supported builds.
