# Separate live server queue counts

Implemented on the development branch; no release or package publication implied.

WolfLauncher reads the separate DayZ queue count exposed by the pinned GameDig
5.3.3 DayZ protocol (`packaging/npm/node_modules/gamedig/protocols/dayz.js`,
`processQueryInfo`). That upstream parser derives `raw.queue` from the `lqs`
keyword in A2S_INFO tags. WolfLauncher validates the entire original token because
GameDig's `parseInt` also accepts malformed numeric suffixes. A single ASCII
unsigned integer from 0 through 65535 is accepted. Duplicate or malformed `lqs`
tags are unknown; an integer `raw.queue` is also supported when no queue tag is
present. Player count and capacity are never used to infer queue size.

The Server Browser player column and selected-server summary show, for example,
`60 / 60 +12`. Favourites use the same measurement in compact form: `60/60+12`.
With no fresh positive queue, the browser shows `2 / 60` and Favourites show `2/60`.
Automatic browser live checks, selected-server checks and favourite refreshes
use the existing bounded query workers; no additional queue-specific requests
are sent. Sorting by players still uses the numeric player count.

- `2 / 60` shows the current players and capacity, with spaces around `/`.
- `20 / 20 +2` adds the queue only when a fresh observation shows people waiting.
- Empty, unknown and expired queues add no suffix. Their distinct states remain
  in the stored measurement and tooltip; absence of a suffix does not certify
  a measured empty queue. No `+0` or `+?` appears in the player count.
- Failed live checks and successful responses without a queue clear earlier
  observations. Counts expire after two minutes, with missing/invalid/future
  timestamps also treated as expired. A ten-second display timer removes expired
  suffixes even when network polling is disabled; it stops during shutdown.

Background replies update values in place. Table headers sort once when clicked,
without enabling Qt's continuous reordering. Full snapshots of the same search
retain the visible order of surviving matches, append new matches and restore
selection/scroll. Changing search, filters, edition, limit or the sort controls
starts a fresh ordered view. Matches leaving a filtered/limited result can still
be removed; stale rows are not retained as if they continued to match.

Browser cache schema 10 adds a nullable count and its own query timestamp;
existing rows migrate to unknown. The favourite status cache also preserves the
nullable count with its existing query timestamp. A directory/provider refresh
cannot refresh a local queue timestamp or transfer its count to a changed
endpoint. Browser cache expiry is independent of provider freshness.

## Evidence and remaining checks

`tests/fixtures/dayz_queue_live.json` contains minimal captured fields from two
read-only public live queries on 3 November 2026: New Dawn Cherno
`198.244.177.109:2303` (6/30 players) and Deerisle `198.244.177.109:2503` (1/20).
Both returned `lqs0` and `raw.queue: 0`. The fixture excludes player lists.
A positive queue of 12 is covered by a synthetic full-server response; a real
nonzero queue has not yet been captured.

Eight new tests cover strict decoding, captured live responses through status
parsing and enrichment, unknown versus zero versus expiry, loss of evidence,
old/invalid favourite caches, schema migration, provider refresh/endpoint changes,
and incremental Qt updates with selection and numeric sort data preserved.
Existing presentation, startup and shutdown tests cover the new labels/timer.
Offscreen Qt previews checked positive, zero, unknown and stale rows/cards at
1100px width. Native packaged Windows/Linux UI and a real positive queue remain
release-time checks. No game launch, Workshop action, OS registration or release
publication was needed for this feature.
