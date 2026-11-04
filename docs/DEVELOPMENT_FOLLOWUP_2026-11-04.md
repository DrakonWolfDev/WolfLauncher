# Development follow-up — 4 November 2026

Work remains on `dev/release-preparation`, pushed directly without a PR. This
record separates local evidence from future native builds and release checks.
No version change, release publication, API deployment, Steam/game launch,
Workshop download or system configuration change was performed.

## PERF-01 and PERF-02: preserve the measured improvements

The existing table optimisation and optional-polling ownership logic were already
implemented. They were not reopened as a model/view rewrite.

Linux measurements use Python 3.12.3, PySide6/Qt 6.11.1, the application theme,
a 1200×600 offscreen table and five-sample medians. Baseline table code comes
from `1b31437`; both implementations use the current presenter, including queue
labels. Synthetic records only; these measure UI work, not query latency.

| Rows | Population baseline / current (ms) | 50 enrichments (ms) | 50 mod previews (ms) |
| --- | --- | --- | --- |
| 200 | 77.37 / 28.02 | 59.73 / 15.67 | 40.35 / 3.59 |
| 500 | 193.42 / 69.41 | 132.66 / 17.79 | 99.51 / 4.14 |
| 1,000 | 436.71 / 129.58 | 237.27 / 16.84 | 199.03 / 3.71 |

Separate fresh processes at 1,000 rows measured RSS before population and the
largest of five post-population RSS samples using `/proc/self/status`:

| Implementation | Before (KiB) | Populated (KiB) | Difference (KiB) | Descendant widgets |
| --- | --- | --- | --- | --- |
| Baseline | 75,100 | 161,796 | 86,696 | 2,018 |
| Current | 75,048 | 96,388 | 21,340 | 18 |

RSS includes Qt/native allocations and allocator retention. It is not Python-only
memory, a continuously sampled peak, or a packaged/full-window memory claim.
The benchmark now accepts `--rows` and reports these RSS samples. Reproduce each
memory comparison in its own process:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/benchmark-server-table.py --rows 1000 --revision 1b31437
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/benchmark-server-table.py --rows 1000
```

A full model/view migration is not justified by this evidence. Packaged scrolling,
scaling and real-play background-work measurements remain useful release checks.
Existing PERF-02 pause/resume regression coverage remains intact.

## API-02: use existing compression before introducing a new contract

Both discovery truth documents and the producer source were inspected. WolfAPI
already implements gzip and representation ETags/304 responses. The launcher
previously requested plain JSON without negotiating gzip.

A bounded public read of `/api/v1/servers?limit=500&offset=0&product=stable` on
4 November returned 500 rows, 968,784 decoded bytes and 77,829 gzip bytes: about
92% fewer body bytes. An immediate request with its ETag returned 304 and no
body. This is one sample, not a cache-hit-rate or latency benchmark. The completed client also
retrieved 500 rows through its normal parser with Stable edition isolation intact.

JSON requests now advertise gzip and decode within the existing wire and decoded
size limit. Invalid/truncated/trailing gzip, unsupported encodings and compressed
expansion beyond the limit fail cleanly. Cancellation is rechecked after reading.
TLS, endpoint/filter/edition isolation, response parsing and timestamps retain
their existing semantics. Four new regressions exercise these boundaries.

A lossless-style array projection estimated 69,660 gzip bytes; this is modest
compared with the initial compression gain and requires a new schema. A
counts/status-only projection estimated 15,015 gzip bytes, but omitted directory
fields and is **not** a valid replacement response. This list contains mod counts,
hashes and metadata state, not full mod lists; a shared mod table would not remove
a repeated inline mod manifest from this endpoint.

Conditional client persistence and new delta/count endpoints are deferred. Their
contract must specify generation IDs, age after 304, deletions/tombstones,
retention, moved endpoints and edition-specific identities. A 304 must not reset
observation timestamps or make expired validation live. Gzip needs no producer
change or deployment; no API repository source was changed.

## PLATFORM-01: packaged loader environment reproduction and source fix

The existing `WolfLauncher-0.9.3.5b-x86_64.AppImage` was run with temporary XDG
config/data, a local query stub and automatic directory refresh disabled. No
Steam/game was launched. The stub recorded only loader paths and a system Python
child's SSL library paths/version; it did not dump the environment.

The host `/usr/bin/python3` child inherited PyInstaller's `_internal` loader path
and loaded the AppImage's OpenSSL 3.0.2 libraries. Restoring the original loader
path made it load the host's OpenSSL 3.0.13 libraries. Both probes exited normally;
this proves library leakage, not a reproduced Steam crash. The packaged startup
smoke exited 0. A [minimal recorded probe](evidence/2026-11-04-appimage-environment.json)
retains the artifact hash and allowlisted output with the extraction path normalised.

The source now constructs a child-only environment for frozen Linux host
handoffs: restore `LD_LIBRARY_PATH_ORIG`, remove bundled PATH/Qt entries and
preserve host overrides, display/session variables and selected-prefix settings.
Steam startup, game/fallback launch dialogs, local server/SteamCMD processes,
host diagnostics and desktop URL handoffs use this boundary. Bundled GameDig,
its Node runtime and the launcher's own process keep their existing environment.
Source runs and Windows retain their existing platform behaviour.

Eight environment tests cover restored/unset loader paths, host-variable
preservation, source/Windows behaviour, Qt process configuration, desktop failure
and detached startup. A real harmless QProcess child confirms it receives the
clean environment. That integration check caught PySide's instance overload
returning a bool instead of the static overload's tuple; both forms are handled.
No global environment mutation or platform DLL-search change is introduced.

This follows [PyInstaller's external-program guidance](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application).
The existing AppImage was used for reproduction; it has not acquired the source
fix. A fresh native package and actual Steam/browser handoffs remain required.
The external fallback launcher continues to require its documented host tools;
bundled tool paths are not injected into host Steam or desktop programs.

## PLATFORM-02: read-only Linux memory-map health

Settings' Linux compatibility group now reads `/proc/sys/vm/max_map_count` and
compares it with the community DayZ/Proton recommendation of 1,048,576. Lower
values warn; unreadable/malformed values remain unknown; Windows does not read
this Linux file. This never blocks joining or writes a sysctl.

The number is a compatibility recommendation, not an independently proven minimum
for every DayZ version. The [upstream CLI launcher's requirements](https://github.com/bastimeyer/dayz-linux-cli-launcher#requirements)
and [Fedora's compatibility change](https://fedoraproject.org/wiki/Changes/IncreaseVmMaxMapCount)
identify DayZ and this value. The [kernel documentation](https://www.kernel.org/doc/html/latest/admin-guide/sysctl/vm.html#max-map-count)
defines the per-process memory-map limit. The UI uses that qualified language;
meeting it alone does not establish game compatibility. Three new tests cover
low/high/invalid/missing reads and platform/group integration.

## BUILD-01: build-time provenance and bundle inventories

AppImage and Windows portable builders now capture source and tool inputs before
compilation and verify that source still matches at completion. A JSON sidecar
records Git commit, dirty state, all nonignored source-file hashes, dependency
lock/spec/script inputs, Python/package versions, supplied tool executable hashes,
artifact size/SHA-256 and the relative bundle inventory. Bundle file permissions
and relative symlinks are recorded; escaping/broken/absolute symlinks are rejected.
No environment dump, credentials or absolute checkout path is included.

The installer workflow retains these sidecars. Its tag-only publication gate
checks artifact hashes, the expected source commit and a clean source snapshot
before the existing release step. This session did not invoke that workflow.

The existing AppDir inventory was also checked: 1,085 entries including 30 valid
relative symlinks, without attributing that older build to current source.

Five new tests cover artifact/bundle tampering, changed/added/deleted source during
a build, honest dirty-development metadata, ignored build output, symlinks and
release commit/cleanliness gates. See [usage and limitations](BUILD_PROVENANCE.md).
Native Windows/PowerShell and complete current AppImage builds remain unexecuted;
PyInstaller is absent from this source environment. Existing local artifacts were
not relabelled with current-source provenance. Setup/DEB/RPM/wrapper-specific
inventories and independent signed attestations remain follow-up work.

## QUALITY-01: simulated guarded join integration

Five new tests traverse the real identity coordinator, worker bodies, preflight,
mod inspection and native command builder. External queries/discovery are test
fixtures; the process handoff is recorded instead of executed. The flow starts
with a validated shared-link endpoint and covers stopped Steam becoming ready,
cancellation before a late callback, a conflicting game port, malformed mod
requirements and an unpublished requirement that must not trigger a download.
No production injection flag or arbitrary-command helper was added.

The source suite covers 971 tests: **964 passed, 7 skipped** on Linux. Required
Ruff lint/formatting, compilation, shell syntax, workflow YAML and whitespace
checks pass. These are source/local checks, not a native release certification.

## Remaining list items

- **BACKLOG-07:** optional LAN discovery remains a separate product addition.
  Direct LAN joining is already implemented and user-tested. Interface/custom-port
  coverage and a real discovery fixture are still absent; no broadcast sweep was
  run against the user's network while they were away.
- **BACKLOG-08:** localisation still needs deliberate language choices and a
  translation/review workflow. No guessed translations or partial catalogue added.
- **UPDATE-01:** signed installable updates remain a separate design decision.
  Signing authority, artifact verification, version/rollback policy and atomic
  replacement need agreement; the existing notification updater remains in place.
- **SUPPORT-01:** existing explicit, redacted launch/diagnostic reports remain the
  starting point. A broader support-data collection flow has not been justified.
- **REL-02/API-01:** the earlier missing camera-settings evidence and exact
  remembered alert identity remain unresolved; neither was guessed.

The next useful unattended work is extending provenance to wrapper/native package
formats and validating rebuilt Linux artifacts in isolation. Native Windows,
real Steam/DayZ joins and the previously documented release checks remain needed.

## Further performance work: review priorities 1–3 implemented

Andi approved the first three items in
[the source performance review](PERFORMANCE_REVIEW_2026-11-04.md). The other
opportunities remain candidates; this work does not reopen PERF-01, PERF-02 or
the completed gzip change.

**Completion-order browser results.** `ServerEnrichmentWorker` now delivers each
finished query immediately, preserving its original server/cache-key association
and completed count. Its final aggregate retains input order. Cancellation
suppresses late progress and final result delivery. The existing eight-query
concurrency cap and endpoint/edition guards remain in place.

The same local two-query probe used for the review simulated a 200 ms first
query and a 5 ms second query. Before: the fast query completed at 6.2 ms and its
progress arrived at 201.2 ms. After: it completed at 6.1 ms and its progress
arrived at 6.2 ms, while the slow reply arrived at 201.2 ms. These demonstrate
delivery latency, not public server/network performance. An event-gated
regression requires the fast reply to arrive before releasing the slow query.

**Staged required-mod results.** The coordinated inspector shows a copied
requirements/local-presence snapshot before HTTP metadata and live Steam state
finish. Rows and the heading explicitly say readiness is being checked. Cached
display fields may supply names/descriptions/previews, but never cached revision
timestamps or installed-state evidence. The displayed snapshot is separate from
the launch cache; checking results are rejected by cached preflight and command
preparation. Workshop resolution/force-update controls stay disabled while checking.

Completed readiness can reach launch continuations before optional PBO advisory
comparisons finish. The advisory completion never runs the same continuation
twice, revokes readiness merely because an advisory read failed, or replaces a
newer check/Steam progress snapshot. Generations reject superseded queued signals;
request, installation, edition and endpoint checks remain active. Staged refreshes
reuse the existing mod-table population helper to preserve selected mod, sorting
and scroll. Live manifest, state, completion and post-download checks remain.

**Shared metadata requests.** A process-local broker shares overlapping requests
by public Workshop ID and children/dependency completeness. Identical concurrent
requests use one HTTP load; partially overlapping batches share the repeated IDs.
Authoritative calls always obtain live HTTP evidence rather than completed cached
revisions. Explicit forced rechecks and forced-update revision capture bypass
older in-flight requests. Steam revision acknowledgements remain installation-
and edition-scoped; public display metadata cannot bless another library.

HTTP batches contain at most 100 IDs, at most four HTTP loads run concurrently,
and at most 400 owned item requests are active. The display cache retains at most
512 entries and 8 MiB of encoded field payload for five minutes. Results are
copied between callers. Missing/error responses are not cached as successes.
Followers can cancel independently; a cancelled owner releases followers to
retry. Mod-worker cancellation reaches HTTP admission/read checks and shared
request waits. An active blocking socket operation can still wait for its existing
timeout; this is not a claim of immediate cancellation throughout network I/O.

Validation: **990 tests run / 983 passed / 7 skipped**, including **19 new
regressions** for completion order, staged ownership, real Qt table selection,
early-result launch exclusion, stale advisory results, cancellation, forced
rechecks, metadata sharing, limits, expiry and failure recovery. The sandbox
initially denied the suite's local IPC/TLS sockets; the final complete run passed
with those local sockets available. No public live query, Steam/game action or
Workshop transfer was needed for these checks.

Ruff 0.15.22 lint/formatting, hardened-boundary mypy, compilation and whitespace
checks pass. The release-lock dependency audit reports no known vulnerabilities.
The type check exposed an existing Qt enum alias absent from the installed
stubs; host URL handling now uses the equivalent fully qualified enum member,
with its existing environment/handoff regressions passing.

Source completion is verified locally. Current packaged Linux, native Windows
and real Steam/DayZ validation remain pending. No version change, build, tag,
release publication, public-link change or API deployment was performed.

## Remaining performance review areas — 4 November 2026

Andi requested continuation through as many of the remaining improvements as
practical. All four suggested areas now have bounded source improvements.

### Thumbnail reuse

The mod inspector reuses the same pending URL/revision request and validated
cached previews. Returning to a mod avoids clearing/refetching its image while
the entry is valid. Published revision changes and five-minute expiry require a
new request. Cache entries retain original validated images so rendering at a
different inspector size need not magnify an already downscaled thumbnail.
The cache is limited to 32 entries and 16 MiB of decoded pixel storage estimates;
this is not a process-RSS bound.

Original/final HTTPS URL checks, raster MIME checks, transfer limits and timeout
remain. Reply buffering is limited, image dimensions are checked before decoding,
and the detected format must also be PNG/JPEG/WebP. Bad responses are not cached.
Changing selection aborts obsolete requests, whose late replies cannot repaint
another mod. No persistent disk cache or speculative image prefetch was added.

### Incremental mod tables and download progress

Rows retain native table items when their presentation is unchanged. Metadata
updates alter affected cells, preserve selection/sort/scroll, and retain user
column widths. Published IDs and separate local-requirement identities keep rows
associated with their contents. Short columns use representative text sizing;
the name stretches and full cell text remains available in tooltips. Population
restores signal, paint and sorting state even if an update raises an exception.

Progress snapshots are indexed once by ID, removing the per-row linear snapshot
search. Unchanged text, values and progress widgets are reused. Sorting is paused
only when a change requires it, preventing moving rows from mixing item updates.
Terminal states remove completed progress overlays. All Steam state/callback
processing remains immediate; no terminal updates or cancellation events are
dropped, and this makes no claim to increase Steam's content-transfer rate.

### Browser filtering outside the GUI thread

The application loads SQLite browser snapshots through one cancellable worker
with one latest pending query. Each worker owns a read-only connection and uses
one read transaction for filter options, result rows, match count and summary.
Cancellation reaches SQLite's progress handler; lock waits have a 100 ms timeout.
The main thread applies only matching query/filter/edition generations against
an unchanged database token. It keeps the displayed rows while a same-edition
query runs; edition changes clear the previous edition's rows immediately.

Filter options and edition summaries are reused only while the database token
is unchanged. Main-connection writes, external commits and transaction-state
changes invalidate reuse. Disappearing options trigger a query for the resulting
controls. Pending live freshness checks wait for the applied rows before resuming
their existing bounded batches. Shutdown cancels and waits for the worker through
the existing lifecycle coordinator. In-memory fixtures retain a direct path.
Substring/alias matching, provider freshness timestamps and live evidence rules
are unchanged; no database schema or API contract changed.

### Less repeated Workshop name work

Server checks first obtain the manifest, freshly enumerate numeric directories
with `scandir`, and read names only for required IDs. Total installed counts stay
accurate without reading every unrelated `meta.cpp`. Failed server queries still
report the installed count without reading mod names. Full library/Experimental
views reuse names only when their path and current device/inode/size/mtime/ctime
match, and validate identity again after a file read. The thread-safe name cache
retains at most 1,024 names, each at most 8 KiB of encoded value. Missing files,
changed/replaced content and concurrent edits cannot reuse an old identity.

This is a display-name cache and targeted scan, not a cached claim that a mod is
installed/current. Directory presence is still enumerated on each check; native
launch path checks, selected-library revision/state checks and Experimental's
official-launcher path precedence remain. A persistent directory index would need
additional cross-platform invalidation evidence and was not introduced.

### Measurements and validation

`scripts/benchmark-mod-table.py` records five-sample medians for initial
population, unchanged refresh and a one-row size change, including event
processing. Linux offscreen Qt, application theme, 1200×600 table and synthetic
mods only; filtering/detail-card work is stubbed. The baseline method is loaded
from `ccf2a55` while using the same current presenter and dependencies:

| Rows | Initial baseline / current (ms) | Unchanged baseline / current (ms) | One changed baseline / current (ms) |
| --- | --- | --- | --- |
| 200 | 23.82 / 15.02 | 17.67 / 4.90 | 17.69 / 5.12 |
| 500 | 39.41 / 33.32 | 38.78 / 7.85 | 39.72 / 7.77 |
| 1,000 | 73.10 / 61.78 | 66.14 / 12.13 | 67.38 / 12.65 |

Reproduce in separate processes:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/benchmark-mod-table.py --revision ccf2a55
QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/benchmark-mod-table.py
```

These timings are not packaged scrolling, disk, network or end-to-end join
benchmarks. Deterministic regressions also verify one GET for repeated pending/
cached thumbnails, no item allocations for unchanged mod rows, and one name-file
read for a server requiring one item from a ten-mod library. No live server,
Steam/game or Workshop action was needed.

Final Linux verification: **1,013 tests run / 1,006 passed / 7 skipped**, including
**23 new regressions** for these changes. Required Ruff lint/formatting, hardened
core type checks, compilation and whitespace checks pass; the release-lock
dependency audit reports no known vulnerabilities. Packaged Linux, native Windows,
high-DPI/manual accessibility and real Steam/DayZ checks remain distinct follow-up
evidence. No package build, version bump, tag, release publication, public-link
change or API deployment was performed.
