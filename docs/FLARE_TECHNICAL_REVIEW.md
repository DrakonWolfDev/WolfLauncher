# Flare Launcher technical review

Reviewed 2 November 2026. Flare revision
[`89954428a15745fe10d5f3dc351ac6fdedd20f8c`](https://github.com/CallMeLewis/flare-launcher/tree/89954428a15745fe10d5f3dc351ac6fdedd20f8c),
version `1.6.1-beta.1`; WolfLauncher revision `1b314377ac9cb038bed4545b24722a83bfff18f4`.
WolfLauncher's existing uncommitted changelog edit was left untouched.

## Assessment

Flare offers several worthwhile implementation ideas, particularly around Workshop
update completion and server/client mod compatibility. Its Rust/Tauri/React stack
does not by itself demonstrate better performance or reliability than Python/Qt.
The useful improvements can be implemented within WolfLauncher's current architecture.

This is a source review with targeted local experiments, not a runtime comparison
of installed launchers. The public checkout requires a **private `flare-common`
repository** for UI components, its updater and release tooling. A complete Flare
build and updater audit could not be performed from the public source alone.
[Flare development instructions](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/docs/development.md#run)
explicitly document this dependency. They also disclose that core Steam/DayZ
download and launch paths have not been exercised with real installations on either
platform, and browser join links have not been tried on either platform. Build and
smoke-test coverage should therefore be distinguished from game integration evidence.

## Prioritised opportunities

### 1. Fix premature success during forced Workshop updates — high priority

Flare records each installed item's timestamp before requesting a download. For
the first 20 seconds it does not accept an unchanged installed state as completion
unless a successful download callback arrives or the timestamp changes. It also
records download/subscription failures and checks whether Steam closes during a
download.
[Implementation](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/workshop.rs#L195)

WolfLauncher's `subscribe_workshop_items()` requests forced downloads and then
immediately accepts an installed snapshot plus an existing directory
(`wolflauncher/workshop_subscription.py:365`, completion check at line 416).
Steam can expose the old installed state before publishing its update state.

**Reproduced locally:** using the repository's `FakeWorkshopClient`, supplied the
sequence `INSTALLED → INSTALLED|NEEDS_UPDATE → DOWNLOADING → INSTALLED` with an
existing item directory and `force_update=True`. The function returned success
after observing only the first state (`4`); states `12`, `16`, and `4` remained
unread. This establishes the control-flow issue under delayed Steam state changes;
it does not measure how often real Steam exhibits that timing.

**Recommendation:** track update requests through an explicit pending state and
require completion evidence before reporting success. Include rejected download
requests and Steam disconnection in the outcome. Use a bounded wait with a clear
uncertain result where completion cannot be established. Flare's 20-second grace
period is a useful mitigation, but elapsed time alone is not proof of completion.
The existing ready-item force-update test verifies that a download was requested;
add a delayed-state regression case that verifies completion was actually awaited.

### 2. Retain server mod hashes and explain version mismatches — high value

Flare reads the server's advertised mod hashes, collects the SHA-1 trailers from
local PBO files, combines them using its implementation of DayZ's hash algorithm,
and reports differing mods. It reads only the trailing 20 bytes of each PBO, avoiding
a full scan of potentially large mod files. It also handles a reported Linux server
case involving duplicate PBOs with differently cased names; that compatibility
search is capped at 12 PBOs because the number of combinations grows exponentially.
[Hash implementation](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/mod_hash.rs#L1)

WolfLauncher already reads each server mod hash but discards it in
`wolflauncher/dayz_mod_query.py:110`. Keeping it would enable a useful distinction
between missing files, an available Workshop update, and files differing from the
server's copy.

**Recommendation:** retain the hash in the parsed model, validate the algorithm
against captured server/local fixtures, then add asynchronous compatibility checks
for the selected server. Start with advisory results. Preserve separate states for
matching, differing, and unavailable evidence, and invalidate local results when
the installed files change. A trailer comparison is not a full file-integrity check.

Flare returns an empty mismatch list when queries or local reads cannot establish
a result, and its UI describes differing mods as the server lacking the latest
version. A mismatch alone does not establish which side is newer. WolfLauncher
should say “different from the server” unless further evidence supports direction.
[UI checks](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src/components/server-detail.tsx#L216)

### 3. Validate the reported DayZ 1.30 perspective-tag change — investigate soon

Flare has a version-dependent interpretation of `no3rd`: from DayZ 1.30 it inverts
the tag. Its documentation reports checking server build `1.30.164200` and explains
how to reproduce the behaviour with `thirdPersonView = 0`.
[Workaround and tests](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/servers.rs#L176),
[reported evidence](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/docs/development.md#dayzs-mistakes)

WolfLauncher's `perspective_from_keywords()` interprets the tag without a version
(`wolflauncher/server_perspective.py:4`). **If Flare's reported behaviour is
confirmed, this can reverse our perspective labels and filters for affected raw
query results.** This review did not independently verify a running 1.30 server.

**Recommendation:** capture responses from known first- and third-person servers
and check the WolfAPI normalisation contract before changing the client. Apply
any workaround only to affected versions and raw sources; already corrected
provider values must not be inverted again. Define an upper version boundary when
the game fixes the tag, rather than assuming all future versions remain affected.

### 4. Use a model-backed server table — medium priority, profile first

Flare uses a virtualised table with stable row keys and 12 rows of overscan. Only
the visible portion and its buffer need rendered row elements.
[Table](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src/components/server-table.tsx#L137)

WolfLauncher creates 18 table items per displayed server and a QWidget/layout/label
for each favourite marker (`wolflauncher/server_browser_table.py:37`, `:131`).
Repaint suppression helps, but allocation and refresh work still scale with all
displayed rows. There are no comparative timings in this review.

**Recommendation:** benchmark table population, filtering and scrolling at realistic
row counts. If significant, use `QTableView` with `QAbstractTableModel` and painted
delegates for stars/icons. Preserve stable selection, sorting and incremental
enrichment updates. This is a Qt implementation change, not a reason to change stacks.

Flare also deduplicates simultaneous ICMP probes by host, labels A2S response-time
fallbacks as estimates, and batches UI result notifications every 250 ms.
[Query handling](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/query.rs#L294),
[scheduler](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src/hooks/use-pings.ts#L25)
These are useful refinements, subject to measurement. **Visible-row query priority
is already implemented in WolfLauncher** at
`server_browser_feature.py:1255`; it is not a missing feature.

### 5. Separate directory metadata from frequent live counts — coordinated API work

Flare downloads a full directory conditionally using ETags and refreshes player
counts from a separate small live response. It also uses shared mod ID/name tables
to avoid repeating mod strings for each server.
[Directory and live refresh](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/servers.rs#L429)

WolfLauncher's inspected WolfAPI directory fetch requests the JSON representation
and parses the returned rows (`wolflauncher/server_discovery.py:562`). A similar
split could reduce repeated payloads, but requires an agreed WolfAPI contract and
measurements of compressed transfer size and refresh frequency.

**Recommendation:** consider conditional snapshots plus small dynamic updates with
explicit timestamps, stable identities, removals and cache retention rules.
Preserve edition isolation and selected-server live checks. Flare's exact cache
implementation should not be copied unchanged: its 15-minute generation-age check
runs when a body is parsed, while a `304` reuses cached servers without rechecking
their generation time. Its live response has no timestamp to establish count age.
These are static source findings, not a reproduced production outage.

### 6. Adopt the join-link delivery pattern for the existing roadmap

Flare implements an HTTPS share page leading to a custom launcher scheme. Links
select a server and leave Play to the user. A pending address survives frontend
startup, and single-instance delivery brings the existing window forward. The
parser excludes passwords, extra paths and arbitrary launch parameters.
[Link handling](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/links.rs#L1)

This maps well to `docs/ROADMAP.md`'s direct server links. Retain WolfLauncher's
edition-aware server resolution, live checks, and existing Workshop confirmation.
Test cold start, an already open window, invalid links and unavailable servers.
Flare's browser-to-launcher delivery is explicitly documented as untested.

### 7. Smaller platform and product ideas

- **AppImage child-process environment:** Flare strips paths and variables pointing
  inside its AppImage before opening Steam or desktop applications. WolfLauncher's
  QProcess launch path does not visibly apply an equivalent scrub. Test an actual
  packaged launch for inherited-library problems before introducing a narrowly
  scoped environment helper. This is a plausible gap, not a reproduced failure.
  [Environment helper](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/desktop.rs#L61)
- **Linux preflight:** Flare reads `vm.max_map_count` and offers advice when below
  its chosen threshold of 1,048,576. Consider a read-only Settings health check after
  verifying DayZ's requirement; avoid silently changing system settings.
  [Check](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/launch.rs#L223)
- **LAN discovery:** bounded UDP broadcast discovery across interface broadcast
  addresses, followed by direct info/mod queries, could complement WolfLauncher's
  local-server tooling. It covers six default query ports, so cannot promise to
  find every custom-port server.
  [LAN implementation](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/lan.rs#L1)
- **Translations:** Flare has catalogues and checks for missing translations and
  lost placeholders, including backend error-template consistency. Useful precedent
  when localisation becomes a product priority.
  [Catalogue tests](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src/lib/i18n.test.ts#L49)
- **Updates:** visible configuration requests signature and signed-version checks;
  CI includes Windows signing and artifact startup tests. These are useful product
  capabilities, but the private updater implementation prevents verification of
  its download, replacement and recovery behaviour. WolfLauncher's current updater
  intentionally provides notifications and a validated destination only.
  [Configuration](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/tauri.conf.json#L43),
  [build workflow](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/.github/workflows/build.yml)

## Safeguards and strengths to retain

WolfLauncher already has a disposable Steam helper, progress/stall handling, direct
mod queries, selected-server validation, viewport-prioritised live checks, a SQLite
cache, Stable/Experimental separation and artifact packaging checks. The AppImage
builder starts the actual artifact, Debian CI instantiates the main window, RPM
checks installation/startup/removal, and Windows scripts test packaged artifacts.
Flare's smoke tests therefore offer refinements rather than an absent testing layer.

WolfLauncher's binary manifest validation is stricter. An isolated Rust harness
compiled from Flare's unmodified `Reader`, `parse_mods()` and supporting parser
functions accepted all of these as `Some([])`:

| Input manifest | Result in Flare's extracted parser |
| --- | --- |
| Valid empty protocol-2 manifest | Accepted |
| Unsupported protocol 99 | Accepted |
| Protocol 2 with overflow flag set | Accepted |
| Empty manifest lacking the signature-count byte | Accepted |

WolfLauncher validates protocol, overflow, byte stuffing, IDs and signature framing
in `dayz_mod_query.py:69`. Preserve those checks when adding hash support. Accepting
an incomplete manifest as an empty mod list risks treating an uncertain requirement
as a vanilla server.
[Flare parser](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/query.rs#L150)

For listed servers, Flare's Play path reads cached directory mods and its backend
launch reads the same server cache; the hash check is asynchronous and does not
gate Play. Keep WolfLauncher's connection context and live preflight rather than
taking the shorter cached launch path as a reliability improvement.
[Play flow](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src/App.tsx#L451),
[backend launch](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/launch.rs#L147)

## Verification and suggested order

Ran successfully in WolfLauncher's existing virtual environment:

```sh
.venv/bin/python -m unittest tests.test_dayz_mod_query \
  tests.test_workshop_subscription tests.test_server_perspective \
  tests.test_server_enrichment tests.test_native_launcher -q
```

**101 tests passed.** Additionally ran the delayed-update reproduction against
WolfLauncher's actual function and the isolated Flare parser harness described
above. No live Steam actions, subscriptions, game launches, package installations,
or comparative performance measurements were performed. No application code was
changed by this review.

Suggested sequence: fix the forced-update completion race; validate the perspective
tag report; retain and evaluate mod hashes; profile table rendering; implement the
already planned join links; then consider the coordinated directory/live API split.
