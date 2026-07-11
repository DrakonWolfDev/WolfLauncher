# Release Checklist

Use this checklist before publishing a WolfLauncher release. Unit tests cover
the offline application contracts; the Steam/Proton checks cover the external
behavior that CI cannot reproduce.

## Automated checks

- [ ] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover`
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
- [ ] Partially missing mod set is blocked and lists the missing Workshop pages.
- [ ] Steam already running reaches handoff.
- [ ] Steam initially stopped can be started by the handoff.
- [ ] DNS-hosted server uses the resolved connect target.
- [ ] External launcher remains selectable and can perform a fallback handoff.

Automatic Workshop subscription and downloading are not release requirements.
Mod management remains read-only and requires the user to approve subscriptions
through Steam.

## Release

- [ ] Review `CHANGELOG.md` and move the release entries out of `Unreleased`.
- [ ] Commit the release state.
- [ ] Create an annotated `vX.Y.Z` tag at the tested commit.
- [ ] Push the branch and tag.
- [ ] Confirm GitHub Actions passes for the tagged commit.
