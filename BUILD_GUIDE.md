# WolfLauncher build guide

A short, repeatable build guide for the two supported build platforms:

- **Linux:** build a native-architecture Debian package (`.deb`).
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
