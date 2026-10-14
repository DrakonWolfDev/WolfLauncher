# Wolf Launcher — Local next-bug investigation notes

Status: active investigation notes

## Objective

Investigate and fix three reported reliability issues without broad UI or launch-flow
redesign. Preserve existing Linux and Windows behaviour except where a test proves the
reported behaviour is wrong.

Wolf Forge principle: **Calm on the surface. Detailed underneath.**

## Priority 1 — Editor mod rows disappear while scrolling

Status: implemented locally on 13 October 2026. The picker remains effect-free and
the separate selected-mod summary now creates static pills without per-row graphics
effects or animations. Regression coverage exercises 60 picker rows and 46 summary
pills, including scroll, filter, refresh, selection state, and effect ownership.

### Report

Darren found that, with a large installed-mod collection, entries in the Editor page's
left-hand mod list can disappear while scrolling up and down. The issue was reproduced
with approximately 54 mods.

A later build with 46 enabled mods showed the same visible symptom in the separate
`DayZ Editor selection` panel: some selected-mod pills rendered normally while several
intervening rows were blank. This proves the picker-only mitigation is not sufficient.
The selection panel still creates a `QGraphicsOpacityEffect` and animation for every
pill in `_update_selected_mod_pills()`, so that path must be isolated and covered too.

### Relevant implementation

- `wolflauncher/local_tools_feature.py::_refresh_editor_mod_picker()` rebuilds the
  `QListWidget`, applies a fixed row size, and then reapplies the filter.
- `_filter_editor_mod_picker()` hides individual items based on the current text.
- The picker uses uniform item sizes. Its widget-level opacity effect was removed after
  it was identified as unsafe for a long virtualized item view.
- `_update_selected_mod_pills()` previously gave every selected-pill frame its own
  opacity effect and short animation. Those per-pill effects have now been removed.

### Investigation

1. Reproduce with at least 54 realistically named Workshop entries, including enough
   rows to scroll well beyond one viewport.
2. Confirm whether the underlying item count and hidden flags remain correct when rows
   disappear. This separates data loss/filtering from a paint or viewport problem.
3. Test scrolling both directions after refresh, filter, filter clear, selecting mods,
   switching Editor/Local Server, and changing window/DPI scale.
4. Temporarily isolate uniform item sizing and explicit size hints in the picker, then
   separately remove the per-pill effects/animations from the selection summary to
   identify the smallest causal change.
5. Check Windows and Linux native Qt styles; do not rely on a platform-specific visual
   workaround unless the failure is demonstrably platform-specific.

### Acceptance criteria

- A list of at least 60 mods remains fully visible and scrollable in both directions.
- Scrolling never changes the model count, selection, check state, or filter state.
- Refreshing or clearing a filter keeps the correct rows visible.
- Editor dependency rows and user-selected rows retain their current behaviour.
- Add regression tests for both the long picker and a selection summary containing at
  least 46 pills. Exercise scrolling, refresh/filter state, and effect ownership;
  include a focused manual rendering check if Qt painting cannot be asserted reliably
  in the automated suite.

## Priority 2 — Windows Connect opens/selects DayZ Tools instead of DayZ

Status: reproduced three times by Andi on 14 October 2026 with DayZ Tools and
DayZ Publisher open. Direct BattlEye handoff implemented and manually verified by
Andi on Windows from the repository: DayZ loaded successfully with Publisher open.
Native Linux regression verification remains outstanding.

### Report

On Windows, if DayZ Tools is already open and the user clicks Connect, Steam selects or
starts DayZ Tools rather than the DayZ game executable. DZSA Launcher reportedly has a
similar problem.

The repeated 14 October report narrows the affected tool to Publisher: Connect
hands off to Publisher, Steam reports DayZ as running, and Steam's force-close/Stop
action closes Publisher instead of the game. This is more than an observed focus
change.

### Current evidence

- Read-only inspection on 14 October found `DayZToolsLauncher.exe` and
  `Publisher.exe` running from the installed DayZ Tools directory, with no
  `DayZ_x64.exe` or `DayZ_BE.exe` in that process snapshot.
- Steam's `logs/gameprocess_log.txt` explicitly records Publisher as a tracked
  process for **AppID 221100**, rather than merely bringing a Tools window forward.
  On 14 October, the log timestamps show Publisher PID 23168 added at 16:13:32,
  PID 5660 added at 16:15:24, and the current PID 12652 added at 17:22:59.
  These are Steam log timestamps; their timezone has not been established.
- The same log associates WolfLauncher `--multiprocessing-fork` worker processes
  with AppID 221100. This warrants checking Steam API initialization and inherited
  app identity in addition to the Connect command. It does not prove that
  WolfLauncher caused Publisher's association.
- The Windows backend matches executable names exactly and case-insensitively.
  The captured `DayZToolsLauncher.exe` and `Publisher.exe` names cannot match the
  configured `DayZ_x64.exe` / `DayZ_BE.exe` game/bootstrap names.

- Before this patch, native launch construction explicitly used `steam.exe -applaunch 221100` for Stable
  DayZ; it does not intentionally select the DayZ Tools app.
- Windows running-process matching compares exact executable names for `DayZ_x64.exe`
  and `DayZ_BE.exe`; `DayZDiag_x64.exe` is already excluded by tests.
- Andi's control test confirms Publisher is registered as DayZ even with WolfLauncher
  closed. Its misleading Steam running status is an external quirk and no longer
  blocks the verified WolfLauncher handoff; correcting that status is outside this fix.

### Investigation

Andi confirmed that Steam reports DayZ running with Publisher open even when
WolfLauncher is closed. The official DayZ launcher waited at “Launching BattlEye”
but eventually started the game and allowed a server join. A captured process command
from that successful Stable launch was:

```text
"<DayZ install>\DayZ_BE.exe" 0 1 1 -exe DayZ_x64.exe -name=Andi
"-mod=<absolute !Workshop mod paths separated by semicolons>"
-connect=198.244.177.109:2702:2703
```

The patch uses this bootstrap sequence for Windows Stable Connect and preview,
retaining WolfLauncher's prepared absolute mod paths and using game and query ports.
It starts in the selected DayZ directory and retains the existing BattlEye monitoring
and retry handling. A missing bootstrap fails with setup guidance rather than falling
back to the affected Steam handoff. Linux Stable/Experimental keep their Steam app-ID
handoff; Windows Experimental and offline/local-session command construction are
unchanged. Publisher's Steam registration itself is not changed.

Validation: focused unittest run passed on Windows (18 executed, 48 Linux-only tests
skipped), including simulated Linux Stable/Experimental command contracts. Native
Linux tests remain required. Andi subsequently ran the patched repository launcher
on Windows and confirmed the game loaded with Publisher open. The source checkout
required Node on PATH and `npm.cmd ci --prefix .\packaging\npm --ignore-scripts`
for its local GameDig dependency before testing.

1. Reproduce on Windows with Steam running, DayZ Tools open, and DayZ fully closed.
2. Record the exact process names/paths before and after Connect and the copyable launch
   report/command generated by Wolf Launcher.
3. Test both the normal Stable native path and any configured external-launcher path.
4. Confirm whether Steam receives app ID `221100`, whether DayZ briefly starts, and
   whether focus merely returns to Tools versus Tools actually being launched.
5. Repeat with DayZ Tools closed as the control case and, if useful, with Steam freshly
   restarted.
6. If Steam misroutes a correct `-applaunch 221100` request while Tools is open, test a
   narrowly scoped handoff alternative. Do not kill DayZ Tools or unrelated processes
   without explicit user consent.
7. Capture Steam's process-tracking log before Connect as well as after it: Publisher
   may already be registered under DayZ's app ID before the launch request. Compare
   Publisher alone, Tools alone, and both open, then correlate the copyable WolfLauncher
   command with Steam's launch records. Check scoped Steam app identity handling in
   Workshop workers without changing the parent process environment speculatively.

### Acceptance criteria

- Connect targets the correct DayZ product and executable while DayZ Tools is open.
- DayZ Tools is neither treated as an already-running game nor selected as the launch
  target.
- Stable and Experimental routing remains product-correct.
- Existing BattlEye bootstrap handling and duplicate-launch protection still work.
- Add Windows-oriented regression coverage using captured process names and the exact
  generated launch command; complete one real Windows verification because mocked
  subprocess tests cannot prove Steam client behaviour.

## Priority 3 — Server status failures are presented as offline

Status: implemented locally on 13 October 2026. Status checks now preserve explicit
online, offline, timeout, network-error, invalid-response, cancellation, and general
check-error outcomes. Unproven failures render and count as unknown. Completed refresh
batches show one recoverable status-bar notice when every attempted check fails, with
the notice reset after recovery. The persisted status cache and copyable diagnostics
include query timing, last success, consecutive failures, endpoint and safe error detail.

### Report

One Windows installation showed all seven configured servers as:

`0 online · 7 offline`

Each server displayed `offline, restarting, or incomplete query response`, while the
same servers were online from another Wolf Launcher installation and in CF Cloud.
Restarting Windows cleared the problem. The root cause is unknown and there is no
evidence that Wolf Launcher caused it, but the incident exposed misleading status and
weak diagnostics.

### Relevant implementation

- `wolflauncher/status.py::ServerStatus` currently reduces every failed outcome to
  `online=False`, while the `error` string carries DNS, timeout, subprocess, malformed
  response, and incomplete response detail.
- `check_server()` uses the same false value for a confirmed unavailable response and
  for a query failure.
- `curated_servers_controller.py::update_curated_status_summary()` counts the rendered
  `OFFLINE` rows, so query failures can inflate the offline total.
- Workers and presenters construct and consume the same binary status model; the change
  must be carried end-to-end instead of changing only display text.

### Required behaviour

Represent what is actually known. Use explicit internal outcomes where the protocol and
query tool support them, for example:

| Outcome | Suggested user wording |
|---|---|
| Online response | Server online |
| Confirmed unavailable/offline | Server offline |
| Query timeout | Server isn't responding |
| DNS/socket/network failure | Unable to check server |
| Invalid or incomplete response | Couldn't read server status |
| Not checked yet | Waiting for first check |

If the available evidence cannot prove a server is offline, classify it as unknown or
unavailable rather than confirmed offline.

The summary should report known and unknown states, for example:

`0 online · 0 offline · 7 unknown`

When every completed query fails, show one unobtrusive, non-repeating notice explaining
that no server statuses could be checked and offering refresh/diagnostics. Do not claim
that the internet connection is broken.

### Diagnostics and recovery

Capture safe troubleshooting data through the existing logging/support-report path:

- endpoint and query port;
- query start time and duration;
- normalized failure category and safe error detail;
- timeout occurrence;
- last successful query time; and
- consecutive failure count.

Never log passwords, Steam credentials, tokens, or raw sensitive environment data.
Consider retaining last-known good details, but mark them stale with their observation
time and never present them as current status.

Ensure failed queries release their process/socket resources, automatic retries remain
bounded, manual refresh works, and a successful later query clears the error state.

### Acceptance criteria

- Failed queries are not automatically counted as confirmed offline.
- The summary distinguishes online, offline, and unknown/not-checked states.
- DNS failure, timeout, non-zero GameDig exit, malformed JSON, incomplete response, and
  cancellation have explicit tested outcomes.
- A widespread-failure notice appears only after enough checks complete and is not
  repeated on every automatic refresh.
- Last-known data, if retained, is visibly stale and cannot be mistaken for a fresh
  connection decision.
- Recovery works without restarting Wolf Launcher on Windows and Linux.
- Existing server discovery, identity resolution, saved-server compatibility, and
  Connect behaviour remain unchanged.

## Priority 4 — Update check delays application shutdown

Status: implemented locally on 13 October 2026 and corrected after manual retesting.
Update checks now have a cooperative cancellation signal. Shutdown releases the Qt
worker promptly, suppresses late results, and prevents a cancelled transport from
recording a successful check. Manual retesting also exposed two confounding issues:
the update-check status message was not cleared after completion, and concurrent server
status workers ignored shutdown interruption. The message now clears and GameDig probes
receive a cancellation event so they terminate promptly during application shutdown.

### Report

Closing WolfLauncher while the status bar said `Checking for WolfLauncher updates…`
left the application open long enough for the shutdown dialog to change to:

`A background check is taking longer than expected. WolfLauncher will close as soon as it stops safely…`

That message appears only after the shutdown coordinator's 15-second deadline, so this
was not merely a brief orderly handoff.

### Current evidence

- `wolf_update.qt.QtUpdateChecker` runs `UpdateService.check()` in a `QThreadPool` and
  is included in the runtime worker list as `update_thread`.
- `GitHubReleaseSource` passes a nominal 10-second timeout to `urllib.request.urlopen()`.
- Shutdown calls `requestInterruption()` on active workers. The update checker now
  signals cancellation and promptly releases its Qt runnable while the bounded urllib
  operation winds down independently.
- The coordinator can kill the separate WolfAPI `QProcess` after its shutdown deadline.
  Update cancellation does not forcibly terminate Python threads; it releases the Qt
  worker while the bounded daemon transport winds down independently.

### Required behaviour

An in-progress automatic or manual update check must not keep WolfLauncher visible for
an unbounded period after the user closes it. Shutdown should request real cancellation
and complete promptly, while avoiding unsafe forced termination of a Python/Qt worker
thread.

### Investigation

1. Reproduce with a deliberately stalled opener/DNS path and record time from close
   request to process exit.
2. Add cooperative cancellation around update transport work, or use a transport whose
   reply can be aborted safely from the owning Qt thread.
3. Treat configured network timeouts as a final safety bound rather than relying on a
   no-op interruption method.
4. Ensure late results cannot update widgets, show dialogs, or persist state after
   shutdown has started.
5. Verify normal completed checks, failed checks, and repeated checks still release all
   runnable/signal objects cleanly.

### Acceptance criteria

- Closing during a stalled update check exits within a short, documented bound and
  does not reach the 15-second overdue message under the controlled test.
- `requestInterruption()` or an equivalent shutdown method causes meaningful,
  test-covered cancellation.
- Shutdown remains non-blocking on the GUI thread and does not forcibly terminate a
  running Python thread.
- No update result UI or settings write occurs after shutdown begins.
- Normal automatic and manual update checks continue to work on Windows and Linux.

## Priority 5 — Edition verification message never clears

Status: implemented locally on 13 October 2026. Successful edition resolution now
clears the exact status-bar message owned by that request. Invalidated, replaced, and
stale requests also clear only their own message, avoiding both an indefinitely stale
“Verifying…” state and accidental removal of a newer status message.

### Report

After selecting New Dawn Pripyat, the status bar remained on
`Verifying the DayZ edition for New Dawn Pripyat…` for an apparently indefinite time.
The resolution worker was not necessarily still active: the coordinator displayed the
message when work started but never cleared it on the successful continuation path.

### Acceptance criteria

- Successful resolution clears the verification message before continuing.
- Failure still replaces it with the actionable error for a bounded time.
- Selection changes, cancellation, and replacement requests cannot leave stale text.
- A late callback cannot clear the message belonging to a newer request.

## Priority 6 — Force update rejects installed-library selections

Status: implemented locally on 13 October 2026. “Force Steam update selected mod” now
uses the selected installed-Workshop row when the all-mods library view is active. It
starts a one-item library update session and refreshes that library on completion,
without requiring an unrelated selected-server mod check. Server-specific rows retain
their existing request-context validation.

### Report

Using Force Steam update in the Installed DayZ Workshop library incorrectly displayed
`Mod check unavailable` and asked for the selected server to be rechecked. The shared
button handler only searched the last server-specific `ModCheckResult`, even though the
button had been enabled from an installed-library selection.

### Acceptance criteria

- A selected installed-library mod can be submitted for a forced Steam update check.
- The operation does not require or reuse a server-specific mod result.
- Existing Steam-running, installation, confirmation, and single-operation guards apply.
- Server-specific force updates continue to require a matching successful server check.

## Suggested delivery order

1. Reproduce and fix the Editor list rendering issue because its scope is isolated.
2. Capture a real Windows launch report with DayZ Tools open, then fix only the proven
   handoff or detection fault.
3. Refactor server status into explicit outcomes, update summaries/diagnostics, and add
   recovery coverage as a focused reliability change.
4. Make update checks cooperatively cancellable and bound close latency with a focused
   lifecycle regression test.
5. Clear edition-verification status ownership on success, failure, cancellation, and
   request replacement.
6. Route installed-library force updates through the library update workflow rather
   than selected-server validation.

Keep each issue as a separate reviewable change with its own regression tests.
