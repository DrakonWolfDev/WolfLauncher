# Remaining Jobs and Decisions

Updated: 2026-07-24

This is a practical execution list. The authoritative ordered backlog remains
[`PRODUCTION_READINESS_REVIEW.md`](../PRODUCTION_READINESS_REVIEW.md).

## Release before v1.0

### PR-08 — Packaged-artifact desktop validation

- Run or explicitly waive Mint 21, Mint 22, Ubuntu 22.04 and Ubuntu 24.04
  desktop rows.
- Validate native Steam and Flatpak Steam where applicable.
- Record clean install, upgrade, read-only resources, migration, offline cache,
  secondary-library, uninstall, checksum and provenance evidence.
- Human systems and dated validation evidence are required.

### PR-09 — Production release

- Choose the final version.
- Move release entries out of `Unreleased` in the changelog.
- Re-run automated and package gates on the exact release artifact.
- Create an annotated tag, publish checksums and installation guidance, and
  confirm tagged CI.
- Release-owner decisions and publishing authority are required.

## Engineering hardening

### PR-14 — External data and image bounds

- Complete: preview URLs accept HTTPS only, with recognised Steam CDN HTTP URLs
  upgraded to HTTPS. Responses require an image content type, are bounded to
  2 MiB, and decoded images are capped at 2048 pixels per side.
- Complete: invalid provider rows are dropped individually while valid rows
  remain available; provider endpoint, identity and metadata fields are bounded.
- Complete: IPv6 is explicitly unsupported and rejected for curated input and
  provider ingestion rather than appearing as a partial launch/search path.
- Real Mint validation confirmed the safe preview path works with live Workshop
  image traffic after retaining Qt's tolerant JPEG decoder for imperfect CDN
  image data.

### PR-15 — Accessibility evidence

- Complete: screen-reader review, including named curated-server cards and
  server-specific Connect/favourite actions.
- Complete: keyboard-only checks across the main tabs, curated selection,
  Server Browser, Mods, Settings and dialogs.
- Complete: high-contrast, large-text and reduced-motion review.
- Complete: review 75%, 100%, 125%, 150%, 175% and 200% scaling.
- Complete: status meaning remains clear through text, icons and action state,
  not colour alone.
- Linux Mint validation passed at 75%, 100%, 125%, 150%, 175% and 200% after
  main workspaces gained an outer scroll boundary; previously unreachable
  controls at 175% and 200% are now reachable.

### PR-16 — Remaining resilience and performance work

- Complete: deterministic, synthetic hostile/truncated YAML and JSON corpus
  covers curated YAML, discovered-server imports, raw HTTP JSON and each
  discovery-provider parser. Invalid input fails with controlled errors or is
  dropped per-row while a valid neighbour remains available.
- Add property/fuzz coverage for provider parsing, endpoint normalization,
  cache migration and settings.
- Measure startup, third-character remote search, large-table refresh and memory
  with a production-scale cache.
- Set and document pass/fail performance budgets.
- Fuzz coverage can be implemented locally; representative performance evidence
  remains open until it can run on a DayZ minimum-spec system, which will define
  the supported performance baseline.

### PR-17 — Updates and retention

- Establish signing identities and protected CI signing boundaries.
- Publish signed channel manifests and assets.
- Implement an in-app availability notice.
- Implement a signed Windows bootstrapper with prompted verified installer
  updates.
- Publish a signed Linux APT repository and setup package.
- Define retention for cache, logs, thumbnails and reports.
- Exercise update, interrupted-update, downgrade/recovery and user-data
  preservation on the desktop matrix.
- Signing/repository decisions, credentials and desktop validation are required.

## Explicit decisions

- Decide whether PR-10 is formally complete beyond its delivered lifecycle and
  feature-extraction slices, or remains an ongoing incremental maintenance item.
- Decide whether crash reporting remains local-only or gains opt-in upload. If
  uploads are approved, choose a provider, retention period, consent wording and
  data-processing policy.
- Approve release-scope waivers for any unavailable PR-08 desktop rows.
- Choose release version/tag timing and the supported Linux distribution matrix.
