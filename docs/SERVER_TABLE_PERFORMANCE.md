# Server table responsiveness

Measured on 3 November 2026 on the local Windows development machine, using
Python 3.15.1, PySide6/Qt 6.11.1 and Qt's offscreen platform. Synthetic servers;
no network requests, Steam operations or game launch. Each timing is the median
of five repetitions with the application theme, fonts and a 1200 x 600 table.
Deferred widget deletion is drained between samples.

The baseline loads `wolflauncher/server_browser_table.py` from local Git `HEAD`
(`1b314377ac9cb038bed4545b24722a83bfff18f4`);
the comparison loads the working tree implementation. Sort order is server name
ascending. Enrichment changes player counts and ping for 50 servers. Mod previews
replace 50 Mods cells. Times include Qt event processing.

| Rows | Populate before / after (ms) | 50 enrichments before / after (ms) | 50 mod previews before / after (ms) |
| --- | --- | --- | --- |
| 200 | 95.56 / 31.24 | 64.21 / 18.19 | 35.67 / 4.04 |
| 500 | 263.12 / 70.71 | 109.25 / 18.17 | 80.07 / 4.26 |
| 1,000 | 597.12 / 144.14 | 206.13 / 21.26 | 166.39 / 4.36 |

At 1,000 rows, table descendant widgets fell from 2,018 to 18. This is a widget
count, not a process-memory measurement. The table still owns 18 items per row.

The focused change removes the widget/layout/label created for each favourite
star, reuses the identity/font calculation within a row, and lets Qt reposition
an individual enriched row instead of re-sorting the entire table for every
status or mod-preview result. The active sort cell is replaced last so a moving
row retains all its cells. Favourite state is retained explicitly during updates.

Reproduce from the repository root with an environment containing the app's
dependencies:

```sh
python scripts/benchmark-server-table.py --revision HEAD
python scripts/benchmark-server-table.py
```

After committing the change, replace `HEAD` with the pre-change revision when
repeating the baseline. This measures GUI work, not server query latency, API
throughput or full-window startup. Linux, packaged builds, process memory and
interactive scrolling latency have not been benchmarked. A full model/view
migration and background polling changes remain separate candidates.

Validation covers every column in ascending/descending sorting, row consistency,
selection, scroll position, keyboard navigation, star clicks, favourites, mod
previews and existing table/presenter behaviour. All 79 targeted tests pass. A
themed render was visually inspected for the stars, lock and game-time icons.

## Linux follow-up — 4 November 2026

The existing optimisation was remeasured on Linux with queue labels. At 1,000
rows, population was 436.71 / 129.58 ms and 50 enrichments 237.27 / 16.84 ms
(baseline / current). Separate-process RSS samples measured about 84.7 / 20.8 MiB
above the pre-population process size. The benchmark now supports `--rows` and
reports Linux RSS; use separate processes for memory comparisons. See
[complete method, measurements and limits](DEVELOPMENT_FOLLOWUP_2026-11-04.md).
