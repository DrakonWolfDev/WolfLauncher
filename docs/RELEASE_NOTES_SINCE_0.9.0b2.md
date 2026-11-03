# WolfLauncher — changes since 0.9.0b2

Unreleased changes from tag `v0.9.0b2` through commit `006101f` (20 commits).
This document covers the completed work up to that push; it does not assign a
new release version.

## Faster Workshop library

- Local installed mods appear before Steam's network checks finish.
- Repeat visits show cached results immediately while names and update state
  refresh in the background.
- Background refreshes preserve selection, sorting and scroll position.
- Cached results stay separate for each installation and edition. Late results
  from another installation do not replace the current view.
- These improvements work on both Windows and Linux.

## Workshop mod management

- Added **Uninstall mod** to the Stable installed Workshop library, with
  confirmation before unsubscribing through Steam. Experimental shares Stable
  content and directs subscription management to Stable.
- Confirmed uninstalls remove the entry without resetting the list to the top
  or immediately rescanning files that Steam has not finished removing.
- Added a separate confirmation to permanently delete leftover local mods that
  Steam reports as unsubscribed, including mods removed from the Workshop.
  Cleanup is restricted to the selected numeric mod folder and rejects linked
  folders. Canceling or a deletion failure keeps the list entry.
- Cleanup warns that mods removed from Steam may not be downloadable again.
- Mods without a readable local name now use their Steam Workshop title when
  available, with the numeric Workshop ID retained as the final fallback.
- Fixed **Force Steam update selected mod** in the installed library requiring
  an unrelated server-specific mod check.
- Linux Workshop automation can also find `libsteam_api.so` in sibling DayZ
  Server installations when the Steam runtime does not supply it.

## Favourite servers and status checks

- Failed startup queries receive one immediate retry rather than waiting for
  the normal refresh interval. Successful queries can finish independently.
- Last known details remain visible with a **Rechecking** indicator during
  startup checks, without presenting cached information as a live result.
- Query timeouts, network failures and invalid responses now show as unknown
  rather than automatically declaring the server offline.
- Added an unknown-status count and a notice when all favourite checks fail.
- Status history, logging and diagnostics now include query outcomes, timing,
  last successful checks and consecutive failures.
- Removed Recent servers shortcuts and launch-attempt history; the saved-server
  page contains favourites only.
- Failed favourite startup checks now pause briefly before their retry instead
  of immediately repeating a request that has just failed.
- Unsuccessful live checks explain that the server may be offline, restarting
  or temporarily unreachable instead of presenting the result as conclusive.

## Launching and server browsing

- Fixed Windows DayZ launching while DayZ Tools / Publisher is open by targeting
  the selected installation's BattlEye launcher directly.
- Fixed Windows Experimental launches and launch previews dropping the configured
  player name, including names containing spaces and the blank-name fallback.
- Fixed a browser worker lifetime race when searching or scrolling around the
  completion of a live freshness check.
- Added handling for server-cache contention during browser refreshes.
- Fixed edition-verification messages remaining in the status bar after a
  successful check or an invalidated request.
- WolfLauncher now restores and focuses itself when DayZ exits after a launch
  that minimized the launcher, including launches from DayZ Editor.
- Reworked browser filters into a compact, responsive layout with active-filter
  chips, clearer advanced filters and a reset action.
- Added server perspective filtering and details for first-person-only,
  third-person-enabled and unknown camera modes.
- Map filtering now keeps official maps first, separates community maps and
  displays normalized map names consistently.

## Editor and image previews

- Fixed Editor mod-picker and selected-mod summary entries disappearing while
  scrolling through large selections by removing problematic opacity effects.
- Fixed repeated Qt **device not open** warnings by checking failed, canceled
  or closed Workshop preview and Editor image replies before reading them.

## Application updates

- Added background update notifications and **Check for Updates** on the About
  page, with stable/experimental release filtering and correct prerelease ordering.
- Automatic checks are throttled to once per 24 hours. Manual checks bypass the
  throttle and can show previously dismissed updates.
- Added a non-modal banner with expandable release notes, **View Update** and
  **Dismiss** actions. View Update opens the official WolfLauncher website.
- Updates are notification-only: packages are not downloaded or installed by
  the launcher.
- Fixed a Qt crash after update checks and improved shutdown handling so late
  update results do not change the UI after shutdown begins.
- Fixed a Linux crash during repeated update checks by delivering results through
  a queued GUI-thread slot without retaining deleted Qt runnable objects.
- Included the reusable update package in source, wheel, Linux AppImage and
  Windows packaging, with supporting documentation and regression tests.

## Runtime, security and reliability

- Added native Windows TLS verification for WolfAPI requests, avoiding failures
  caused by expired cached cross-signed certificates while retaining expiry,
  trust and hostname checks. Diagnostics now report the active TLS backend.
- Added public offline TLS regression fixtures for certificate-chain tests.
- Aligned the source and test PySide6 version with the release-pinned 6.11.1
  runtime to avoid shutdown aborts on Python 3.10 and 3.11.
- Updated the locked cryptography and HTTP cache dependencies to address known
  dependency audit advisories.
- Fixed the first Workshop download request being delayed when the monotonic
  clock value was lower than the retry interval.
- Preserved original UTF-8 bytes and CRLF line endings during saved-profile
  transaction recovery, and improved SQLite contention handling on Python 3.10.
- Corrected cross-platform CI fixtures, cleanup and installer-test selection.

## Distribution and documentation

- Recorded code signing as work planned after 1.0; unsigned packages distributed
  through GitHub and the official website do not block the 1.0 release.
- Updated the README, changelog, architecture, build guidance, update-check
  documentation and browser validation notes to reflect the changes above.
- Added a roadmap for planned queue counts and direct server links; these items
  remain unassigned to a release.

Full commit comparison: [v0.9.0b2 to 006101f](https://github.com/DrakonWolfDev/WolfLauncher/compare/v0.9.0b2...006101f).

## Additional unreleased work: Editor / LAN Play

- Renamed the Editor / Local Tools tab to **Editor / LAN Play**.
- Connecting to a LAN server now queries its required Workshop mods and includes
  matching installed items automatically, alongside explicitly selected extras.
- Missing items are listed with names, Workshop IDs and Steam links. When Steam
  reports subscription state, the list distinguishes unsubscribed items from
  subscribed items whose downloads are incomplete.
- LAN profiles now save a separate query port (`steamQueryPort`). Leave it blank
  to use game port + 3; the game connection still uses the supplied game port.
- If the server's mod query fails, the launcher explains the failure and offers
  an explicit connection using the manually selected mods.
- Automated local-tool checks pass; live LAN connection validation is pending.

## Additional unreleased work: Workshop completion

- Workshop update monitoring now waits for Steam's successful download-completion
  notification, an idle item state and the installed folder. An old installed flag
  alone no longer ends a newly requested update.
- Downloading and queued items stay incomplete even when Steam also marks them
  installed. Failure notifications report the item and Steam result code.
- A successful no-op completion can finish the request without downloaded bytes;
  silence still results in a stall/timeout rather than success.
- Post-download revision checks remain active. Metadata-only timestamp
  acknowledgement is now scoped to the same library, edition, captured revision
  and unchanged content evidence, with a successful Steam check and live idle
  state required. Live Windows/Linux Steam verification remains outstanding.

## Additional unreleased work: server list responsiveness

- Favourite stars now render as ordinary table items, removing two child widgets
  per server row.
- Live status and mod-preview updates reposition only the affected row instead
  of re-sorting the whole server list. Row contents, favourites, sorting and
  selection are preserved during updates.
- Local synthetic benchmarks at 1,000 rows show roughly four times faster full
  refreshes and ten times faster batches of server-status updates. These measure
  GUI work; server/network response times are unchanged.
- Measurements and platform limits are recorded in SERVER_TABLE_PERFORMANCE.md.

## Additional unreleased work: mixed mods and background checks

- Mixed server manifests preserve unpublished/local requirements alongside
  downloadable Workshop items. Manual requirements are clearly listed and block
  guarded launching until resolved; they never receive fabricated Steam IDs.
- Optional automatic status/provider/browser checks pause while hidden, joining,
  resolving Workshop items or monitoring a launched game, then resume stale-data
  checking. Downloads and game monitoring continue.
- Explicit normalized perspective fields from providers are preserved. The two
  supplied name-based server candidates both advertise the same perspective tag;
  a version-specific correction remains pending verified camera settings.
- Full evidence and verification limits are in RELIABILITY_FOLLOWUP_2026-11-03.md.

## Local testing build: 0.9.3.5b

The additional unreleased work above is included in the local **0.9.3.5b** test
artifacts built on 3 November 2026: Windows portable ZIP and Setup, Linux x86_64
AppImage and user-local installer archive. Windows numeric metadata is 0.9.3.5.
See [local build record](LOCAL_BUILD_0.9.3.5b.md) for artifacts, checksums and
validation limits. This is not a published release.

### 0.9.3.5b LAN feedback refresh

- Added Query server and a visible required-mod list in Local Server selection,
  with installed/missing/pending states. Querying does not launch DayZ; first joins
  and changed manifests pause for review.
- Split the LAN address into compact IP/hostname, Game port and Query port fields.
  Existing saved profiles retain their values.
- Failed GameDig queries now identify the query port and explain checking it.
  The reported DrakonCherno favourite used 2303; live replies confirmed 3303.
- The user's initial LAN test confirmed joining with the correct mods loaded.
