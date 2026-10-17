# WolfAPI discovery handoff

## Windows HTTPS validation — 2026-10-17

WolfAPI's current public certificate and full server chain validate normally.
An affected Windows 10 installation contained the obsolete cross-signed
ISRG Root X2 certificate (SHA-1 thumbprint
`151682F5218C0A511C28F4060A73B9CA78CE9A53`, expired 2025-09-15).
Adding that public certificate to an isolated Python default SSL context
reproduced `CERTIFICATE_VERIFY_FAILED: certificate has expired`; a native
Windows truststore context with the same certificate validated successfully.

Launcher now uses Windows native verified chain building for provider HTTP
requests. Users need no certificate-store modifications. This does not permit
expired server certificates or bypass trust/hostname checks. Linux keeps its
existing system-trust backend. See `ARCHITECTURE.md` for implementation details.

No API deployment, endpoint/schema, identity, freshness, cache or rollout-default
change is required. This source fix needs a new published Launcher build before
downloaders receive it; GitHub's existing 0.9.0b2 installer is unchanged.
API-side record: `../WolfAPI/DISCOVERY_FRESHNESS_CONTRACT.md`.

Initial TLS validation on the Windows development machine (the later
[CI repair record](docs/CI_VALIDATION.md) supersedes the test/format limitations):

- All 23 focused TLS, HTTP, diagnostics and startup tests passed. Offline TLS
  tests prove that adding an expired intermediate changes legacy validation
  from success to the exact expiry error while native validation still succeeds.
- Live liveness and a one-row discovery request passed through the provider
  helper with the expired public ISRG Root X2 certificate loaded only in memory.
- Full UTF-8 discovery ran 768 tests: 700 passed, 55 skipped, 13 failed. An
  unchanged HEAD snapshot ran 760 tests with the exact same 13 failing test IDs
  (Linux shell installers, Windows SQLite cleanup and newline rollback checks).
  These failures predate this transport change; the full Windows suite is not green.
- Repository-wide lint and changed-file formatting passed. Repository-wide
  formatting still flags six unchanged files. Release dependency declarations
  and the hash-pinned truststore runtime were checked.

Build verification must use a clean terminal PATH: the initial tool-enriched
Codex environment caused PyInstaller to pick up Poppler's incompatible ICU DLL
and fail importing QtCore. That verification artifact must not be distributed.

The clean-PATH Windows PyInstaller build completed successfully. Its offscreen
startup smoke test exited 0 using disposable settings and initialized the native
TLS context. Archive inspection confirmed truststore._windows is bundled and
its MIT license is present. Existing published installers were not overwritten.
