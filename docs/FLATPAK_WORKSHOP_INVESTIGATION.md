# Flatpak Steam Workshop Investigation (Archived)

## Release position

Flatpak Steam is not currently compatible with WolfLauncher. It is excluded
from Settings, Auto detection and launch handoff, along with Snap Steam. This
document preserves the failed lifecycle evidence and the criteria that would
be required before a future deliberate compatibility project could restore it.

During packaged testing on Linux Mint 22, a disposable helper that loaded
Steamworks with DayZ's app ID could leave Steam reporting DayZ as running after
both `SteamAPI_Shutdown()` and the helper's process exit. This blocks a later
DayZ launch and is therefore a correctness failure, not a cosmetic one.

Flatpak users must install Valve's native Steam package before using
WolfLauncher. The historical acceptance criteria below remain the minimum
evidence for reconsidering that decision.

This is historical failure evidence, not release certification.

## Investigation protocol

Do not modify the production helper or re-enable automation before reproducing
the problem with a minimal probe on a packaged WolfLauncher installation.

For each run, record the OS and version, Flatpak and Steam versions, Steam
channel, Proton version, DayZ build, launcher artifact checksum, account state,
and the selected Steam library location. Capture redacted timestamps for:

1. immediately before the probe;
2. after `SteamAPI_InitSafe`;
3. after the first UGC state query or subscription request;
4. after `SteamAPI_Shutdown` and helper process exit; and
5. after 5, 30 and 60 seconds.

At each timestamp collect `flatpak ps`, the Steam/DayZ process state, and
relevant Steam logs. Preserve only redacted data in the repository or issue.

Run the following cases independently, starting Steam from a clean stopped
state and repeating each case at least three times:

1. Launch-only control: no Steamworks helper.
2. Helper initialization and shutdown only.
3. Read-only `ISteamUGC::GetItemState` query.
4. One known installed item.
5. One missing item after explicit confirmation.
6. Cancellation, timeout/stall, and forced helper termination.

The current helper is a host process loading the Steam API library from a
Flatpak Steam installation. If the minimal probe reproduces the failure, the
next experiment is a deliberately isolated helper running inside the Flatpak
runtime. Do not assume that this is feasible or safe: prove the runtime,
library, permissions, Steam client visibility and shutdown semantics first.
Do not mix this experiment with the supported native-Steam path.

## Reconsideration criteria

Flatpak compatibility may be reconsidered only when all of the following are
true:

- the minimal probe has a documented explanation or a demonstrably reliable
  runtime boundary;
- every probe case leaves Steam no longer reporting DayZ as running within 60
  seconds after helper exit, across three consecutive runs;
- a packaged-artifact test passes ready, missing, update, cancellation/stall,
  helper-close, Steam-stopped and Steam-running cases;
- the normal DayZ handoff succeeds immediately after each completed or aborted
  helper session; and
- a complete Flatpak compatibility row is added back to
  `RELEASE_CHECKLIST.md`, rerun and recorded as passed.

Any failure keeps Flatpak excluded. The helper exiting with a zero status is
not sufficient evidence.
