# Controlled source startup measurements

```sh
.venv/bin/python scripts/benchmark-startup.py
```

Requires Linux bubblewrap with working user/PID/network namespaces. The runner
creates temporary config/data/cache/runtime directories, private `/tmp` and no
public network access. Internal modes reject ordinary config/data paths before
application initialization. It seeds 1,000 synthetic Stable cached rows outside
the timed launches and records five fresh Python processes against that temporary
profile. `--repeats` accepts 3–10. The profile is reused between samples; no OS
page/disk caches are flushed. Read the printed output root for `result.json` and
per-sample logs. Internal/child/parent timeouts bound the run.

The harness uses the real application entry point, including single-instance
setup, retention, logging, theme, window construction, asynchronous snapshots and
coordinated shutdown. It opens the browser at its default 200-row display limit.
A synthetic session pause suppresses optional polling after construction. A Qt
event observer records the first browser paint after its 200 cached rows have
been applied; that means cached rows are visible, not verified safe to join.
There are no live server queries, mod readiness checks or Steam/game launches.

Reported import/first-paint/snapshot times start at the script timestamp after
standard-library imports; construction and snapshot-worker durations are separate
elapsed intervals. External process wall time additionally includes interpreter
startup and shutdown. Instrumentation is confined to the benchmark process:
subclasses/wrappers observe the existing window and worker without adding a
production profiling flag. No application source is modified while measuring.

4 November baseline versus the one-scan Editor/LAN construction refinement,
five-sample medians on this Linux source environment:

| Measurement | Baseline (ms) | Refined (ms) |
| --- | ---: | ---: |
| Imports | 224.78 | 230.56 |
| Window construction | 438.48 | 397.64 |
| First window paint | 738.16 | 693.21 |
| Cached snapshot applied | 778.80 | 731.05 |
| Browser painted with 200 rows | 807.77 | 758.33 |
| Process start through shutdown | 1,000.61 | 961.97 |

These observations support a modest local improvement (about 41 ms construction
and 49 ms to populated browser paint), not a universal percentage or packaged
cold-start claim. Raw normalized samples and source/benchmark identities are in
[baseline evidence](evidence/2026-11-04-startup-baseline.json) and
[refined evidence](evidence/2026-11-04-startup-optimized.json). Each metric has its
own median; rows are not one representative process trace.

Profiling identified three Editor/LAN picker refreshes during construction.
Profile loading/target selection now finish before one fresh library scan, and
its summary shares that scan only within the same redraw. Later refreshes and
selection changes still read the current library; launch checks remain separate.
