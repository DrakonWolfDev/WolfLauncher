# WolfLauncher

WolfLauncher is a DayZ desktop launcher built with Python and PySide6. Browse
public servers, save favourites, check Workshop mods, and connect through Steam.
It also includes DayZ Editor and local server tools.

Linux and Windows are supported platforms. Linux offers a user-local installer
and Debian packages; Windows offers a Setup installer and portable ZIP builds.
The current source version is **0.9.0b2**;
see the [changelog](CHANGELOG.md) for version history and unreleased changes.

## Features

- **Server Browser:** search and filter the hosted WolfAPI directory, inspect
  servers, and keep cached results available offline. Steam Master is an
  alternative discovery provider.
- **Favourite servers:** add servers by hostname or IPv4 address, organise them
  into groups, and connect from the Servers tab.
- **Workshop checks:** query the selected server's required mods and compare
  them with installed Workshop content. Subscribe, download or update through
  Steam after explicit confirmation.
- **Steam launch:** detect Steam libraries, DayZ and Workshop folders, check
  readiness, and hand the launch to Steam. The native Python engine is the
  default; the external shell launcher remains a Linux fallback.
- **Editor / Local Tools:** launch DayZ Editor with selected mods, save local
  development profiles, and install or manage a local dedicated server with
  client/server mod paths and confirmed public-key synchronisation.
- **Troubleshooting:** Settings health checks, copyable diagnostics, mod reports
  and saved launch reports.
- **Update notifications:** quietly checks applicable GitHub releases after
  startup, shows inert release notes, and opens the official
  [WolfLauncher page](https://wolf-forge.co.uk/wolf-launcher.html) only when
  **View Update** is selected. Use **About → Check for Updates** for an immediate
  manual check. WolfLauncher never downloads or installs updates.

## Install

You need Steam and a copy of DayZ to join servers. Install and launch DayZ from
Steam once before using WolfLauncher so first-run setup can complete. On Linux,
DayZ uses Proton. WolfLauncher leaves Workshop downloads under Steam's control.

### Linux

The user-local installer works across Ubuntu 22.04/24.04/26.04, Debian 12+,
Linux Mint 21+, Pop!_OS, Fedora 40+, Nobara, Arch Linux, Manjaro/EndeavourOS,
openSUSE Tumbleweed/Leap, NixOS, Alpine 3.20+ in a non-musl environment, and
SteamOS 3/HoloISO.

Download the versioned Linux installer archive from Releases, verify its
checksum, extract it and run:

```bash
./install.sh
```

The installer copies the bundled AppImage, adds a desktop entry and creates
`~/.local/bin/wolflauncher` and `wolflauncher-uninstall`. It installs into your
user account without requiring `sudo` or downloading application dependencies.

Launch WolfLauncher from the desktop menu or run:

```bash
~/.local/bin/wolflauncher
```

See [Installing on Linux](docs/INSTALL_LINUX.md) for distro prerequisites,
source-archive installation, path overrides and uninstall instructions.
Debian/Ubuntu-family users can also build a `.deb` using the
[build guide](BUILD_GUIDE.md#linux--debian-package-build).

Native Steam is supported. Flatpak and Snap Steam are not supported in this
version. Check the detected installation in
**Settings → Check health** before connecting.

### Windows

Check the [GitHub releases](https://github.com/DrakonWolfDev/WolfLauncher/releases)
for the version you want. Where provided, use the Windows Setup executable or
extract the portable ZIP and run `WolfLauncher.exe`.

Windows packages target 64-bit Windows. The Setup installer requires Windows
10 version 1809 or later, installs per user without administrator privileges,
and offers an optional desktop shortcut. Both package formats bundle Python,
Qt and Node.js/GameDig, so you do not need to install those separately.

The build scripts produce unsigned packages. Code signing is planned as a
post-1.0 distribution improvement and does not block the 1.0 release through
GitHub and the official WolfLauncher website. To build your own Setup or portable
package, follow the [Windows build instructions](BUILD_GUIDE.md#windows--portable-zip-build).

## Join a server

For DayZ Stable:

1. Open **Settings** and use **Check health** to confirm the selected Steam,
   DayZ and Workshop installation. Set your player name on the **Servers** tab
   if needed; Windows also provides this field in **Settings**.
2. Find a server in **Server Browser**, or use **Add a favourite server** on
   the **Servers** tab. New installations start with an empty favourites list.
3. Select **Connect**. WolfLauncher checks the server and required mods. If
   Workshop changes are needed, review and confirm the Steam operation.
4. After the mod check succeeds, WolfLauncher hands the launch to Steam.

A successful handoff means Steam received the launch request. It does not prove
that DayZ finished starting or joined the server. If connecting fails, check
**Mods**, **Settings → Check health**, and the saved launch report.

At startup, favourites keep their last known details visible while checking the
servers in parallel. These details are marked as rechecking rather than live.
Failed startup queries receive one immediate retry before showing a failure;
they do not have to wait for the normal refresh interval. This works on both
Windows and Linux.

The server browser starts on **Stable**. Use its visible **Stable / Experimental**
selector to browse either edition. Favourites remain together with edition tags.
Before joining, WolfLauncher verifies the server's live game ID
and selects that installation automatically; unresolved identity blocks the launch.
Your Stable external-launcher preference is retained; Experimental uses native launching.

Install **DayZ Experimental** in the Steam Library, launch it through Steam once to
complete initial/BattlEye setup, close it, then use **Settings → Rescan installations**.
Experimental can be browsed without an installation; saved EXP entries remain visible
with installation guidance. Detection alone does not verify first-run setup.

- **Linux:** WolfLauncher launches Experimental through Steam using app ID
  `1024020` and creates mod symlinks in the Experimental install pointing to the
  configured Stable Workshop content. Steam handles Proton using Experimental's
  compatibility settings. Launch preparation is covered by automated tests;
  game startup and server joining have also been confirmed in a Linux user test.
- **Windows:** Experimental launches through `DayZ_BE.exe` using existing local
  mods, including Stable's `DayZ/!Workshop` folders.

## Manage installed mods

Open **Mods** and select the installed Workshop library to review local mods.
Names come from local mod metadata, with Steam Workshop titles used when the
local name is missing. If neither source supplies a name, the Workshop ID remains
visible.

The local list appears before Steam's network checks finish. Repeat visits show
cached results immediately while refreshing names and update state in the
background. Refreshes preserve the current selection, sort and scroll position.
This behavior is shared by Windows and Linux.

For Stable, select a mod and use **Uninstall mod** with Steam running. After
Steam confirms the unsubscribe, its row disappears without resetting the list's
scroll position. Steam may take a moment to remove the local files.

If Steam reports the mod is already unsubscribed, WolfLauncher offers a separate
confirmation to permanently delete its leftover local folder. This also handles
mods whose Workshop pages have been removed. Deletion cannot be undone, and a
removed Workshop mod may not be downloadable again. Canceling or a deletion
failure keeps the entry. Experimental shares Stable Workshop content; manage
uninstalls from Stable.

## Editor and local servers

The **Editor / Local Tools** tab provides DayZ Editor sessions and saved local
development profiles. Select installed Workshop mods for your session and use
the verification controls to check requirements before launching. DayZ Editor,
CF and Dabs Framework form the Editor's automatic baseline. Editor and local
development profiles use **Stable**, independently of the server browser selection.
Experimental support for this section is out of scope for now.

Local server controls can use an existing server installation, a Steam-owned
Windows server installation, or a SteamCMD installation at a chosen path.
Configure the server root, configuration file and mod paths, then use the local
start/stop controls. Public-key copying requires confirmation. These tools are
for local development; network exposure and public hosting configuration remain
your responsibility.

## Run from a source clone

You do not need a sibling WolfAPI repository to build or run WolfLauncher.
Public discovery uses the configured hosted service. The clone includes source,
assets, tests and packaging tools, with generic examples and no personal server
list.

For source development, install Python, Node.js and npm. Qt also needs your
platform's system libraries; see the [Linux guide](docs/INSTALL_LINUX.md).
Run these commands from the repository root after cloning.

### Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci --prefix packaging/npm --ignore-scripts
.venv/bin/python main.py
```

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd ci --prefix .\packaging\npm --ignore-scripts
.\.venv\Scripts\python.exe main.py
```

Both use the lockfile-pinned GameDig dependency under `packaging/npm`.
A global GameDig installation is unnecessary.

### Tests and package builds

Run tests in the same Python environment:

```bash
# Linux
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover
```

```powershell
# Windows
.\.venv\Scripts\python.exe -m unittest discover
```

For wheels, source archives, `.deb` files and Windows packages, see
[BUILD_GUIDE.md](BUILD_GUIDE.md). That guide identifies the requirements files
and build scripts used by each packaging path.

### Implementation plans

- [Combined Stable/Experimental browser and automatic launching](docs/COMBINED_BROWSER_IMPLEMENTATION_PLAN.md)
  — proposed phases, migration safeguards, detailed tests, and release acceptance criteria.

## Your settings and server lists

| Data | Linux default | Windows default |
| --- | --- | --- |
| Settings and curated servers | `~/.config/wolflauncher/` | `%APPDATA%\wolflauncher\` |
| Cached servers and launch reports | `~/.local/share/wolflauncher/` | `%LOCALAPPDATA%\wolflauncher\` |

Linux respects `XDG_CONFIG_HOME` and `XDG_DATA_HOME`. The user-local installer's
application files live under the data directory's `runtime/` subdirectory.
Settings and caches are kept separate from those installed files.

Use the UI to manage favourite servers, or use
[example.servers.yaml](example.servers.yaml) as a reference for your own curated
YAML. Hosts can be DNS names or IPv4 addresses; IPv6 endpoints are not supported.
Discovered-server imports use a
separate cache; an [example import file](examples/discovered_servers.sample.yaml)
is included.

## Troubleshooting

- **The GUI does not open:** run WolfLauncher from a terminal and check the
  reported error. On Linux, confirm the Qt system libraries are installed.
- **Steam, DayZ or Workshop is missing:** check the selected installation in
  Settings, including any secondary Steam libraries, then run **Check health**.
- **Server queries fail:** confirm the installer completed its Node.js/GameDig
  step, or rerun the local `npm ci` command when using a source clone.
- **DayZ fails after handoff:** try launching it directly through Steam and
  review the saved launch report. Settings also includes known external
  Steam/Proton compatibility notes.
- **An update check fails:** normal startup and all launcher features remain
  available. Retry from **About → Check for Updates** and confirm GitHub is
  reachable. WolfLauncher will not redirect to GitHub or download anything.

For bug reports, use the [issue tracker](https://github.com/DrakonWolfDev/WolfLauncher/issues).
Include your OS, WolfLauncher version, installation method, steps to reproduce,
and relevant diagnostics. Review copied reports before posting them publicly.

## Documentation and licence

- [Build guide](BUILD_GUIDE.md)
- [Linux installation guide](docs/INSTALL_LINUX.md)
- [Source architecture](ARCHITECTURE.md)
- [Update notifications](docs/UPDATE_NOTIFICATIONS.md)
- [Changelog](CHANGELOG.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

WolfLauncher is licensed under the
[GNU Affero General Public License, version 3](LICENSE) (`AGPL-3.0-only`).

Copyright © 2026 Andrew Hodgson trading as Wolf Forge.

The vendored `dayz-linux-cli-launcher` is MIT-licensed; its licence and
attribution remain in `external/dayz-linux-cli-launcher/`.

Saved-data migration and restoration are described in the [combined browser validation notes](docs/COMBINED_BROWSER_VALIDATION.md#saved-data-and-restoration).
