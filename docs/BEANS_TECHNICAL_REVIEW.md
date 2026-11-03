# Beans Launcher core technical review

Reviewed 2 November 2026 against public snapshot
[`fa89a86cbbe0b72a5c2a82de989b336d1c141b94`](https://github.com/TheDmitri/dayzbeans-launcher-core/tree/fa89a86cbbe0b72a5c2a82de989b336d1c141b94).
`SNAPSHOT.txt` identifies launcher version `1.6.1` and private source commit
`dc0781ff98a7dfa8b3c254b03e4c23536e30c1f1`; the published `package.json` says
`1.6.0`. Findings are pinned to the snapshot commit rather than assuming these
version labels are interchangeable. WolfLauncher was at
`1b314377ac9cb038bed4545b24722a83bfff18f4`.

## Scope and conclusion

Beans offers useful lessons beyond [the Flare review](FLARE_TECHNICAL_REVIEW.md):
more detailed Workshop freshness tracking, explicit handling of unpublished mods,
existing DayZ player-profile discovery, and coordination between joins and
background work. These can inform independent improvements to WolfLauncher.

The public repository contains the Electron main process and preload bridge,
not the Angular interface, server discovery/ranking implementation or backend.
Consequently this review cannot compare the full browser, its performance, the
renderer-side interpretation of results, or the complete installed product.
The [licence](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/LICENSE)
permits inspection and verification but expressly prohibits using its source in
other software. No Beans code was added to WolfLauncher.

## Most valuable implementation lessons

### 1. Model Workshop freshness through completion, including no-op requests

Beans combines Steam's state flags with local install timestamps and Workshop
update timestamps. It captures a freshness target before downloading and checks
that target while waiting. This avoids treating an already-installed item as a
completed update before Steam changes its state.
[Status calculation](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/steam-service.ts#L906),
[completion predicate and wait](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/mod-management.ts#L125)

It also addresses a subtler case: a Workshop timestamp can change while Steam has
no new files to download. Requiring the local install timestamp to reach every
Workshop edit can then cause repeated updates or a wait that never settles.
Beans observes activity for a 45-second grace period, requires a suitably spaced
second request and quiet period, and persists an acknowledged Workshop timestamp.
Queued/downloading states count as activity, preventing an ordinary busy queue
from being classified as a no-op.
[Tracker](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/mod-update-tracker.ts#L1)

WolfLauncher already compares Workshop and local timestamps through
`RequiredMod.remote_update_available` (`wolflauncher/mods.py:103`), and the Flare
review reproduced premature completion in `subscribe_workshop_items()`.
Beans contributes a more complete design for fixing that flow, including what to
do when a download request legitimately changes nothing.

**Recommendation:** use explicit per-item requested, queued, downloading,
completed, failed and uncertain states. Carry the initial freshness target into
the helper and back through post-download revalidation. Test delayed state changes,
rejected requests, metadata-only edits and retries after cancellation.

**Caveats:** quiet time and repeated requests remain a heuristic, not proof that
files match the server. Beans also accepts an advanced local timestamp below its
predicted target. Its persisted acknowledgements are keyed by Workshop ID alone;
WolfLauncher should scope any equivalent to the selected installation and suitable
content evidence so one library's result cannot bless another library's older copy.
Keep unavailable evidence distinct from verified freshness: Beans falls back to
Steam flags when a Workshop query fails despite its stronger-sounding comments.

### 2. Preserve unpublished mod entries without losing subsequent Workshop mods

Beans decodes a zero-length Workshop ID as an unpublished mod and continues reading
the manifest. Its local-server result separates `unpublishedMods` from downloadable
Workshop requirements. For a server on the same machine it can resolve local mod
folders through a registry of inspected server processes.
[Decoder](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/a2s/dayz-a2s-codec.ts#L286),
[separate requirements](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/local-servers/local-server-discovery.ts#L360)

**Verified locally:** a synthetic protocol-2 manifest containing an unpublished
`Local mod` followed by Workshop item `1559212036` decoded into both entries in
Beans. WolfLauncher's actual decoder rejected the same bytes with
`DayZ mod manifest contains an invalid Workshop ID length`.

WolfLauncher's rejection is safe, but loses useful information about the server's
requirements (`wolflauncher/dayz_mod_query.py:110`).

**Recommendation:** represent unpublished requirements explicitly and preserve the
following valid Workshop entries. Show that the unpublished requirement needs a
local or manual source. Continue blocking readiness until it is resolved; simply
dropping it would allow an incomplete launch. Keep the existing strict protocol,
overflow, duplicate-ID and framing checks.

Beans' packet assembler also checks fragment identity, total count, duplicate
fragments and aggregate size. Its decoder tests include captured server responses,
which are useful precedent for adding realistic fixtures to our existing malformed
input coverage.

### 3. Discover existing DayZ player profiles before choosing a launch name

Beans scans recognised per-profile filenames, ranks profiles by modification time,
resolves the Windows Documents known folder, and checks common Proton locations.
It can clone an existing profile under a new name using exclusive file creation
and attempts to remove partial copies on failure. It also records profile names
before launching so a later new profile can be offered as a possible in-game change.
[Profile handling](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/dayz-profiles.ts#L1)

WolfLauncher currently passes the configured player name, with a `Survivor`
fallback (`wolflauncher/native_launcher.py:156`). Its local development profiles
are mod/launch configurations, a different concept from DayZ's saved player settings.

**Recommendation:** first add a read-only picker for existing player profiles.
This can reduce the experience of apparently reset keybindings/settings when a
new name selects a different profile. Treat cloning as a separate explicit action.
Derive Proton prefixes from the selected Steam library and edition; Beans' shown
candidate list uses common Stable/default-library locations and is not sufficient
as-is for every Experimental or secondary-library installation.

### 4. Give a join priority over background work; reduce idle work deliberately

Beans uses counted join ownership with idempotent release functions. A background
update sweep yields at batch boundaries and resumes once overlapping joins have
ended. Reference counting prevents an older cancelled join from releasing the queue
while a newer retry still uses it.
[Join coordination](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/join-phase.ts#L1)

Its sleep policy also avoids unloading the renderer during a join. Otherwise it
may navigate to a small page after two game-running checks, or after ten minutes
hidden in the tray, and reload the previous route on return.
[Sleep policy](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/deep-sleep-policy.ts#L1)

**Recommendation:** for WolfLauncher, prioritise connection-critical work and
pause nonessential discovery/image polling while hidden or playing, then refresh
stale visible data on return. Keep downloads, cancellation and required process
monitoring active. Our existing single Workshop-session guard and shutdown
coordination already cover part of this problem. Only introduce a counted queue
owner if concurrent work actually needs it; do not add background update sweeps
just to reproduce Beans' architecture.

Renderer unloading is specific to Electron. No comparative CPU or memory numbers
were measured, so this is a policy lesson rather than evidence that Beans is
lighter than Qt or Flare. The public suspension service exposes notifications and
callbacks; renderer-side responses are outside this repository.

### 5. Make shipped code independently verifiable

Beans publishes a manifest of compiled main-process JavaScript hashes and a
script that compares it with a compilation or the contents of `app.asar`. Public
CI recompiles on Windows, Linux and macOS and compares those hashes. Source maps
are excluded because they contain machine-specific paths. Separate documentation
describes artifact hashes and Sigstore bundles.
[Hash tooling](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/scripts/electron-hashes.js#L1),
[verification workflow](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/.github/workflows/verify.yml)

WolfLauncher already publishes and checks artifact SHA-256 manifests. The additional
lesson is linking packaged contents to a public source commit and verifiable build
provenance. Consider signed provenance and a packaged-file inventory before
claiming reproducible AppImage or Windows builds. Matching a hash manifest alone
does not establish that code is safe, and reproducibility of the published core
does not reproduce the unpublished renderer. This review did not rebuild Beans'
release or verify an installed binary or Sigstore bundle.

## Other patterns and limits

- **Validated boundaries:** Beans requires a schema when registering IPC handlers,
  including explicit no-argument schemas, and restricts external-link schemes.
  Useful precedent for WolfLauncher's helper messages and future URL handler;
  Electron's renderer boundary itself is not something Qt needs to emulate.
  [Registration](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/ipc-register.ts#L1)
- **Connection identity:** direct-address lookup only accepts candidate query
  responses whose advertised game port matches the requested server, with a
  narrow fallback for an explicit query-port hint. This is a useful invariant to
  retain alongside WolfLauncher's existing endpoint/edition validation.
  [Lookup](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/local-servers/local-server-discovery.ts#L263)
- **Batched Workshop queries:** Beans asks for metadata in pages rather than one
  request per mod. WolfLauncher already batches public Workshop metadata; this is
  shared practice, not a new missing feature.
- **Offline storage:** atomic temporary-file/rename writes keep large server
  snapshots separate from small settings. WolfLauncher already uses SQLite for
  discovered servers; replacing it with Beans' opaque snapshot file would not
  provide an established improvement.
- **Test seams:** Steam, spawning and timing can be replaced for development end-to-end
  checks, with the environment-controlled hooks disabled in packaged builds.
  Useful precedent for testing an entire join flow without starting a game.
  [Hooks](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/e2e-hooks.ts#L1)

## Implementations to avoid adopting unchanged

The updater requires a SHA-256 match, but the expected checksum comes from the same
backend-controlled metadata as the download URL. Its inspected install path does
not perform an independent signature/provenance check. Linux replacement copies
directly over the running AppImage and checks its size afterward, without an
atomic replacement/rollback path. Keep this distinct from published manual
verification instructions and Windows installer signing.
[Update verification and installation](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/update-service.ts#L569)

The Windows launch path automatically kills existing DayZ processes before
launching. WolfLauncher should retain user control over an existing game session.
Beans also trims server passwords, so the whitespace-preserving Flare behaviour
remains the better reference for that detail.
[Launch path](https://github.com/TheDmitri/dayzbeans-launcher-core/blob/fa89a86cbbe0b72a5c2a82de989b336d1c141b94/src/electron/dayz-launcher.ts#L180)

Beans' decoder returns unsupported protocol versions rather than rejecting them,
and accepts a missing signature-count byte. Both were reproduced in isolation.
Its local probe still reads `no3rd` without the version-dependent workaround
reported by Flare. Preserve our strict parsing and independently validate the
perspective-tag report instead of treating either competitor as authoritative.

Its main process also implements persistent install identifiers in update checks
and crash reporting enabled by default. Those are product/privacy choices, not
prerequisites for better launch reliability, and do not follow automatically from
adopting the engineering lessons above.

## Comparison with Flare and verification

| Area | Most useful evidence from these reviews |
| --- | --- |
| Workshop completion | Beans' target-aware waiting and no-op handling expand on Flare's timestamp/callback grace period. |
| Server/client mod compatibility | Flare's PBO/server hash comparison remains the distinctive implementation; no equivalent was found in the inspected Beans core. |
| Unpublished requirements | Beans preserves and separates them; WolfLauncher currently rejects the manifest. |
| Player profiles | Beans offers discovery, selection support and cloning absent from the inspected WolfLauncher launch path. |
| Large browser rendering | Flare exposes its virtualised table; Beans' unpublished interface prevents comparison. |
| Release verification | Beans exposes core hash reproduction tooling; WolfLauncher already has artifact hashes and packaging smoke checks. |

Validation performed:

- **83 existing Beans standalone logic specifications passed** across the tracker,
  join ownership, sleep policy, Workshop batching, install locator, external links,
  A2S codec and local-server parsing. They ran using Node's TypeScript transform
  with a small Jasmine-compatible assertion harness in `/tmp`, not the project's
  full Angular/Electron runner or a TypeScript type check.
- **136 targeted WolfLauncher tests passed** for mod rules, Workshop subscriptions
  and dependencies, mod checks, local tools/servers, lifecycle and native launching.
- Compared the same synthetic mixed unpublished/Workshop manifest in both decoders;
  also exercised unsupported protocol and missing signature framing in Beans.

No real Steam operations, subscriptions, game launches, profile changes or updates
were performed. No installed-product performance benchmark was run. The existing
changelog edit and Flare report were preserved; only this review document was added.

Suggested combined order: fix Workshop completion with both delayed-state and no-op
cases; investigate the perspective-tag report; improve unpublished-mod diagnostics;
evaluate Flare-style hash compatibility; add existing-player-profile selection;
then profile table rendering and idle background work before larger changes.
