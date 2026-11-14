# WolfLauncher next-session handoff

Updated **14 November 2026**, after publication of **0.9.4b** and workspace cleanup.
This is the starting point for future **0.9.5** work; its scope has not been chosen.

## Current baseline

- Public beta: [v0.9.4b](https://github.com/DrakonWolfDev/WolfLauncher/releases/tag/v0.9.4b).
- Released source: `ff59edb266bcc4ee085bbb86bf443d045340e4d3`, on remote main.
- Develop on **dev/release-preparation** and push directly to that branch.
  Main/tag changes require a new explicit release request. Preserve
  `dev/linux-package-previews` and the released tags.
- Application version remains **0.9.4b**. Do not bump it, tag, publish packages,
  change live download links or deploy WolfAPI as part of routine development.
- Release validation: 1,039 tests, OK / 7 skipped locally; tagged CI, native
  package checks, matching clean-source provenance and complete publication passed.
  [Release evidence](RELEASE_0.9.4b.md) records the source and workflow runs.
- The maintainer confirmed the fresh Linux test installer passes again and
  previously confirmed Windows launcher/link operation. Keep hands-on reports,
  source checks and final-tag package evidence distinct.

## Start the next session here

1. Check the current branch, worktree and this handoff before editing. Preserve
   any existing work. Confirm the maintainer's intended 0.9.5 scope when it arrives.
2. Consult the [archived implementation history](NEXT_SESSION_HANDOFF_0.9.4b_ARCHIVE.md)
   before reopening old issues. It preserves the detailed completion updates and
   their limitations; the early investigation lists are historical.
3. Use [the roadmap](ROADMAP.md) for candidates. Optional additions are not an
   instruction to implement them all, and this cleanup starts no feature work.
4. Keep strict query parsing, edition/library isolation, bounded background work,
   and existing Connect/Workshop confirmations.
5. Run relevant regression tests. Before pushing an integrated development
   snapshot, run the full offscreen unittest suite and the workflow's quality
   checks, as required by [AGENTS.md](../AGENTS.md).

## Remaining maintenance and evidence

- **Product-site feed reachability:** publication updated the shared Wolf Forge
  manifest successfully, but wolflauncher.co.uk served its bundled fallback.
  Website commit `51f6285` refreshed that snapshot and automatically deployed;
  both live feeds were verified at 0.9.4b. Check runtime access to the shared feed
  before relying on automatic refresh at the next release. This is a website
  maintenance item; no WolfAPI deployment is implied.
- **Perspective tags (REL-02):** no raw-tag inversion was added without known
  camera settings. Preserve normalized provider fields; gather verified settings
  and raw responses before changing interpretation.
- **Remembered API/PHP alert (API-01):** its exact identity remains unconfirmed.
  Reconcile the advisory/patch with existing maintenance records rather than
  duplicating a completed fix. Read WolfAPI instructions before any API work.
- Broader changed-content/bulk Workshop, accessibility, older-distro and long-run
  verification remains bounded by the evidence in the archived handoff. Release
  publication does not silently close those investigations.

The LAN/query-port, Workshop completion, mixed unpublished requirements, profile
picker, server sharing, queue counts, responsiveness and npm parser fixes shipped
in 0.9.4b. Check their implementation updates before proposing further changes.

## Local workspace after cleanup

- Superseded private installers, extracted packages, build intermediates and
  Python/tool caches have been removed. Public release artifacts remain on GitHub.
- Small private-build logs, helper scripts, screenshot, checksums and provenance
  are retained under ignored `build/evidence/0.9.4b-preparation/`, with an inventory.
  These records describe the old private builds, not the published artifacts.
- Existing `.venv/`, `venv/`, npm dependencies, Graphify knowledge/memory and local
  settings are preserved. They are local dependencies/data, not cleanup targets.
- `build/toolchains/` includes a roughly 13 GB WSL `ext4.vhdx`; it is a virtual
  machine disk, not a disposable package output. It and reusable build tools remain.
- [Full 0.9.4b handoff archive](NEXT_SESSION_HANDOFF_0.9.4b_ARCHIVE.md) stays in this
  directory so its relative evidence links continue to work.

## Cleanup verification — 14 November 2026

Removed 44 generated output/cache paths (about **2.18 GiB** of logical files),
retaining 26 small evidence files (about 2.6 MiB including the inventory).
The archived handoff was checked byte-for-byte against its previous committed
content. Post-cleanup full regression: **1,039 tests, OK / 7 skipped**; workflow
Ruff formatting/lint, hardened-core mypy and whitespace checks pass. No application
source or version changed, no release tag was pushed, and main was left alone.
