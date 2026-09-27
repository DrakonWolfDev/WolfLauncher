# WolfLauncher build guide

A short, repeatable build guide for the two supported build platforms:

- **Linux:** use the distro-neutral user-local installer, build a portable
  AppImage, or build a native-architecture Debian package (`.deb`).
- **Windows:** build a portable ZIP, then optionally a per-user Setup installer.

> [!important]
> Build each platform’s release artifact on that platform. Do not build a Windows executable from Linux or a Linux `.deb` from Windows.

## Before you begin

1. Clone the repository and open a terminal in its root.
2. Make sure the working tree is in the state you mean to build:

```text
git status --short
```

3. Start with a clean `dist/` directory if you need to know exactly which files this build produced. It is ignored by Git.
4. The build scripts download pinned Node runtimes/dependencies as needed, so internet access is required on the first build.

## Repository inputs

The requirements files have separate purposes; install the set for your task:

| File | Purpose | Used by |
| --- | --- | --- |
| `requirements.txt` | Runtime dependencies for running from source | README setup, user-local Linux installer, unit-test CI |
| `requirements-dev.txt` | Runtime dependencies plus pinned Python build tools | Wheel/source archive and Debian builds |
| `requirements-quality.txt` | Pinned lint, type-check and dependency-audit tools | Quality CI, alongside runtime dependencies |
| `requirements-release.txt` | Exact runtime versions and package hashes | Debian payload and release dependency audit |
| `requirements-windows-release.txt` | Release runtime set plus pinned Windows freezer dependencies | Windows portable bundle build |

`pyproject.toml` declares installed-package metadata and runtime dependencies.
Keep its dependency ranges aligned with `requirements.txt`. The release files
lock a tested dependency set and include transitive packages and hashes.

The Windows build has two stages: `scripts/build-windows.ps1` creates and
smoke-tests the portable bundle; `scripts/build-windows-installer.ps1` packages
that bundle with Inno Setup. `scripts/install-inno-setup.ps1` obtains the verified
compiler, and `scripts/test-windows-installer.ps1` checks the installer lifecycle.
The commands below are the supported entry points and are also used by CI.

The public repository includes tests, CI, build scripts, examples and licence
notices so contributors can build and verify releases. Generated `build/`,
`dist/`, virtual environments, local agent settings and `graphify-out/` are
excluded from version control and source distributions. Publish the versioned
artifacts produced by the build scripts, rather than a copy of a working folder.

## Linux — user-local installer

The newer user-local installer works across Ubuntu 22.04/24.04/26.04,
Debian 12+, Linux Mint 21+, Pop!_OS, Fedora 40+, Nobara, Arch Linux,
Manjaro/EndeavourOS, openSUSE Tumbleweed/Leap, NixOS, Alpine 3.20+
(non-musl environment) and SteamOS 3/HoloISO. This distro coverage is confirmed
by the maintainer. See [Installing on Linux](docs/INSTALL_LINUX.md).

Run `./scripts/wolflauncher-install.sh` from the source checkout. The `.deb`
build below remains specific to Debian/Ubuntu-family systems.

## Linux — AppImage build

The AppImage bundles Python, Qt, Node.js and GameDig into one executable. Build
it on the oldest glibc-based Linux baseline you intend to support: AppImage
removes package-manager dependencies, but it does not make a binary compatible
with glibc versions older than the build host.

Install the runtime and AppImage build dependencies:

```bash
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt -r requirements-appimage.txt
./scripts/build-appimage.sh
```

The script downloads checksum-pinned Node.js 20.20.2, appimagetool 1.9.1 and
the AppImage type-2 runtime, builds a PyInstaller payload, runs an off-screen
packaged startup smoke test, and writes these files under `dist/`:

```text
WolfLauncher-<version>-x86_64.AppImage
WolfLauncher-<version>-x86_64.AppImage.sha256
```

Run it with:

```bash
chmod +x dist/WolfLauncher-*.AppImage
./dist/WolfLauncher-*.AppImage
```

Verify its checksum with:

```bash
cd dist
sha256sum --check WolfLauncher-*.AppImage.sha256
```

## Linux — Debian package build

The package build supports the current machine architecture (`amd64` or `arm64`). Build on a Debian/Ubuntu-family machine that matches the architecture you want to release.

### Dependencies

Install these system packages:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential dpkg-dev curl xz-utils tar
```

- Python **3.12 is recommended** (the current Ubuntu 24.04 baseline uses it).
- `dpkg-dev` provides `dpkg-deb`, which creates the `.deb`.
- `curl`, `xz-utils`, and `tar` let the build script fetch and unpack its pinned Node.js runtime.
- You do **not** need to install Node.js or GameDig globally for the release package; the build bundles its own pinned runtime and uses the lockfile-pinned GameDig dependency.

### Build

Create a virtual environment and install the pinned build tools:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt
```

Run the build:

```bash
./scripts/build-deb.sh
```

### Output

The script prints the artifact path and writes these files under `dist/`:

```text
wolflauncher_<version>_<label>_<architecture>.deb
wolflauncher_<version>_<label>_<architecture>.deb.sha256
```

### Verify

```bash
cd dist
sha256sum --check wolflauncher_*.deb.sha256
```

Optional local package smoke test:

```bash
sudo apt install ./wolflauncher_*.deb
wolflauncher
```

**Checkpoint:** the checksum passes and the installed app opens. The `.deb` is a local build artifact; release artifacts should still be smoke-tested in the release CI environment.

## Windows — portable ZIP build

Build this on 64-bit Windows using PowerShell.

### Dependencies

Install:

- **Python 3.12 (64-bit)** — available with the `py -3.12` launcher.
- **Node.js 24.14.0 Windows runtime** — includes `node` and `npm`.
- Internet access for Python packages and `npm ci`.

Install Node.js:

```powershell
winget install OpenJS.NodeJS.LTS
```

Close and reopen PowerShell, then verify:

```powershell
py -3.12 --version
node --version
npm.cmd --version
```

> [!note]
> Use `npm.cmd` in PowerShell if execution policy blocks `npm.ps1`.

### Prepare Python

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-windows-release.txt
```

### Build the portable ZIP

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1 `
  -Python .\.venv\Scripts\python.exe
```

The script:

- installs the lockfile-pinned GameDig tree in `packaging\npm`;
- bundles the current Node runtime and Python application with PyInstaller;
- runs a packaged off-screen GUI and Windows Credential Manager smoke test;
- writes the ZIP and its SHA-256 sidecar to `dist\windows`.

### Output and verification

```powershell
Get-ChildItem .\dist\windows
Get-FileHash .\dist\windows\wolflauncher-*.zip -Algorithm SHA256
```

**Checkpoint:** there is a versioned ZIP and matching `.sha256` file. Extract the ZIP somewhere outside the repository and start `WolfLauncher.exe` as a final manual smoke test.

## Windows — per-user Setup installer (optional)

Build the portable ZIP first. The installer consumes that bundle.

### Extra dependency

The repository provides a script that installs the hash-pinned Inno Setup compiler:

```powershell
$iscc = powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-inno-setup.ps1
```

### Build

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-windows-installer.ps1 `
  -Iscc $iscc `
  -Python .\.venv\Scripts\python.exe
```

### Output

```text
dist\windows\wolflauncher-<version>-setup-windows-x64.exe
dist\windows\wolflauncher-<version>-setup-windows-x64.exe.sha256
```

### Verify

Run the repository’s installer test:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-windows-installer.ps1 `
  -Installer .\dist\windows\wolflauncher-<version>-setup-windows-x64.exe
```

This checks isolated install, packaged startup, in-place reinstall, and uninstall behavior while confirming the user’s configuration/cache location is preserved.

## Common problems

| Symptom | What to check |
| --- | --- |
| `node` or `npm` not found | Close/reopen PowerShell after Node installation; use `npm.cmd` if PowerShell blocks the `.ps1` shim. |
| Linux build rejects the architecture | The `.deb` script currently supports only `amd64` and `arm64`. |
| `dpkg-deb` not found | Install `dpkg-dev`. |
| Windows build fails before PyInstaller | Confirm Python 3.12 and the `requirements-windows-release.txt` install completed in the virtual environment. |
| Artifact has no SHA-256 file | Treat the build as incomplete; the relevant build script should always write a sidecar hash. |

## Useful non-release commands

Run the application from source:

```bash
# Linux
.venv/bin/python main.py
```

```powershell
# Windows
.\.venv\Scripts\python.exe main.py
```

Run tests:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover
```

```powershell
.\.venv\Scripts\python.exe -m unittest discover
```

## Source of truth

- `scripts/build-deb.sh` — Linux package build.
- `scripts/build-windows.ps1` — Windows portable bundle.
- `scripts/build-windows-installer.ps1` — Windows installer.
- `README.md` — broader development, installation, and release context.
