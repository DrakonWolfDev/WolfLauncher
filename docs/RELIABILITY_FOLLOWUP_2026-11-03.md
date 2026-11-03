# Reliability and background-work follow-up

Source work completed on 3 November 2026. No version bump, installer publication,
WolfAPI deployment, game launch or live Workshop subscription/update was performed.

## Workshop completion and metadata-only edits (REL-01)

The earlier callback-based completion fix remains in place. Forced checks now
capture the published revision and size before asking Steam to update an item.
After a successful helper result, a metadata-only acknowledgement is saved only
if the selected library's installed manifest and bounded file-stat evidence are
unchanged. The acknowledgement is scoped to the resolved Workshop directory,
edition, item, published timestamp/size and local content evidence.

Subsequent checks reuse it only with a live installed, idle Steam state and the
same evidence. New revisions, changed files/manifests, other libraries/editions,
queued downloads, missing live state, cancellation and failed checks cannot reuse
it. The record is an atomic per-item file in the launcher's user-data directory;
it does not modify Steam's ACF or the mod files. File-stat evidence is not a
cryptographic integrity check. Missing/oversized manifests, excessive file counts
and cache-write failures leave the timestamp discrepancy unresolved.

Installed revision reads now use `WorkshopItemsInstalled` from the selected
Workshop library rather than merging timestamps from other libraries or remote
Workshop detail entries. Progress awaiting a completion callback remains incomplete
in the Mods UI. Guarded connection updates now request a forced check when their
published revision is newer, allowing the acknowledgement path to finish that case.

Live Windows and Linux Steam checks remain necessary, including actual delivery
of a completion callback for a metadata-only edit. Automated cases simulate those
callbacks and verify the acknowledgement boundaries.

## Mixed unpublished and Workshop requirements (REL-03)

A protocol-2 entry with a zero-length Workshop ID now represents an unpublished
requirement. Positive Workshop IDs after it are retained. An explicitly encoded
numeric zero, duplicate positive IDs, truncation, bad byte stuffing, unsupported
protocols, overflow and malformed signature framing remain invalid.

Unpublished requirements retain their names without inventing IDs or Steam links.
They are listed as manual/local requirements and block readiness and guarded
launching. The launcher explains that matching folders and instructions must come
from the server administrator. Download actions include only published items;
manual requirements cannot be passed to Steam or treated as the Workshop root.
Automatic matching of unidentified local mod folders is not implemented.

## Perspective investigation (REL-02 remains open)

The user supplied two candidates selected by their names. WolfAPI resolved their
exact query ports, then both answered direct A2S_INFO queries:

| Name | Game endpoint | Query port | Build | Raw perspective tag |
| --- | --- | --- | --- | --- |
| Broken Line -PVP- -HC- -FIRST PERSON- -LOOT+- | 194.55.236.254:2053 | 4053 | 1.30.164289 | no3rd |
| Gears of War -PVP- -THIRD PERSON- -ARENA- | 194.55.236.70:2026 | 4026 | 1.30.164289 | no3rd |

The initial supplied-port and +1/+3 probes timed out; those were not evidence of
offline servers. Captured raw fields are in
[`perspective_candidates_2026-11-03.json`](../tests/fixtures/perspective_candidates_2026-11-03.json).
The camera settings were **not** confirmed in game or from server configuration.
The same tag on both candidates therefore does not establish a universal
inversion. No build-specific inversion or Unknown override has been shipped in
the source changes. Existing raw-tag interpretation is retained. An explicit
normalized provider `perspective` field, when supplied, is now preserved.

Bohemia documents a new vehicle-only third-person setting for 1.30, which adds
another reason to capture the actual settings before designing a workaround:
[server configuration](https://community.bistudio.com/wiki/DayZ:Server_Configuration),
[1.30 experimental notes](https://dayz.com/article/game-update/1-30-experimental-release/dayz-steam-patch-notes).
Next evidence needed: known camera settings plus raw replies for the same build,
including `thirdPersonView=2`, and an independent check of the reported 164200
behaviour. Names alone are never used for perspective classification.

## Optional polling during joining and play (PERF-02)

Automatic favourites polling, provider auto-refreshes and browser status/freshness
scheduling defer while the main window is hidden/minimised, identity/mod checks
are active, preflight is visible, Workshop resolution is running, or a monitored
game session is active. Existing bounded requests can finish; downloads,
cancellation and process monitoring continue.

A lightweight window-owned timer observes the current owners. It does not use a
shared "release" flag that an old request could clear after a newer join starts.
After resuming, it refreshes automatic status according to the user's setting and
reschedules stale-data checks for the visible server browser once. Explicit manual
favourite refreshes remain available. No automatic refresh is enabled when the
user has disabled it.

Game sessions are monitored even when a launch surface does not minimise the
window. Those sessions do not activate the launcher on exit. The monitor allows
startup time and a transient missing process snapshot; shutdown stops both the
optional-polling timer and the game monitor.

The scheduling test suppresses all ten simulated automatic polling ticks while
paused, then permits work after resume. This demonstrates reduced request
scheduling, not a measured CPU, battery or network-byte improvement. Live playing,
Linux and packaged-window behaviour still require manual verification.

## Automated validation

The full local unittest suite ran 861 tests successfully, with 67 platform or
optional-integration skips (794 passed). Ruff 0.15.22 lint and the repository's
formatting gate pass. The interpreter is local Windows Python 3.15.1, with the
existing PySide6 6.11.1 environment on `PYTHONPATH`; QtSvg was preloaded for the
SVG plugin dependency and `QT_QPA_PLATFORM=offscreen` was used. The environment's
old `.venv` launcher points at an unavailable Python 3.12 interpreter, so it was
not used as the executable. These checks do not establish Linux/package behaviour
or replace live Steam/DayZ tests.

Added coverage includes evidence-scoped no-op acknowledgements, changed local
content/manifest and published revisions, library/edition isolation, cancellation,
missing Steam state, worker integration, mixed-manifest decoding and launch guards,
provider-field preservation, polling suppression/resumption, overlapping requests,
and game monitoring without automatic window activation.
