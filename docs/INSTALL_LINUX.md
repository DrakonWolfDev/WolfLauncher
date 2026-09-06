# Installing WolfLauncher on Linux

WolfLauncher ships two installation paths on Linux. The distros below are tested
or validated by inspection; anything not listed should still work but is
"best-effort" until a maintainer verifies it.

## 1. The all-in-one installer (recommended, every distro)

The installer lives at [`scripts/wolflauncher-install.sh`](../scripts/wolflauncher-install.sh).
It installs into `~/.local` (XDG-compliant), needs no `sudo`, and works on every
mainstream distribution.

```bash
git clone https://github.com/DrakonWolfDev/WolfLauncher.git
cd WolfLauncher
./scripts/wolflauncher-install.sh
```

Or pipe from a release tarball:

```bash
curl -fsSL https://github.com/DrakonWolfDev/WolfLauncher/releases/latest/download/wolflauncher-install.sh | bash
```

> The `.github/workflows/installer.yml` workflow publishes three things to every GitHub release:
>
> - `wolflauncher-install.sh` and `wolflauncher-uninstall.sh` (with their SHA-256 sums in `wolflauncher-installer-scripts.sha256`) — the canonical `curl ... | bash` payload.
> - `wolflauncher-<version>-installer-source.tar.gz` (with SHA-256 sidecar) — the full installer payload as a single archive.
>
> Download the tarball, verify the checksum, extract, and run `./scripts/wolflauncher-install.sh` from inside the bundle if you'd rather inspect the bundle before running anything.

What it does:

- Detects your distribution family (Debian/RHEL/Arch/SUSE/NixOS/Alpine) and
  prints native install hints for Steam and Qt libraries.
- Installs Python 3.10+ dependencies and the WolfLauncher app into
  `~/.local/share/wolflauncher/python/`.
- Downloads a private Node.js + pinned GameDig runtime so live server status
  checks work even when no system `node` is available.
- Vendors the external `dayz-launcher.sh` fallback.
- Installs a desktop entry and icon under `~/.local/share/applications/` and
  `~/.local/share/icons/hicolor/`.
- Drops a launcher script at `~/.local/bin/wolflauncher`.

To uninstall:

```bash
./scripts/wolflauncher-uninstall.sh            # keep settings/favourites
./scripts/wolflauncher-uninstall.sh --purge    # remove everything
```

### Environment overrides

| Variable                    | Effect                                                        |
| --------------------------- | ------------------------------------------------------------- |
| `WOLFLAUNCHER_PREFIX`       | Override install prefix (default `~/.local/share/wolflauncher`) |
| `WOLFLAUNCHER_BIN_DIR`      | Override launcher directory (default `~/.local/bin`)           |
| `WOLFLAUNCHER_REPO`         | Override source checkout location                              |
| `WOLFLAUNCHER_VERSION`      | Force a version string in the wrapper script                   |
| `WOLFLAUNCHER_ASSUME_YES=1` | Skip optional yes/no prompts                                   |
| `WOLFLAUNCHER_SKIP_SYSTEM`  | Skip distro-specific install hints                             |

## 2. The `.deb` package (system install, Debian/Ubuntu/Mint only)

The existing `scripts/build-deb.sh` continues to produce a `.deb` for
distribution through the Debian/Ubuntu ecosystem. See
[`BUILD_GUIDE.md`](../BUILD_GUIDE.md) for details.

| Distro family     | Path                                      |
| ---------------- | ----------------------------------------- |
| Debian / Ubuntu  | `apt install ./wolflauncher_*.deb`        |
| Fedora / RHEL    | Not yet packaged (see "Packaging status") |
| Arch / Manjaro   | Not yet packaged (use the installer)       |

## Distro matrix

The installer is distro-neutral; the table below lists what's been verified
and the system packages you'll likely want for Steam and the Qt runtime.

| Distro                          | Installer verified | Steam                  | Qt libs                                           |
| ------------------------------- | ------------------- | ---------------------- | ------------------------------------------------- |
| Ubuntu 22.04 / 24.04            | yes                 | `steam` (apt) or Flatpak | `libegl1 libxcb-cursor0 libxkbcommon0`           |
| Debian 12+                      | yes                 | `steam` (non-free) or Flatpak | same as Ubuntu                            |
| Linux Mint 21+                  | yes                 | `steam` or Flatpak     | same as Ubuntu                                    |
| Pop!_OS                         | yes (same as Ubuntu) | Flatpak recommended   | same as Ubuntu                                    |
| Fedora 40+                      | yes                 | `steam` (RPM Fusion) or Flatpak | `mesa-libEGL libxkbcommon dbus-libs`        |
| Nobara                          | yes                 | preinstalled           | preinstalled                                      |
| Arch Linux                      | yes                 | `steam` (pacman) or Flatpak | `libegl libxkbcommon libxcursor dbus`        |
| Manjaro / EndeavourOS           | yes                 | `steam` or Flatpak     | same as Arch                                      |
| openSUSE Tumbleweed / Leap      | yes                 | `steam` (Packman/Education) or Flatpak | `libEGL1 libxkbcommon0 libdbus-1-3` |
| NixOS (unstable)                | yes (in user dir)   | enable `programs.steam` | install `pkgs.libxkbcommon` etc. into profile    |
| Alpine 3.20+ (non-musl)        | best-effort         | Flatpak only           | `mesa-egl libxkbcommon dbus-libs`                 |
| SteamOS 3 (HoloISO)             | yes                 | preinstalled           | preinstalled                                      |

"Verified" means the installer runs and the app launches on a fresh user
account. Steam itself is not part of WolfLauncher — install it from the
suggested source above. The launcher will detect native, Flatpak, and Snap
Steam installs automatically.

## What about OS store packaging?

The user-local installer is the first step toward AUR/Flatpak/Snap packaging:

- **AUR:** a thin `PKGBUILD` that wraps `wolflauncher-install.sh` is trivial.
- **Flatpak:** the desktop entry, icon and runtime layout already match
  Flatpak conventions; only a manifest and a wrapper script are missing.
- **Snap:** same shape as Flatpak. The Linux backend already detects Snap
  Steam at `~/snap/steam/...`.
- **nixpkgs:** the user-local installer is reusable via `pkgs.callPackage`.

Tracked in [`ROADMAP.md`](../ROADMAP.md) under "Distribution".

## Troubleshooting

- **`python3 -m pip` is disabled by an externally managed environment**: the
  installer does not use `pip install` against system Python — it targets a
  user-local prefix. If `ensurepip` is disabled too, install `python3-pip` (or
  `python3-pipx`) via your package manager and re-run.
- **`~/.local/bin` is not on `$PATH`**: most distros add it automatically; if
  not, add `export PATH="$HOME/.local/bin:$PATH"` to your shell rc file.
- **The GUI does not start**: install the Qt libs listed for your distro, or
  run `wolflauncher` from a terminal to see the underlying error.
- **Server status checks fail**: ensure Steam is installed (the launcher only
  uses `node`/`gamedig` for status — Steam is needed for launch).
- **Live server query returns "gamedig not installed"**: confirm
  `~/.local/share/wolflauncher/node/node_modules/gamedig/bin/gamedig.js`
  exists. The installer pins GameDig to `5.3.3`.