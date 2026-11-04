# Linux resource and live Steam checks

Run the source resource soak using the project's Python environment:

```sh
.venv/bin/python scripts/soak-launcher.py --cycles 300
```

The Linux runner requires bubblewrap with working PID/network namespaces. It
creates private temporary XDG directories and `/tmp`, mounts the host filesystem
read-only, disables public networking and runs offscreen. It keeps `result.json`,
stdout and stderr in the printed temporary output directory. Direct child mode
rejects ordinary user-data paths before application initialization.

Each cycle alternates Stable/Experimental, rapidly replaces three browser queries,
waits for the latest snapshot, checks edition isolation, refreshes 200 mod rows,
checks item/selection reuse, changes tabs and churns two unique 512×512 cached
previews. The initial fixture contains 1,000 Stable and 10 Experimental servers.
Real browser snapshot workers and cancellation run; Steam download and mod-check
workers are not exercised by this synthetic scenario.

Every ten cycles records Linux resident memory (RSS), process threads, open file
descriptors, descendant Qt objects, thumbnail bytes/entries and browser auxiliary
cache entries. Samples from cycle 50 onward are compared. The run fails if final
RSS exceeds that baseline by 32 MiB, or a later sampled thread/file-descriptor/Qt
object count exceeds baseline by 2/2/10. Thumbnail bounds and idle pending-request
cleanup are asserted during the run. These are bounded diagnostic thresholds,
not a guarantee of leak freedom. The default is 300 cycles; accepted counts are
100–1,000, with a 150-second internal and 180-second parent deadline. Slower or
larger runs can correctly time out. Fixture setup and synchronous updates count
in the maximum event-loop gap, so it is not a frame-rate measurement.

For a separately authorized live check, open native Steam, sign in with a DayZ
account, and run:

```sh
.venv/bin/python scripts/check-live-workshop.py
```

This uses the production installation detector and disposable Workshop state
helper. It queries at most 20 existing local Workshop item IDs, three times by
default, with a 15-second state timeout per helper. It never calls subscription,
unsubscription or download methods. Output includes only aggregate states,
counts, elapsed times and remaining multiprocessing children; no account IDs,
Workshop item IDs or library paths are recorded. `--items` accepts 1–20 and
`--repeats` 1–5. Success requires all requested states and helper cleanup; a
returned non-ready state is reported without making the diagnostic fail.

Read-only queries cannot prevent Steam's own pre-existing automatic update
activity. These checks do not establish real download completion/cancellation,
game joins, multi-hour stability, frozen-package resource behaviour, Windows
compatibility or native desktop accessibility. Keep those evidence boundaries
separate from synthetic source and read-only Steam results.
