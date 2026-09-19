# Combined Stable and Experimental browser and launch plan

Status: Phases 1–4 implemented with automated coverage; Phase 5 integration and
release documentation implemented. **Manual release validation remains open** for
the Linux/Windows runtime matrix. See the
[implementation and validation record](COMBINED_BROWSER_VALIDATION.md).

Phase 0 feasibility investigated on 15 September 2026: **launcher work can proceed
without a WolfAPI contract change**, using live game identity to handle conflicting
directory labels. Combined `product=all` endpoints are already deployed. See
[findings and evidence](PHASE0_PRODUCT_IDENTITY_FINDINGS.md) for the observed conflict,
successful GameDig checks, final freshness/retry contract, and test results.

## Revised requirements — 16 September 2026

The browser starts on Stable and has a visible Stable / Experimental selector. It
shows only the selected edition, so browser rows do not need EXP tags. Favourites
and recent servers stay mixed and retain edition/readiness tags. The browser choice
does not choose the launch product or the editor product. Experimental remains
selectable when not installed, with setup guidance and joining disabled.

Editor / Local Tools retains its original interface and uses Stable only.
Experimental support for this section is out of scope for the current work.

## Goal and agreed behaviour

WolfLauncher identifies each server's DayZ edition, checks mods against the correct
installation, and launches that edition automatically. Users browse one directory
and keep one visible collection of favourites and recent servers.

- The server browser starts on **Stable** on each startup. A visible
  **Stable / Experimental** selector shows only the chosen edition. Browser rows
  need no edition badge. This selector never controls launch routing.
- Experimental remains browsable when it is not installed. Setup guidance explains
  installation and browser Join is disabled until detection succeeds.
- Existing Experimental favourites and recent entries remain visible, labelled
  **EXP · Installation required**. Joining explains setup instead of launching Stable.
- Setup instructions: install **DayZ Experimental** from the Steam Library, launch
  it through Steam once to complete initial/BattlEye setup, close it, then rescan.
  Do not claim that finding its directory proves first-run setup has completed.
- Joining a known server needs no edition-switch confirmation. Normal Steam, mod,
  running-game, and launch error handling continues to apply.
- Unknown or conflicting identity is resolved before installation/mod preparation.
  If it cannot be resolved, explain the issue and offer retry; never silently use
  Stable or infer Experimental from a name or release number.
- Local tools without a target server use Stable independently of server
  joining and the combined browser.

## Current implementation and scope

Both Steam products are defined in `dayz_product.py`. Product-specific detection
and native launch preparation are reused. Server joining now resolves a fresh live
identity and captures an immutable installation/context before mod preparation.

`server_launch_coordinator.py` owns request invalidation and stale callback guards.
The Settings global game switch has been removed. The browser selector scopes
discovery only; local profiles and Editor use Stable without an edition selector.

Models, discovery workers, schema-8 cache records, saved profiles, and launch history
carry identity/evidence. `saved_servers.py` combines the two legacy profiles without
a startup rewrite. Legacy entries remain unknown until a successful live query;
profile location, server names, and version numbers are not launch authority.

This is an incremental refactor. Automatic game installation, automatic first-run
completion, a replacement Workshop system, and redesigning unrelated UI are out of scope.

## Architecture decisions

### Server identity and evidence

Introduce a server edition value: `stable`, `experimental`, or `unknown`.
Keep conflicting evidence as a resolution state with diagnostic details. An absent
or invalid value must not pass through `product_from_key()` and become Stable.
Only resolve a concrete `DayZProduct` after identity validation.

Keep evidence separate from the conclusion: source, observed time, and whether it
is verified or merely a legacy profile hint. Use explicit provider product metadata
and validated product-scoped discovery provenance. Preserve the metadata through
workers, cache writes, model conversion, favourites, previews, and recent launches.

For manual addresses, resolve through WolfAPI with `product=all` and bounded requests.
Phase 0 verified full game IDs through the existing GameDig dependency. Use a live
identity check before automatic joining to settle contradictory directory labels;
the initial policy requires a supported live ID before mod preparation. Do not rely
on the short A2S AppID field or introduce a version table.
Versions remain display/compatibility information only.

Define evidence precedence and freshness in one resolver. Fresh contradictory
authoritative evidence blocks joining and triggers resolution. A supported live
game ID for the exact endpoint can settle contradictory directory labels; generic status
refreshes and missing metadata do not erase a verified identity. Cached offline
records keep their badge, but an unresolved refresh must not be presented as fresh
verification. Use the existing provider freshness policy where suitable and specify
a separate identity freshness policy if it is not suitable.

### Per-launch context

Create one immutable context containing server identity/endpoints, resolved product,
selected Steam installation, launch engine, Workshop/mod source, and a request ID.
Resolve it before mod checks. Preview, preflight, Workshop completion, command
construction, and diagnostics must use the same context.

Experimental always uses its supported native path; a user's Stable external-launcher
preference remains intact. Mod-result reuse must match server identity, product,
installation and Workshop source. All asynchronous callbacks validate their request
ID/context before altering UI state or launching.

### Persistence and UI

Use explicit product columns/fields for filtering; source names remain provenance.
Scope provider IDs and endpoint aliases appropriately so two editions cannot overwrite
one another. Resolve records found in both product directories as a conflict when
they represent the same live endpoint, rather than treating duplicate rows as proof.

Initially combine the existing profile files in memory using a repository/adapter
that writes back to the correct profile. Preserve file layout unless a new format
has a demonstrated benefit. This reduces migration risk while allowing one visible
favourites collection. New and updated records persist verified edition metadata.

Keep discovered row identity stable across sorting, refresh, filtering, and selection.
Changing a filter must never cause Join to target whichever row takes an old index.

## Delivery sequence

Each phase is a reviewable change with its listed tests passing before the next.
Names for new test modules below are proposals; extend existing suites where the
behaviour already has a natural home. Do not write tests that merely mirror fields
or method calls: exercise persisted data, routing outcomes, and stale-result handling.

### Phase 0 — Prove identification and record contracts

**Completed 15 September 2026.** Evidence and the final policy are recorded in
[Phase 0 findings](PHASE0_PRODUCT_IDENTITY_FINDINGS.md). The executable contract is
`wolflauncher/server_identity.py`, tested by `tests/test_server_identity.py`.
Reuse successful exact-context checks for up to 30 seconds; otherwise refresh before
mods/handoff. Later phases must wire this contract into polling and launch context.

Work:

1. Inspect representative Stable and Experimental WolfAPI list, search, and resolve
   responses and Steam discovery results. Record product metadata and provenance.
2. Capture sanitized direct-query responses from at least one known server of each
   edition. Check whether a full game ID is present and correctly decoded by the
   current query path; do not assume protocol support means DayZ supplies it.
3. Document the exact resolution priority, freshness, conflict, and retry rules.
   Provider product assertions should have the same validation for both editions.
4. Identify any WolfAPI contract gap as a separately scoped backend dependency.
   If direct-query identity is unavailable, use directory resolution and preserve
   unknown for unlisted addresses. Do not compensate with version/name heuristics.

Tests/evidence (`test_server_discovery.py`, `test_status.py`, proposed
`test_server_product.py`):

- Known Stable and Experimental fixtures classify correctly, including identical
  displayed version strings and misleading server names.
- Missing, malformed, unsupported, and contradictory product values return an
  explicit unresolved/error outcome.
- Full query game ID, absent extended ID, truncated short ID, malformed response,
  and unsupported game ID cannot accidentally classify as the other edition.
- Manual endpoint: found only in Stable, only in Experimental, neither, or both;
  each has a defined result. A timeout is distinguishable from an empty result.
- Game and query ports remain distinct; hostname and IP aliases resolve correctly.

Gate: commit the fixture-backed contract and state which direct-query cases are
actually verified. If neither directory nor direct query can identify a manual
server, keep that case explicitly unsupported for automatic joining.

### Phase 1 — Carry identity and preserve saved data

Work:

1. Extend models and all conversions, including server copies used for resolved IPs,
   curated rows, imports/exports, workers, status enrichment, and recent shortcuts.
2. Add an additive, transactional cache migration (current schema is 7; use the next
   free version at implementation time). Update cache primary/unique keys, aliases,
   upserts, source syncing, and lookup APIs consistently.
3. Read both curated/favourite profiles through the adapter. Treat an old profile
   location as a hint: the reported bug means a Stable file can contain Experimental
   favourites. Resolve legacy hints before automatic joining.
4. Preserve stars across legacy name-based keys and new identity matching. Avoid
   losing a star after a server rename. Decide and test duplicate merging explicitly.
5. Extend history entries with product/evidence as needed. Legacy history is unknown
   until resolved. Ignore legacy local-tool edition settings;
   preserve unrelated/unknown keys and existing Stable engine preference.
6. Back up authoritative user files before any format rewrite. Make migrations
   repeatable and atomic; do not delete legacy files on first successful startup.

Tests (`test_config.py`, `test_settings_schema.py`, `test_app_favourites.py`,
`test_launch_history.py`, cache migration suites):

- Fresh database and every supported migration route reach the current schema.
- Opening migrated data twice produces no duplicate favourites/history or lost fields.
- Inject a migration/write failure: previous usable data remains; retry succeeds.
- Stable-only, Experimental-only, both-profile, empty, and partially malformed data
  preserve all recoverable user entries; corruption is reported rather than overwritten.
- A misfiled legacy Experimental favourite is resolved correctly before joining.
- Same endpoint across editions, shared provider IDs, aliases, changed names, and
  verified product changes do not silently overwrite, duplicate stars, or reuse old mods.
- Cache/import/export/worker round trips retain identity and evidence. Status-only
  updates retain known identity. Verified contradictions become conflicts.
- Legacy history has no fabricated product; new history reopens the correct edition.

Gate: existing data remains readable and no launch path depends on guessing missing
identity. Record the backup/restore procedure and any older-binary schema limitation.

### Phase 2 — Detect availability and provide setup guidance

Work:

1. Build a background availability snapshot for both editions using existing Steam
   detection, respecting selected Steam mode and multiple library locations.
2. Distinguish missing Steam, missing game, unusable/incomplete installation, and
   detected installation. Do not use a directory alone as proof of readiness.
3. Add Experimental setup/status and rescan in Settings. Keep optional Steam opening
   user initiated; do not initiate installation or a game launch during detection.
4. Revalidate the chosen installation before handoff if it disappeared or changed.

Tests (`test_platform_detection.py`, settings-health/controller/presenter suites):

- Neither game, Stable only, Experimental only, and both games installed.
- Separate libraries, custom manifest install directory, paths with spaces/non-ASCII,
  selected Steam mode, inaccessible libraries, missing executable and stale manifest.
- Rescan observes installation/removal without restart and rejects stale scan results.
- Detection errors are distinct from confirmed absence; a temporary scan failure
  does not erase favourites or remove the browser edition selector.
- Setup text includes install, first Steam launch, close game, and rescan; UI never
  claims first-run completion based solely on a manifest/directory.

Gate: readiness is product-specific and scanning does not block the Qt UI thread.

### Phase 3 — Route every join through the resolved context

Work:

1. Introduce the resolver/context boundary in `launch_feature.py`,
   `connect_preflight.py`, `launch_preflight.py`, and `launch_execution.py`.
2. Apply it to browser Join, favourites, recent servers, manual additions, mod checks,
   and native previews. Audit every command-building entry point.
3. Update mod workers, reuse checks, and Workshop completion callbacks to carry the
   same context. Cancel/invalidate old requests on selection/context changes.
4. Reuse native launch implementations. Preserve existing game-running safeguards;
   never try to switch an already-running DayZ process between editions.
5. Show EXP in saved-server surfaces now. Missing Experimental yields setup guidance;
   unknown identity yields resolution failure. Neither launches Stable as a fallback.
6. Include product and installation in support reports without changing the browser's
   active selection or global Settings profile during joining.

Tests (launch-selection/preflight/execution/native-launcher, app mod-context and
favourite suites; proposed `test_connect_preflight_product.py`):

- Stable → Experimental → Stable joins select the correct install every time, even
  while the old global setting has the opposite value.
- Assert the final Linux Steam app ID and game path; assert Windows executable,
  working directory, mod paths, and arguments for each product.
- Experimental selects native while Stable retains its external preference;
  Experimental is never passed to the Stable-only external script.
- Product is resolved before any mod/Workshop work; same endpoint and Workshop path
  with different product/context cannot reuse an earlier successful mod check.
- Existing Experimental mod-link/local-mod behaviour works; missing Workshop data
  gives actionable errors. Vanilla and modded cases both run through intended checks.
- Selection changes, cancellation, double Join, out-of-order worker completion,
  window close, installation removal, and changed identity cannot launch a stale target.
- Preview and actual launch agree on product, install, mods, and endpoint.
- Repeat the routing assertions through favourites, recent shortcuts, and manual
  endpoint resolution. Missing/unresolved/conflicting cases launch no process.
- Already-running Stable or Experimental continues to prevent a second game launch.
- A failed/cancelled handoff does not create a misleading successful history entry;
  preserve/report the existing history policy explicitly if entries represent attempts.

Gate / first useful milestone: automatic routing and saved-server badges work with
the existing browser arrangement. There is no remaining server launch decision
based on the global edition setting.

### Phase 4 — Scope discovery, queries, and presentation

Implemented behaviour:

1. Request the selected `stable` or `experimental` directory and preserve explicit
   product metadata. `product=all` remains available for manual identity resolution.
   Keep selected-edition totals separate from global directory coverage.
2. Carry edition generations through discovery, search, map and cache callbacks.
   Reject responses for an old edition or obsolete search/filter combination.
3. Use the same product/filter predicates for rows and matching counts before the
   display limit. Scope map/source/version options and cache summaries by product.
4. Default to Stable and keep the two-edition selector visible without row badges.
   Mixed favourites/recent servers retain edition and installation-readiness tags.
5. Preserve cached rows on provider errors. Refresh each edition independently.
   A delayed old-edition worker cannot replace the current view.
6. Preserve selection by identity; clearing/filtering the selection invalidates
   outstanding join preparation.

Automated coverage includes product-scoped row/count queries, source sync, identity
collisions, stale directory callbacks, edition switching, sorting/selection and
mixed saved profiles. Performance evidence for 20,000 cached rows is recorded in
[validation](COMBINED_BROWSER_VALIDATION.md). Runtime network outage and full user
interaction checks remain in the manual release matrix.

Gate: one browser supports both editions independently; rows, counts and filters
agree, and automatic routing tests remain green.

### Phase 5 — Retire global server mode and complete release validation

Work:

1. Remove the global Settings game-edition switch and Experimental-mode warning.
   Replace Settings with availability/setup, retaining a clearly scoped local-tools
   edition selector where necessary. Remove obsolete profile-switch worker plumbing
   only after auditing callers.
2. Update README installation/Experimental guidance and relevant help text to describe
   automatic selection, EXP badges, filtering, setup, and unresolved manual addresses.
3. Document migration/backups, support-report fields, verified identification sources,
   and known limitations. Keep any backend requirement explicit in release notes.
4. Run the automated and manual gates below. Do not claim actual game joins were
   verified where only mocked command construction was exercised.

Regression tests: startup with old settings; Stable external engine; local tools/editor
with explicit edition; Workshop operations; server selection; favourite persistence;
recent entries; diagnostics; clean startup with no Experimental installation.

## Automated validation procedure

Use temporary config/data directories and SQLite databases. Mock process launches,
network, Steam and Workshop mutations in automated tests. Deterministic recorded
fixtures are the contract tests; optional live probes are separately labelled and
must not be required for ordinary CI. Use Qt offscreen mode in headless environments.

Run focused suites for each phase, then the existing CI checks at integration gates:

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 venv/bin/python -m unittest discover -v
venv/bin/ruff format --check wolflauncher tests main.py scripts/render-windows-icon.py
venv/bin/ruff check wolflauncher tests main.py scripts/render-windows-icon.py
venv/bin/mypy wolflauncher/paths.py wolflauncher/persistence.py wolflauncher/redaction.py wolflauncher/secret_store.py
```

Use the Windows virtual-environment equivalent on Windows. Follow the current CI
matrix in `.github/workflows/tests.yml` if it changes; the existing mypy command is
a limited baseline, not proof that the new resolver is type-checked. Include any new
pure resolver/context modules in targeted type checking where practical.

## Manual end-to-end release matrix

Run on supported Linux/Steam/Proton and Windows configurations. Record OS, launcher
revision, installation layout, fixture/server identity source, expected/actual result,
and a redacted launch report for each case. Real joining requires an available server
compatible with the installed build; report that separately from command correctness.

| Case | Expected observable result |
| --- | --- |
| Stable only | Stable directory usable; Settings gives Experimental setup; saved EXP entry remains but cannot launch |
| Experimental only | Experimental usable without a Stable game install when existing mod-source prerequisites are met; missing prerequisites explained |
| Both installed | Stable default; toggle to EXP and back; join Stable, EXP, Stable without visiting Settings |
| Separate Steam libraries | Each join uses its own game path and the intended Workshop source |
| Experimental freshly installed | Setup instructions remain accurate; incomplete first-run setup is not reported as verified ready |
| Install/rescan and uninstall/rescan | Readiness updates; selector and mixed favourites remain available |
| Manual EXP favourite added while formerly in Stable mode | Resolves to EXP, keeps its star after restart, launches EXP |
| Offline/unknown/conflicting manual server | Clear retry/error; no guessed edition and no wrong-game launch |
| Vanilla and modded server of each edition | Correct preflight and mod paths; no cross-edition reuse |
| Rapid selection/filter changes during mod checks | No stale join; selected target and resulting command agree |
| Provider partial outage | Remaining results usable, failed source identified, cached entries retained appropriately |
| Existing user upgrade | Both profiles and recent records recoverable; no lost stars; legacy ambiguous records resolve before joining |
| Preview, favourite, recent, browser Join | All paths agree on edition and installation |
| Game already running | Second launch blocked with existing actionable guidance |
| Local tools and Stable external engine | Stable tools and engine preference still work after EXP joining |

## Definition of done

- [x] Phase 0 identity contract and representative evidence are recorded.
- [x] No release-number or server-name heuristic selects an edition.
- [x] Models, cache, favourites, aliases, workers, and history preserve identity.
- [x] Migration/retry/failure tests preserve user data; restoration is documented.
- [x] Server launch entry points select a context before mods and carry it through handoff; runtime matrix pending.
- [x] Request/context guards reject stale callbacks and cached mod results, with regression coverage.
- [x] Missing Experimental provides setup guidance and preserves saved entries.
- [x] Browser defaults to Stable with a visible Stable / Experimental selector; favourites stay mixed.
- [x] Edition-scoped queries, counts and stale-response guards are implemented and covered by automated tests.
- [x] Global server mode is retired; local tools remain Stable-only.
- [x] Automated gates pass; commands, results and limitations are recorded in the validation notes.
- [ ] Complete the real-game manual release matrix on Linux and Windows.
- [x] Restore the original Editor / Local Tools interface; Experimental tools are out of scope.
- [x] README/help and release notes describe the delivered behaviour accurately.

Completion evidence should include implementation commits, test commands/results,
manual matrix results, migration notes, and any remaining external dependency.
