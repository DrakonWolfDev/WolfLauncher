# Local Windows and Debian test rebuild — 14 November 2026

Requested private test packages from development commit
`5fe27bddc8a0fd5bdb48399076a25765dc556281` on
`dev/release-preparation`. The source worktree was clean when builds started.
Version remains **0.9.3.5b**; dated artifact labels distinguish these packages
from the older packages with the same displayed version. No release, tag,
public upload or API deployment was made.

## Packages

- Windows: `dist/windows/wolflauncher-0.9.3.5b-setup-windows-x64-test-20261114.exe`
- Linux Mint 22.3 amd64: `dist/wolflauncher_0.9.3.5b_mint22-test-20261114_amd64.deb`
  (requires Python >=3.12 and <3.13, plus libegl1).

Each package has adjacent `.sha256` and `.provenance.json` files. The Windows
portable ZIP with the same dated label is also retained. Older Windows packages
were preserved, and the previous unpacked bundle is under
`dist/archive-before-2026-11-14/WolfLauncher`.

## Verification

- Full Windows suite: 1,038 tests, OK, 75 skipped.
- Full Linux suite in WSL Ubuntu 22.04 / Python 3.10: 1,038 tests, OK, 7 skipped.
- Windows frozen startup smoke passed with temporary application data and
  required keyring support. Portable and Setup inventory/provenance checks passed.
- Frozen Windows archive explicitly contains `player_profile_dialog` and
  `player_profiles` modules.
- Mint-targeted Python 3.12 suite: 1,038 tests, OK, 7 skipped. Ruff formatting
  and lint, core mypy, compilation, whitespace and locked Python dependency
  audit passed. npm reported two low-severity dependency advisories; pinned
  dependencies were preserved for this rebuild.
- Debian built from a clean Linux-native temporary checkout using Python 3.12.
  Package inventory/provenance and checksum checks passed. The extracted payload
  launched with temporary settings, displayed the existing-profile button and
  closed successfully. It was not installed on the host.
- The superseded Python 3.10 attempt on the Windows-mounted filesystem failed
  Debian control-directory permission validation; it is not the delivered package.

Native installer lifecycle, real Windows Documents/OneDrive profile discovery,
desktop Debian installation, and DayZ settings reuse remain user testing tasks.
The user's running installed launcher was not replaced by the build process.
The existing-profile picker is in Settings and Favourite Servers; it selects a
profile name without copying or rewriting DayZ profile files.

## Servers toolbar follow-up

Moved **Open a server link…** out of Settings into the Servers bottom toolbar,
between **Add a favourite server** and **Move up**, using the existing link
coordinator and standard button sizing. Windows artifacts were not rebuilt.
The Linux Mint package uses the additional `toolbar` filename label; the earlier
packages are preserved. This private package records the toolbar edits as a
dirty source delta from `5fe27bd`, rather than claiming a clean committed build.

Linux Python 3.12 regression suite: 1,038 tests, OK, 7 skipped. Workflow Ruff
format/lint and core mypy checks passed, as did `git diff --check`.
Compilation passed. The new package is
`dist/wolflauncher_0.9.3.5b_mint22-toolbar-test-20261114_amd64_amd64.deb`,
with adjacent SHA256 and provenance sidecars. Independent extraction of payload
and Debian control metadata matches the complete provenance inventory; checksum
verification passed. Offscreen extracted-package startup confirmed compact
toolbar sizing/order, absence from Settings and delegation of a click to the
existing link prompt. A screenshot was visually inspected. Native installation
and live link/server joining remain separate user checks. Existing pinned npm
dependencies still report the two low-severity advisories recorded above.

## Player-name row rebuild

Rebuilt only the Mint Debian test installer with the matching Settings name row
and existing Servers toolbar move. New filename:
`dist/wolflauncher_0.9.3.5b_mint22-profile-test-20261114_amd64.deb`.
Checksum, independently extracted full inventory, normal packaged startup/close
and isolated UI/action checks passed. Version remains 0.9.3.5b; older packages
and Windows artifacts are preserved. See
[release-readiness evidence and remaining checks](RELEASE_READINESS_2026-11-14.md).
