# Shared DayZ server links

FEATURE-03 is implemented on `dev/release-preparation`. The matching HTTPS
fallback page now lives in
[Wolf-Launcher-Website](https://github.com/DrakonWolfDev/Wolf-Launcher-Website),
served at `https://wolflauncher.co.uk/join/` by its Docker/Coolify deployment.
The original Wolf Forge branch is historical implementation evidence, not the
current deployment source. Publish matching launcher binaries before advertising
server-link support in public downloads.

## User flow

Favourite Server and Server Browser context menus offer **Share server link…**.
The resulting compact HTTPS URL opens a page showing the supplied address and separate
game/query ports, with an explicit **Open in WolfLauncher** action, installation
guidance and a short-link copy option. A bounded WolfAPI directory lookup can
show the matching server name as advisory text. The page never guesses whether the launcher
is installed, automatically navigates to a protocol handler, starts a download or
queries the game server. Download links use the existing product download page.

The launcher accepts an HTTPS or `wolflauncher:` link from the OS, its command
line, or **Servers → Open a server link…**. A cold launch queues it until the
main window is shown. A second instance forwards it to the running window.

Incoming links first open **Review shared DayZ server**. Where a directory
reference is present, a cancellable worker checks it through WolfAPI at the
supplied game address. A matching row may update the query port and provide a
display name; it cannot change the game address. If the reference is missing,
unavailable, mismatched or moved, the review explicitly offers the supplied
address as a fallback without attaching an unverified ID.

Pressing **Inspect server**/**Inspect supplied address** selects an in-memory
target and starts the normal edition/mod inspection. It does not connect, start
Steam or subscribe/download merely because a link arrived. The user reviews the
results in Mods and then uses Connect, with the existing installation, identity,
Steam and Workshop confirmations. Links cannot replace an active connection,
monitored game, Workshop operation or another link review. Reopen the link after
that operation finishes. No new favourite is created by receiving a link.

## Version-one contract

```text
https://wolflauncher.co.uk/join/?v=1&host=203.0.113.10&game_port=2302&query_port=27016
wolflauncher://join?v=1&host=203.0.113.10&game_port=2302&query_port=27016
```

Required fields are `v=1`, an IPv4 address or ASCII DNS hostname, and decimal
`game_port`/`query_port` values from 1 to 65535. Optional `server_id` is a bounded
directory reference; optional `product` is `stable`, `experimental` or `unknown`.
The edition hint is never live launch authority. A supported full game ID still
has to be verified by the normal live query before selecting an installation.

The canonical HTTPS origin is exactly `https://wolflauncher.co.uk`, and its route
is `/join/` (also accepting `/join`). The protocol authority is exactly `join`,
with an empty or `/` path. The previous exact `https://wolf-forge.co.uk/join/` origin
is accepted for already-shared links; newly copied links use wolflauncher.co.uk.
Both parsers accept the optional slash that GIO can
insert when serialising a URI. IPv6 and raw Unicode hostnames are outside this
initial transport contract; ASCII IDNA names can use the normal DNS form.

Repeated/missing/unknown fields, credentials in the authority, fragments,
malformed escapes, control characters, invalid ports, unsupported versions and
oversized input are rejected. No password, player name, mod list, executable,
file path or arbitrary launch argument is accepted in a link. Browser and Python
parsers share byte-identical regression vectors in their respective repos.

A directory reference is bound to the supplied endpoint, not a global relocation
lookup. The current resolve API is endpoint-based. If an address has moved or
been reassigned, users see an unconfirmed-reference warning and must review the
explicit fallback. A link's game endpoint is additionally locked in the live
identity flow: an advertised conflicting game port is rejected before install
or Workshop work, and that lock survives launch-context serialisation.

## Desktop integration and handoff

- Windows Setup offers an **unchecked**, per-user server-link task. Selecting it
  registers `HKCU\Software\Classes\wolflauncher` with the executable and `%1`
  separately quoted, passing only `--open-url`. Uninstall or deselection removes
  the registration only if its command still belongs to that installation.
  The Windows installer smoke script now checks opt-in registration, owned-key
  cleanup and preservation of a replacement handler. It skips those registry
  tests when a pre-existing user registration would be disturbed.
- Linux desktop entries advertise `x-scheme-handler/wolflauncher` and `Exec` with
  `%u`. User, Debian and RPM installers refresh the desktop capability cache
  when the utility is available; they do not force an `xdg-mime` default. An
  installed wrapper must be on the desktop session's PATH, as for normal desktop
  launching. A standalone portable/AppImage build can always use Settings paste;
  OS opening requires desktop integration or explicit user configuration.
- The single-instance socket is restricted to the current user. It accepts the
  legacy activation message and one framed JSON `open_url` request per connection,
  with a 4 KiB frame, 2 KiB URL, 16-client and one-second incomplete-frame limit.
  At most four pre-handler startup URLs are retained. Invalid JSON, duplicate
  IPC keys, extra data and unsupported actions are rejected.
- Link delivery is acknowledged. A sender that contacts an old or unresponsive
  running launcher displays a retry/restart message instead of silently assuming
  that activation delivered the link. Plain activation remains compatible.
  Secondary cleanup cannot unlink the primary's socket. URL delivery is queued
  after socket cleanup, so a modal review does not keep the transport open.
- CLI arguments are parsed before Qt receives them. Only normal help/version
  options and one positional URL or `--open-url URL` are accepted. This also makes
  installer `--help`/`--version` checks exit without launching the GUI.

## Validation on 3 November 2026

Full Linux launcher suite: **938 run / 931 passed / 7 skipped**. Twenty-two added
tests cover the shared URI vectors, metadata/edition boundaries, fallback, review
and cancellation, cold/secondary startup, fragmented/invalid/oversized IPC,
acknowledged real-process delivery, old receivers, strict game-port binding and
GIO desktop URI dispatch. GIO used an isolated stub executable, not the installed
launcher or a real game. Existing installer regressions also pass.

The website's four existing release-manifest tests and 41 new JavaScript
contract/page tests pass. Local headless Chrome checks verified valid/invalid
browser DOM state and desktop/narrow-screen layouts. The Opera connector was
unavailable; an isolated temporary Chrome profile was used. The web page was
served only on loopback for verification.

Ruff 0.15.22 lint/formatting, Python compilation, shell syntax, desktop-file
validation, shared-vector parity and whitespace checks pass. Native Windows
Setup/registry execution, packaged Windows/Linux URI opening, browser-to-handler
permission prompts, real Steam/game joins and the deployed HTTPS route still
need release-time verification. The extended Windows smoke script has not been
executed on this Linux host. No package build, version bump, website deployment,
live desktop registration or game/Workshop action was performed for this work.

## Domain migration — 14 November 2026

Newly generated HTTPS links and the launcher's About/Update website destinations
use wolflauncher.co.uk. The old exact Wolf Forge HTTPS origin remains accepted
for input compatibility. The protocol link and all endpoint, field, edition,
confirmation and IPC rules remain unchanged.

The standalone website includes the join page in its static build and Docker
image, serves both /join and /join/, and serves JavaScript modules with the
correct MIME type. It keeps the existing release feed and download controls.
The page uses the current Servers-tab manual-opening instruction and excludes
shared addresses from search indexing. The parser fixtures are byte-identical
between launcher and website. No query data is inserted as HTML or sent to a
server lookup by the page.

## Compact sharing and directory names — 14 November 2026

Newly copied links use a compact, self-contained HTTPS format, for example
`https://wolflauncher.co.uk/s/Ecb0sW0I_gj_`. The example represents
198.244.177.109, game port 2302, query port 2303 and a Stable hint. Its data is
encoded directly; no saved mapping, new database or persistent volume is needed.
This format is not a signed identity and does not replace normal review.

Python and JavaScript decode the same versioned binary layout: a flags byte
(upper five bits 0x10, bit 2 indicates hostname, low two bits select unknown,
stable or experimental), four IPv4 bytes or a one-byte length plus ASCII
hostname, two big-endian 16-bit ports, then the optional ASCII directory ID.
Unpadded base64url encodes the payload. Strict field validation is reused and
noncanonical encodings, extra queries/fragments and unknown versions are rejected.
Hostnames and directory references are retained, even when these make a code
longer than the IPv4 example. Long HTTPS/protocol links remain supported.

The webpage looks up only the existing fixed WolfAPI HTTPS resolve endpoint.
A name is shown only for one row matching the host, both ports, and directory
ID when supplied. Missing, stale/unmatched or failed lookups do not disable the
address or launcher-opening button. Names are rendered as plain text and marked
as directory information that may have changed. No direct game-server probes,
arbitrary fetch targets or automatic protocol navigation are added. Sharing a
link in the desktop app remains local and requires no network request.

The website name service limits response bytes, concurrent requests, cache
entries, cache lifetime and request duration. Its share field copies the compact
HTTPS URL; its opening button uses the existing full wolflauncher protocol URL.
New desktop builds accept short links from paste/CLI/IPC; older builds can use
the website opening button to receive a supported full protocol link.
