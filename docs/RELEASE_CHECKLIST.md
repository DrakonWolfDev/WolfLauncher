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

### 2026-07-20 — Windows 11 Pro 24H2, native Steam, source checkout

- A clean Python 3.12 virtual environment started the Qt desktop application
  from the installed `wolflauncher.exe` console entry point.
- Fresh settings selected the native launcher automatically. Settings Health
  detected the running signed-in Steam client, DayZ installation and Workshop
  directory through the Windows registry and Steam library manifests.
- An unmodded curated server completed the Steam handoff and reached a visible
  `DayZ_x64.exe` loading screen.
- A read-only Steamworks check for New Dawn Cherno returned all 58 required
  Workshop items as installed, including item names, IDs, sizes and previews.
- The 58-mod launch used direct absolute Workshop paths, passed the guarded
  handoff, loaded DayZ Expansion and connected to `198.244.177.109:2302`.
  The DayZ RPT recorded live world-entity loading from the server session.
- The first transition from the unmodded run to the BattlEye server requested
  a game restart. Repeating the identical guarded launch after closing DayZ
  proceeded normally; no command or path change was required.
- No Workshop subscriptions, downloads, updates or removals were requested
  during this validation. Those state-changing Windows flows still need a
  separate explicitly confirmed test row.

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
- DNS-hosted launch displayed and handed off the resolved numeric connect target
  (`95.146.83.17:3302`); a separate raw-IP server handed off its configured
  `198.244.177.109:2302` target.
- With native Steam fully exited, Connect started Steam without manual
  intervention and completed the DayZ handoff.
- The external compatibility engine remained selectable, resolved the existing
  `~/dayz-launcher.sh`, and completed a Steam/DayZ fallback handoff; native mode
  remained available for reselection afterward.
- With networking disabled, packaged startup preserved curated favourites and
  displayed the existing discovered-server cache instead of clearing offline
  data; networking could then be restored normally.
- A fully installed mod set was recognized as ready and reached the native
  Steam/DayZ handoff without an unnecessary download prompt.
- A missing/outdated Workshop flow identified required work, obtained explicit
  confirmation, completed through Steam, rechecked readiness and launched.
- Packaged Settings Health and diagnostics copy actions passed with useful
  native/Flatpak, DayZ, Workshop and troubleshooting state; home paths were
  shortened and no API key or Steam userdata identifier was exposed.
- Automatic Connect persisted a copyable launch report containing its UTC
  timestamp, Steam argument-vector handoff output and confirmed DayZ process
  detection. The report contained no literal home path or credential.
- Package removal deleted the registered launcher, desktop entry, icon and
  read-only seed while settings, favourites, curated YAML and backup, cached
  status, launch report and SQLite cache remained byte-for-byte unchanged.
  Reinstallation restored the menu application and preserved those data plus
  the previously selected external-engine setting; fallback handoff and its
  persisted launch report still passed after reinstall.
- Closing during a background check passed after the non-blocking shutdown
  fix: the modal progress dialog appeared promptly and remained fluid, closing
  the dialog did not kill the active worker, a repeated exit request restored
  the feedback, and the application closed automatically when the check
  finished.

### 2026-07-18 — Linux Mint 22, Flatpak Steam

- Independent packaged testing did not pass the Flatpak release row. Basic
  Steam detection worked, but the isolated Steamworks Workshop helper could
  leave DayZ marked as running after the helper should have released it.
- Flatpak automatic Workshop state/subscription helpers are disabled pending a
  reliable lifecycle design. Missing or outdated items fail safe to manual
  Steam Workshop pages, completion through Steam Downloads and **Recheck
  mods**. Native Steam retains its validated automatic helper.
- This is failure evidence plus a safe fallback, not Flatpak release
  certification. Re-run the complete Flatpak row after the helper lifecycle is
  deliberately redesigned or replaced.
- Mint 21 and Ubuntu 22.04/24.04 real-desktop rows still require machines or
  explicit release-scope waivers. CI package build/startup evidence alone is
  not recorded as desktop certification.
