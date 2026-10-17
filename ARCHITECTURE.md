# Architecture

WolfLauncher is a Python and PySide6 desktop application for finding DayZ
servers, checking required Workshop mods, and handing launch control to Steam.
Linux is the primary platform; Windows builds remain experimental. See
[the Linux installation guide](docs/INSTALL_LINUX.md) for distro coverage and
[the build guide](BUILD_GUIDE.md) for packaging from source.

## Source layout

| Area | Modules |
| --- | --- |
| Application entry points | `main.py`, `wolflauncher/__main__.py`, `wolflauncher/app.py` |
| GUI features | `wolflauncher/*_feature.py`, presenters, controllers and table helpers |
| Curated servers | `config.py`, `curated_servers_controller.py`, `curated_status_cache.py` |
| Public discovery | `server_discovery.py`, `wolfapi_refresh_process.py`, `server_cache.py` |
| Live server status | `status.py`, `server_enrichment.py`, `dayz_mod_query.py` |
| Workshop checks | `mods.py`, `workshop_resolution_controller.py`, `workshop_subscription.py` |
| Launch preparation and handoff | `connect_preflight.py`, `launch_preflight.py`, `native_launcher.py`, `launch_execution.py` |
| Platform-specific behavior | `platforms/linux.py`, `platforms/windows.py`, `platform_detection.py` |
| Settings and local data | `settings.py`, `paths.py`, `persistence.py`, `secret_store.py` |
| Update notifications | `update_feature.py`, top-level `wolf_update/` package |
| UI assets | `wolflauncher/assets/` |
| Packaging and tests | `packaging/`, `scripts/`, `tests/` |

Module paths above are relative to `wolflauncher/` unless otherwise shown.

## Server discovery and local configuration

WolfAPI is a hosted directory consumed through HTTP. Building or running this
repository does not require a WolfAPI source checkout or its deployment tools.
The server browser stores discovered data in a local SQLite cache. Curated
servers and favourites are user-owned configuration; the shipped
`example.servers.yaml` starts with an empty server list.

Directory results provide cached server metadata. Background live queries
check the selected server and required mods; directory metadata alone is not
proof that a server is currently reachable or ready to join.

## Launch workflow

The native Python engine checks the detected DayZ and Workshop installation,
server endpoint and required mods before preparing the Steam launch command.
Workshop subscriptions, downloads and updates require explicit confirmation
and are performed through Steam. WolfLauncher does not remove subscriptions.

Platform backends own operating-system-specific detection and launch details.
Linux also exposes the vendored shell launcher as a compatibility fallback.
Its sources and license remain under `external/dayz-linux-cli-launcher/`.
A successful launcher exit means control was handed to Steam; it does not prove
that DayZ finished starting or connected to the server.

## Application update notifications

WolfLauncher configures the reusable top-level `wolf_update` package with its
live `wolflauncher.__version__`, GitHub repository, experimental channel and
official HTTPS destination. GitHub is used only to discover versions and obtain
displayable release notes. The sole **View Update** destination is the separately
configured Wolf Forge page.

The shared core performs release parsing, PEP 440 comparison, channel filtering,
throttling, dismissal policy and destination validation without depending on
WolfLauncher or PySide6. `wolf_update.qt` uses a one-task `QThreadPool` so network
access never blocks the GUI. WolfLauncher's `update_feature.py` owns the banner,
manual About-page action and persistence through the existing settings mapping.

The updater has no artifact-selection, download, installer, AppImage replacement
or rollback path. Release-note markup is converted to inert text and cannot
provide a navigation destination. See
[the update-notification guide](docs/UPDATE_NOTIFICATIONS.md) for behavior and
release testing.

## Building and testing

Install the dependencies and run the application as described in
[README.md](README.md). Run `python -m unittest discover` in that Python
environment. The repository includes unit tests and GitHub Actions workflows;
package builds and installer instructions live in the linked public guides.
User settings, caches, virtual environments and generated build outputs are
not part of source distributions.

## HTTPS certificate validation

Provider JSON, form and HTML requests share a verified HTTPS context. Windows
uses truststore's CryptoAPI chain builder, avoiding OpenSSL selecting an expired
cached intermediate or cross-sign instead of a valid server-supplied chain.
Linux retains OpenSSL system trust. Certificate trust, expiry and hostname
verification remain required, with TLS 1.2 as the minimum; no unverified retry,
certificate-store edits or global SSL injection are used. Windows distributions
include truststore and its native backend. Diagnostics report the runtime and
verification backend without contacting external services.

This changes HTTP transport only: WolfAPI endpoints, row identity, freshness,
cache retention and selected-server checks are unchanged. See
`DISCOVERY_FRESHNESS_HANDOFF.md` for the coordinated API handoff.
