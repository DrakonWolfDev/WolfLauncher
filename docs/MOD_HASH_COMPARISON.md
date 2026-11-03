# Advisory server mod-hash comparisons

Implemented for development on 3 November 2026. No version bump, package build or
release publication was performed for this change.

Selected-server checks in the Mods inspector now compare the server's advertised
hash with the selected installation's PBO trailers. The existing `ModWorker` performs file work
off the GUI thread. The Mods table, inspector and copied report distinguish a
match, a difference and unavailable evidence **at the last check**. The summary
counts each outcome. Browser readiness previews, launch preflight and LAN-query
workers skip these optional reads so joining does not wait for them.

These results are advisory. They do not change readiness, subscribe to anything,
request a download or assert that the server or local copy is newer. Matching
32-bit trailer aggregates do not prove full file integrity or authenticity.

## Aggregation format and evidence

The implementation uses the format documented by
[Flare's pinned mod-hash implementation](https://github.com/CallMeLewis/flare-launcher/blob/89954428a15745fe10d5f3dc351ac6fdedd20f8c/src-tauri/src/mod_hash.rs).
WolfLauncher's Python implementation was checked against actual server replies
and installed local files, independently of Flare's test runner:

1. Read the final 20-byte SHA-1 trailer from each top-level `.pbo` in the mod's
   `addons`, `dta` and `bin` directories, accepting different letter case. Require
   the preceding zero marker and a complete trailer. Do not read the PBO body.
2. Sort the trailers bytewise, retaining duplicates. Concatenate their lowercase
   hexadecimal representations, then calculate that ASCII string's SHA-1.
3. Apply RSHash to the byte `40` followed by that SHA-1's lowercase hexadecimal
   ASCII representation: initial hash zero, initial multiplier 378551,
   multiplier factor 63689, wrapping both accumulators to unsigned 32 bits.

Read-only A2S_RULES queries to the saved New Dawn Cherno server
(`198.244.177.109:2303`) and DeerIsle server (`198.244.177.109:2503`) supplied
**53 and 56 installed requirements respectively**. Every independently computed
local aggregate matched the corresponding advertised hash. The final comparison
module also matched all 109 observations. Two servers sharing a mod can repeat an
observation; this is not a claim about 109 distinct mods or all DayZ builds.

The regression fixture
[`mod_hash_capture_2026-11-03.json`](../tests/fixtures/mod_hash_capture_2026-11-03.json)
retains one complete binary rules response and the local SHA-1 trailers of three
matching requirements (one, two and three PBOs). It contains no PBO bodies or
personal filesystem paths. Tests decode the response with the strict protocol
parser before comparing the local trailers; expected hashes come from the server,
not the calculation under test. The fixture includes its capture timestamp.

## Bounds, isolation and invalidation

- Each worker shares a three-second cooperative comparison budget across its
  requirements. Each mod is limited to 8,192 directory entries and 2,048 PBOs.
  Cancellation and deadline checks occur during enumeration, reads, duplicate
  searches and final validation. An operating-system file read itself cannot be
  interrupted by the cooperative timer.
- A nonmatching aggregate is also checked for possible duplicated PBOs on a
  Linux server, up to 12 local PBOs (4,095 nonempty duplication combinations).
  A match through this allowance is explained in the details. Above that cap,
  a nonmatch remains unavailable rather than an unqualified version mismatch.
  The duplicate allowance has synthetic regression coverage; it was not observed
  on the two live servers in this session.
- Missing hashes, empty data directories, incomplete or unsupported trailers,
  unreadable files, linked data directories/PBOs, limits and changing files yield
  unavailable evidence. Missing/unpublished requirements and mods awaiting a
  Steam update are not compared.
- Stable uses the selected Workshop library. Experimental uses the same resolved
  official-launcher `!Workshop` paths as native Experimental launch. No other
  library is searched to find a matching copy. Failure to resolve those paths
  leaves the advisory unavailable and does not fail the underlying mod check.
- Results belong to the existing server/library/edition/request context. No
  cross-request or persistent hash cache is used. Every new selected-server
  check rereads the trailers. File and directory identity, size, modification
  and change timestamps are checked again before accepting a result, including
  the original selected mod path. Concurrent updates invalidate it.
- A subsequent Steam state snapshot clears an earlier advisory. The UI explicitly
  presents a last-check snapshot and asks for a recheck after file changes; there
  is no continuous file watcher and no claim that a displayed snapshot remains
  current after an external edit.

## Validation limits

Automated coverage includes the live capture, ordering/duplicates, data-directory
and extension case, ignored nested/signature files, missing/zero hashes, malformed
or unreadable files, concurrent edits/additions, cancellation/work limits, linked
files, library isolation, Experimental path selection, worker integration, stale
Steam state invalidation, visible unknown results and unchanged download/readiness
policy. Linux live reads verified the exact aggregation against two servers.

Interactive rendering, packaged Windows/Linux behaviour and native Windows
filesystem/junction handling still need manual verification. A simulated matching
Experimental path is not a real Experimental game/server validation. The existing
0.9.3.5b local packages predate this feature.

Final automated validation: **896 tests run, 889 passed, 7 skipped**, including
24 hash/worker/coordinator regression tests. Ruff 0.15.22 lint and the CI formatting
gate pass, as do compilation and whitespace checks.
