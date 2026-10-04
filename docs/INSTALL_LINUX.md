# Installing WolfLauncher on Linux

The newer user-local installer works across Ubuntu 22.04/24.04/26.04,
Debian 12+, Linux Mint 21+, Pop!_OS, Fedora 40+, Nobara, Arch Linux,
Manjaro/EndeavourOS, openSUSE Tumbleweed/Leap, NixOS, Alpine 3.20+
(non-musl environment) and SteamOS 3/HoloISO. This distro coverage is confirmed
by the maintainer. See [Installing on Linux](INSTALL_LINUX.md).

This version requires native Steam. Flatpak and Snap Steam are not supported.

## Distro matrix

The installer is distro-neutral; the table below lists what's been verified
and the system packages you'll likely want for Steam and the Qt runtime.

| Distro                          | Installer verified | Steam                  | Qt libs                                           |
| ------------------------------- | ------------------- | ---------------------- | ------------------------------------------------- |
| Ubuntu 22.04 / 24.04 / 26.04            | yes                 | `steam` (apt) | `libegl1 libxcb-cursor0 libxkbcommon0`           |
| Debian 12+                      | yes                 | `steam` (non-free) | same as Ubuntu                            |
| Linux Mint 21+                  | yes                 | `steam`     | same as Ubuntu                                    |
| Pop!_OS                         | yes (same as Ubuntu) | `steam` (apt)   | same as Ubuntu                                    |
| Fedora 40+                      | yes                 | `steam` (RPM Fusion) | `mesa-libEGL libxkbcommon dbus-libs`        |
| Nobara                          | yes                 | preinstalled           | preinstalled                                      |
| Arch Linux                      | yes                 | `steam` (pacman) | `libegl libxkbcommon libxcursor dbus`        |
| Manjaro / EndeavourOS           | yes                 | `steam`     | same as Arch                                      |
| openSUSE Tumbleweed / Leap      | yes                 | `steam` (Packman/Education) | `libEGL1 libxkbcommon0 libdbus-1-3` |
| NixOS (unstable)                | yes (in user dir)   | enable `programs.steam` | install `pkgs.libxkbcommon` etc. into profile    |
| Alpine 3.20+ (non-musl)        | yes                 | unsupported this version           | `mesa-egl libxkbcommon dbus-libs`                 |
| SteamOS 3 (HoloISO)             | yes                 | preinstalled           | preinstalled                                      |

## Install the release bundle

Download `WolfLauncher-<version>-linux-x86_64-installer.tar.gz` and its
`.sha256` sidecar from the chosen GitHub release, then run:

```bash
sha256sum -c WolfLauncher-<version>-linux-x86_64-installer.tar.gz.sha256
tar -xzf WolfLauncher-<version>-linux-x86_64-installer.tar.gz
cd WolfLauncher-<version>-linux-x86_64
./install.sh
```

The bundle contains the complete AppImage payload. Installation does not need
Python, pip, npm or a network connection and does not require `sudo`.

The installer places the AppImage under
`~/.local/share/wolflauncher/runtime/`, adds a desktop entry and creates both
`~/.local/bin/wolflauncher` and `~/.local/bin/wolflauncher-uninstall`.
Personal settings and curated servers stay under `~/.config/wolflauncher/`;
cached server data stays outside the installation's `runtime` directory.

```bash
wolflauncher-uninstall          # preserve settings and cached data
wolflauncher-uninstall --purge  # also remove configuration
```

Supporting desktop environments also show **Uninstall WolfLauncher** in the
application entry's actions menu.

## Install from source

Install Python 3.10 or newer, pip, and the Qt system libraries first. On
Debian/Ubuntu/Mint the Qt packages include `libegl1`, `libxcb-cursor0`,
`libxkbcommon0` and `libdbus-1-3`. Install native Steam separately.

```bash
git clone https://github.com/DrakonWolfDev/WolfLauncher.git
cd WolfLauncher
./scripts/wolflauncher-install.sh
```

Alternatively, download `wolflauncher-<version>-installer-source.tar.gz` and
its `.sha256` sidecar from the chosen GitHub release, when available:

```bash
sha256sum -c wolflauncher-<version>-installer-source.tar.gz.sha256
tar -xzf wolflauncher-<version>-installer-source.tar.gz
cd wolflauncher-<version>
./scripts/wolflauncher-install.sh
```

Replace `<version>` with the release version. The installer needs the complete
source checkout or archive; downloading the shell script alone is insufficient.
Internet access is required for Python dependencies and Node.js/GameDig.

The source installer places the application and private Node.js/GameDig runtime
under `~/.local/share/wolflauncher/runtime/` and creates the same menu and
launcher commands. Add `~/.local/bin` to your `PATH` if necessary.
Personal settings and curated servers stay under `~/.config/wolflauncher/`;
cached server data stays outside the installation's `runtime` directory.
New installations start with an empty server list. Add your own favourites or
use the Server Browser.

```bash
wolflauncher-uninstall          # preserve settings and cached data
wolflauncher-uninstall --purge  # also remove configuration
```

Use the same path overrides when installing and uninstalling:

| Variable | Purpose |
| --- | --- |
| `WOLFLAUNCHER_PREFIX` | Installation directory, default `$XDG_DATA_HOME/wolflauncher/runtime` |
| `WOLFLAUNCHER_BIN_DIR` | Launcher directory, default `$XDG_BIN_HOME` or `~/.local/bin` |
| `WOLFLAUNCHER_APPIMAGE` | Explicit AppImage payload for a binary installation |
| `WOLFLAUNCHER_REPO` | Source checkout or unpacked archive directory |
| `WOLFLAUNCHER_SKIP_SYSTEM` | Suppress distribution-specific package hints |

Keep the installation directory separate from personal data directories.
`--purge` removes configuration only; cached data is retained.

## Build packages or develop your own version

See [BUILD_GUIDE.md](../BUILD_GUIDE.md) for AppImage, installer bundle, `.deb`
and Windows packaging, and [README.md](../README.md) for development setup.
The repository retains source, tests, build scripts and license notices so
forks can build and validate their own changes. Generated build outputs,
virtual environments, local graphs, credentials and personal databases are
excluded from version control. Build source distributions with
`python3 -m build --sdist`; do not archive your entire working directory.

## Troubleshooting

- If pip or ensurepip is unavailable, install your distribution's Python pip
  package and retry. The installer targets a private directory.
- If the GUI fails to start, run `wolflauncher` in a terminal and check the Qt
  runtime libraries above.
- If Node.js cannot be downloaded, install native Node.js and npm, then rerun
  the installer. GameDig requires its complete lockfile dependency set.
