# WolfLauncher visual design direction

## Goal

WolfLauncher should feel like a calm, capable desktop application rather than
a terminal-oriented utility. It remains Linux-first, but the visual system and
interaction model must translate cleanly to a later Windows version without
teaching users a different workflow on each platform.

The HTML files under `Theme ideas/` are visual references, not an
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
6. Treat card-like curated server rows or grouped Settings health sections as
   separate structural changes requiring another desktop review.
7. Perform Windows font, scaling, standard-dialog and interaction testing when
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
