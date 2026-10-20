# WolfLauncher update notifications

## Purpose and scope

WolfLauncher includes a notification-only update checker. It tells users when an
applicable GitHub release is newer than the installed version and directs them to
the official WolfLauncher website for downloads and installation guidance.

WolfLauncher does not download, stage, verify, execute or install application
packages. It does not select Windows or Linux artifacts.

## Configured application values

The WolfLauncher integration in `wolflauncher/update_feature.py` supplies:

- repository: `DrakonWolfDev/WolfLauncher`;
- channel: `experimental`;
- installed version: `wolflauncher.__version__`; and
- official destination: `https://wolf-forge.co.uk/wolf-launcher.html`.

The destination is validated as HTTPS at configuration time. GitHub release
notes, release pages and asset URLs cannot replace it. If the browser or official
website is unavailable, WolfLauncher reports the problem and does not fall back
to GitHub.

## User behavior

- A quiet automatic check is scheduled after the main window becomes usable.
- No more than one successful automatic check runs in 24 hours.
- Draft releases and malformed versions are ignored.
- The experimental channel accepts applicable final and prerelease versions.
- No notification is shown when the installed version is current.
- An available release shows a non-modal banner with version, inert release
  notes, **View Update** and **Dismiss**.
- Dismissing a version suppresses later automatic notices for that version.
- A genuinely newer version is shown normally.
- **About → Check for Updates** bypasses automatic throttling, reports success or
  failure, and shows an available release even if it was previously dismissed.

The two persisted settings are `update_last_successful_check` and
`update_dismissed_version`. They use the existing WolfLauncher settings file and
do not introduce another user-settings system.

## Release publication path

- A manual Installer workflow run produces internal Windows and Linux artifacts without
  publishing a release.
- Pushing a tag that exactly matches `v` plus `wolflauncher.__version__` builds and tests the
  Windows installer, portable Windows archive and Linux installer from that tag.
- The workflow publishes one GitHub prerelease only after both required platform installers and
  their checksums are present.
- After publication it sends a `desktop_release_published` event to the Wolf Forge website. The
  website validates the version, expected artifact names and live GitHub URLs before committing
  its new download manifest.
- `WOLF_FORGE_SITE_TOKEN` must be configured as a fine-grained repository secret with Contents
  read/write access limited to `DrakonWolfDev/wolf-forge-static`. A missing token stops tagged
  publication during preflight; failed website validation leaves the previous links intact.

## Architecture and safety boundary

The reusable `wolf_update` core owns discovery, version policy, throttling,
dismissal state, safe release-note conversion and destination validation. It has
no dependency on WolfLauncher or Qt.

The optional PySide6 adapter performs checks through a single-task `QThreadPool`.
This keeps network timeouts off the GUI thread and participates in WolfLauncher's
normal shutdown lifecycle. A checker-owned signal source delivers results to an
explicitly queued QObject slot on the GUI thread. Delivery carries a generation
number rather than retaining a QRunnable after QThreadPool has deleted it;
cancellation invalidates queued results, and deleting the checker disconnects
pending delivery. Release notes are placed into a plain-text, read-only
widget, so their links and markup are not interactive.

The package exposes no download or installer API. Both Linux and Windows
PyInstaller specifications explicitly collect `wolf_update`, and the root
setuptools configuration includes it in wheels and source distributions.

## Maintainer test checklist

Run the focused automated coverage:

```bash
python3 -m unittest -v \
  tests.test_wolf_update \
  tests.test_state \
  tests.test_wolf_update_qt \
  tests.test_update_feature \
  tests.test_about_feature \
  tests.test_lifecycle \
  tests.test_packaging
```

Before publishing a release, test a source or packaged build on a real desktop:

1. Start WolfLauncher and leave it open for at least 15 seconds.
2. Confirm normal startup remains responsive and no up-to-date popup appears.
3. Select **About → Check for Updates** several times and confirm polite,
   consistent feedback without a crash.
4. Against a newer test release, confirm the version and safely rendered notes.
5. Confirm **Dismiss** hides the banner and suppresses that automatic notice.
6. Confirm a manual check still shows the dismissed release.
7. Confirm **View Update** opens exactly
   `https://wolf-forge.co.uk/wolf-launcher.html` in the default browser.
8. Repeat the startup and manual-check test in the Linux and Windows packaged
   builds.

The Qt worker regression test completes 25 rapid checks to guard against the
cross-thread destruction crash found during initial manual testing.
