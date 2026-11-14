# Clean installer rebuild with npm fix — 14 November 2026

At the maintainer's request, removed the old contents of `dist` and built fresh
private Windows Setup and Linux Mint 22.3 amd64 Debian installers. Application
version remains **0.9.3.5b**. Both builds use clean development commit
`20b8e6f3e93bb3a6bcbec94b0b4827d3076f0588`, including the scoped
fast-xml-parser 5.12.0 override and unchanged GameDig 5.3.3.

The old installers were removed as requested. A verified Node download cache was
retained under ignored `build/downloads`; fresh Windows intermediate bundle and
portable ZIP evidence are under ignored `build/verified-windows-npm-20261114`.
Only the two installers and their checksum/provenance sidecars are delivered in
`dist`.

## Windows

- Artifact: `dist/wolflauncher-0.9.3.5b-setup-windows-x64.exe`.
- SHA256: `06370bc912a7f8d9083ed6775863dcc0261509740bd3de11e973cde03940d638`.
- Native Python 3.12.10, PySide6 6.11.1, pinned Node 24.14.0 and verified Inno
  Setup 6.7.3 compiler; locked npm installation reports zero vulnerabilities.
- Full native suite: **1,038 tests, OK / 75 skipped**.
- Native frozen startup passed with isolated settings and required keyring.
- All three runtime tests passed using the actual bundled Node executable and
  modules: bounded malformed-XML rejection, XML-consumer compatibility and a
  loopback UDP DayZ CLI query.
- Installer checksum and require-clean/expected-commit provenance passed.
  Independent extraction of the fresh portable ZIP matches the installer bundle
  inventory, including file hashes/sizes.
- Isolated install/reinstall/start/uninstall passed, with test user-data
  preservation. Existing real server-link registration was preserved; handler
  ownership checks were skipped because a handler was already registered.
  The existing lifecycle test was run from an ignored helper copy adding hidden
  process windows; its test assertions were unchanged.

## Mint

- Artifact: `dist/wolflauncher_0.9.3.5b_mint22-npm-test-20261114_amd64.deb`.
- SHA256: `fe7c950e14b3f6ebbe8b4de34ca02acb1953f2585aee8463f4e586c36fae45ae`.
- Built in a clean native Linux checkout with Python 3.12.16, the locked release
  dependencies and pinned Node 20.20.2. Requires Python >=3.12 and <3.13 plus
  libegl1, matching Mint 22.3.
- Locked npm installation reports zero vulnerabilities. Extracted payload
  confirms GameDig 5.3.3 and fast-xml-parser 5.12.0.
- SHA256 and clean expected-commit provenance pass. Complete independent Debian
  payload/control extraction matches the inventory, including modes.
- All three runtime tests pass using the independently extracted package's Node
  executable and dependencies, including actual CLI queries to a loopback DayZ
  fixture.
- Normal offscreen packaged startup/shutdown passed from a separate temporary
  working directory with isolated settings. The import path was explicitly
  checked to be the extracted payload, rather than the source checkout.
- Native Mint installation/upgrade remains a maintainer check. Source regression
  and quality evidence for this commit is in the npm audit record: 1,038 tests,
  OK / 7 skipped, with required Ruff and core mypy checks passed.

## Scope

Automated checks use synthetic server fixtures and isolated settings. Real server
refresh, browser handoff and Steam/DayZ joining with these rebuilt installers
remain hands-on checks. No installed user application was replaced, version
bumped, main merged, tag created, public upload made or download links changed.
