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

## Clean domain-migration rebuild

Superseding private Mint package:
`dist/wolflauncher_0.9.3.5b_mint22-join-test-20261114_amd64.deb`, built from
clean integrated source `4815172`. Includes the new wolflauncher.co.uk domain,
name row and toolbar move. Checksum, full independently extracted inventory with
require-clean/expected-commit provenance, packaged UI/domain checks and normal
startup/shutdown pass. See [matching website deployment and full evidence](JOIN_DOMAIN_MIGRATION_2026-11-14.md).

## Compact sharing rebuild

Latest private Mint installer:
`dist/wolflauncher_0.9.3.5b_mint22-share-test-20261114_amd64.deb`,
from clean source 1cb10dd. Adds Share server link… and compact HTTPS sharing.
Checksum, independently extracted full inventory with clean/expected-commit
provenance, isolated UI/short-code checks and normal startup/shutdown pass.
The matching website shows names after its scoped, verified TLS-proxy routing
fix. See [full evidence](SHORT_SERVER_SHARING_2026-11-14.md).

## Matching Windows sharing test installer

The maintainer confirmed completion of the requested Linux hands-on checks,
including installer/settings, profile/name, sharing/handoff and server joining.
This is maintainer-reported verification, separate from automated evidence.

At their request, built the matching Windows installer from clean development
commit `d6e162d54692e67f72bf0c34ecc698ec3b100611`. Application source matches the
latest Mint sharing build; intervening commits only record verification.
Version remains **0.9.3.5b**. Older packages are preserved.

- [Windows test installer](../dist/windows/share-test-20261114/wolflauncher-0.9.3.5b-setup-windows-x64.exe)
- SHA256: `ecf5f925e91fc00ee5f26911a82f39ac8117c0ca66c9c544bce237cba35603f6`
- Adjacent checksum and provenance records, plus the portable ZIP and checksum,
  are retained in the same dated directory.
- [Tests workflow 43616145919](https://github.com/DrakonWolfDev/WolfLauncher/actions/runs/43616145919):
  all eight jobs passed, including Windows packaging, Linux packages, Python
  3.10/3.11/3.12 suites and quality/dependency-audit checks.
- Windows: **1,038 tests, OK / 68 skipped**. Native frozen startup and installer
  install/reinstall/start/uninstall checks passed, including user-data preservation
  and protocol registration/ownership checks.
- Downloaded installer and portable checksums passed. Installer provenance verifies
  the expected clean commit. Independently extracted portable paths, sizes and
  hashes match all **1,020** recorded bundle files; native build checked its
  inventory before packaging. The Linux extraction check does not attest Windows
  file modes.

The maintainer subsequently confirmed that the launcher and link work on
Windows. This is maintainer-reported hands-on evidence; Windows profile
discovery and Steam/DayZ joining were not separately confirmed in that report.
No version bump, main merge, tag, public installer publication or download-link
change was made. Explicit final release instructions remain pending.
