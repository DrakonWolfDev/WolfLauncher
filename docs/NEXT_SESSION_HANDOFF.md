# WolfLauncher consolidated next-session handoff

Prepared **2 November 2026** for work later or on **3 November 2026**.
This is a planning handoff, not a release deadline. No fixes, builds or deployments
were performed as part of assembling it.

## Start here

The aim is to improve reliability first, then consider useful additions identified
in Flare Launcher and Beans Launcher. Keep each change independently reviewable.
The LAN connection issue and the remembered PHP/WolfAPI alert need follow-up, but
Andi explicitly said they did not require an immediate fix.

Next session:

1. Capture the LAN failure with the official launcher as a working control.
2. Identify the exact PHP/WolfAPI alert and whether its associated patch is already
   applied, shipped or deployed. Do not duplicate a completed fix.
3. Fix the reproduced Workshop completion race, including delayed Steam state and
   no-op download cases.
4. Validate the reported DayZ perspective-tag change against known servers.
5. Select subsequent improvements from the backlog below; optional features are
   not prerequisites for completing the reliability work.

### Current evidence and worktree

- WolfLauncher reviewed at `1b314377ac9cb038bed4545b24722a83bfff18f4`.
  Recheck HEAD and the worktree before starting; these are dated findings.
- Existing modified `CHANGELOG.md` belongs to earlier work. Preserve it.
- [Flare technical review](FLARE_TECHNICAL_REVIEW.md): source revision
  `89954428a15745fe10d5f3dc351ac6fdedd20f8c`, version `1.6.1-beta.1`.
- [Beans technical review](BEANS_TECHNICAL_REVIEW.md): public snapshot
  `fa89a86cbbe0b72a5c2a82de989b336d1c141b94`. Snapshot metadata says `1.6.1`;
  its package metadata says `1.6.0`. Use the commit to identify the reviewed code.
- Those two reviews contain pinned source links and detailed evidence. This handoff
  contains the combined work scope and completion criteria so it can stand alone.
- Beans is source-available and prohibits code reuse in other software. Implement
  lessons independently; do not transplant its code. Flare's shared UI/updater is
  private. Beans' UI, directory discovery/ranking and backend are private.

## A. Reported issues to investigate

### LAN-01 — LAN server appears offline although the official launcher connects

**Status:** user-reported; failure not reproduced in this review. Scheduled
follow-up, not an emergency.

Andi's clarification: **LAN connections showed as offline, while the official
launcher could do a direct connect.** It is not yet established whether this was
the Local Development tool, a saved Favourite, or another browser surface; whether
WolfLauncher actually blocked Connect; or whether only its status was wrong.

**First investigation:**

- Record the affected OS/build, launcher surface, Stable/Experimental edition,
  same-machine versus another LAN host, and the redacted launch/status report.
- Record the server's configured game port and query port separately. Compare
  the exact official-launcher target with WolfLauncher's chosen target.
- Reproduce with a vanilla LAN server first, then the affected mod configuration.
  Distinguish successful game connection from successful A2S status querying.
- Check explicit query ports, query-disabled/firewall-filtered servers, loopback,
  private addresses, hostnames and multiple servers sharing an address.
- Inspect whether public discovery/identity rules are accidentally being used as
  prerequisites for a deliberate local connection.

**Starting points:** `wolflauncher/local_tools.py::parse_local_endpoint()`,
`local_tools_feature.py::_join_local_test_server()` and
`_launch_verified_local_test_server()`, `native_launcher.py`, `status.py`,
`server_launch_context.py` and the selected-server preflight path.

One concrete inspection lead: `_launch_verified_local_test_server()` constructs
`Server(..., host, port, port)` from a single `host:game-port` field. Game and
query ports can differ. This is a lead, not a proven explanation of Andi's failure.
Beans' direct-address lookup validates that a query reply belongs to the requested
game port; that is a useful invariant if candidate-port probing is introduced.

**Done when:** the reported case has a reproducible diagnosis and focused fix;
query failure is represented honestly rather than as proof of offline status;
a deliberate direct-connect path remains available where appropriate without
requiring a public directory listing; endpoint, edition and mod safeguards still
apply; and the connection is manually verified against an actual LAN server.
Add regression coverage for separate game/query ports and unavailable query data.

Keep automatic LAN discovery as a separate optional feature (BACKLOG-07). Finding
servers automatically is not required to fix a known address that cannot connect.

### API-01 — Remembered PHP alert associated with WolfAPI and a possible patch

**Status:** reported follow-up; exact alert and patch identity unconfirmed.
Andi clarified it was more to do with WolfAPI and believes a fix patch also had
to be applied. Searches of local Launcher/API notes did not identify a PHP-named
alert. Do not silently rename it or assume PHP itself needs changing.

**Relevant documented maintenance trails to reconcile:**

| Dated record | What the record establishes | What remains to check |
| --- | --- | --- |
| [Launcher/API HTTPS handoff](../DISCOVERY_FRESHNESS_HANDOFF.md), 17 October | A Windows Python/OpenSSL certificate-chain failure was reproduced; Launcher uses native verified Windows trust through `truststore`. The record says a new Launcher build was needed to distribute it. | Whether this was the remembered alert, and which distributed artifact contains the fix. |
| [WolfAPI TLS security maintenance](../../WolfAPI/SECURITY_MAINTENANCE_2026-10-24.md), 24 October | Python/OpenSSL runtime and certifi were updated. The document records a verified production rollout of release `20261024T112029Z-16823bb`. | Whether this matches the remembered alert; current deployment status has not been checked in this session. |
| [Launcher CI repair record](CI_VALIDATION.md), 17 October | Hash-pinned cryptography was updated to `50.0.2` following advisory `PYSEC-2026-3552`, alongside CI/runtime fixes. | Whether a dependency alert or local patch was being remembered, and whether it reached the intended build. |

These are candidate evidence trails, not three newly discovered open incidents.

**First investigation:** recover the exact alert text, package/component, advisory
identifier if any, affected version and original location. Match it to commits and
artifact/deployment evidence. Distinguish source patched, local runtime patched,
published Launcher patched, and WolfAPI deployed. Record any actual remaining task
and the reason it can be deferred. If already resolved, close this entry with the
matching evidence instead of applying another patch.

**Done when:** the alert is identified, its relevance to the deployed/API or packaged
Launcher runtime is established, and either the fix is verified at the appropriate
boundary or a precise residual action is recorded. Do not suppress a warning or
weaken TLS verification as a substitute for identifying it.

Any later coordinated API change must first read `../../WolfAPI/AGENTS.md`,
`../../WolfAPI/DISCOVERY_FRESHNESS_CONTRACT.md` and the Launcher handoff. Preserve
both worktrees and maintain the contract documents together. This planning task
does not initiate production work or claim current production health.

## B. Reliability improvements identified by the reviews

### REL-01 — Await actual Workshop update completion

**Evidence:** reproduced locally. With an existing item directory and
`force_update=True`, `subscribe_workshop_items()` accepted the first `INSTALLED`
snapshot and returned success before observing later
`INSTALLED|NEEDS_UPDATE → DOWNLOADING → INSTALLED` states.

**Scope:** `workshop_subscription.py`, its helper/worker messaging and resolution
coordinator, `mods.py`, and connection/local-tools post-download revalidation.

Capture each item's initial freshness target and pending request. Combine state,
callback/result, timestamps and local directory evidence; a requested download is
not a completed update. Surface rejected requests, Steam disappearance, cancellation,
stall and overall timeout accurately. Keep retries bounded.

Include the legitimate no-op case: a Workshop metadata edit may advance its update
timestamp without downloadable file changes. Beans' repeated-request/activity
tracker offers a design lesson; Flare's initial timestamp/callback grace period
offers another. Neither elapsed time alone nor a silent queue proves compatibility.
Any acknowledgement must be scoped to the selected installation and item/content
evidence so a result for one library cannot bless another's stale copy.

**Done when:** delayed state, unchanged/no-op state, real queued downloads, failed
requests, helper exit, cancellation/retry and post-download checks all have correct
outcomes. Preserve existing confirmation, subscriptions and single-session guards.
Never claim completion merely because the old installed flag remains set.

**Implementation update - 3 November 2026:** the premature installed-state race
has a focused source fix. Both helper backends now retain DayZ's
`DownloadItemResult_t` notifications; accepted requests require a successful
completion callback, idle item flags and a local directory. Rejected requests
remain incomplete and retry at a bounded interval; queued/downloading flags,
failed callbacks, cancellation, stalls and timeouts cannot report success. The
progress monitor also treats pending completion notifications as incomplete.
A successful callback supports requests that transfer no new bytes; silence or
elapsed time does not. The existing post-download revision checks remain active.

**Later implementation update - 3 November 2026:** metadata-only acknowledgement
is now implemented, scoped to the selected library, edition, item, captured
published revision/size and unchanged installed manifest/file-stat evidence. It
requires a successful forced Steam completion and a live idle state on reuse.
Other libraries, changed content, newer revisions and active/unknown Steam state
cannot reuse it. Installed timestamps now come only from the selected library's
installed-item section. Live Windows/Linux Steam verification remains pending.
See [detailed implementation and evidence](RELIABILITY_FOLLOWUP_2026-11-03.md).
No build, version bump or publication was performed.

### REL-02 — Verify DayZ 1.30 perspective-tag interpretation

**Evidence:** Flare reports `no3rd` is reversed from build `1.30.164200` and applies
a version-based workaround. This has not been independently verified. WolfLauncher
currently interprets the tag without a version; Beans does likewise.

Capture raw responses from known first- and third-person servers, with versions
and actual settings. Check whether WolfAPI already normalises the data. If confirmed,
apply a bounded workaround only to the affected raw sources/versions, with tests
for older versions, unknown versions and already-normalised provider fields.

**Done when:** the evidence supports correct labels/filters end to end, without
double-inverting provider values or assuming the bug persists in every future version.

**Investigation update - 3 November 2026:** both supplied name-based candidates
answered on exact query ports resolved through WolfAPI (4053 and 4026). Both
reported build 1.30.164289 and `no3rd`. The user clarified the perspective types
were selected from names, not verified camera settings. No inversion or
build-specific Unknown override is applied. Explicit normalized provider fields
are preserved. REL-02 remains open pending known settings and raw evidence; see
[the capture and limitations](RELIABILITY_FOLLOWUP_2026-11-03.md).

### REL-03 — Represent unpublished mods without discarding the manifest

**Evidence:** a synthetic protocol-2 manifest with an unpublished, zero-length
Workshop-ID entry followed by a normal Workshop entry decoded both in Beans;
WolfLauncher rejected it as an invalid ID length.

Extend `dayz_mod_query.py` and requirement/result models to preserve unpublished
requirements separately from downloadable IDs. Explain manual/local requirements
and preserve later valid Workshop entries. Do not invent a Workshop ID, discard
the requirement, or mark the server ready while it remains unresolved.

**Done when:** mixed manifests, truncation, duplicate IDs, overflow, unsupported
versions, byte stuffing and signature framing are tested, and unresolved local
requirements block readiness with useful guidance. Retain our stricter parser checks.

**Implementation update - 3 November 2026:** zero-length IDs are represented as
unpublished requirements, preserving subsequent valid Workshop entries. Manual
requirements retain their names, have no fabricated Workshop IDs/links, are
excluded from download requests, and block readiness/guarded launches with useful
guidance. Strict malformed-manifest checks remain. Automated parser, presenter,
preflight and native-setup regression coverage is added. Live mixed-server
validation remains pending. See [details](RELIABILITY_FOLLOWUP_2026-11-03.md).

## C. Additions and measured improvements

These are candidates, not approved promises to implement all features in one session.

| ID | Work item and starting point | Completion evidence |
| --- | --- | --- |
| FEATURE-01 | Retain server-advertised mod hashes currently discarded by `dayz_mod_query.py`; investigate Flare-style local PBO trailer comparison. | Captured server/local fixtures establish the algorithm; asynchronous selected-server results distinguish match, mismatch and unknown. A mismatch alone does not establish which side is newer or prove full file integrity. |
| FEATURE-02 | Discover existing DayZ player profiles before passing a new `-name`; optionally add explicitly requested cloning later. | Read-only selection preserves existing settings; selected library, Stable/Experimental, Windows Documents redirection and Proton prefixes are covered. Cloning never overwrites existing files and recovers from partial failure. |
| FEATURE-03 | Implement direct server links already listed in `ROADMAP.md`. | HTTPS install fallback and OS scheme registration work on Windows/Linux, including cold start and an existing window. Validate links, resolve edition/identity, present the target and retain preflight/Workshop confirmation. No arbitrary launch arguments or automatic subscriptions from a link. |
| FEATURE-04 | Add the separate server queue count already listed in `ROADMAP.md`. | Read actual queue evidence, show it beside players and update it during live checks. Unknown/stale is distinct from zero; never infer queue size from player count. |
| PERF-01 | Profile `server_browser_table.py`; consider `QTableView`/`QAbstractTableModel` and delegates instead of per-row widget allocation. | Timings and memory at realistic row counts justify the change; selection, sorting, keyboard access, scaling and incremental enrichment remain correct. No stack rewrite is implied. |
| PERF-02 | Prioritise joining over optional background work and pause nonessential polling while hidden/playing. | Measured reduction in background work; downloads/cancellation/process monitoring remain active; overlapping retries cannot release another join's ownership; restore refreshes stale visible data. Electron renderer unloading is not a Qt requirement. |
| API-02 | Evaluate conditional directory snapshots, compact mod tables and smaller live-count refreshes with WolfAPI. | Measure compressed payloads first; agree timestamps, removal/retention rules, stable identity and edition isolation. Revalidate age after `304`; update and test both sides of the contract. |
| PLATFORM-01 | Test AppImage child-process environment leakage into Steam/desktop apps. | Reproduce using an actual packaged artifact; if needed, scrub only bundled paths/variables for affected children while preserving the intended host environment. |
| PLATFORM-02 | Consider a read-only `vm.max_map_count` Settings health check. | Independently verify the relevant DayZ requirement, explain any low setting accurately, and never alter system settings silently. |
| BACKLOG-07 | Optional LAN server discovery, separate from LAN-01. | Bounded broadcast/probe budget, interface-aware deduplication, cancellation and honest coverage of custom query ports. Direct connection still works when discovery finds nothing. |
| BACKLOG-08 | Localisation with catalogue/placeholder checks. | Choose languages deliberately; maintain plural forms, placeholders and backend/user-facing message consistency. |
| BUILD-01 | Improve release provenance and packaged-file verification beyond our existing SHA-256 artifacts. | Public source commit, dependency/toolchain inputs and package contents are traceable; verify provenance before claiming reproducible native packages. |
| UPDATE-01 | Consider signed installable updates as a separate product decision. | Independently verified artifacts, version policy, atomic replacement, failure recovery and rollback are designed and tested. Retain the existing notification-only updater until replacement is deliberately implemented. |
| QUALITY-01 | Strengthen end-to-end test seams and future input boundaries where needed. | Full simulated join covers Steam states, links, launch arguments and cancellation without launching a game. Future URL/helper inputs have explicit bounded schemas; development injection hooks cannot activate in release builds. |
| SUPPORT-01 | Consider previewable, redacted support reports if existing diagnostics are insufficient. | Explicit user action, understandable contents and minimal data. Competitor install identifiers, tracking and default crash reporting are not prerequisites and should not be introduced incidentally. |

### PERF-01 implementation update - 3 November 2026

A focused table improvement is implemented in source. Favourite stars use normal
Qt items instead of per-row widgets. Live row and mod-preview updates no longer
trigger a full-table re-sort. The active sort cell is replaced last to keep all
cells together when a changed row moves. Favourite state and selection are
preserved explicitly.

The local themed offscreen benchmark at 1,000 rows improved population from
597 ms to 144 ms, 50 enrichments from 206 ms to 21 ms, and 50 mod previews from
166 ms to 4 ms (five-sample medians). See
[measurement details and reproduction](SERVER_TABLE_PERFORMANCE.md).
These are UI timings, not faster network responses. The focused changes avoid
requiring a full model/view migration for this improvement. PERF-02 background
scheduling, Linux/package benchmarking and process-memory measurement remain open.
No version bump or release publication was performed.

### PERF-02 implementation update - 3 November 2026

Optional polling now defers while hidden/minimised, joining, resolving Workshop
items or monitoring a launched game. Active downloads and process monitoring
continue. Current owner state controls resumption, so an old callback cannot
release a newer request. Resume schedules stale visible-data checks once and
respects disabled automatic status polling. Ten simulated paused status ticks
schedule zero refreshes; this is not a CPU/network-byte benchmark. Live play,
Linux and packaged behaviour remain unverified. See
[implementation and validation limits](RELIABILITY_FOLLOWUP_2026-11-03.md).

## D. Preserve these existing strengths

WolfLauncher is not starting from scratch. Retain strict malformed-manifest handling,
live selected-server/preflight checks, identity conflict handling, edition isolation,
SQLite caching, viewport-prioritised enrichment, disposable Steam helpers, user
confirmation, bounded retries and existing packaged-artifact checks.

Avoid copying the weaker competitor behaviours: automatic termination of a running
game, trimmed passwords, treating absent evidence as verified freshness, cached
directory mods as the sole connection authority, checksum-only trust as a substitute
for independent signatures, and non-atomic executable replacement.

`LOCAL_NEXT_BUGS.md` contains older issues with implemented or manually verified
statuses, including editor rendering, Windows Tools/Publisher handoff, honest unknown
server status, shutdown and installed-library force-update routing. Read their status
before reopening them. LAN-01 may touch the status work, but is a distinct reported
case rather than proof that the earlier fix never happened.

## E. Validation record and next-session checks

Review-time evidence, **not a new whole-project validation claim**:

- Flare pass: 101 focused WolfLauncher tests passed, an isolated Rust parser
  experiment, and the delayed Workshop-state reproduction.
- Beans pass: 136 focused WolfLauncher tests passed. Eight standalone Beans logic
  suites supplied 83 specifications, passing in a Node TypeScript-transform harness
  with compatible assertions; this was not its full Electron runner or a type check.
- Mixed unpublished-mod decoding was compared directly. Competitor parser checks
  also reinforced the need to keep WolfLauncher's strict protocol/framing checks.
- No real Steam action, subscription, player-profile modification, game launch,
  update installation or comparative performance benchmark was performed.
- Neither the LAN report nor the remembered PHP alert was reproduced here.

Useful focused baseline, in the existing environment:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest \
  tests.test_dayz_mod_query tests.test_workshop_subscription \
  tests.test_workshop_dependencies tests.test_mods tests.test_local_tools \
  tests.test_local_server tests.test_lifecycle tests.test_native_launcher -q
```

Add regression tests that reproduce the actual changed behaviour, then run the
relevant checks and platform/package verification. Use real LAN and Steam/DayZ
checks where mocks cannot establish the outcome. Follow repository guidance for
broader required gates; do not present the focused baseline as a full release gate.

For each completed item, record the cause, change, test evidence, remaining platform
limits and shipment/deployment status here. Keep source completion, published
Launcher artifacts and production API deployment separate. Do not bump versions,
publish installers or deploy WolfAPI merely to finish this planning document.

### Follow-up validation - 3 November 2026

Full local suite: **861 tests run, 67 skipped, 794 passed**. Ruff 0.15.22 lint and
the CI formatting gate pass. See [environment details and remaining live checks](RELIABILITY_FOLLOWUP_2026-11-03.md).
REL-01, REL-03 and PERF-02 have source implementations and regression coverage;
real Steam/game and Linux/package validation remain outstanding. REL-02 remains
an investigation, with raw candidate captures but no verified camera settings or
version-specific correction. No release artifacts were published or API deployed.

### Local test builds requested - 3 November 2026

The user requested Windows and Linux local builds as **0.9.3.5b**. These are now
built and ready under `dist/`: Windows portable ZIP and Setup installer, Linux
x86_64 AppImage and user-local installer archive. All four SHA-256 files match.
Windows numeric metadata now preserves all four release components (0.9.3.5).

Full suites in the actual build environments: Windows **864 run / 67 skipped**;
Linux **864 run / 7 skipped**. Native packaged startup smoke tests passed on both
platforms. Ruff lint and formatting pass. No release was published and the user's
installed launcher was not replaced.

See [artifact links, checksums, toolchain details and remaining manual checks](LOCAL_BUILD_0.9.3.5b.md).
The Linux build uses an isolated Ubuntu 22.04 WSL distribution named
`WolfLauncherBuild`. Real Steam/LAN/game and interactive update checks remain;
REL-02 still needs confirmed camera settings. This local build record supersedes
earlier source-only/no-build status statements for these changes.

### LAN test feedback and query-port correction - 3 November 2026

The user tested the 0.9.3.5b LAN flow and confirmed DayZ joined with the correct
mods. The remaining UX gap was that detected requirements were not shown before
launch. The LAN screen now has a separate Query server action, displays detected
requirements and ready/missing/pending states in Local Server selection, and
pauses for review before the first join or after the manifest changes. The IP /
hostname, Game port and Query port are separate compact controls. Existing saved
host:port profiles migrate into those controls without changing their endpoints.

The reported DrakonCherno status failure was reproduced as a saved-query-port
mismatch: the favourite used 2303, while direct A2S and GameDig replies confirmed
query 3303 and game 3302. The saved favourite and its index were updated through
the transactional repository, with a timestamped backup in the launcher's config
folder. Later public/LAN query timeouts were explained by the user stopping or
restarting the server. GameDig JSON errors now show the attempted query port and
query guidance instead of claiming an incomplete/offline server response.

The local 0.9.3.5b artifacts have been refreshed with this feedback. See the local
build record for final checksums and validation. Manual retest of the new review
screen remains necessary; the original automatic mod loading already has user
confirmation.

LAN feedback refresh validation: **871 tests run** on each platform. Windows:
**804 passed / 67 skipped**. Linux: **864 passed / 7 skipped**. Both packaged
startup smokes and all four artifact checksum checks pass. Lint/format checks
pass. The local build record has the refreshed hashes; no release was published.


### Development branch and FEATURE-01 foundation - 3 November 2026

Continue development on **`dev/release-preparation`** and push directly to
`origin/dev/release-preparation`, without a PR. Do not push development work to
`main`; merge there only when the maintainer explicitly requests the final
pre-release merge. The existing `dev/linux-package-previews` branch prevents a
branch named exactly `dev`. See the repository's [agent instructions](../AGENTS.md).
Installer CI now also checks development-branch pushes; this does not publish a
release. Existing reliability/LAN/local-build work is preserved on this branch.

FEATURE-01 is **in progress**: the strict binary parser now retains each advertised
unsigned 32-bit mod hash, and direct mod checks carry it into `RequiredMod` for
both Workshop and unpublished requirements. `None` means unavailable; zero remains
an actual advertised value. No local comparison, compatibility claim or new
readiness decision is made from these hashes yet.

Next for FEATURE-01: validate the PBO-trailer aggregation algorithm independently
against captured matching server/local files, then add bounded asynchronous
selected-server advisory results for match, mismatch and unknown. Retain the
review's warnings about duplicate/case-sensitive PBOs and avoid inferring which
side is newer from a mismatch. This step does not complete FEATURE-01.

Validation in this Linux Python 3.12.3 / PySide6 6.11.1 environment: full suite
**872 run / 865 passed / 7 skipped**; Ruff **0.15.22** lint and the CI formatting
gate pass. The sandbox blocked socket operations in TLS and single-instance tests;
the full suite passed outside that restriction. Focused parser/mod-check coverage
includes distinct hashes, byte stuffing, chunk boundaries, unpublished requirements,
zero and missing hashes. No new packaged artifacts, Steam actions, version bump or
release publication were performed in this step; earlier local builds predate it.


### FEATURE-01 advisory comparisons implemented - 3 November 2026

The source implementation now covers local/server PBO-trailer comparisons in
selected-server Mods inspector checks. The main identity/request coordinator
explicitly enables these checks; launch-preflight, LAN and browser-preview
workers leave optional hash reads disabled. Requests retain their server,
selected library, edition and cancellation context. An inspector hash request
queued behind a readiness-only check is not silently lost, and a new hash check
does not reuse a cached local comparison.

Read-only queries to the saved New Dawn Cherno and DeerIsle public servers
provided 53 and 56 installed requirements respectively. Independent aggregation
of existing local PBO trailers matched all 109 advertised values; the finished
comparison module matched them too. A small regression fixture retains a complete
raw rules reply plus three matching local trailer sets, without PBO bodies or
personal paths. This evidence validates the observed aggregation; it is not a
claim about all DayZ versions or unique mods.

The Mods table, details and copied report distinguish matching, different and
unavailable results at the last check. Comparisons never change readiness or
trigger a Steam download. File/directory changes during a comparison invalidate
it; a newer Steam state clears earlier advisories. Every requested hash check
rereads the selected files. Empty/unreadable data, linked PBOs, missing hashes,
active updates, cancellation and work limits remain unknown. A bounded duplicate
PBO allowance handles a possible Linux-server case and explains such a match;
nonmatches above that allowance's cap remain unknown. There is no continuous file
watcher: users recheck after later external edits.

Final Linux validation: **896 tests run / 889 passed / 7 skipped**, including
24 new hash/worker/coordinator/integration tests. Ruff 0.15.22 lint and the CI
formatting gate, compilation and whitespace checks pass. Interactive UI,
Windows/junction and packaged checks remain pending. Existing 0.9.3.5b local
artifacts predate this change. No package build, version bump, game launch,
Workshop update or release publication was performed for this feature.

See [algorithm, captured evidence, bounds and limitations](MOD_HASH_COMPARISON.md).
FEATURE-01 is implemented in source with live Linux aggregation evidence;
remaining platform/manual checks are recorded there. The next feature candidate
is **FEATURE-02: read-only discovery and selection of existing DayZ profiles**.
REL-02 still requires verified camera settings; API-01 still needs the exact
remembered alert. Do not invent those missing inputs or repeat completed fixes.
