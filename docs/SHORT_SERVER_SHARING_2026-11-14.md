# Short sharing and directory names — 14 November 2026

The requested features are implemented, pushed and live.

## User behaviour

Servers and Server Browser context menus now say **Share server link…**.
Sharing copies a compact HTTPS review URL. The website shows a matching name
from the WolfAPI directory when available and copies the same short share URL.
Its opening button still sends the full existing protocol URL to the launcher.

Maintainer's example:
**https://wolflauncher.co.uk/s/Ecb0sW0I_gj_**

Decoded endpoint: 198.244.177.109, game port 2302, query port 2303, Stable hint.
Observed name: **New Dawn Cherno PVE|Discord|Missions|DayzDog|Treasure|Trader|Ex**.

Short codes encode versioned endpoint data directly. No code/address database,
network request to create a share link, persistent volume or expiring mapping
is required. Hostnames, both ports, directory IDs and edition hints survive
round trips. Encoded data remains untrusted: normal address review, edition/mod
checks and Connect/Workshop confirmations still apply. Long HTTPS and protocol
links remain accepted. Earlier link-capable installers can use the webpage's
full protocol opening action even if they cannot paste compact URLs directly.

## Website name lookup and production routing

The website queries only the existing fixed public WolfAPI HTTPS resolve
endpoint. It matches exactly one row by host, both ports, and the optional
directory reference. Directory names are advisory plain text, not live launch
authority. Missing, ambiguous or failed metadata cannot disable the endpoint or
opening action. Background requests, timeout, response size, cache lifetime and
entry count are bounded. No game-server query or automatic launch/download occurs.

Initial workstation/Docker name checks passed, but production public-API requests
timed out. With the maintainer's open Coolify session, read-only checks confirmed
correct public DNS and successful external GitHub TCP/443, while the API public
IP timed out. The website's existing incoming proxy connection identified its
working LAN TLS proxy. A direct request preserving API Host/SNI and normal
certificate validation returned HTTP 200 and the expected name.

The fix is a hostname entry scoped to this website's Coolify Docker options,
pointing the API hostname to the already-used TLS proxy. The public URL/HTTPS
port and certificate checks remain unchanged. This avoids the documented
NAT-loopback/hairpin path. Actual deployment details are recorded in the private
website README. There was no global DNS, router/firewall, shared proxy, WolfAPI
code/deployment or TLS-trust change. The unrelated Docker-gateway certificate was
rejected, not trusted. No secrets/environment values were read or printed.

The API repo's AGENTS, freshness contract, source resolve implementation,
WORKLOG and SSH/security runbooks were inspected. The endpoint/schema already
supports the required lookup; no API source change was needed. Its Linux SSH
alias was unavailable; the user-provided Coolify session supplied the scoped
website/host diagnostics. Every diagnostic finished; no remote monitor remains.

## Verification

- Launcher source **1cb10dd3c83b33f8be6d2bdfe76a9ca442a70bfc**:
  **1,038 tests, OK / 7 skipped**, required Ruff format/lint, core mypy,
  compilation and whitespace checks pass.
- Website feature commit **60cd0ba**; safe diagnostics **22b7a0a**; routing
  documentation **77c7e03**. Website suite: **83 tests passed**.
- Byte-identical Python/JavaScript URL vectors cover compact and long formats,
  malformed codes, authority/path/query attacks and boundary lengths.
- Name tests cover endpoint/ID mismatches, ambiguous data, malformed/oversized
  replies, outage fallback, cache expiry, overlap deduplication and concurrency.
- Docker build and production-container short-route/name-query checks passed.
- Desktop/mobile and invalid-link Chrome checks passed; screenshots inspected.
- After the scoped routing redeploy, live metadata returned the expected name
  and live isolated Chrome verified its name, endpoint/protocol link and share UI.
- [Recorded public test endpoint/name and limits](evidence/2026-11-14-short-share-live.json).
- Real browser permission prompts, installed desktop handoff and Steam/DayZ
  joining were not exercised by the automated checks.

## Matching private Mint installer

[Latest Mint test installer](../dist/wolflauncher_0.9.3.5b_mint22-share-test-20261114_amd64.deb)

Built from clean launcher commit **1cb10dd** with the new sharing wording and
compact link generation/acceptance. Version stays **0.9.3.5b**.

SHA256:
`88a651c6a96546b16d1422774dffea00ee5d757b235cd7a078130ef90b29605f`

Adjacent checksum and provenance sidecars are retained. Artifact checksum,
independent complete extracted payload/control inventory, expected-commit and
require-clean provenance pass. Extracted package UI confirms the name controls
and short-link generation/decoding; normal packaged startup/shutdown exits 0
with isolated settings/runtime. Existing installers and Windows artifacts are
preserved. Python 3.12 and libegl1 are required.

Both source repositories remain on their intended branches: launcher development,
website main. No launcher main merge, version bump, tag, public desktop binary
upload/download-manifest change or WolfAPI deployment occurred.
