# WolfLauncher Production Readiness Review

Reviewed: 2026-07-18

Scope: the complete WolfLauncher repository, excluding a line-by-line audit of
the vendored legacy launcher whose role is already limited to a compatibility
fallback. This review covers application architecture, launch and Workshop
boundaries, persistence, networking, concurrency, security, testing,
documentation, packaging and release operations.

This is the authoritative engineering backlog for the production push.
`PROJECT_STATE.md` describes current truth, `ROADMAP.md` describes milestones,
and `docs/RELEASE_CHECKLIST.md` records release-candidate evidence. New release
work should be added here or linked here instead of creating another planning
note.

## Executive opinion

WolfLauncher is a serious, unusually well-tested pre-1.0 desktop application.
Its strongest qualities are the explicit native-versus-legacy launch boundary,
care around Steam/Workshop state, honest user-facing diagnostics, offline-first
server data, conservative launch preflight, and 426 fast unit tests. The choice
of Python, PySide6 and SQLite is appropriate for a Linux desktop launcher of
this size. Rewriting it in another language would add risk without addressing
its present weaknesses.

I would not publish the current repository as a general production release yet.
The core behavior is credible, but installation, application-data placement,
shutdown lifecycle, recoverable writes, secret handling, release metadata and
real-environment validation still need a deliberate production pass. These are
solvable engineering and release-management issues rather than evidence that
the product or technology stack is fundamentally wrong.

My overall assessment is **strong beta / release candidate after the P0 gates
below**, not production-ready as currently packaged.

## What is already good

- The product boundary is well understood. WolfLauncher does not claim that a
  successful Steam handoff proves DayZ started, and it retains diagnostics and
  a legacy fallback.
- Launch arguments are passed as argument vectors, not interpolated through a
  shell. Player names and server values therefore do not create ordinary shell
  injection paths in the Python launcher.
- YAML uses `safe_load`; SQLite queries use bounded, mapped sort/filter columns
  and parameter binding; network calls have explicit timeouts.
- Steamworks ownership is isolated in spawned helper processes. That is a good
  response to Steam's process-lifetime behavior and is more robust than keeping
  the API loaded in the GUI.
- SQLite has explicit schema versions and migrations, including stable server
  IDs and endpoint aliases. Remote discovery remains read-only and curated YAML
  remains conceptually separate.
- Background work keeps the Qt GUI responsive. Status and enrichment
  concurrency is bounded.
- The test suite is substantial and focused on behavior: launch construction,
  platform selection, cache migrations, provider parsing, preflight policy,
  Workshop state, presentation and Qt table behavior are covered.
- Documentation is far above the norm for a project at this stage. The
  architecture, project state, roadmap, discovery handoff and release checklist
  establish useful intent.

## Production gates

### P0 — fix before a public production release

#### 1. Build an installable, reproducible application

Evidence:

- There is no `pyproject.toml`, wheel/application build, desktop entry or
  installed application icon.
- `requirements.txt` contains only unbounded lower constraints for PySide6 and
  PyYAML.
- Setup is a development script that globally installs `gamedig` with npm.
- Packaging is still listed under roadmap v0.9.9.

Why it matters: users cannot install, upgrade, roll back or verify a defined
WolfLauncher artifact. A future PySide6/PyYAML release can change the runtime
without a WolfLauncher code change, and the external Node/gamedig dependency is
not version-controlled.

Recommended solution:

1. Add `pyproject.toml` with project metadata, Python version support, a console
   entry point and package-data declarations for SVG/PNG assets.
2. Pick one first-class Linux format. A `.deb` is a good initial fit for the
   documented Mint/Ubuntu scope; AppImage can follow if its Qt and Steam/Flatpak
   integration is validated.
3. Produce a locked release dependency set or constraints file, including an
   explicitly tested `gamedig` version. Keep broad ranges for development only.
4. Add a desktop file, icon, uninstall/upgrade behavior and a clean-machine
   install test in CI or a disposable VM.
5. Generate checksums and document provenance for release artifacts.

Acceptance: a clean supported OS can install, run, upgrade and uninstall a
tagged artifact without cloning the repository or globally mutating npm by an
opaque latest-version install.

#### 2. Move mutable curated data out of the source/install directory

Evidence: `MainWindow` sets `servers.yaml` to the repository/package parent and
creates it there at startup. This works from a checkout, but a package installed
under `/usr`, an AppImage mount or another read-only location cannot write it.

Recommended solution: place the user's curated server file under an XDG user
directory, preferably `~/.config/wolflauncher/servers.yaml`, and treat the
packaged example as read-only seed data. On first run, migrate an existing
checkout-local `servers.yaml` only after detecting it, never overwrite either
copy, and document the migration.

Acceptance: startup and all curated add/edit/remove operations work with the
application code and resources mounted read-only, while existing user YAML is
preserved.

#### 3. Make shutdown lifecycle safe for every worker and child process

Evidence: `MainWindow` can own status, mod, Workshop-state, preflight,
discovery, search, cache-merge, enrichment and per-selection `QThread` workers,
plus a WolfAPI `QProcess`. `closeEvent` only cancels/waits for
`workshop_subscription_worker`, then closes the shared SQLite connection.

Why it matters: closing during network or discovery activity can leave threads
emitting into deleted Qt objects, produce `QThread: Destroyed while thread is
still running`, race against the closed database, or leave child work alive.

Recommended solution: introduce a single task/lifecycle coordinator. Give
long-running workers cooperative cancellation, stop timers, disconnect or
ignore late results, terminate bounded helper processes when appropriate, and
wait with a finite policy before closing SQLite. Where practical, use
`QObject` workers in managed `QThread`s or a shared executor rather than many
ad hoc thread fields.

Acceptance: automated Qt tests repeatedly close the window during each worker
type, remote search, enrichment, cache refresh, mod query and Workshop helper;
the process exits cleanly with no warnings, late DB access or orphan helpers.

#### 4. Make all user-owned writes atomic and recoverable

Evidence: JSON settings and launch history use temporary-file replacement, but
curated YAML add/edit/remove writes directly to `servers.yaml`. Writes do not
consistently create the destination parent, preserve a backup, flush/fsync, or
report persistence failures. Settings and launch-history read/write errors are
often silently discarded.

Recommended solution: centralize persistence behind atomic same-directory
temporary writes (`flush`, `fsync`, `os.replace`), restrictive permissions for
sensitive settings, and an optional last-known-good backup for curated YAML.
Validate the fully serialized YAML before replacement. Surface actionable save
errors to the user and keep the in-memory model unchanged when persistence
fails.

Acceptance: simulated disk-full, permission, interrupted-write and malformed
existing-file tests cannot truncate the only good curated/settings copy.

#### 5. Resolve credential storage and diagnostic-redaction policy

Evidence: the Steam Web API key is stored in plaintext in
`~/.config/wolflauncher/settings.json`. That may be acceptable for this threat
model only if it is explicit and the file is owner-only. There is no stated
redaction contract guaranteeing keys, usernames and local paths cannot leak
into copied diagnostics or reports.

Recommended solution: use the desktop secret service through a small optional
keyring abstraction, with a clearly labelled owner-only local-file fallback.
Set config files/directories to `0600`/`0700` where applicable. Add centralized
redaction and tests for API keys, home paths, Steam account identifiers and
other tokens in every copyable support report.

Acceptance: the key is never present in ordinary diagnostics/logs, and local
storage behavior is documented and permission-tested.

#### 6. Synchronize version, behavior and release truth

Evidence:

- `wolflauncher.__version__` is `0.8.0`, while the repository describes active
  v0.9 hardening and packaging preparation.
- The release checklist says automatic Workshop subscription/downloading is
  not a release requirement and mod management remains read-only. The README
  and current implementation say automatic Steam-managed resolution is the
  default Connect preflight behavior.
- Architecture opens with an old v0.5.2 framing despite describing much newer
  functionality elsewhere.

Recommended solution: define one release version source and derive package/UI
metadata from it. Update the checklist to test the actual automatic Workshop
flow and helper cancellation/stall behavior through native Steam. Treat
Flatpak and Snap Steam as incompatible release exclusions. Perform a focused
truth-doc reconciliation before every release.

Acceptance: version shown by package metadata and the application matches the
tag, and README, architecture, project state, roadmap, changelog and release
checklist describe the same behavior.

#### 7. Complete release-grade real-system validation

The unit suite mocks external services and Steam behavior effectively, but it
cannot prove native Steam, Proton, Steamworks ABI, DayZ processes,
network providers, permissions or packaging on a user's desktop.

Recommended solution: maintain a release evidence matrix for Debian 13, Mint
22.x and Ubuntu 24.04/26.04 LTS, native Steam, Steam running/stopped, no mods,
complete mods, missing/update/stalled mods, DNS and raw IP servers, secondary
libraries, offline startup and upgrade from the prior data schema. Record the
tested Steam client/Proton/gamedig versions and retain sanitized reports for
failures. Record Flatpak and Snap Steam as explicit incompatible exclusions,
not untested release rows.

Acceptance: every required matrix row has a dated pass or an explicit release
waiver, performed against the packaged artifact rather than the source checkout.

## P1 — high-value hardening immediately after the gates

### Final UI purpose review

Before the next beta/release pass, review every visible button, field, option
and setting. Each control must earn its place by directly helping a player
choose, prepare for or join a server, or by providing essential support or
advanced recovery capability. Remove duplicate or non-actionable controls;
keep necessary advanced tools behind the established compact disclosures; and
preserve clear explanations where uncertainty or an external boundary matters.

Record the outcome in the release notes or project state so the review is a
deliberate product decision rather than an informal visual tidy-up.

### Discovery recovery and server submissions

Next build: add a compact **Add by address** journey for a server missing from
the directory. It should accept an explicit `host:port`, use the normal local
inspection, mod-validation and guarded-launch path, and let the player save it
to their own favourites without mutating WolfAPI.

Follow with a separate, explicitly confirmed **Submit this server to WolfAPI**
path only after WolfAPI has a server-side validation, rate-limit and moderation
contract. A submission must never publish a row immediately, bypass quality
controls or turn Launcher discovery into a source of untrusted directory data.

### Decompose `app.py` by feature ownership

At 4,255 lines, `MainWindow` builds four tabs, owns application state, runs
discovery, coordinates persistence, controls Workshop operations and performs
launch orchestration. Existing pure presenter/policy modules prove that gradual
extraction works.

I would keep PySide6 and extract one feature at a time into controllers/services:

- curated servers and status refresh;
- server browser/search/enrichment;
- mods and Workshop resolution;
- settings/health;
- launch/preflight orchestration;
- a shared task coordinator and application-state model.

Do not perform a wholesale MVC rewrite. Extract behavior behind tests, leave Qt
views thin, and use explicit typed result objects/signals. A practical target is
for `MainWindow` to compose tabs and route cross-feature navigation, not contain
the implementation of every workflow.

### Add static quality and security checks

CI currently runs unit tests only. Add Ruff (format plus lint), mypy or Pyright
incrementally on non-Qt core modules, dependency vulnerability scanning,
`pip-audit`, and a build/install smoke job. Pin GitHub Actions by immutable
commit SHA for supply-chain hardening rather than floating major tags. Add
`git diff --check` and import/startup smoke tests to CI.

### Improve network-client consistency

The standard-library `urllib` implementation is viable and avoids another
dependency, but provider code repeats request, decoding and exception policy.
Create a small HTTP client abstraction with:

- consistent User-Agent derived from the real application version;
- bounded response sizes before JSON decoding;
- connect/read timeout policy;
- status/content-type validation;
- limited retry with jitter only for idempotent transient failures;
- cancellation support and structured provider errors;
- optional ETag/cache support where the API contract provides it.

Do not retry launch-time truth checks aggressively; fast, honest failure is
better there.

### Harden SQLite operational behavior

Schema design and migrations are solid. Before wider release, enable and test a
busy timeout, consider WAL mode for concurrent reader/helper writes, wrap
migrations and multi-step identity changes in explicit transactions, and back
up or recover gracefully from corruption/migration failure. Add a startup path
that offers to quarantine and rebuild only the disposable discovered cache;
never apply that policy to user-owned curated data.

### Establish structured logging and crash reporting boundaries

Support is currently centered on copied diagnostics, which is useful. Add
rotating local structured logs with levels, timestamps, operation IDs and
automatic secret/path redaction. Keep telemetry/crash upload opt-in. Catch
unhandled GUI-thread exceptions and show a recoverable error with a sanitized
report location rather than relying on a terminal traceback.

### Validate and bound all external data

Provider parsing is defensive, but production clients should also bound JSON
body sizes, string lengths, list counts, ports and image downloads before data
reaches SQLite or Qt. Validate thumbnail schemes/content types and cap decoded
image dimensions as well as byte size. Normalize hostnames/IPs consistently,
including an explicit decision about IPv6, which current `host:port` parsing
mostly treats as unsupported.

### Improve accessibility and localization readiness

The UI has deliberate hierarchy and keyboard work, but production review should
include screen-reader names/descriptions, focus order across every tab/dialog,
high-contrast and reduced-motion behavior, 125–200% scaling, keyboard-only
operation and color-independent status cues. Keep user-facing strings separated
enough that future translation is possible even if v1 ships English-only.

## P2 — maintainability and product maturity

- Replace mutable, loosely typed dataclasses passed across layers with clearer
  immutable input/snapshot types where practical. Avoid mutating shared mod
  result objects after background work.
- Introduce settings schema/version validation and migrations instead of
  scattered `dict.get` coercions. Preserve unknown keys during upgrades.
- Add explicit time provenance to cached curated statuses; today a last-known
  status can be loaded without a persisted observation timestamp.
- Add property/fuzz tests for provider parsers, endpoint normalization, cache
  migrations and hostile/truncated YAML/JSON.
- Measure startup, third-character remote search, large-table refresh and memory
  behavior with production-size caches. Set budgets and keep benchmark results.
- Implement the supportable update strategy in `docs/UPDATE_STRATEGY.md`:
  prompted signed installers on Windows and a signed APT repository on Linux.
  Do not silently self-update.
- Review whether `gamedig` should remain a system Node dependency. Keeping it is
  reasonable because it is proven, but the packaged product must own version
  detection and compatibility. A native Python replacement should happen only
  if measurements show a real reliability or distribution benefit.
- Define retention/cleanup for cache, logs, thumbnails and launch reports so
  disk use remains bounded.

## Technology assessment

### Python

Good fit. The launcher is integration-heavy rather than CPU-heavy, Python has
excellent filesystem/process/network ergonomics, and the current suite makes a
future runtime upgrade manageable. Require and package a specific supported
Python range; do not depend on whatever interpreter happens to be installed.

### PySide6 / Qt 6

Good fit for a Linux desktop launcher. Qt provides mature widgets, process
handling, networking primitives, accessibility and high-DPI support. The main
risk is deployment size and platform-plugin/system-library compatibility, not
the UI framework itself. Package and smoke-test the exact Qt runtime instead of
asking users to assemble it through a development virtual environment.

### SQLite

Excellent fit for the disposable, searchable discovered-server cache. Keep
curated user intent in a separately backed-up human-readable file as designed.
Add operational settings and corruption recovery; do not replace SQLite with a
service or heavier database.

### YAML and JSON

Appropriate choices. YAML is friendly for curated lists and JSON is adequate
for simple settings. Both need versioned schemas, atomic writes and visible
validation errors. Consider TOML only if packaging/config interoperability
creates a concrete benefit; changing formats now is not inherently an upgrade.

### `urllib`, subprocesses and external tools

All are acceptable, but they need shared policy. Argument-vector process launch
is already the correct security choice. External tools are sensible at this
stage, provided versions, discovery, timeouts, output limits and error messages
are controlled by the packaged product.

### Steamworks through `ctypes`

This is the highest-risk technical boundary but also a pragmatic one. The
minimal binding and isolated-process lifetime reduce blast radius. Keep the ABI
surface tiny, validate supported interface versions, fail closed before launch,
and retain manual Workshop actions plus the external launcher until packaged
real-world evidence is consistently strong.

## Authoritative execution list

Complete these in order. A checked item requires its stated acceptance evidence,
not merely source changes.

### Release gates

- [x] **PR-00 — Reconcile planning and truth documents.** Establish this file
  as the single backlog; reduce `PROJECT_STATE.md` and `ROADMAP.md` to their
  distinct roles; update stale architecture, README and release-checklist
  claims; remove superseded design mockups.
- [x] **PR-01 — Choose the production version and centralize it.** Make package,
  application, tag and documentation metadata derive from one source. Update
  the changelog only when the release candidate is cut.
- [x] **PR-02 — Move curated YAML into XDG config.** Seed new profiles from the
  packaged example and safely migrate an existing checkout-local file without
  overwriting either copy. Prove operation with resources mounted read-only.
- [x] **PR-03 — Centralize recoverable persistence.** Use atomic same-directory
  writes, parent creation, appropriate permissions, validation and useful error
  reporting for curated YAML, settings and launch history. Add failure-mode and
  migration tests before changing the live location.
- [x] **PR-04 — Make shutdown lifecycle complete.** Inventory every thread,
  timer and helper process; add coordinated cancellation/late-result handling;
  close SQLite last; test repeated closure during every asynchronous workflow.
- [x] **PR-05 — Establish credential and support-report policy.** Add owner-only
  permissions, optional desktop keyring storage with a documented fallback,
  centralized redaction and tests covering every copyable report.
- [x] **PR-06 — Create the reproducible application artifact.** Add
  `pyproject.toml`, package data, a console entry point, locked release
  dependencies and a versioned `gamedig`; build one first-class Linux package
  with desktop entry, icon, checksums, provenance and documented
  install/upgrade/uninstall behavior.
- [x] **PR-07 — Expand automated release gates.** Add lint/format, incremental
  typing, dependency audit, immutable CI action pins, build/install/import and
  offscreen startup smoke checks while retaining the supported Python test
  matrix.
- [ ] **PR-08 — Execute packaged-artifact validation.** Run the supported
  Mint/Ubuntu native-Steam, Workshop, network, secondary-library,
  offline, clean-install and upgrade matrix in `docs/RELEASE_CHECKLIST.md`.
  Record dated evidence or an explicit waiver for every required row. Flatpak
  and Snap Steam remain incompatible; the archived Flatpak investigation
  defines the evidence needed before any future compatibility project.
- [ ] **PR-09 — Cut the production release.** Re-run all gates on the exact
  artifact and commit, synchronize the changelog/version/tag, publish checksums
  and installation guidance, and confirm CI on the tag.

### Hardening after the release gates

- [x] **PR-10 — Extract feature ownership from `app.py` incrementally.**
  `MainWindow` is now composition, window lifecycle and small presentation
  helpers; feature behavior is owned by the Servers, Server Browser, Mods,
  Settings and Launch mixins plus dedicated shutdown, preflight, Workshop
  resolution and settings-health coordinators. This preserves tested behavior
  and the approved GUI hierarchy.
- [ ] **PR-11 — Unify and bound network clients**, including response limits,
  versioned User-Agent, content validation, cancellation and structured errors.
- [ ] **PR-12 — Harden disposable SQLite operation** with busy handling,
  transactional migrations and safe quarantine/rebuild of cache corruption.
  Busy waiting, WAL mode and transactional schema initialization are complete;
  corruption quarantine/rebuild remains.
- [ ] **PR-13 — Add redacted structured local logging and GUI crash boundaries**
  with bounded retention and opt-in-only upload.
- [ ] **PR-14 — Bound external/provider data and image decoding**, and document
  the product's IPv6 decision.
- [ ] **PR-15 — Complete accessibility, scaling and keyboard review** and keep
  user-facing strings localization-ready. Include the observed favourite UX
  follow-ups: filled stars for active favourites, outline stars as the Server
  Browser promotion/favourite affordance, reversible unstar behavior, and
  in-game server time on Favourite Servers when live status provides it.
- [ ] **PR-16 — Add schema migrations, fuzz/property coverage and performance
  budgets** for settings, parsers, cache identity, startup and browser search.
- [ ] **PR-17 — Implement the defined update strategy and complete retention
  policies** for packages, cache, logs, thumbnails and reports.

Ideas beyond PR-17 belong in the post-v1 roadmap only when they have a concrete
user outcome. They must not displace unfinished release gates.

## Review evidence

Commands run from the repository root on 2026-07-18:

```text
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover
Ran 426 tests in 1.453s — OK

.venv/bin/python -m compileall -q main.py wolflauncher scripts
Completed successfully

git diff --check
Completed successfully
```

These checks establish a clean offline code baseline. They do not substitute
for the packaged, real-Steam release matrix described above.

Remote release-gate evidence on 2026-07-18:

- GitHub Actions run `29640723322` passed the Python 3.10, 3.11 and 3.12 unit
  matrices plus formatting, lint, scoped typing, dependency audit, compilation
  and whitespace checks.
- The same run built, extracted, imported, checksum-verified and uploaded
  versioned `.deb` artifacts on Ubuntu 22.04/Python 3.10 and Ubuntu
  24.04/Python 3.12. Clean desktop installation, upgrade and uninstall remain
  PR-08 real-system evidence rather than CI claims.
