# WolfLauncher visual design direction

## Goal

WolfLauncher should feel like a calm, capable desktop application rather than
a terminal-oriented utility. It remains Linux-first, but the visual system and
interaction model must translate cleanly to a later Windows version without
teaching users a different workflow on each platform.

Historical HTML mockups were visual references, not an
implementation specification. Their warm charcoal surfaces, restrained amber
accent, muted technical detail and clear status treatment are the intended
direction. WolfLauncher should reproduce that visual language with native
PySide6 widgets and Qt Style Sheets (QSS), rather than embedding a web view or
copying browser-specific details exactly.

## Interaction principles

- Keep controls familiar, labelled and predictably placed on Linux and
  Windows. Important actions retain text labels; icons reinforce meaning but
  do not replace it.
- Preserve the established tab rhythm: current state or summary, common
  controls, results, primary next action, then advanced and support tools.
- Keep frequent actions visible and advanced functions available through
  compact, clearly labelled disclosures.
- Use colour, icons and text together for status. Colour alone must never be
  the only indication of online, warning, error or readiness state.
- Maintain visible keyboard focus, logical tab order, usable click targets and
  sufficient contrast.
- Keep information selectable and copyable. Addresses, ports, commands,
  Workshop IDs, paths and diagnostics remain real Qt text/table content.
- Avoid hover-only information, unexplained icon-only controls, frameless
  windows, excessive animation and heavily customised interaction patterns.

## Visual language

- Use a restrained **Wolf at the treeline** atmosphere around the workspace
  perimeter: a near-black, desaturated foggy conifer line concentrated in
  otherwise unused lower space, fading to charcoal behind functional content.
  The atmosphere supplies identity and depth, never information or spectacle.
- Keep controls, cards and data surfaces opaque enough for dependable contrast.
  Background art must disappear naturally as a page fills with results and
  must never sit at readable contrast directly behind dense text.
- Use fine warm-grey framing with a restrained amber lower-edge detail to tie
  the application shell to the action colour without creating a gamer-style
  glow. Wolf branding is a small geometric, front-facing mark with amber eyes,
  used for the application icon and a secondary tab-bar lockup rather than a
  large header or illustrated mascot.
- Avoid characters, weapons, zombies, military imagery, copied DayZ key art,
  distressed-metal framing, bright red chrome and prominent photographic
  scenery. WolfLauncher should remain calm, technical and recognisably its own.
- Keep icon use deliberately sparse: one muted geometric icon per primary tab,
  plus only unambiguous repeated actions such as Add, Refresh, Launch and
  Recheck. Text labels remain authoritative; tables, filters, statuses and
  ordinary secondary actions do not receive decorative icons.
- Use warm charcoal surfaces rather than pure black or generic platform grey,
  with two or three surface levels providing hierarchy.
- Reserve amber/rust for the active tab, focus, favourites and the principal
  action in the current context. Normally only one action per tab or task
  context should receive the filled primary treatment.
- Use green, amber and red consistently for positive, advisory and failed or
  offline states, always paired with a word or recognisable symbol.
- Use bright text for names and actions, and quieter text for addresses,
  timestamps, versions and supporting detail.
- Use modest corner radii, fine borders and consistent spacing. Avoid making
  native desktop screens look like collections of oversized web cards.
- Use the normal interface font for most content. Reserve a portable
  monospace font for paths, commands, addresses, ports and identifiers.
- Keep Server Browser data-dense. Consider more compact summary rows for the
  curated Servers tab only if a later desktop review shows they improve
  scanning without hiding operational detail.

The reference palette is a starting point rather than a fixed contract:

| Role | Reference |
| --- | --- |
| Main background | `#15130f` |
| Raised surface | `#1c1912` |
| Input/alternate surface | `#201c15` |
| Border | `#322c20` |
| Primary text | `#efe9db` |
| Secondary text | `#8a8477` |
| Accent | `#e8a33d` |
| Positive | `#6fcf97` |
| Negative | `#e07a7a` |

Final values must be checked on real displays for contrast and should be kept
as central theme tokens rather than repeated throughout widget code.

## Cross-platform requirements

- Prefer shared QSS and standard Qt widgets, with small platform adjustments
  only where native behaviour genuinely differs.
- Do not rely on one platform's system palette, font metrics or glyph
  availability. Layouts must tolerate common Linux fonts and Windows Segoe UI.
- Avoid fixed text widths. Labels, controls and rows must tolerate different
  font metrics, scaling and longer text.
- Validate at 100%, 125%, 150% and 200% display scaling before Windows support
  is considered ready.
- Use Qt standard dialogs and filesystem abstractions where appropriate, and
  present paths in the native platform form. Long paths may be visually elided
  but must remain available through selection, tooltip or copy actions.
- Keep platform-specific Steam, DayZ and launch detection behind presentation
  interfaces so the same UI states can describe either platform honestly.

## Implementation sequence

The visual pass should preserve the approved hierarchy and behaviour:

1. Add a central theme module containing colour and spacing tokens plus the
   application-level QSS.
2. Theme existing tabs, inputs, buttons, tables, headers, selections,
   disclosures and scrollbars without restructuring the screens.
3. Give actions explicit primary, secondary and destructive roles and align
   status/ping colours with the shared tokens.
4. Review the result on a real Linux desktop, including keyboard use, focus,
   contrast, collapsed/expanded states and the existing 1350x720 baseline.
5. Revisit table density, fonts, icons and branding after the foundation is
   stable.
6. Curated server card rows were approved and implemented as the sole visible
   Favourite Servers layout. Treat grouped Settings health sections as another
   change requiring desktop review.
7. Add the low-contrast perimeter atmosphere as a reviewable visual layer,
   preserving the ability to adjust or remove it independently of content.
8. Perform Windows font, scaling, standard-dialog and interaction testing when
   the Windows implementation phase begins.

QSS cannot provide content-dependent cell colours, reliable per-row side
borders, responsive browser-style wrapping or fully rounded table rows by
itself. Use presenters, item data, delegates or small native icons where those
details materially improve clarity; do not add custom painting merely to copy
the HTML references one-for-one.

## Timing

There is no technical prerequisite for establishing the shared theme. The
lowest-risk point for implementation is after current functional hardening has
settled enough that controls and data are no longer moving frequently. A
behaviour-preserving theme foundation can then precede any larger Servers or
Settings restructuring.

## Current implementation status

The shared palette, QSS, typography, action roles, application/window mark,
tab-bar lockup, restrained SVG tab/action icons and low-contrast perimeter
atmosphere are implemented. Favourite Servers uses the approved native card
layout. The completed review established that Server Browser gates its
direct actions to a real selection without repeating the selected row, and
Mods separates server identity, readiness guidance and technical detail while
preserving the server through inspection, Workshop resolution and a persistent
Launch action. Discovered-server inspections pair that forward action with a
contextual left-arrow return to the Browser results. A real-desktop keyboard,
density and handoff review remains before this flow pass is considered settled.

Server Browser uses directory freshness as the calm scanning state: Live,
Recent, Stale, Offline or Unverified. Provider provenance belongs in tooltips
and contextual detail rather than being repeated as table jargon. Holding a
selection briefly may show Checking and perform one bounded local query; its
Online/Offline result, ping and other live fields then take precedence for a
short cache window. Bulk visible-row checking is an advanced diagnostic action,
not part of ordinary browsing.
Opening the Browser renders cached rows only and must not replace them
automatically. A selected-server check updates that row in place; it must not
rebuild or visibly bounce the surrounding result list.
After a selected server is locally confirmed, its Mods cell may quietly move
from directory metadata to a short local readiness state: Checking, Ready,
`N missing` or Unavailable. This is preview feedback, not launch authority and
never initiates a Workshop change. Keep **View mod details** secondary; the
primary action names the selected server and deliberately enters pre-flight.
This hierarchy passed desktop design review and is final for now.
Keep both **Mods** and **Game Style** in the common scanning controls. Use the
order Search, Mods, Game Style, Map and bound Search so it does not crowd out
the categorical dropdowns. Keep the group contiguous by making Search the
elastic control; do not distribute surplus space as gaps or force the entire
group into a fixed left-aligned block.
Selected-server checks may
use a small bounded runner pool to keep comparison responsive, but must retain
per-endpoint deduplication/cooldowns and must never become automatic visible-row
probing.
Do not pair tab opening with a provider refresh or automatic first-page local
probe sweep. Cached/API freshness is sufficient until the user explicitly
refreshes or expresses interest through selection. Preview setup must reuse background/cached platform
context and preserve the table viewport; filesystem detection or row resorting
must not visibly freeze or disorient browsing.
Common dropdowns should self-label where their neutral choice is unambiguous;
use **Any game style** rather than spending horizontal space on a separate Game
Style label. Advanced bulk checks may update compact progress copy, but must not
commit rows or rebuild/sort the results table repeatedly while running.
Provider downloads and large cache merges are both background work. Keep the
previous cached result surface interactive until the merge transaction commits,
then refresh the visible page once without clearing it during the operation.
For WolfAPI, "background" means process isolation: Python threads still share
the GUI interpreter lock. HTTP paging, JSON normalization and cache merging must
remain outside the Qt process, with only the final compact summary handed back.

## Server Browser styling handoff

This pass is implemented for desktop review; it did not reopen completed
Favourite Servers, Mods or Settings layouts. It preserves the Browser behaviour
established in commit `07c0263`: cached-first opening, explicit provider
refresh, bounded selection checks, transient local mod readiness, stable
selection/scroll and named Launch pre-flight.

### Locked interaction hierarchy

1. Summary and cache/result count.
2. One fluid common-filter row: elastic Search, then Mods, Game Style, Map and
   Online only. Dropdowns self-label through their neutral choices.
3. Dense sortable results remain the primary scanning surface.
4. Bottom row: advanced disclosure left; Add to Favourite Servers, secondary
   **View mod details**, and primary **Launch [selected server]** right.
5. Opening the tab must never refresh or locally probe automatically. Selection
   may refine only deliberately selected endpoints and must not bounce the list.

### Implemented master/detail direction

Use a restrained horizontal table/inspector split related to the completed Mods
workspace, without copying its Workshop-card contents or turning each server
into a Favourite-style card.

- Left: keep the operational table compact. Common columns are Server Name,
  Status, Map, Game Time, Players, Region, Ping, Features and Mods.
  Region now displays the trusted API country code with an unknown fallback;
  its tooltip retains provider provenance. The table has a dedicated native
  surface treatment for its frame, header accent, selection and row rhythm.
  Server Name flexes into unused scan width and yields to dynamic Mods readiness
  text without horizontal overflow. Inspector connectivity remains independent
  from a conditional actionable mod-status pill.
- Right: one calm selected-server inspector. It should show the full server
  name, endpoint, map/location/time, player and ping state, local/API truth
  basis, freshness/provenance, concise features and mod readiness.
- Move Host, ports, Source, Version, last checked/seen, quality-warning detail
  and other diagnostics out of the common table into the inspector or detailed
  columns. Do not remove them from copied details or advanced support paths.
- Give the inspector the established semantic left edge: green for locally
  Online/API Live, amber for Recent/Stale/Checking/Unverified, and red only for
  confidently Offline or a failed local readiness state. Amber table selection
  remains restrained and distinct from status colour.
- Before selection, show a quiet purposeful empty state such as “Select a
  server to inspect its details”; do not fill the panel with decorative art.
- Selection-driven progress belongs in the inspector and affected row only.
  Avoid modal progress, hover expansion and full-table relayout.
- Use a draggable gutter and responsive proportions derived from the Mods split,
  then validate independently at 1350×720 and 1920×1080. Do not assume the Mods
  inspector width or typography scale transfers unchanged.

### Data boundary

The inspector can be prototyped with existing fields, but final table balance
should wait for the planned data work:

- **Game Time** is locally measured live state returned by `gamedig` and retained
  through discovered-server enrichment and schema v7. Show 24-hour time with a
  broad sun/moon cue and effective day/night multiplier. Unknown remains
  explicit until locally checked.
- **Region** means nullable geographical `country_code` supplied with provenance
  by WolfAPI, not the existing Steam integer region. Never infer or display a
  country from that integer and do not silently guess from IP addresses.
- The Mods cell is a readiness preview: Checking, Ready, `N missing` or
  Unavailable. Launch pre-flight remains final authority and the only workflow
  that may offer Workshop subscription/update.

### Review boundary

The inspector and compact table passed real-desktop review with honest unknown
states, locally measured Game Time and trusted Region metadata. The split ratio,
column set, inspector density and high-resolution behavior are locked as the
current best fit; revisit only when later usage exposes a concrete issue.
Region may remain absent until the shared API field is implemented; its absence
must not block improving the existing selected-server panel.

The first review found the plain full-height text card insufficiently distinct.
The inspector now uses a restrained selected-server identity band: small
eyebrow and semantic status badge, stronger name, amber technical endpoint and
a compact Map/Players/Ping facts strip. Lower truth, feature, mod-readiness and
support sections remain quiet so the emphasis does not become decorative or
compete with the Launch action.

An original WolfLauncher-owned environmental atlas fills the inspector's
otherwise-unused lower space with map flavour: severe snow for Namalsk, misty
conifers for Chernarus, wet green lowlands for Enoch/Livonia and volcanic cold
for Sakhal. Unknown and community maps use a more heavily darkened neutral
treatment. This is ambient category artwork, not a server banner, map screenshot
or claim about the selected server; all operational meaning remains in
selectable text. The artwork expands only after the compact identity, facts,
truth, readiness and support content has taken the space it needs.
The initial square-panel atlas cropped into close terrain when fitted to the
narrow tall inspector. Its v2 replacement uses four purpose-composed portrait
vistas in a horizontal source atlas so distant horizons and environmental depth
survive the actual panel proportions.
The rendered vista receives a native charcoal vignette: pronounced vertical
fades dissolve its top and bottom into the inspector surface, while a lighter
side falloff removes the hard rectangular edge without obscuring the map
flavour or competing with the semantic status border.

Mods deliberately remains table-first because required sets commonly contain
dozens of items. A draggable horizontal master/detail split pairs a focused
Status, Name, Workshop ID and Size table with one selection-driven Workshop
inspector. The inspector borrows the Favourite Servers card language without
converting every mod into a card. It may show optional public Workshop
description and thumbnail metadata, but the table remains stable while
scanning and the detail view works with mouse or keyboard selection rather
than relying on hover-only disclosure.
On taller desktop windows, the inspector scales its preview and local
typography from the 720p baseline within separate bounded limits. Typography
grows more gently than the preview; table text and the surrounding application
remain at the established density.
Mods avoids hover-only description and Steam-path disclosures; the selected
card owns visible Workshop detail and explicit support reports retain technical
context.

Real-desktop review approved this Mods master/detail direction as final at the
720p baseline and a taller high-resolution window. Preserve the four-column
table, draggable inspector, semantic selected-item edge, gutter and separately
bounded media/type scaling unless testing reveals a concrete interaction
problem.
The selected-mod inspector uses the shared semantic edge language—green ready,
red missing and amber update/pending—and a narrow gutter separates it from the
table while retaining a draggable split.

Settings uses a small number of operational health groups rather than a table
or one card per individual check. Launcher readiness, Steam and DayZ, and
Graphics and launch each aggregate their status while retaining concise,
selectable row detail. Exhaustive health rows belong in an explicit support
dialog and copied reports, preserving diagnostics without making them the
primary visual hierarchy.

Real-desktop review approved the Settings layout as final. Preserve the three
group hierarchy, shared row-label guide, bottom inset, persistent health/save
actions and explicit full-health support dialog unless a concrete usability
issue is later observed.

Real-desktop review also approved Favourite Servers as final. Preserve the
card-only layout, status edge, two-level metadata, player/ping block, favourite
control and row-level Connect action unless later usage reveals a concrete
problem.

Editor / Local Tools is an intentionally separate advanced workspace and does
not reopen the approved player-facing tabs. Keep its simple vertical rhythm:
summary, then a shallow primary **DayZ Editor** card with Workshop artwork at
left and its description/action at right. Follow it with a compact searchable
installed-extra-mod picker, then the **Local Development** card containing the
saved local profile form. Each card has one filled action at most; verification
and missing-Workshop actions remain secondary. It must state plainly that v1
joins an existing LAN/test server and does not host or expose a server. Its
initial layout requires a real-desktop review before it becomes a locked
hierarchy.

The settled cross-tab visual pattern is a dense operational surface paired
with calm contextual grouping, restrained amber selection, semantic status
edges and no decorative clutter. Carry that pattern into unfinished surfaces
such as Server Browser without mechanically converting completed tabs or
forcing every screen into the same widget structure.
