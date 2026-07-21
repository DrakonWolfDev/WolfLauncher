# WolfLauncher update strategy

Status: approved direction; implementation remains a release gate.

WolfLauncher should make updates easy to receive without allowing the running
application to silently replace itself or system-owned files. Windows and
Linux share release policy and metadata, while installation remains native to
each platform.

## Shared release contract

Publish stable and beta channels from a controlled HTTPS endpoint. Each channel
manifest contains the release version, minimum supported updater or bootstrap
version, publication time, release-notes URL, platform asset URL, download size
and SHA-256 digest. Sign the manifest independently of transport and keep the
verification public key in the installed application.

The launcher may check the manifest quietly at startup no more than once per
day. It shows a non-blocking update notice with **View changes**, **Update now**
and **Remind me later**. Security-critical releases may be prominent, but must
still explain what will happen. Never update during a DayZ launch, active
Workshop operation or server-enrichment job.

GitHub Releases can host immutable versioned assets initially. A small stable
project URL owns the channel manifest so hosting can move later without
replacing every installed client. Release publication is an explicit tag or
manual workflow, not an artifact retained from every development push.

## Windows

Provide a small evergreen `WolfLauncherSetup.exe` bootstrapper. It contains no
application runtime; it reads the stable manifest, downloads the current
per-user installer, verifies the manifest signature, SHA-256 digest and Windows
Authenticode signature, then opens the normal guided installation. It also
supports repair and an explicit beta-channel choice.

An installed launcher uses the same manifest to offer updates. After consent it
downloads the full signed installer in the background, verifies it, closes
WolfLauncher cleanly and runs the installer. Start with full installers rather
than binary deltas: the simpler recovery and verification model is worth the
extra download while the user base is small. Preserve roaming configuration
and local cache exactly as the current installer lifecycle does.

Code-sign the bootstrapper, installer and shipped executables with one stable,
trusted publisher identity before calling Windows supported. Do not embed a
long-lived signing secret in the repository or application.

## Linux

Publish WolfLauncher through a signed APT repository for the supported
Debian/Ubuntu family. A small repository-setup `.deb` installs the repository
definition and scoped signing key; after that, Update Manager or `apt` owns
download, verification, upgrade and rollback-visible package history.

The launcher may notify that a newer version exists and offer to open the
platform update UI or show exact package-manager instructions. It must not
invoke hidden privilege prompts, write into `/usr` itself or maintain a second
private copy beside the package-managed installation.

Portable AppImage-style updating can be considered only after the supported
APT lane is stable. It remains a distinct installation channel so two updaters
never compete for the same installation.

## Failure and recovery

- An unavailable manifest leaves the installed version working quietly.
- Signature, digest or publisher verification failure blocks installation and
  produces a redacted support report.
- Interrupted downloads resume or restart safely from a temporary location.
- Failed installation leaves the previous installation and all user data
  recoverable.
- The launcher never claims an update succeeded until the newly installed
  version starts and reports its version.

## Implementation order

1. Establish release signing identities and protected CI signing boundaries.
2. Publish versioned assets and the signed channel manifest.
3. Add the in-app availability notice without automatic installation.
4. Add the Windows bootstrapper and verified prompted installer handoff.
5. Publish the signed APT repository and repository-setup package.
6. Exercise install, update, interrupted-update, downgrade/recovery and
   user-data preservation on the release desktop matrix.
