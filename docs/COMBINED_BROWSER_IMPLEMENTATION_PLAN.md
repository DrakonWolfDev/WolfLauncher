# Combined Stable and Experimental browser and launch plan

Status: Phase 0 complete; Phases 1–5 pending. A tested pure identity contract is
available, but automatic routing and the combined browser are not yet integrated.

Phase 0 feasibility investigated on 15 September 2026: **launcher work can proceed
without a WolfAPI contract change**, using live game identity to handle conflicting
directory labels. Combined `product=all` endpoints are already deployed. See
[findings and evidence](PHASE0_PRODUCT_IDENTITY_FINDINGS.md) for the observed conflict,
successful GameDig checks, final freshness/retry contract, and test results.

## Goal and agreed behaviour

WolfLauncher identifies each server's DayZ edition, checks mods against the correct
installation, and launches that edition automatically. Users browse one directory
and keep one visible collection of favourites and recent servers.

- Both editions installed: show both in the browser by default, mark Experimental
  servers **EXP**, and remember a **Hide Experimental** filter.
- Experimental missing: omit known Experimental servers from general discovery and
  hide the browser filter. Settings shows installation instructions and a rescan
  action. A previous filter preference survives temporary uninstallation.
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
- Local tools without a target server retain an explicit edition choice. This
  choice does not control server joining or the combined browser.

## Current implementation and scope

The current code already defines both Steam products in `wolflauncher/dayz_product.py`,
detects product-specific installations in `platform_detection.py`, and supports
Experimental in `native_launcher.py`. Reuse these implementations.

The principal coupling is `LaunchFeatureMixin.dayz_product()`, which reads global
settings. `SettingsFeatureMixin._apply_dayz_product_switch()` reloads favourites,
replaces browser context, and changes mod/launch settings. Do not call that method
automatically when selecting or joining a row.

`Server` and `DiscoveredServer` currently have no explicit product field. WolfAPI
Experimental responses are checked for a `product` value, but the row converter
does not preserve it. Discovery uses product-specific requests/source namespaces.
Cache keys, favourite keys, and recent-history keys have different definitions;
audit all three before changing identity semantics.

Existing persisted state includes separate curated/favourite files per product,
a shared discovery cache, and a shared recent-history file. In particular, history
currently lacks a product field; do not assume it is already isolated by edition.

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
   until resolved. Add settings migration for filter preference and local-tool edition;
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
  does not erase favourites or a remembered filter preference.
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

### Phase 4 — Combine discovery, queries, and presentation

Work:

1. Use WolfAPI `product=all` when both installations are available, with `stable`
   when Experimental is excluded. Use separate product requests only for providers
   that need them. Combine results through product-aware cache queries, not by
   invoking the Settings switch twice. Preserve separate filtered totals and global
   coverage counts as described in the Phase 0 findings.
2. Extend refresh workers/process messages and remote search/endpoint resolution with
   product plus request generation. Preserve independent per-product refresh status.
3. Apply one inclusion policy to displayed rows, counts, pagination, map/source filters,
   and remote results. Count matching records before pagination; avoid page starvation
   from concatenating two independently limited lists.
4. Add accessible EXP labels in table/cards/details and a persisted Hide Experimental
   toggle. Labels use text as well as colour. Filtering affects the general browser;
   saved favourites/recent entries remain available with readiness labels.
5. Handle partial provider failure explicitly: keep useful cached results with freshness
   indicators, show which edition failed, and never erase a directory on timeout.
6. Keep selection by identity. If the selected row is filtered out, clear its join
   context or retain a clearly visible separate selection; choose one and test it.
   Prefer clearing the browser selection and disabling Join.

Tests (browser controller/presenter/table, workers, discovery-refresh and cache suites):

- Both available + fresh settings shows both; toggle removes only Experimental;
  restarting preserves preference. Missing Experimental hides its general rows/toggle.
- Uninstall/reinstall changes availability without losing the saved hide preference.
- EXP favourites remain visible and cannot join when their installation is missing.
- Text, map, population, quality, password/mod filters and source filtering compose
  with product inclusion; counts and page boundaries match actual visible rows.
- Same-name servers of different editions show correct badges and join targets;
  provider ID/endpoint conflicts follow the Phase 0 policy.
- Search request A finishing after B, filter changes during refresh, cancellation,
  and a delayed Experimental response cannot replace the current view incorrectly.
- One directory times out while the other succeeds: successful rows appear, cache
  for the failed directory survives, and retry does not duplicate rows.
- A verified empty result clears only the intended source/product scope.
- Unknown rows are not falsely labelled Stable/EXP; joining still resolves identity.
- Refresh and sorting preserve selection identity; hiding the selected row disables
  Join and invalidates outstanding preparation for that selection.
- Record baseline rendering/query timing on a realistic cached dataset, then compare
  combined data of the same total size. Set an explicit acceptable budget before
  merging; assert bounded concurrency/requests and no per-row Steam scanning.

Gate: one browser supports both editions, all visible counts/filters agree, and the
automatic routing milestone remains green.

### Phase 5 — Retire global server mode and complete release validation

Work:

1. Remove the server-browser edition switch and global Experimental-mode warning.
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
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -v
.venv/bin/ruff format --check wolflauncher tests main.py scripts/render-windows-icon.py
.venv/bin/ruff check wolflauncher tests main.py scripts/render-windows-icon.py
.venv/bin/mypy wolflauncher/paths.py wolflauncher/persistence.py wolflauncher/redaction.py wolflauncher/secret_store.py
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
| Both installed | Combined rows and EXP badge; join Stable, EXP, Stable without visiting Settings |
| Separate Steam libraries | Each join uses its own game path and the intended Workshop source |
| Experimental freshly installed | Setup instructions remain accurate; incomplete first-run setup is not reported as verified ready |
| Install/rescan and uninstall/rescan | Rows/toggle/readiness update; favourites and filter preference survive |
| Manual EXP favourite added while formerly in Stable mode | Resolves to EXP, keeps its star after restart, launches EXP |
| Offline/unknown/conflicting manual server | Clear retry/error; no guessed edition and no wrong-game launch |
| Vanilla and modded server of each edition | Correct preflight and mod paths; no cross-edition reuse |
| Rapid selection/filter changes during mod checks | No stale join; selected target and resulting command agree |
| Provider partial outage | Remaining results usable, failed source identified, cached entries retained appropriately |
| Existing user upgrade | Both profiles and recent records recoverable; no lost stars; legacy ambiguous records resolve before joining |
| Preview, favourite, recent, browser Join | All paths agree on edition and installation |
| Game already running | Second launch blocked with existing actionable guidance |
| Local tools and Stable external engine | Explicit tool edition and Stable preference still work after EXP joining |

## Definition of done

- [x] Phase 0 identity contract and representative evidence are recorded.
- [ ] No release-number or server-name heuristic selects an edition.
- [ ] Models, cache, favourites, aliases, workers, and history preserve identity.
- [ ] Migration/retry/failure tests preserve user data; restoration is documented.
- [ ] Every server launch path selects its context before mods and uses it through handoff.
- [ ] Stale callbacks and cached mod results cannot cross launch contexts.
- [ ] Missing Experimental provides setup guidance and preserves saved entries.
- [ ] One browser displays both editions with EXP badges and a remembered filter.
- [ ] Remote/local filtering, counts, pagination, and partial refresh failures agree.
- [ ] Global server mode is retired; local tools retain explicit edition control.
- [ ] Automated gates pass and the manual matrix has recorded outcomes/limitations.
- [ ] README/help and release notes describe the delivered behaviour accurately.

Completion evidence should include implementation commits, test commands/results,
manual matrix results, migration notes, and any remaining external dependency.
