# WolfLauncher Project State

Updated: 2026-07-20

WolfLauncher is a Linux-primary DayZ launcher GUI built with Python and PySide6,
with experimental portable and installed Windows builds.
The v0.8 native-launch baseline is validated and tagged; v0.9 production
hardening is the active cycle. The native Python engine is the default and the
vendored MIT shell launcher remains a visible compatibility fallback.

## Current truth

- Native Steam handoff has passed real-desktop testing with Steam running and
  stopped, unmodded servers, complete mod sets and missing/update flows.
- Flatpak Steam packaged testing is currently a failed PR-08 row. Basic
  detection works, but the isolated Steamworks Workshop helper could leave DayZ
  marked as running after helper shutdown. Flatpak automatic Workshop handling
  is therefore disabled and fails safe to manual Steam Workshop pages plus
  **Recheck mods** until its lifecycle can be made reliable.
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
- Fixed startup probing of discovered rows is retired. Provider data is browsing
  evidence; selected-server inspection and launch-time checks remain local
  truth.
- The Server Browser, Mods, Settings and Favourite Servers layouts have passed
  real-desktop review. Preserve their information-first hierarchy unless new
  evidence requires a change.
- Server Browser live truth is selection-driven: WolfAPI supplies fluid cached
  browsing, one background GameDig worker checks the selected row, and launch
  preflight is authoritative. Bulk visible-row enrichment and redundant cache
  refresh controls are retired. Explicit refreshes and completed searches may
  check up to ten matching rows on one coalescing background worker. Settings
  hides non-actionable and platform-irrelevant controls from the normal Windows
  experience and keeps its health cards full-width and vertically ordered.
- Server Browser text search does no cache query or table rebuild before three
  normalized characters and debounces the eventual local refresh. Conflicting
  live endpoint corrections never replace another stable WolfAPI identity.
- Result freshness is ordered from the table viewport, visible top row first,
  and uses only each provider row's primary query port for speed. Thorough
  fallback-port probing remains selection- and launch-driven.
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
- The automated suite contains 482 tests at this snapshot. The Windows run
  passes all applicable tests (423 passed, 59 Linux-only skipped), Ruff and
  compilation. Windows CI repeats the portable and installer lifecycle builds
  and produces checksums for both. The established Linux CI/release matrix
  remains authoritative for Linux behavior.

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
helper lifecycle failure described above; that row remains failed with a safe
manual-Workshop fallback rather than release validation. Mint 21 and Ubuntu
desktop rows remain unavailable and need evidence or an explicit release-scope
waiver before PR-08 closes.

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
3. **Flatpak Steam is an experimental lane behind its safe fallback.** Keep
   automatic Workshop helpers disabled until their lifecycle is proven; retain
   manual Steam Workshop actions plus **Recheck mods**, and merge only changes
   that cannot regress native Steam.
4. **Windows is an experimental packaging lane.** Preserve direct absolute
   Workshop paths and native `steam.exe` handoff; do not introduce symlink or
   shell-launcher requirements. Handoff, confirmed Steamworks resolution and
   portable packaging have passed. Per-user install, reinstall and uninstall
   behavior now pass locally with user data preserved. Signing, updates and
   release-artifact desktop coverage remain separate release gates.

At each stable checkpoint, run the affected repository's complete checks,
commit and push each repository independently, test native/Flatpak behavior
when relevant, synchronize shared truth documents and remove merged experiment
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

Treat this as an external Steam/Proton/DayZ compatibility issue until it is
reproduced. WolfLauncher must not set or recommend this option by default.

## Cross-repository handoff

WolfAPI and WolfLauncher form one discovery product boundary. Before changing
shared endpoints, identity, search/resolve, freshness, validation, caching,
polling or rollout behavior, read `DISCOVERY_FRESHNESS_HANDOFF.md`,
`../WolfAPI/AGENTS.md` and `../WolfAPI/DISCOVERY_FRESHNESS_CONTRACT.md`.

The API's bounded required-mod metadata job has passed its initial canary and
scheduled cycle. Continue observing production cycles and increase its global
budget progressively; direct Launcher inspection remains final truth.

## Truth documents

- `PRODUCTION_READINESS_REVIEW.md` — authoritative ordered work backlog.
- `ROADMAP.md` — release milestones and completion boundary.
- `ARCHITECTURE.md` — module and behavior contracts.
- `DISCOVERY_FRESHNESS_HANDOFF.md` — Launcher/API shared contract and rollout.
- `docs/RELEASE_CHECKLIST.md` — release-candidate execution evidence.
- `CHANGELOG.md` — delivered behavior by release.
- `VISUAL_DESIGN.md` — approved visual hierarchy and design tokens.
