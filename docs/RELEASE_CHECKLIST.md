# Release Checklist

Use this checklist before publishing a WolfLauncher release. Unit tests cover
the offline application contracts; the Steam/Proton checks cover the external
behavior that CI cannot reproduce.

## Automated checks

- [ ] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover`
- [ ] `.venv/bin/python -m compileall -q main.py wolflauncher scripts`
- [ ] `git diff --check`
- [ ] GitHub Actions passes on every supported Python version.
- [ ] `wolflauncher.__version__`, `CHANGELOG.md`, `README.md`, `ROADMAP.md` and
      `PROJECT_STATE.md` agree on the release state.

## Desktop smoke checks

- [ ] WolfLauncher starts without a terminal traceback.
- [ ] Curated servers load and a selected server can be refreshed.
- [ ] The discovered-server cache opens without changing curated YAML rows.
- [ ] Settings health and diagnostics can be copied.
- [ ] The latest launch report can be copied after its launch dialog closes.

## Native launch checks

Run the applicable cases across native Steam and Flatpak Steam. Preserve a
diagnostics report, mod report and launch report for any failure.

- [ ] Native launcher is selected for a fresh settings profile.
- [ ] An existing saved external-launcher selection is preserved.
- [ ] Unmodded server reaches Steam/DayZ handoff.
- [ ] Fully installed mod set reaches Steam/DayZ handoff.
- [ ] Missing mod set requests confirmed Steam subscriptions/downloads, waits
      for helper exit, rechecks readiness and then reaches handoff.
- [ ] Installed-but-outdated item is updated and rechecked before handoff.
- [ ] Helper stall or incomplete Steam state exits with an actionable result and
      continues to block launch.
- [ ] Hiding and reopening the Workshop monitor preserves one helper session.
- [ ] Closing WolfLauncher during Workshop work leaves no orphan helper.
- [ ] Steam already running reaches handoff.
- [ ] Steam initially stopped can be started by the handoff.
- [ ] Steam stopping during Workshop work fails safely.
- [ ] Secondary Steam library is detected and used.
- [ ] DNS-hosted server uses the resolved connect target.
- [ ] Raw-IP server uses the expected connect target.
- [ ] Offline startup preserves and displays the existing discovered cache.
- [ ] External launcher remains selectable and can perform a fallback handoff.

Workshop changes always require explicit confirmation and are performed by the
signed-in Steam client. WolfLauncher must not download bytes itself or remove
subscriptions.

## Packaged artifact checks

Record the OS, package version, Steam client, Proton and `gamedig` versions for
each run. Required release rows are Mint 21/22 and Ubuntu 22.04/24.04, covering
native and Flatpak Steam where supported; record an explicit waiver when a row
cannot be run.

- [ ] Clean install works without a repository checkout or global unversioned
      npm mutation.
- [ ] Application starts with its code/resources mounted read-only.
- [ ] First run seeds curated YAML under XDG config.
- [ ] Existing checkout-local curated YAML migrates without data loss or
      overwriting either source.
- [ ] Upgrade from the prior release preserves settings, favourites, curated
      YAML and SQLite schema data.
- [ ] Uninstall removes packaged files without removing user data.
- [ ] Release artifact checksum and provenance are published.

## Release

- [ ] Review `CHANGELOG.md` and move the release entries out of `Unreleased`.
- [ ] Commit the release state.
- [ ] Create an annotated `vX.Y.Z` tag at the tested commit.
- [ ] Push the branch and tag.
- [ ] Confirm GitHub Actions passes for the tagged commit.

## Validation evidence

### 2026-07-18 — Linux Mint 22.3, native Steam, packaged `0.9.0~dev0`

- CI artifact checksum and Debian metadata verified before installation.
- Clean Cinnamon-menu launch passed from the installed package; curated
  servers and saved settings loaded correctly with no visible layout or startup
  problem.
- Existing checkout-local curated YAML migrated byte-for-byte into XDG config;
  the source remained unchanged and config/data permissions tightened to
  owner-only.
- Reinstallation of the corrected artifact preserved settings and curated
  servers.
- Curated status refresh and unmodded native-Steam/DayZ handoff passed.
- A fully installed mod set was recognized as ready and reached the native
  Steam/DayZ handoff without an unnecessary download prompt.
- A missing/outdated Workshop flow identified required work, obtained explicit
  confirmation, completed through Steam, rechecked readiness and launched.
- Closing during a background check passed after the non-blocking shutdown
  fix: the modal progress dialog appeared promptly and remained fluid, closing
  the dialog did not kill the active worker, a repeated exit request restored
  the feedback, and the application closed automatically when the check
  finished.
