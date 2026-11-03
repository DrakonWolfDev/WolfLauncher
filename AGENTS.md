# WolfLauncher repository instructions

## Development and release branches

- Continue development on `dev/release-preparation`. Commit and push directly to
  `origin/dev/release-preparation`; do not create pull requests for this work.
- Do not push development changes to `main`, merge into `main`, or create a PR
  targeting `main`. Keep changes on the development branch until the maintainer
  explicitly requests the final merge immediately before release.
- The name is intentional: the existing `dev/linux-package-previews` branch
  prevents Git from creating a branch named exactly `dev`. Preserve that branch.
- Before committing or pushing, check the current branch and worktree. Preserve
  existing work and use an explicit development-branch destination when pushing:
  `git push -u origin dev/release-preparation`.
- Development pushes are not releases. Do not tag, publish installers, deploy
  WolfAPI, update public download links or bump versions without a request.

## Work list and verification

- Continue from `docs/NEXT_SESSION_HANDOFF.md`, checking its implementation
  updates before reopening completed work. Record progress and remaining evidence.
- Run regression tests relevant to changed behaviour. Before pushing an integrated
  development snapshot, run the full unittest suite with
  `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -q` and the lint
  and formatting checks in `.github/workflows/tests.yml`.
- Keep source completion, live Steam/DayZ verification, packaged validation and
  publication status distinct. Preserve strict query parsing, edition/library
  isolation, bounded background work and existing launch/Workshop confirmations.
