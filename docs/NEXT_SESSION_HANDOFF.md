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


### FEATURE-02 existing-profile picker implemented - 3 November 2026

Favourite Servers and Settings now offer an explicit existing-player-profile
picker. It scans recognised primary files in the selected edition's Windows
Documents location or its actual library's Proton prefix, groups matching names
and shows modification dates and locations. Discovery reads names and metadata
only. Choosing a row updates the existing launcher-wide player-name setting;
DayZ profile files are not opened, created, renamed or cloned.

A window-owned cancellable Qt worker bounds enumeration and participates in
shutdown. Closing the picker or encountering a changed installation, removed
profile or save failure cannot apply an unintended name. Windows uses Qt's
Documents known-folder lookup, including redirection. Stable and Experimental
folders/app IDs stay separate; Linux never falls back to another library or the
host Documents directory. Character/variable caches, backups, empty files and
ambiguous encoded names are not guessed as primary profiles. Custom `-profiles`
locations, custom prefix overrides and alternate Wine usernames remain outside
this initial discovery scope; manual name entry remains available.

Read-only local discovery found one primary profile in each installed Proton
edition, correctly excluding their character and variable caches. Real names and
contents were not captured. No configured name or game profile was changed.
An offscreen synthetic picker preview was inspected. Twenty new regression
tests include a real Qt worker/dialog cancellation case.

Final Linux validation: **916 run / 909 passed / 7 skipped**. Ruff 0.15.22 lint
and formatting, compilation and whitespace checks pass. Native Windows/OneDrive,
packaged UI and in-game settings reuse remain manual checks; source completion
is not a claim that those boundaries are verified. No version bump, package
build, game launch or publication was performed for FEATURE-02.

See [scope, locations, evidence and limitations](PLAYER_PROFILE_DISCOVERY.md).
The next feature candidate is **FEATURE-03: direct server links**. Its acceptance
criteria still include validated inputs, cold/running-instance handoff, Windows
and Linux scheme registration, HTTPS install fallback and the existing identity,
preflight and Workshop confirmations. REL-02 and API-01 still need their previously
recorded missing evidence; do not guess it or reopen completed fixes.


### FEATURE-03 direct server links implemented - 3 November 2026

Favourite Server and Server Browser menus can copy a versioned HTTPS server link.
The launcher accepts canonical HTTPS/protocol links through its command line,
Windows/Linux handlers or Settings paste. It shows a target review, then uses
normal live edition/mod inspection. Receiving a link does not connect, start a
Workshop download or create a favourite; Connect retains its existing guards.

Links contain only a version, host, separate game/query ports and optional
endpoint-bound directory reference/edition hint. Missing, repeated, unsupported
or oversized input is rejected. An unconfirmed/moved reference has an explicit
endpoint fallback; it cannot silently redirect the game address. Hints do not
verify an edition. Shared targets reject live replies advertising a conflicting
game port, and retain that restriction in resolved launch contexts.

Cold startup and already-running delivery are implemented. Local handoff is
user-restricted, framed and bounded, supports split input, and acknowledges URL
receipt. An older running launcher without acknowledgement produces a retry /
restart message. Windows Setup's per-user handler task is unchecked by default;
cleanup preserves a different installation's handler. Linux advertises its
protocol capability and refreshes desktop caches without forcing a default.
The Windows installer smoke script includes registry ownership/reinstall checks.

The matching HTTPS fallback is prepared in the separate `wolf-forge-static`
branch **`dev/wolflauncher-server-links`**. It validates the same contract, displays
the address, opens the app only on a click, and retains download/manual-paste
instructions. No public page, download manifest or product placement was changed.
Ship that route with a matching launcher release before advertising HTTPS links.

Validation: launcher **938 run / 931 passed / 7 skipped**, including 22 new
link/IPC/context/GIO regressions. Website: **4 existing Python tests and 41 new
JavaScript tests pass**. Desktop/mobile headless Chrome previews and valid/invalid
DOM checks pass. Ruff 0.15.22 lint/formatting, compilation, shell syntax,
desktop-file, fixture parity and whitespace checks pass. Native Windows Setup,
packaged handlers/browser permission flows, deployed HTTPS and real game joins
remain release-time checks. No package build, version bump, live OS registration,
game/Workshop action or website publication was performed.

See [the complete contract and remaining checks](DIRECT_SERVER_LINKS.md).
The next candidate is **FEATURE-04: separate live server queue counts**. REL-02
and API-01 retain their earlier evidence requirements; do not guess missing inputs.


## FEATURE-04 implementation update — 3 November 2026

Separate live queue counts are implemented in development source. The pinned
GameDig DayZ parser reads `lqs` keywords into `raw.queue`; the launcher validates
whole tokens and keeps missing/malformed/ambiguous values unknown. Browser,
selected-server details and favourite cards/details show counts alongside players
without changing numeric player sorting or inferring anything from capacity.
Existing automatic and selected live checks populate this data.

A separate queue timestamp survives browser cache/provider updates without being
refreshed by them, and is not carried to a moved endpoint. Schema 10 migrates old
rows to unknown; favourite status caching preserves nullable counts. Failed or
queue-less live checks clear previous evidence. Counts expire after two minutes;
a presentation-only ten-second timer updates labels with polling disabled and
stops during shutdown.

Two read-only public live queries captured `lqs0` / queue 0: New Dawn Cherno
198.244.177.109:2303 (6/30) and Deerisle :2503 (1/20). Minimal fixture fields are
saved without player lists. Positive queue behaviour uses a synthetic queue of 12;
a real positive queue remains uncaptured. Offscreen Qt preview checked positive,
zero, unknown and stale rows/cards.

Validation: **946 run / 939 passed / 7 skipped**. Eight new queue tests cover the
live decoder/enrichment/presentation path, malformed evidence, expiry, cache
migration, provider refresh/endpoint moves and incremental Qt updates. Required
Ruff lint/formatting and whitespace checks pass. No package build, version bump,
main merge, PR, publication, game or Workshop action was performed.

See [queue behaviour and evidence](SERVER_QUEUE_COUNTS.md). Next candidate in list
order: **PERF-01: profile the server browser before deciding whether a model/view
change is justified**. PERF-02 already has implementation updates earlier in this
handoff; preserve those results. REL-02 and API-01 retain their evidence needs.


## List follow-up — 4 November 2026

Continued unattended work after FEATURE-04, preserving the existing PERF-01 and
PERF-02 implementations. Linux benchmarks confirm the table improvement and add
process RSS evidence. API-02 evaluation found a 92% body-size reduction using
WolfAPI's existing gzip support; bounded client decoding is now implemented.
Conditional persistence, compact schemas and count deltas still need an agreed
age/deletion/generation contract and were not introduced speculatively.

PLATFORM-01 was reproduced using the existing AppImage: an external system Python
loaded bundled SSL libraries. Frozen Linux host handoffs now use child-only
loader/PATH/Qt cleanup while bundled helpers keep their environment. A real
harmless QProcess child verifies delivery. PLATFORM-02 adds the read-only,
qualified community-recommendation memory-map check in Settings.

BUILD-01 now has source-snapshot consistency, tool/dependency inputs, artifact
hashes and staged bundle inventories for AppImage and Windows portable builds;
sidecars and clean matching-source checks are retained by the existing tag-release
workflow. Native wrappers/Setup/DEB/RPM provenance and independent signatures
remain open. QUALITY-01 adds five integrated simulated join/cancel/failure flows
using the real coordinators and command builder without a game/Steam launch.

Validation: **971 run / 964 passed / 7 skipped**, required Ruff lint/formatting,
compilation, shell syntax, workflow YAML and whitespace checks. Current native
packages were not rebuilt (PyInstaller is absent here), and Windows/PowerShell
validation remains pending. No main merge, PR, version bump, publication, API
deployment, Workshop action or system setting change was performed.

See [full evidence, decisions and remaining list items](DEVELOPMENT_FOLLOWUP_2026-11-04.md)
and [provenance usage](BUILD_PROVENANCE.md). Next useful work: wrapper/native
package provenance and isolated rebuilt Linux validation. Localisation, signed
installable updates and broader support collection retain their design choices;
LAN discovery still needs interface/custom-port coverage and real LAN evidence.
REL-02/API-01 retain their specific missing inputs; do not guess them.


## Performance priorities 1–3 — 4 November 2026

Andi approved the first three items from the additional source performance review.
Completion-order browser results, staged required-mod presentation/readiness and
bounded shared Workshop metadata requests are now implemented. Early snapshots
cannot authorize launch; forced rechecks bypass older metadata requests and late
advisories cannot replace newer Steam evidence. Final Linux validation: 990 tests
run, 983 passed, 7 skipped; required lint/formatting, core type checks, compilation,
whitespace and release-lock dependency audit pass. See the [implementation and
evidence](DEVELOPMENT_FOLLOWUP_2026-11-04.md#further-performance-work-review-priorities-13-implemented).
Packaged/native Windows and live Steam/DayZ evidence remains pending. Review items
4–7 remain candidates; no release, version bump, package build or API deployment
was performed. Preserve this completion update before planning further work.


## Remaining performance areas implemented — 4 November 2026

Andi approved continuing the remaining source performance improvements. Validated
thumbnail reuse, incremental mod-table/progress updates, asynchronous read-only
browser snapshots with bounded scheduling/invalidation, and targeted Workshop
name reads with a file-identity display cache are implemented. Directory presence
and launch freshness remain freshly checked; no persistent installed-state cache
was added. Final Linux checks: 1,013 run, 1,006 passed, 7 skipped; required quality
checks and the release-lock dependency audit pass. See [measurements, safeguards
and remaining platform evidence](DEVELOPMENT_FOLLOWUP_2026-11-04.md#remaining-performance-review-areas--4-november-2026).
All four remaining review areas now have source improvements; do not reopen them
from the earlier candidate list. Packaged Linux, native Windows, high-DPI/manual
accessibility and live Steam/DayZ validation remain pending. No release, version
bump, package build, public-link change or API deployment was performed.


## Isolated Linux artifact validated — 4 November 2026

Rebuilt a private AppImage from clean commit 292f1b734f2f01538571844e423724c304493cbd
with the pinned runtime/build tools in a temporary checkout. Basic smoke and
extended frozen UI/runtime checks passed at 1× and 2× Qt scaling inside private
XDG/tmp, PID and network namespaces. Provenance verifies the commit, clean source,
artifact hash and 1,111 staged bundle entries. A clipped Size-column unavailable
label found during inspection was corrected, rebuilt and revalidated. See
[results, artifact identity and limits](DEVELOPMENT_FOLLOWUP_2026-11-04.md#isolated-linux-package-validation--4-november-2026)
and [repeatable validation](ISOLATED_LINUX_VALIDATION.md).

Source checks: 1,016 run, 1,009 passed, 7 skipped; quality checks and dependency
audit pass. Local offscreen packaged evidence is now complete for the recorded
synthetic scenarios. FUSE, older distros, native desktop/a11y, Windows and live
Steam/Workshop/DayZ checks remain open. Existing artifacts, user configuration and
Steam content were preserved. Version stays 0.9.3.5b; no tag, installer execution,
publication, public-link change or API deployment occurred.


## Bounded resource soak and live Steam evidence — 4 November 2026

Added repeatable isolated source UI resource and read-only Steam diagnostics.
300- and 600-cycle soaks passed; the longer run's final ten sampled RSS values
were identical, with stable Qt object/cache counts and decreasing threads/file
handles. The production Steam state helper successfully queried 20 installed
mods three times, all ready, and left no helper process behind. No game launch,
subscription change or download request was needed. See [results and limits](DEVELOPMENT_FOLLOWUP_2026-11-04.md#resource-soak-and-live-steam-state--4-november-2026)
and [repeatable diagnostics](RESOURCE_SOAK_VALIDATION.md). Final runner guard also
has a passing 100-cycle check and rejects direct child use against ordinary data.

1,016 regression tests run / 1,009 passed / 7 skipped; workflow quality checks
pass. This adds accelerated synthetic source resource evidence and actual
read-only Steam state/cleanup evidence. It does not close multi-hour stability,
real downloads/cancellation, game joins, frozen-package resource behaviour,
Windows, native desktop/accessibility or older distro/FUSE checks. Native wrapper
package provenance also remains useful follow-up work. No runtime change,
release/version/publication or API deployment in this batch.


## Native package provenance source implementation — 4 November 2026

BUILD-01 now has source integration for DEB/RPM/Windows Setup/Linux installer
archives, with sealed staged inputs and verified parent chains where applicable.
Do not reopen this as missing source work. Clean native builds/extracted-payload
checks and Windows compiler/install/uninstall evidence remain separate next steps.
See [the follow-up](DEVELOPMENT_FOLLOWUP_2026-11-04.md#native-package-provenance-chain--4-november-2026).


## Windows CI failures investigated — 4 November 2026

Previous Linux CI jobs pass, but Windows exposed seven failures/two errors before
packaging. Platform-neutral test-fixture/cleanup repairs and a bounded advisory
hash-directory membership recheck are implemented. 1,021 Linux tests run / 1,014
passed / 7 skipped; Windows needs the next native runner result. Initial independent
native extraction also found DEB control-file mode normalization and extra RPM
build-ID links; source corrections are included and clean rebuilds are next.
See [details](DEVELOPMENT_FOLLOWUP_2026-11-04.md#windows-ci-repair-and-native-payload-corrections--4-november-2026).


## Native/Linux/live validation and startup refinement — 4 November 2026

Clean private 13649a7 AppImage/Linux installer/DEB/RPM artifacts now have passing
independent extracted inventories. DEB/RPM extracted startup smoke and native
X11 AppImage checks at 1×/2× pass; host FUSE mount/unmount passes separately.
These artifacts predate the subsequent IPC/startup source refinements. Keep
exact source identities and do not relabel them or publish them as current.

Real Steam no-byte completion, cancellation and retry pass on one existing
subscribed item with no helper left behind. DayZ menu/process launch and normal
exit were verified; no server join occurred. Andi has now supplied a Stable test endpoint; its real join check follows
separately. No bulk or changed-content download claim is made.

Startup profiling found repeated Editor/LAN library scans; source now performs
one fresh construction scan and shares its result within that redraw. Later
refreshes remain fresh. Controlled source browser-paint median improved from
807.77 to 758.33 ms. See [full evidence and boundaries](DEVELOPMENT_FOLLOWUP_2026-11-04.md#native-evidence-live-checks-and-measured-startup-refinement--4-november-2026).
Windows activation now passes in CI; the final font-adaptive table fixture still
needs its next runner result, followed by portable/Setup compilation and smoke.
Remaining broader items: chosen real join, changed-content/bulk download evidence,
Windows/native accessibility, older distro evidence, multi-hour stability,
REL-02/API-01 specifics, LAN discovery coverage and the documented product/signing
choices. No release/version/publication or API deployment.


## Calm server browsing — 5 November 2026

Andi reported moving “waterfall” rows and requested compact players/capacity/queue
counts. Browser headers now sort on request rather than continuously during
background replies. Same-query snapshots preserve surviving row order and restore
selection/scroll, appending new matches. Changed searches/filters/edition/limit or
sort controls use fresh query ordering. Rows leaving a filtered/limited result
can still disappear; do not retain nonmatching rows as live matches.

Browser, Favourites and cards use `10/20+0`, `20/20+5`, or `10/20+?` for unknown or
expired queue evidence. Tooltips explain the notation; strict parsing, nullable
counts, two-minute expiry and numeric player sorting are preserved. Browser
summary copy now shows matching results, with directory/cache diagnostics in its
tooltip. Its action says “Join server”, with a simple first-use instruction.

Product direction: **complex underneath, calm and easy on the surface**. A new
player should be able to select and join a server and understand Settings without
someone explaining it. Preserve necessary checks/confirmations, disclose technical
information progressively, and avoid a wall of internal implementation language.
This focused browser correction is implemented; a complete Settings/other-screen
usability review has not been completed in this batch.

Regression evidence: **1,026 run / 1,019 passed / 7 skipped**. Tests cover actual
header clicks, stable live enrichment/mod updates across all table columns,
snapshot order/selection/scroll, new/removed matches, changed searches, compact
queue values and honest expiry. Quality/dependency checks are recorded in the
[detailed follow-up](DEVELOPMENT_FOLLOWUP_2026-11-04.md).

Earlier Windows CI on b1cde4d now passes the unit tests and portable/Setup build
and smoke/install/uninstall checks. This is evidence for that earlier commit;
the current browser correction still needs its own native/package confirmation.
The approved Stable endpoint is 198.244.177.109, game 2702/query 2703. The live
review found 64/64 required mods ready, accepted the normal preflight and observed
the game process; actual server connection was not verified. Do not mark it done.
Andi clarified the reported closing was the temporary launcher; its ten-minute
diagnostic shutdown is a plausible explanation, with no exception found in the
inspected current test log. A production crash is not established or claimed fixed.
No release, version bump, public-link change or API deployment.


## Address-only browser names suppressed — 5 November 2026

Andi's screenshot showed address-only rows and a bare `!` near the top of the
browser. The existing malformed-name filter only rejected decoding damage and
control characters; addresses/punctuation were accepted. Shared name validation
now rejects IP literals/endpoints (including bracketed IPv6) and names containing
no letters or digits. Genuine `! [GER] ...` titles, non-Latin names and names
containing an address remain usable. A usable locally checked title can rescue a
provider address placeholder; unverified provider/live fields cannot do so.

Cache schema 11 stores a derived browsable-name flag, backfilled in batches of
500 within the migration transaction and recalculated on every upsert. Filtering
runs inside SQL before LIMIT and count, keeping pages/counts correct without
Python callbacks on every redraw. Cached endpoints remain available to explicit
lookup; records and saved Favourites are not deleted. Restart the source launcher
to load this fix and migrate the cache; no fresh provider download is needed.

Validation: **1,029 run / 1,022 passed / 7 skipped**; required quality checks and
locked dependency audit pass. Regressions cover the screenshot-style names,
Unicode/genuine exclamation titles, filtering before LIMIT/count, live-name
rescue/loss and schema-10 backfill. Legacy migration fixtures now include the
pre-existing live-name/status fields used by the derived classification.
A separate in-memory 50,000-row check migrated all batches in 350.89 ms and loaded
200 rows with 45,000 matches in a five-sample median 17.83 ms. These are synthetic
local measurements, not packaged or cold-start evidence. Native/package checks
for this correction remain separate; no release/version/publication/deployment.


## Freshness after small map lookups — 5 November 2026

Andi found that selecting a map fetched WolfAPI results but did not live-check
small lists. The successful map callback refreshed cached rows without scheduling
freshness, leaving it dependent on incidental viewport/scroll activity. It now
explicitly schedules the existing bounded pass; the snapshot loader waits until
new rows are applied before continuing. Freshness context now uses the complete
BrowserQuery, so a map/edition/version change with unchanged search text clears
previous attempts and cancels the previous-context batch appropriately.

Validation: **1,032 run / 1,025 passed / 7 skipped**; required Ruff format/lint,
core mypy, compilation/whitespace and locked dependency audit pass. An integrated
regression merges map responses, uses the real read-only snapshot loader/table,
and confirms one/three/five-result lists start live checks after snapshot delivery
with no scrollbar. Other regressions cover changed filter context and failed or
obsolete map callbacks. Existing TTL, worker/batch bounds, polling pause rules,
selection checks and stable row updates remain in place. No real API/game check
or package rebuild was performed for this fix; native/live confirmation remains
separate. Restart the source launcher to load it. No release/version/deployment.


## Clear Favourite port roles and status messages — 5 November 2026

Andi's screenshot showed game port 3302 in Edit and query port 2303 in the timeout
message. These are two saved roles, not interchangeable ports; no live evidence
establishes the correct query port for that server. Preserve both saved values.
The Favourite edit disclosure now names and shows its saved status query port,
opens automatically for a non-default port pair, and explains joining versus
status/player/mod queries. It no longer hides a differing port behind an
unspecific “advanced connection port” label. Usual game+1 pairs remain collapsed.

Default status messages now give the concise outcome, with full query failure
text and labelled join/status endpoints retained in Favourite card/table tooltips
and existing diagnostic logs. Query timeout still means unknown status rather
than proof the game server is offline. No launch gate or probing route changed.

Validation: **1,034 run / 1,027 passed / 7 skipped**; required quality checks and
locked dependency audit pass. Regressions cover the 3302/2303 dialog pair,
unchanged saved values, disclosure edits, short failure text and full diagnostic
retention. An offscreen themed dialog preview was visually checked; a clipped
helper paragraph was shortened and rechecked. Native/package evidence remains
separate. No actual server query/port repair, release, version bump or deployment.


## Requested Offline labels and quieter player counts — 5 November 2026

Andi explicitly prefers nonresponding servers to display Offline, and player
counts as `2 / 60` or `20 / 20 +2`. This supersedes the earlier visible `+0`/`+?`
notation and timeout-as-Unknown presentation. Browser and Favourite timeouts now
use the Offline label/colour; a successful later check restores Online. The
underlying TIMEOUT outcome/local_timeout source and diagnostic details remain
intact. DNS/network/tool/read/cancellation errors still display Unknown rather
than being attributed to the server. Existing retry timing and launch guards
are preserved; no extra polling loop was added.

The shared formatter adds spaces around `/` and before a positive queue suffix.
Zero, unavailable and expired queues have no suffix; nullable evidence and expiry
remain distinct in data/tooltips. No fabricated empty queue or old positive count
is displayed. Numeric player sorting and stable row order are preserved.

Validation: **1,035 run / 1,028 passed / 7 skipped**, required quality checks and
locked dependency audit pass. Coverage checks exact formatting, zero/missing/
expired/future observations, expiry without polling, Offline timeout cards,
other failure states and timeout-to-Online recovery. This is source regression
evidence; current native/package/live confirmation remains separate. Restart the
source launcher to load the change. No release/version/publication/deployment.


## Favourite-only compact counts — 5 November 2026

Andi refined the spacing preference: Favourites use `2/60` or `20/20+2`, while
the server browser retains `2 / 60` or `20 / 20 +2`. The shared formatter now has
an explicit compact option used by Favourite startup/live/expiry rendering;
browser rendering keeps the spaced default. Positive-only fresh queues, nullable
observations, expiry, sorting and Offline presentation are preserved.

Validation: **1,035 run / 1,028 passed / 7 skipped**; required quality checks and
locked dependency audit pass. Existing regressions verify both formats, initial
Favourite status, live measurements and different browser/Favourite expiry text.
Source checks only; no native/package rebuild, release/version or deployment.


## Hide stale population on Offline rows — 5 November 2026

Andi reported an Offline browser row still showing nine players. Failed local
checks cleared ping/queue but retained the older population. Failed enrichment
now clears current/capacity counts too. The shared browser presentation also
hides population/queue for every Offline classification, including existing
cached local timeouts, local offline results and provider-reported offline rows,
without requiring another query. Such rows have no numeric player sort value.
The queue display timer cannot reinstate a hidden historical count. A successful
check restores the newly reported population; Offline is not rendered as a
fabricated zero. Favourite failure rows already clear their population cells.

Validation: **1,036 run / 1,029 passed / 7 skipped**; required Ruff format/lint,
core mypy, compilation/whitespace and locked dependency audit pass. Regression
coverage checks all three cached Offline cases, inspector/table/timer suppression,
online recovery and failed enrichment clearing population. Source regression
evidence only; no current native/package/live verification, version bump,
release, publication or deployment. Restart the source launcher to load the fix.
