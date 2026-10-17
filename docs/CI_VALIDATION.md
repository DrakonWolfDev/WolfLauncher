# CI repair record — 2026-10-17

The failed Tests workflow at `622deb7` was investigated from its job logs and
compared with the pre-TLS run at `8706fb1`. Successful packaging jobs did not
establish that the separate test and quality gates passed.

## Repairs

- Updated the required Ruff formatting without weakening the checks. Quality
  checks now include the reusable `wolf_update` package.
- Wrote the Unicode Steam manifest fixture explicitly as UTF-8. Closed the test
  SQLite connection before deleting its directory on Windows. POSIX shell
  installer tests now skip on Windows while remaining enabled on Linux.
- Replaced a Python 3.11-only SQLite authorizer reset in the migration test with
  the supported Python 3.10 callback. Write contention recognizes SQLite primary
  and extended BUSY/LOCKED codes, with a text fallback for Python 3.10, and still
  raises unrelated database errors.
- Fixed a real saved-profile rollback bug: the undo journal captures original
  UTF-8 bytes without translating CRLF. A failed multi-file write restores the
  original files exactly. The regression explicitly creates CRLF on every host.
- Reproduced the Linux segmentation fault with full unittest discovery and
  faulthandler; its stack ended in the update runnable's completion lambda.
  Replaced that callback with checker-owned signals, a queued QObject slot and
  generation IDs. Tests cover repeated completion, GUI-thread delivery,
  cancellation followed by a new check, and receiver deletion before delivery.
- Fixed the first Workshop download request being throttled at low monotonic
  uptime. Only actual previous requests start the retry interval; the test fixes
  the clock at zero to cover freshly started systems deterministically.
- Updated hash-pinned cryptography from 49.0.0 to 50.0.2 after the dependency
  audit identified PYSEC-2026-3552. The artifact hashes come from PyPI metadata.

## Local validation

- Windows / Python 3.12: 771 tests, passing with 66 platform-specific skips.
- WSL Ubuntu 24.04 / Python 3.12: 771 tests, passing with 7 platform-specific skips;
  full discovery exits normally after the previously crashing update-check test.
- Ruff formatting and lint pass, including `wolf_update`.
- The four configured hardened-core mypy targets pass.
- Direct audit of the fully pinned release list reports no known vulnerabilities.
  The local WSL system lacks ensurepip, so this local audit used `--disable-pip
  --no-deps`; GitHub's quality job retains its original resolver-backed audit.

GitHub's Python 3.10/3.11/3.12 test matrix, quality job and platform packaging
jobs remain the final CI gates. No test or quality job was disabled. The
separate Installer workflow is still responsible for distribution artifacts.
There are no WolfAPI endpoint, discovery-contract or production deployment changes.
