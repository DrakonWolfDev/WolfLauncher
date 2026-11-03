# Local test build 0.9.3.5b

Built locally on 3 November 2026 from the current uncommitted working tree, based
on commit `1b314377ac9cb038bed4545b24722a83bfff18f4`. No commit, tag, release
upload or WolfAPI deployment was made. The displayed version is `0.9.3.5b`;
Windows executable and Setup numeric metadata are `0.9.3.5`.

## Artifacts

| Artifact | Size | SHA-256 |
| --- | --- | --- |
| [wolflauncher-0.9.3.5b-setup-windows-x64.exe](../dist/windows/wolflauncher-0.9.3.5b-setup-windows-x64.exe) | 61.3 MiB | `4bda0d0a0e0269dba0a52bb0caad5d46052eff54a3d6189d7533f4ba6ece6ed0` |
| [wolflauncher-0.9.3.5b-windows-x64.zip](../dist/windows/wolflauncher-0.9.3.5b-windows-x64.zip) | 89.1 MiB | `a02676e4e6953598c392335c5a36f79f267139820438337b292d6c7ddfb99ac4` |
| [WolfLauncher-0.9.3.5b-x86_64.AppImage](../dist/WolfLauncher-0.9.3.5b-x86_64.AppImage) | 96.4 MiB | `19f9bf3bafc302cb47454194e8a95fbb09975bd84cc9de66ca0887e0e51e9927` |
| [WolfLauncher-0.9.3.5b-linux-x86_64-installer.tar.gz](../dist/WolfLauncher-0.9.3.5b-linux-x86_64-installer.tar.gz) | 95.6 MiB | `8f12837f14e15a737635c655dd0733b1a37765328ed7a1ecfddd48a9c2b57568` |

Each artifact also has an adjacent `.sha256` file. All four checksums were
recomputed and matched. The Windows ZIP passed its archive integrity check.
The AppImage is Linux x86_64; copy it to Linux and mark it executable before
running. The Linux installer archive contains that AppImage and install/uninstall
scripts. These are local testing candidates, not a published release.

## Included work

- Editor / LAN Play naming, automatic LAN Workshop matching, missing-item lists
  and a separate saved query port.
- Steam completion callback handling, evidence-scoped metadata-only update
  acknowledgement and selected-library installed revision checks.
- Mixed unpublished/Workshop manifests with clear manual requirements and guarded
  launch blocking.
- Faster server-list population and incremental updates, plus optional polling
  deferral during joins, Workshop work, game sessions and hidden/minimised windows.
- Explicit normalized provider perspective fields remain authoritative. No raw-tag
  inversion has been introduced; known camera settings are still needed.

## Build and validation

- Windows: native Windows x64, Python 3.12.10, PySide6 6.11.1, PyInstaller 6.21.0,
  hooks 2026.6, Node.js 24.14.0, verified Inno Setup 6.7.3. Built with the normal
  Windows scripts and repository-pinned release requirements after bootstrapping
  the repository's setuptools/wheel versions. Executable and Setup version fields
  were inspected directly.
- Linux: isolated Ubuntu 22.04 x86_64 WSL2 environment (`WolfLauncherBuild`), Python
  3.10, glibc 2.35, PySide6 6.11.1, PyInstaller 6.21.0 and bundled Node.js 20.20.2.
  The official Ubuntu rootfs checksum was verified. Runtime requirements were
  bootstrapped for Python 3.10's conditional dependencies, then release-pinned
  requirements were installed; AppImage/runtime/Node download hashes were checked
  by the build script. This is a native Linux build, not Windows cross-compilation.
- Windows full suite: **871 run, 67 skipped, 804 passed**.
- Linux full suite: **871 run, 7 skipped, 864 passed**.
- Both packaged startup smoke tests passed with isolated temporary settings/data.
  Embedded app versions and the presence of `wolf_update`, Workshop freshness and
  background-polling modules were checked in both frozen payloads.
- Ruff lint and the repository formatting gate pass.

The isolated toolchains, dependency inventories and build/test logs remain under
`build/toolchains/`; the verified Inno compiler is under `build/tools/`. The WSL
distribution is registered as `WolfLauncherBuild`, with its filesystem stored
under `build/toolchains/linux-wsl`. The existing `.venv` was not replaced.

## Manual checks still needed

Real Steam updates/subscriptions, LAN joining, game launch/exit and interactive
About -> Check for Updates (including a 15-second responsiveness check) remain
manual validation tasks. The startup smoke is shorter and does not establish
these outcomes. Windows Setup install/reinstall/uninstall testing was deliberately
not run after detecting an existing WolfLauncher installation registration; the
installed launcher was not replaced. Linux was built/tested in WSL; testing on a
normal Linux desktop and other distributions remains necessary.

See [reliability follow-up](RELIABILITY_FOLLOWUP_2026-11-03.md) and
[server-table measurements](SERVER_TABLE_PERFORMANCE.md) for implementation
limits. The perspective investigation is recorded in the follow-up.

## Refreshed after LAN test feedback

The same 0.9.3.5b artifact paths were rebuilt after the user's LAN test. Replace
previous downloads of this version with these refreshed files; the table above
contains their current hashes.

The LAN screen now has compact IP/hostname, Game port and Query port controls,
plus Query server. Detected installed, missing and pending requirements appear
in Local Server selection before launch. The first join queries and pauses for
review; a changed manifest pauses again. Saving the profile preserves its queried
selection, and changing the address/ports invalidates the previous result.

The user's original test confirmed LAN joining with the correct mods loaded.
The separate DrakonCherno status report was traced to the saved favourite querying
2303: direct A2S and GameDig successfully read DrakonCherno on query 3303 and
reported game 3302. The favourite and its index were corrected transactionally
with a timestamped backup. Later query failures coincided with the user stopping
or restarting the server. GameDig JSON errors now show the attempted query port
and useful guidance instead of a generic incomplete/offline response.

The updated layout was rendered and visually inspected, including preservation
of the displayed requirements after saving. Manual retest of the new query/review
workflow remains pending. Packaged startup smokes passed after the refresh.
