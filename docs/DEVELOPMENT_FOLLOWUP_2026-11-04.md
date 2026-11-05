# Development follow-up — 4 November 2026

Work remains on `dev/release-preparation`, pushed directly without a PR. This
record separates local evidence from future native builds and release checks.
The initial source pass made no version/release/API or Steam/game changes.
Later sections separately record authorized native and live Steam/DayZ checks.

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

## Isolated Linux package validation — 4 November 2026

Andi approved the next step of building and validating an isolated Linux package.
The AppImage was rebuilt from clean source commit
`292f1b734f2f01538571844e423724c304493cbd` in a separate temporary checkout.
Original repository artifacts were preserved. The version remains `0.9.3.5b`;
this is a local development artifact, not a newly published release.

The temporary environment installed the hash-locked release runtime and pinned
PyInstaller 6.21.0/hooks 2026.6. Cached checksum-pinned AppImage/Node tools and an
npm cache populated from the lockfile allowed the entire build, including its
basic packaged startup smoke, to run without network access. No dependencies or
build tools were installed into the launcher's source virtual environment.

An opt-in extension to the existing smoke mode now exercises synthetic UI flows
inside the actual frozen application. The runner creates private temporary XDG,
`/tmp`, process and network namespaces; private `/tmp` is needed to isolate Qt's
single-instance socket as well as settings. It rejects ordinary user-data paths
before inserting fixtures. See [usage and exact boundaries](ISOLATED_LINUX_VALIDATION.md).

Both final AppImage runs exited normally with all checks passing:

| Qt scale | Browser rows | Mod rows | Extract/run/check/close wall time |
| --- | --- | --- | --- |
| 1× | 1,000 Stable, then 10 Experimental | 200 | 2,080 ms |
| 2× | 1,000 Stable, then 10 Experimental | 200 | 2,219 ms |

Checks cover rapid latest-query replacement, edition separation, browser
scroll/selection, unchanged mod-item reuse, retained mod selection, cached
synthetic preview rendering, bundled Node `v20.20.2`/GameDig availability and
normal shutdown. The frozen launcher handed off a harmless system-Python child,
which loaded host OpenSSL 3.0.13 without bundled `_internal` SSL libraries.
This supplies actual frozen-runtime evidence for the earlier host-environment fix.

Screenshot inspection found the Size column clipping "Unavailable". Its initial
width now uses the actual monospace font and the unavailable label, while still
avoiding content-wide sizing. A regression and the packaged check assert that
fit. The package was rebuilt and both scale runs repeated after that correction;
the initially validated artifact was preserved separately rather than relabelled.
The corrected 1× screenshot was inspected; 2× also passed its fit assertion.

The final artifact is **109,693,432 bytes**, SHA-256
`66648af87c9ec2fed3393b7029486e99c38f7988c78518b174b09caa9b49fbfa`.
Provenance verification passed for the full expected commit, a clean source
snapshot, the artifact hash and **1,111 staged bundle entries**. This is unsigned
build evidence, not an independent publisher signature or byte-reproducibility
claim. [Minimal retained evidence](evidence/2026-11-04-isolated-linux-package.json)
records the toolchain, source/artifact/manifest hashes, results and screenshot
hashes without private runtime paths.

The private artifact and full sidecar remain under
`/tmp/wolflauncher-validation-checkout/dist/`. Final run logs/screenshots remain
under `/tmp/wolflauncher-package-ui-x7j3vc3v/` (1×) and
`/tmp/wolflauncher-package-ui-m4btk8ol/` (2×). These temporary paths can be removed
by system cleanup; the committed evidence records the completed checks.

Final source validation: **1,016 tests run / 1,009 passed / 7 skipped**. Three new
smoke/isolation/failure regressions and the Size-column fit assertions pass.
Required Ruff lint/formatting, core type checks, compilation and whitespace checks
pass; the release-lock dependency audit reports no known vulnerabilities.

The timings include extraction, fixture creation and synchronous validation work.
They are not cold-start, frame-rate or normal-use latency benchmarks. This proves
local offscreen extraction-and-run behaviour, not FUSE mounting, older distro
compatibility, native Wayland/X11 rendering, manual accessibility, native Windows
or actual Steam/Workshop/DayZ joins. Those remain open. No Steam/game/Workshop
action, installer execution, version bump, tag, publication, public-download change
or API deployment was performed.


## Resource soak and live Steam state — 4 November 2026

Andi authorized opening Steam/DayZ and confirmed Steam was open. Added repeatable
Linux source diagnostics in `scripts/soak-launcher.py` and
`scripts/check-live-workshop.py`; see [usage and boundaries](RESOURCE_SOAK_VALIDATION.md).
No application runtime behaviour changed in this batch.

Two accelerated offscreen source soaks passed: 300 cycles in 49.3 seconds and
600 cycles in 96.9 seconds. The longer run issued 1,800 explicit rapid browser
requests, alternated Stable/Experimental each cycle, refreshed 200 mod rows each
cycle and churned 1,200 unique 512×512 previews. The real snapshot loader handled
replacement/cancellation, with correct final edition/filter results. Mod item
identity and selection survived refreshes. Temporary data and private PID/network
namespaces prevented changes to everyday configuration or public queries.

At cycle 50/600, RSS was 204,728/215,984 KiB (about 200/211 MiB). The final ten
sampled checkpoints were identical at 215,984 KiB. Descendant Qt objects held at
940; threads fell from 13 to 11 and file descriptors from 21 to 19. Thumbnail
storage held at its 16 MiB pixel estimate (16 entries); the browser auxiliary
cache held two entries. Thresholds allow allocator/cache slack; this short,
accelerated scenario does not prove multi-hour leak freedom. A final 100-cycle
check verifies the added pre-initialization child isolation guard; direct child
invocation without isolated paths is rejected before application imports.

The production disposable Steam state helper queried 20 existing installed mods
three times: all returned ready (state 5), with no remaining multiprocessing
children. Initial timings were 74/75/70 ms; the repeatable diagnostic returned
72/78/76 ms. This is actual read-only Steam evidence, without a game launch,
subscription changes or requested downloads. Steam's own automatic activity was
not controlled. It does not verify download completion/cancellation or game joins.

Source checks: **1,016 run / 1,009 passed / 7 skipped**, required Ruff formatting/
lint, four core type boundaries, compilation, whitespace and release-lock audit.
Normalized [resource and Steam evidence](evidence/2026-11-04-resource-steam-validation.json)
retains samples without account IDs, item IDs or local library paths. Packaged
resource behaviour, native Windows, older Linux/FUSE, real downloads and real
DayZ joins remain open. No version bump, release/publication or API deployment.


## Native package provenance chain — 4 November 2026

BUILD-01 now extends to DEB, RPM, Windows Setup and the AppImage-backed Linux
installer archive. Native payloads are sealed before packaging and checked again
afterward. Wrappers bind verified parent artifact/manifest hashes; RPM and Setup
also compare the parent staged bundle. Full source snapshots must match, so a
same-commit dirty change or stale/replaced AppDir cannot silently acquire current
source provenance. The Linux archive compares its AppImage copy before sealing.
DEB includes control files/hooks; RPM includes its installed wrapper and notices.
CI retains sidecars and the existing tag-only gate checks native/wrapper artifacts
against the expected clean source before publication. No workflow was dispatched.

Four new regressions exercise sealed-input mutations/resealing, parent artifact/
manifest changes, stale bundles and same-commit source mismatch. Local native
build evidence will be recorded separately after clean-checkout validation.
See [provenance usage and assurance limits](BUILD_PROVENANCE.md). Windows build,
installation and removal remain pending on a native Windows runner. These are
unsigned build records, not publisher signatures or a reproducibility claim.

Source validation for this batch: **1,020 run / 1,013 passed / 7 skipped**;
required Ruff, core mypy, compile/whitespace, workflow YAML, ShellCheck and
release-lock dependency audit pass. Previous-commit CI has Windows test failures
now under investigation; local Linux success does not close those failures.


## Windows CI repair and native payload corrections — 4 November 2026

Inspection of [the previous Tests run](https://github.com/DrakonWolfDev/WolfLauncher/actions/runs/41921560643)
found the Linux quality/unit/DEB/RPM/AppImage jobs passing, while Windows failed
seven tests and errored in two before compilation. Repairs retain the assertions:
use native path separators/absolute paths for simulated Linux host-environment
checks, resolve Windows short/long temporary-path aliases, explicitly write the
non-ASCII malformed fixture as UTF-8, close the migrated SQLite database before
removing its temporary directory, use the existing bounded IPC event pump, and
supply the actual 18 browser headers in the dynamic-column fixture. A changed-file
fixture now also changes size so it does not depend on timestamp granularity.

The new-PBO failure also exposed a source boundary: Windows directory metadata
can lag membership changes. Advisory comparisons now re-enumerate the already
bounded directories before accepting a hash outcome, with the existing deadline,
entry caps and cancellation checks. A deterministic regression holds directory
metadata constant while adding a PBO and requires an unknown result. This adds
bounded directory work, not PBO body reads or a weaker readiness condition.

Initial clean native builds from 62b8916 produced AppImage/installer/DEB/RPM
sidecars. Independent extraction verified the installer archive and found exact
DEB bytes with a normalized control-file mode, plus RPM-generated build-ID links
outside the staged inventory. DEB now explicitly sets its control file to 0644;
RPM disables those generated links for its bundled runtime. Corrected builds and
Windows runner results must be recorded separately, without relabelling the
initial artifacts as newer source.

Local validation: **1,021 run / 1,014 passed / 7 skipped**, including the new
coarse-directory-metadata regression; affected groups, workflow quality checks,
shell syntax and the release-lock dependency audit pass. Native Windows success
is pending the next push-triggered runner.


## Activation delivery follow-up — 4 November 2026

The native Windows run at 13649a7 reduced the prior nine test problems to two.
Plain activation previously disconnected before receiving confirmation; unlike
shared-link IPC, it did not keep the sender alive until the primary received its
frame. Activation now uses the same bounded acknowledgement path as links, with
an activation-specific retry message if an older running instance does not
acknowledge. The server continues accepting the existing `activate` frame.
Tests use independent processes, matching real launches, and cover missing
activation acknowledgement. Shared-link parsing, limits and review remain intact.

The table fixture now also calls the actual `configure_data_table` helper, which
hides the row header and sets pixel scrolling. Its former default Qt row header
consumed space absent from the real browser; the zero-overflow assertion is
retained. No production column-width relaxation was introduced.

Linux source verification: **1,022 run / 1,015 passed / 7 skipped**; required
format/lint, core type checks, compilation and whitespace pass. Windows results
remain pending the next native run. Private Linux native artifacts remain tied
to their exact 13649a7 source; they are not relabelled as this newer IPC change.


## Native evidence, live checks and measured startup refinement — 4 November 2026

Clean private Linux builds from **13649a77a15026a3c0f5e2290bc9628472ac532e** now
pass independent extraction/inventory comparisons: AppImage (1,111 entries),
Linux installer archive (9), RPM (1,111) and DEB including controls (5,020).
DEB/RPM extracted startup smoke exits 0. Rebuilt AppImage extended UI/runtime
checks pass on actual X11 at 1×/2×, and both screenshots were inspected. At 2×
on this 1920×1080 desktop, the workspace requires horizontal scrolling; this is
not complete accessibility certification. A host FUSE mount exposed the launcher
and unmounted cleanly; this checks mounting only. Application tests used
extraction-and-run. Namespace FUSE could not use the host setuid helper and is
not claimed as an application failure. Local packages were not installed.
The artifacts remain under `/tmp/wolflauncher-native-final/dist/` and retain
their exact source identities; subsequent IPC/startup changes are source-only.
See [artifact hashes, inventories and normalized results](evidence/2026-11-04-native-package-validation.json).

A real Steam helper sequence on one existing subscribed/installed 1,596-byte
item observed pending state 37, then successful callback/idle state 5. Forced
completion took 575 ms; cancellation on a pending callback returned cancelled
and incomplete in 323 ms; retry completed in 574 ms. All helpers exited, and
final live state was ready. No subscription/unsubscription calls were enabled.
Reported transfer counters stayed zero: this is real no-byte completion/cancel/
retry evidence, not bulk-download or changed-content freshness verification.
DayZ launched through the open Steam session; the production detector observed
its game process after about 10.2 seconds. The main menu was visually verified,
then the normal quit flow was used and process exit confirmed. No target server
or mod arguments were requested. Andi supplied a Stable test endpoint after these checks; real join validation
follows separately.
See [live evidence and limits](evidence/2026-11-04-live-workshop-dayz.json).

Added a repeatable [controlled startup benchmark](STARTUP_BENCHMARK.md), keeping
instrumentation outside production. A profile identified repeated Editor/LAN
library scans during construction. Profile loading and target selection now
coalesce to one fresh picker scan; its summary reuses that dictionary within the
same redraw. Selection changes, subsequent refreshes and launch checks remain
fresh. A regression covers empty/saved profiles, preserved local selections,
exactly one construction scan and fresh changed names/removals on later refresh.

Five-sample source medians improved from **438.48 to 397.64 ms** construction and
**807.77 to 758.33 ms** to the first browser paint with 200 cached rows. The
fixture has 1,000 rows, with a reused temporary profile, optional polling paused
and network isolated. OS caches are not flushed; this is not packaged cold-start
or verified mod/server readiness evidence. Raw samples retain the runtime file
hashes and baseline commit rather than attributing an uncommitted refinement to
an older clean source snapshot.

The last native Windows run passes activation delivery and all but the dynamic
column test. Its fixture now reserves room for the content columns using actual
font metrics, then asserts Mods grows, Name yields and horizontal overflow stays
zero. This preserves the regression's purpose across platform fonts without
relaxing production widths. The next Windows runner must confirm the change.
No version bump, release, tag, public download change, package installation or
API deployment was performed.

Integrated validation: **1,023 run / 1,016 passed / 7 skipped**; required Ruff
format/lint, core mypy, compilation/whitespace and locked dependency audit pass.


## Stable rows and simpler counts — 5 November 2026

A user report identified disruptive row movement while asynchronous status and
mod-readiness results arrived. QTableWidget's automatic sorting moved a row as
soon as its active sort value changed. Browser sorting is now explicit: clicking
a header sorts using current values, while subsequent background replies update
the existing row. Full same-query snapshots retain the visible order of surviving
matches, append new matches and restore selected identity and scroll position.
A changed query starts a fresh ordered view, and its sort indicator reflects the
query without a second table sort overriding it. Membership of filtered/limited
results can still change; nonmatching rows are removed honestly.

Players/capacity/queue now use `10/20+0` and `20/20+5` across the browser, selected
summary, Favourites and cards. `+?` represents unavailable or expired queue
observations; tooltips explain it instead of falsely showing zero. Strict queue
parsing, fresh/nullable measurements, two-minute expiry and numeric player sort
keys are unchanged. The presentation timer expires the compact text and tooltip
without network work or row reordering. Browser summary text shows matching
results; cache/directory totals remain in its tooltip. The browser action and
first-use copy say Join, and inspector headings use plain language.

The governing product direction is complex underneath, calm and easy on the
surface: first-time players should be able to join and use Settings without an
explanation. This batch addresses the reported browser behaviour and related
copy; it does not claim a completed usability audit of every screen.

Validation: **1,026 run / 1,019 passed / 7 skipped**. Added real Qt header-click
coverage and a full-snapshot selection/scroll/order regression, including new and
removed matches and changed queries. The existing all-column row-integrity tests
now also assert that live replies keep rows in place before a deliberate re-sort.
Mod previews preserve order too. Compact count coverage includes measured zero,
positive queues, unavailable/invalid/future/expired observations and tooltip expiry.
Required Ruff format/lint, core mypy, compilation/whitespace and locked dependency
audit are checked before the development push. Current source package/native
validation remains separate; no version bump, package publication or deployment.

Andi clarified that the closing application was WolfLauncher. The temporary live
join diagnostic has a ten-minute self-close timer, so that is a plausible cause;
no exception was found in the inspected test log. No production crash fix is
claimed. The actual Stable join remains unverified: 64/64 mods were ready, the
normal preflight was accepted and the game process appeared, but connection to
198.244.177.109 game 2702/query 2703 was not confirmed.


## Address placeholders in the browser — 5 November 2026

The reported address rows were not caused by the stable-order correction: the
existing malformed-name predicate only screened replacement/control characters.
IP literals and IP:port placeholders, plus punctuation-only `!`, passed that test.
The shared name predicate now rejects those cases while retaining real titles
starting with `!`, non-Latin titles and titles that merely contain an address.
The browser still prefers a usable locally verified title; such a title can make
an otherwise address-only provider record browsable.

Schema 11 adds a derived `browsable_name` flag, computed on every cache upsert and
backfilled for existing records in batches of 500 within the existing atomic
migration. The SQL search/count predicate uses that flag before LIMIT. This
avoids short pages, incorrect match counts and repeated Python name parsing on
redraw. Raw records and endpoint lookup remain available; no entries, Favourites
or user configuration are erased. A launcher restart applies the fix to the
existing cache without a directory refresh. Normal background ordering remains
stable for surviving matches.

Validation: **1,029 run / 1,022 passed / 7 skipped**, Ruff format/lint, core mypy,
compilation/whitespace and locked dependency audit pass. Three regressions cover
address/punctuation versus real names, filtering before count/LIMIT, live-title
rescue/loss and migration of existing schema-10 records. Historical minimal
migration fixtures now include their existing live-name/status columns. A
separate synthetic in-memory 50,000-row migration/query check verified all
batches, excluded 5,000 address placeholders, and returned a full 200-row page
with 45,000 matches. One-time migration: 350.89 ms; five warm snapshot samples:
17.83 ms median. No packaged/cold-start performance claim, native validation,
release, version bump, public download change or API deployment in this batch.


## Freshness checks for small map results — 5 November 2026

A successful remote map lookup merged its results and refreshed the browser but
never requested the live freshness pass. A small result list has no scrolling,
so the viewport timer could not make up for the missing scheduling. The active
map callback now explicitly schedules the existing bounded freshness pass after
requesting the table refresh. The asynchronous snapshot loader defers the check
until its new rows are applied. No extra API fetch or unbounded query loop was
added.

Freshness tracking previously used search text alone. It now uses the complete
BrowserQuery, so changing map, version or edition with identical search text
clears previous attempted identities and cancels an older-context running batch.
Same-context work still coalesces, recent live status still honours its TTL,
paused polling remains paused and live results update rows in place.

Validation: **1,032 run / 1,025 passed / 7 skipped**, required Ruff format/lint,
core mypy, compilation/whitespace and locked dependency audit pass. A regression
runs actual cache merging, read-only snapshot workers and table population for
one, three and five matching servers; it asserts no live worker starts before
the snapshot is applied and that all matches are queued without any scrollbar.
Additional regressions verify filter changes with unchanged search text and no
freshness scheduling for failed/obsolete map callbacks. This is source/simulated
integration evidence; no fresh real API/game or packaged validation is claimed.
No version bump, release, publication, public-link change or API deployment.
