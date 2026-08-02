# WolfLauncher Project State

Updated: 2026-08-01

WolfLauncher is a Linux-primary DayZ launcher GUI built with Python and PySide6,
with experimental portable and installed Windows builds.
The v0.8 native-launch baseline is validated and tagged; v0.9 production
hardening is the active cycle. The native Python engine is the default and the
vendored MIT shell launcher remains a visible compatibility fallback.

The approved v1.0 Linux support contract is Debian 13, Ubuntu 24.04 LTS,
Ubuntu 26.04 LTS and Linux Mint 22.x through native Steam. Flatpak and Snap
Steam are not compatible and are excluded from detection, Settings and the
release matrix.

## Current truth

- Native Steam handoff has passed real-desktop testing with Steam running and
  stopped, unmodded servers, complete mod sets and missing/update flows.
- Flatpak Steam packaged testing failed PR-08 because its isolated Steamworks
  Workshop helper could leave DayZ marked as running after helper shutdown.
  Flatpak and Snap Steam are now explicitly incompatible: neither is exposed
  in Settings or Auto detection, old saved choices migrate to Auto, and stale
  Flatpak native-launch requests fail before handoff.
- Ubuntu 24.04.4 LTS completed the native-Steam launch path on an Intel Core
  i5-8250U with 8 GB RAM. The experience was slow and unpleasant, so this is the
  current provisional minimum functional specification rather than a
  recommended specification. Distro overhead versus hardware limits has not
  yet been isolated.
- Windows 10 completed the native Steam/DayZ launch handoff on an Intel Core
  i5-8250U with 8 GB RAM. This is the Windows functional baseline; Windows
  remains experimental pending signing, update delivery and broader
  packaged-artifact validation.
- On validated native Steam, Connect preflight can explicitly ask the signed-in
  Steam client to subscribe, download or update required Workshop items.
  Steamworks ownership is isolated in a spawned helper which must exit before
  launch continues. WolfLauncher does not download content itself or remove
  subscriptions.
- Discovered servers remain read-only and offline-first in SQLite. Curated
  servers remain user-owned YAML. A discovered row can be inspected or launched
  without promotion.
- WolfAPI v1 is the fresh-install discovery default. Stable IDs, endpoint
  aliases, bounded pagination, indexed remote search/resolve, freshness,
  validation, quality, country and required-mod metadata are supported. Saved
  legacy selections and the explicit legacy fallback remain intact.
- Listing-data warnings are hidden by default. The Launcher also flags an
  obvious cluster of three or more exact normalized provider names across
  different endpoints as advisory duplicate-directory data until WolfAPI
  classifies it at directory scope.
- Fixed startup probing of discovered rows is retired. Provider data is browsing
  evidence; selected-server inspection and launch-time checks remain local
  truth.
- Native mod inspection now queries the selected game server's DayZ
  `A2S_RULES` manifest directly on the existing background worker. The strict
  decoder rejects partial/overflow/ambiguous responses, while Steam remains
  the source for Workshop metadata and local install state. DZSA is retained
  only inside the visible legacy Linux shell-launcher fallback.
- The Editor / Local Tools tab now provides an offline Editor-only picker of
  locally installed extra mods alongside its required framework mods, plus
  saved Local Development profiles for native joining of an already-running
  LAN/test server. It is advanced local
  development tooling, not public hosting. The primary Editor action explicitly
  asks Steam to subscribe/update its three standard requirements, verifies them
  locally and then minimizes after a detected DayZ handoff; dedicated-server
  installation, start/stop control, project-editor opening and log views remain
  staged follow-on work.
- Local Development now has an initial host workspace for server roots visible
  to the Launcher: managed start/stop, Steam-owned Windows setup with completed-install detection, and anonymous SteamCMD custom-path setup,
  explicit local client/server mod folders, file-patching source tests and
  confirmed public-key-only sync. Remote machines without an accessible shared
  root remain connect-only; remote process control is not inferred.
- The Server Browser, Mods, Settings and Favourite Servers layouts have passed
  real-desktop review. Preserve their information-first hierarchy unless new
  evidence requires a change.
- Server Browser live truth is selection-driven: WolfAPI supplies fluid cached
  browsing, one background GameDig worker checks the selected row, and launch
  preflight is authoritative. Bulk visible-row enrichment and redundant cache
  refresh controls are retired. Explicit refreshes and completed searches may
  check all current matching rows six at a time on one latest-search-wins background worker. Settings
  hides non-actionable and platform-irrelevant controls from the normal Windows
  experience and keeps its health cards full-width and vertically ordered.
- Server Browser text search does no cache query or table rebuild before three
  normalized characters and debounces the eventual local refresh. Conflicting
  live endpoint corrections never replace another stable WolfAPI identity.
- Result freshness is ordered from the table viewport, visible top row first,
  and uses only each provider row's primary query port for speed. Thorough
  fallback-port probing remains selection- and launch-driven. Superseded result
  batches terminate their GameDig child processes rather than delaying later searches.
  Batch completion updates status explicitly and never rebuilds the full table.
- Entering the Server Browser schedules four six-server freshness batches in
  visual table order; explicit searches supersede them and may continue across all matches.
- Scrolling is debounced and checks up to 24 stale servers from the settled
  viewport; hidden rows are never used to fill those scroll-triggered batches.
- Region is not shown in normal browsing: BattleMetrics was its only trusted
  source, while the supported Steam/A2S path supplies no reliable country data.
- Linux and Windows storage paths, Steam command discovery and process
  inspection sit behind tested platform backends. On Windows, registry/library
  detection, settings persistence, the offscreen GUI, absolute Workshop mod
  arguments and the required `steam_api64.dll` exports have been validated on
  a real Steam + DayZ install with 111 Workshop directories. Unmodded and
  58-mod handoffs passed, and an explicitly confirmed missing-mod flow installed
  three items before a guarded 62-mod handoff. A portable one-folder ZIP now
  bundles Python, Node and lockfile-pinned GameDig; its packaged GUI and Windows
  Credential Manager backend are smoke-tested during the build. A per-user Inno
  Setup artifact now installs without elevation, supports in-place reinstall,
  starts the packaged application and uninstalls program files while preserving
  roaming configuration and local data. Both Windows artifacts remain unsigned
  and there is no updater yet.
- The local automated suite contains 548 tests at this snapshot. The most recent
  Windows run passes all then-applicable tests (437 passed, 59 Linux-only
  skipped), Ruff and compilation. Windows CI repeats the portable and installer
  lifecycle builds and produces checksums for both. The established Linux CI
  release matrix remains authoritative for Linux behavior.
- The public release signing identity is Wolf Systems, a trading name of
  Emberline Technologies. Certificates/keys and protected CI signing boundaries
  remain PR-17 release work; no signing certificate/key provider has been
  acquired yet, and no signing secret is stored in the repository.
- Settings now provide a persistent Stable/Experimental game-version profile.
  Experimental has an always-visible warning, isolated curated-server and
  favourites files, and isolated Steam discovery cache sources. On Windows it detects Steam App ID
  1024020 and uses the observed official BattlEye handoff: `DayZ_BE.exe 0 1 1
  -exe DayZ_x64.exe`, absolute local-mod paths and `-connect=ip:game:query`.
  Experimental has no separate Workshop application: Stable's `DayZ\!Workshop`
  junction collection is read as a local source. Its explicit, confirmed Steam
  Workshop install/update controls use that same Stable DayZ Workshop context;
  Linux Experimental native launch remains deliberately blocked
  until its handoff is validated.

## Active release boundary

The application is a strong beta, not yet a general production release. The
authoritative remaining work is the ordered backlog in
`PRODUCTION_READINESS_REVIEW.md`. Its P0 gates cover:

1. reproducible release-environment packaging validation;
2. expanded CI and a packaged-artifact desktop validation matrix.

XDG curated-data migration and recoverable persistence are implemented. The
first run copies an existing checkout-local file without modifying it, writes
new profiles under XDG config, and routes JSON/YAML/report writes through the
atomic owner-only persistence boundary.

Shutdown coordination now stops all timers, clears queued work, signals every
singleton and pooled worker, terminates the WolfAPI child process, waits against
one bounded deadline and closes SQLite only after every background owner exits.
An overlong external operation defers window closure instead of destroying a
live Qt thread.

Credential storage now prefers an available desktop keyring and falls back to
the owner-only atomic settings file. Copyable support text passes through one
redaction boundary for known secrets, credential-shaped values, home paths and
Steam userdata identifiers.

The active hardening version is `0.9.0.dev0` and package/application metadata
derive from `wolflauncher.__version__`. Wheel, source archive and versioned
`.deb` artifacts build with desktop resources, locked Python dependencies and
an npm-locked GameDig 5.3.3 runtime. GitHub Actions run `29640723322` passed
build, extraction, import, checksum and artifact-upload checks on Ubuntu
22.04/Python 3.10 and Ubuntu 24.04/Python 3.12.

PR-07 automation is active remotely: Ruff checks, scoped strict typing,
dependency audit, compilation/whitespace checks and the supported Python test
matrix pass alongside the dual-Ubuntu package jobs, with immutable action
revisions. PR-08 packaged-artifact desktop validation is now the active release
gate.

PR-08 has a dated packaged-artifact pass on Linux Mint 22.3 with native Steam:
clean install, XDG migration, settings/cache preservation, native and external
handoffs, Steam stopped/running, ready and missing Workshop flows, DNS/raw-IP
targets, offline cache, redacted reports, responsive shutdown, uninstall and
reinstall all passed. The second Mint 22 machine exposed the Flatpak Steamworks
helper lifecycle failure described above; Flatpak and Snap Steam are now
excluded as incompatible rather than retained as experimental release rows.
Ubuntu 24.04.4 has native-Steam functional-floor evidence on physical hardware,
but the remaining packaged-artifact checks must still be recorded separately.
Ubuntu 26.04 is the next planned physical validation system, followed by the
experimental Windows 10 lane. Debian 13 and the remaining required desktop
rows need evidence or an explicit release-scope waiver before PR-08 closes.

`ROADMAP.md` contains milestones only. `docs/RELEASE_CHECKLIST.md` records the
checks to run against a release candidate; neither file is a second backlog.

## Coordinated completion strategy

Run the remaining product work as three coordinated lanes rather than making
one platform block all progress:

1. **WolfAPI security and production hardening is the primary engineering
   lane.** Work through the P0/P1 findings in WolfAPI's
   `PRODUCTION_READINESS_REVIEW.md` and authoritative
   `API_COMPLETION_CHECKLIST.md` in small independently tested changes.
2. **Native Steam is the validation lane.** Preserve the validated launch path
   and use available systems to collect helper-lifecycle, secondary-library and
   exact-release-artifact evidence. A second machine running the same Mint
   version adds installation diversity but does not replace other-distribution
   evidence or explicit waivers.
3. **Unsupported Steam packages stay out of the product lane.** Do not expose,
   auto-detect or launch Flatpak or Snap Steam. Historical Flatpak code and
   investigation notes may remain dormant until a deliberate compatibility
   project has new lifecycle evidence.
4. **Windows is an experimental packaging lane.** Preserve direct absolute
   Workshop paths and native `steam.exe` handoff; do not introduce symlink or
   shell-launcher requirements. Handoff, confirmed Steamworks resolution and
   portable packaging have passed. Per-user install, reinstall and uninstall
   behavior now pass locally with user data preserved. Signing, updates and
   release-artifact desktop coverage remain separate release gates.

Update delivery is specified in `docs/UPDATE_STRATEGY.md`: Windows should use
a signed evergreen bootstrapper plus prompted, verified installer updates;
Linux should use a signed APT repository and the system update manager. Normal
CI pushes build and smoke-test artifacts without retaining them; tags and
manual release-candidate runs perform artifact uploads.

At each stable checkpoint, run the affected repository's complete checks,
commit and push each repository independently, test native Steam behavior,
synchronize shared truth documents and remove merged experiment
branches. Windows work remains additive and must not weaken the supported Linux
release gates.

## Stable product decisions

- Curated YAML is the user-owned server source; SQLite is a disposable
  discovered-server cache.
- Remote discovery is read-only and must degrade to the local cache.
- Native launch is the default; the external launcher remains a fallback until
  its removal is deliberately approved after packaged real-world evidence.
- Successful command exit means handoff to Steam, not proof that Proton or DayZ
  reached the menu.
- Launch stays guarded by Steam/DayZ/Workshop detection and fresh mod readiness.
- Local development profiles stay separate from curated YAML and discovered
  SQLite server data; they are additive settings data and never enter public
  discovery or hosting flows.
- Prefer a resolved IP for handoff when available.
- Mod resolution is explicit and Steam-managed. Never auto-subscribe,
  auto-download or remove content without the user's confirmation.
- Keep settings, favourites and curated YAML under
  `$XDG_CONFIG_HOME/wolflauncher` (default `~/.config/wolflauncher`) and
  application data under `~/.local/share/wolflauncher`.
- Preserve stable WolfAPI IDs separately from endpoint keys so corrected ports
  merge instead of duplicating rows.

## Known external issue

DayZ currently fails to run when Steam launch options contain:

```text
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

Treat this as an advisory external Steam/Proton/DayZ compatibility issue.
WolfLauncher presents it in Settings as a known external issue and must not
inspect, set or recommend the option.

## Cross-repository handoff

WolfAPI and WolfLauncher form one discovery product boundary. Before changing
shared endpoints, identity, search/resolve, freshness, validation, caching,
polling or rollout behavior, read `DISCOVERY_FRESHNESS_HANDOFF.md`,
`../WolfAPI/AGENTS.md` and `../WolfAPI/DISCOVERY_FRESHNESS_CONTRACT.md`.

The next optional cross-project enhancement is a bounded direct-`A2S_RULES`
WolfAPI preview lane using the existing required-mod persistence. It should
gradually provide advisory counts for “lightly or heavily modded” browsing,
never run synchronously from public requests, never affect reachability truth,
and never be folded into Launcher freshness batches. The native Launcher query
is implemented, materially faster than DZSA in desktop use, confirmed across
the user's Linux sample, and remains final selected-server/launch truth.

## Truth documents

- `PRODUCTION_READINESS_REVIEW.md` — authoritative ordered work backlog.
- `ROADMAP.md` — release milestones and completion boundary.
- `ARCHITECTURE.md` — module and behavior contracts.
- `DISCOVERY_FRESHNESS_HANDOFF.md` — Launcher/API shared contract and rollout.
- `docs/RELEASE_CHECKLIST.md` — release-candidate execution evidence.
- `CHANGELOG.md` — delivered behavior by release.
- `VISUAL_DESIGN.md` — approved visual hierarchy and design tokens.
