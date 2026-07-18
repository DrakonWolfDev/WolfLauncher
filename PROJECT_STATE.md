# WolfLauncher Project State

Updated: 2026-07-18

WolfLauncher is a Linux-first DayZ launcher GUI built with Python and PySide6.
The v0.8 native-launch baseline is validated and tagged; v0.9 production
hardening is the active cycle. The native Python engine is the default and the
vendored MIT shell launcher remains a visible compatibility fallback.

## Current truth

- Native and Flatpak Steam handoff have passed real-desktop testing with Steam
  running and stopped, unmodded servers, complete mod sets and missing/update
  flows.
- Connect preflight can explicitly ask the signed-in Steam client to subscribe,
  download or update required Workshop items. Steamworks ownership is isolated
  in a spawned helper which must exit before launch continues. Manual Workshop
  pages remain available; WolfLauncher does not download content itself or
  remove subscriptions.
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
- The automated suite contains 436 tests at this snapshot. The production
  review baseline passed the full suite, compilation and `git diff --check`.

## Active release boundary

The application is a strong beta, not yet a general production release. The
authoritative remaining work is the ordered backlog in
`PRODUCTION_READINESS_REVIEW.md`. Its P0 gates cover:

1. release/version truth;
2. complete worker and child-process shutdown;
3. credential permissions, optional secret storage and report redaction;
4. reproducible packaging and locked release dependencies;
5. expanded CI and a packaged-artifact desktop validation matrix.

XDG curated-data migration and recoverable persistence are implemented. The
first run copies an existing checkout-local file without modifying it, writes
new profiles under XDG config, and routes JSON/YAML/report writes through the
atomic owner-only persistence boundary.

`ROADMAP.md` contains milestones only. `docs/RELEASE_CHECKLIST.md` records the
checks to run against a release candidate; neither file is a second backlog.

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
