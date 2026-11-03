# Existing DayZ player profiles

FEATURE-02 is implemented in source for the development branch. The **Existing
profile…** button beside Player name, and the matching Settings control, open a
read-only picker for the selected installation and edition. Nothing is selected
for use until the user presses **Use profile name**.

The picker displays recognised names, primary-file modification times and source
locations. It initially highlights the current configured name when present;
otherwise it highlights the most recently modified profile without applying it.
Modification time is not described as last-played time. Identical names are
grouped, with their source locations shown. Selecting a name leaves DayZ to use
its standard profile lookup; it does not force one duplicate file over another.

Using a profile updates the existing WolfLauncher `player_name` setting. That
setting retains its existing launcher-wide scope. This feature does not introduce
separate per-edition name settings or pass a new `-profiles` argument. The selected
name goes through the existing launch-command builders and launch safeguards.

## Search locations

- Windows uses `QStandardPaths.DocumentsLocation`, rather than constructing
  `USERPROFILE/Documents`. Qt's
  [Windows implementation at the installed 6.11.1 version](https://github.com/qt/qtbase/blob/v6.11.1/src/corelib/io/qstandardpaths_win.cpp)
  maps this to `FOLDERID_Documents` / `SHGetKnownFolderPath`, supporting redirected
  Documents locations such as OneDrive. See the
  [Qt API documentation](https://doc.qt.io/qt-6/qstandardpaths.html) and
  [Microsoft known-folder guidance](https://learn.microsoft.com/en-us/windows/win32/shell/known-folders).
  An unavailable Documents location is reported without searching a guessed home
  folder instead.
- Linux derives the prefix from the selected game's actual Steam library:
  `steamapps/compatdata/<client-app-id>/pfx/drive_c/users/steamuser/`.
  Stable uses app ID `221100`; Experimental uses `1024020`. Both `Documents` and
  the older `My Documents` alias are checked and resolved duplicates are skipped.
  The launcher's unrelated or stale `compatdata_dir` snapshot is not used to
  choose another library's profiles. The host Linux Documents folder is not used
  as a fallback for a missing Proton prefix.
- Stable checks `DayZ` and `DayZ Other Profiles/<name>`; Experimental checks
  `DayZ Exp` and `DayZ Exp Other Profiles/<name>`. In an Other Profiles directory,
  the primary filename must agree with its immediate profile-directory name.
  Standard primary/custom layouts are also described in the
  [Bohemia-hosted profile discussion](https://feedback.bistudio.com/feed/?userPHIDs=PHID-USER-ug7k4bnlwwzuenejyoph).

The search recognises nonempty primary `.DayZProfile` files, accepting extension
case differences, ordinary spaces and Unicode names. Character and variable
caches (`chars.DayZProfile`, `*.vars.DayZProfile`, `*.chars.DayZProfile`), XML
presets, backups, empty files and unrelated nested folders are not offered as
player profiles. Profile contents are never opened. File/directory names and
metadata remain local and are not sent to a service or copied into reports.

Percent-encoded filenames are currently omitted with an explicit note rather
than guessing how the engine escapes a name. Custom `-profiles` locations,
custom Proton prefix overrides and alternate Wine usernames are not searched.
Manual name entry remains available. Verifying those layouts and filename
escaping against game-created examples would be separate follow-up work.

## Cancellation and changes during selection

Enumeration runs in a window-owned Qt worker with a cooperative two-second and
4,096-entry budget. Only the recognised roots and one level of Other Profiles
directories are scanned. Inaccessible folders, skipped links and exhausted work
limits are reported as incomplete coverage. An operating-system directory or
metadata call itself cannot be interrupted by the cooperative deadline.

Closing the picker requests cancellation. The main window retains the worker
until it finishes, and application shutdown includes it in the existing worker
cancellation protocol. Cancelled searches cannot publish a late selection.

Before saving, the launcher rechecks the selected installation, edition and
Steam mode, and confirms that a matching nonempty primary file remains present.
An installation change, removed file, cancellation or shutdown leaves the
configured name alone. If saving the launcher setting fails, the previous text
is restored and no success message is shown. Discovery and selection never
clone, rename, create or edit DayZ profile files.

## Validation on 3 November 2026

Read-only discovery against the existing local Proton installation found one
primary Stable profile and one primary Experimental profile, each in its correct
prefix. The corresponding character and variable cache files were excluded.
No real profile names or contents were captured in fixtures or this document;
no player name was changed and no game was launched for this verification.

Twenty new tests cover recognised files, grouping and ordering, metadata-only
discovery, redirected Windows Documents, Stable/Experimental and library
isolation, Proton alias deduplication, empty/unreadable/encoded/linked files,
limits, removal, context changes, save failure, shutdown, dialog selection and
cancellation. A real Qt worker/dialog test closes the picker while discovery is
still running and verifies orderly cancellation without applying a name.
An offscreen synthetic preview was visually checked for layout and readable
controls; this is not a native Windows or packaged UI check.

Full Linux suite: **916 tests run / 909 passed / 7 skipped**. Ruff 0.15.22 lint
and the repository formatting gate pass, along with compilation and whitespace
checks. Native Windows/OneDrive, packaged-window behaviour and actual in-game
reuse of selected keybindings/settings still require manual verification. No
version bump, package build, profile cloning or release publication was performed.
