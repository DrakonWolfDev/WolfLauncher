# Changelog

- Replaced the native Mods-screen and launch-preflight DZSA lookup with a
  direct, background DayZ `A2S_RULES` query to the selected game server. Added
  a strict bounded manifest decoder that rejects incomplete, overflowed,
  duplicate or malformed responses atomically, while retaining Steam for
  Workshop metadata and installed-item truth on Windows and Linux.
- Accepted DayZ's bounded opaque post-signature rules extension after complete
  manifest parsing; this fixes Linux/server combinations that legitimately
  return binary extension bytes without weakening declared-record validation.

## Unreleased

- Established the Windows functional baseline: Windows 10, native Steam, an
  Intel Core i5-8250U and 8 GB RAM successfully completed the DayZ handoff.
  Windows remains experimental pending release-artifact gates.

- Added saved **Move up** and **Move down** controls for Favourite Servers.

- Added **Force Steam update** to the Mods row menu and beside the normal
  install/update action. It acts on the selected mod after confirmation,
  requests a high-priority Steam download check, keeps the subscription
  intact, and rechecks readiness when monitoring ends.

- Removed the remaining Flatpak Steam runtime probes, handoff branches and
  Steam API library candidates. WolfLauncher now only interacts with native
  Steam installations and an explicitly supplied `STEAM_ROOT` library.

- Enabled **Hide listing data warnings** by default and added a conservative
  Launcher safety net: three or more distinct endpoints carrying the same
  normalized provider name are marked as an advisory duplicate-name cluster.
  WolfAPI remains responsible for directory-wide classification.

- Established Ubuntu 24.04.4 LTS on an Intel Core i5-8250U with 8 GB RAM and
  Valve's native Steam download as the provisional minimum functional Linux
  baseline. The validated experience was slow, so this is not a recommended
  specification.
- Marked Flatpak and Snap Steam incompatible. Removed Flatpak from Linux Auto
  detection and Settings, migrated old packaged-Steam selections to Auto, and
  made stale Flatpak native-launch requests fail before handoff.
- Moved the NVIDIA PRIME Steam launch-option notice to a non-blocking **Known
  external issues** disclosure in Settings. WolfLauncher no longer inspects
  Linux PRIME environment values or presents them as launch-health warnings.
- Hardened the disposable discovered-server SQLite cache with a bounded busy
  timeout, WAL mode and transactional schema initialization.

- Tightened Browser-to-Mods context: opening **Mods** directly from **Server
  Browser** now follows the highlighted discovered server using the same
  read-only context as **View mod details**. Stale rows from a different server
  are cleared immediately while the selected server's check starts or queues.

- Renamed the Server Browser's ambiguous **Quality warning** label to
  **Listing data warning**, including its advanced hide control and detail
  headings. The warning continues to describe WolfAPI directory-data quality,
  not server safety, moderation or gameplay quality.

- Fixed a Linux crash race after **Refresh server list**. Manual provider
  refresh no longer starts GameDig while the WolfAPI helper is still updating
  SQLite, and a same-search completion queues one follow-up freshness batch
  without cancelling a running worker. Changed searches still cancel obsolete
  freshness work immediately.
- Clicking **Refresh server list** while a GameDig batch is already active now
  cancels that batch and defers the provider refresh until the worker has fully
  emitted `finished`. The transition is asynchronous, so the Qt interface
  remains responsive and SQLite never has both paths changing it concurrently.

- Aligned Windows and Linux readiness documentation with current validation
  evidence and added the approved cross-platform update-delivery strategy.
- Kept package build and smoke coverage on every CI run while restricting
  large artifact uploads to tags and manually dispatched release candidates.
- Split portable Windows and installer uploads so a validated ZIP remains
  available even when the separate installer lifecycle fails or stalls.

- Server Browser summaries now use WolfAPI v1's `coverage.eligible` for the
  whole directory total on both Windows and Linux, while explicitly labelling
  online and total rows that come only from the local cache. The last known API
  total is retained for offline startup.

- Opening the Server Browser now starts four non-blocking live freshness batches
  for up to 24 servers in visible order. Searches can cancel and supersede this
  initial batch, while cached rows remain immediately usable.
- Scrolling the Server Browser now starts up to four six-server freshness batches
  after movement settles, limited strictly to stale rows in the current viewport.

- Removed Region from the Server Browser table and inspector because its only
  trusted source was the now-disabled BattleMetrics ingestion. Stored country
  fields remain compatible with older caches but are no longer presented as
  current browsing information.

- Clarified the Server Browser count summary so search results and the overall
  directory total cannot be mistaken for a download fraction, for example
  `102 matching servers · 1,113 online in directory`.

- Changed six-server freshness from a total cap into a concurrency batch size.
  The launcher now walks every current matching row in successive top-to-bottom
  batches, while a changed search still cancels the obsolete pass immediately.

- Fixed completed freshness batches leaving the status bar permanently in a
  checking state. Completion now reports explicitly and no longer performs a
  redundant full Server Browser table rebuild after its row-level updates.

- Made repeated searches latest-search-wins for result freshness: a new result
  set cancels in-flight GameDig processes from the obsolete batch, then starts
  at most six visible-row checks with a 750 ms socket / 2 second process budget.
  Selected-server and launch checks retain their thorough timeout policy.

- Made bounded result freshness follow the table's actual visual order, checking
  visible rows from top to bottom before hidden rows. Lightweight result batches
  now probe only the provider's primary query port; selected-server and launch
  checks retain the thorough fallback-port sequence.

- Fixed Server Browser search rebuilding a broad result table on the first
  keystroke. Local and WolfAPI searches now share a three-character threshold,
  while the local table refresh also waits for a short typing pause.
- Prevented live GameDig endpoint corrections from raising into Qt when the
  corrected endpoint already belongs to another stable WolfAPI server. The
  conflicting correction is rolled back and the remaining batch continues.

- Stacked the Steam and launcher health cards at full width with Steam first,
  and replaced Windows' redundant Steam-installation selector with a player-name
  field synchronized with Favourite Servers.
- Added bounded results freshness after an explicit server-list refresh or a
  completed WolfAPI search. Matching rows are checked six at a time by the
  background GameDig worker, and repeated requests coalesce without blocking
  Qt's UI thread.

- Simplified Server Browser freshness into three levels: cached WolfAPI browse
  data, one automatic background GameDig check for the selected row, and the
  authoritative launch preflight. Removed bulk visible-row checking and the
  redundant cache-view refresh control; rapid selections retain only the newest
  pending live check so the Qt event loop remains fluid.
- Made Settings quieter and platform-adaptive: Windows no longer presents an
  irrelevant launch-engine choice or empty Linux health rows, ordinary health
  cards contain only actionable checks, WolfAPI loses the staged label, and
  provider-specific credentials and master overrides appear only when selected.

- Added an experimental Windows runtime backend with registry-backed Steam
  discovery, native process inspection, roaming/local application data paths,
  direct absolute Workshop mod arguments and `steam_api64.dll` discovery. The
  Windows GUI and non-launching native preview are validated on a real Steam +
  DayZ installation; actual DayZ handoff and packaging remain explicit gates.
- Made atomic persistence portable when POSIX `fchmod` and directory `fsync`
  are unavailable, and close SQLite connections when cache initialization
  fails so Windows does not retain a locked database handle.
- Made launch-engine choices, Steam modes, required tools and diagnostics obey
  platform capabilities, removing Flatpak, Proton, PRIME and shell-launcher
  controls from the Windows interface.
- Began the v0.9 production-hardening cycle and centralized the application
  version as `0.9.0.dev0` pending the release candidate.
- Added a tested platform-backend boundary for capabilities, user-data paths,
  Linux Steam command candidates and process inspection while preserving the
  existing shared detection API and validated Linux behavior. This prepares a
  clean future Windows implementation seam; the later Windows backend builds
  on this boundary without changing the validated Linux behavior;
  the extraction also restored the intended Flatpak-running check whose
  `flatpak ps` command had become unreachable.
- Packaged Flatpak testing found that an isolated Steamworks Workshop helper
  could leave DayZ marked as running after helper shutdown. Flatpak automatic
  Workshop state/subscription helpers now fail safe to explicit manual Steam
  actions and **Recheck mods**; native Steam retains its validated automatic
  helper. Settings health also presents a stopped but startable selected Steam
  client as an actionable warning.
- Moved the curated server path to XDG config with non-destructive migration
  from a checkout-local `servers.yaml`, and introduced atomic, durable,
  owner-only persistence with a last-known-good curated YAML backup.
- Added coordinated shutdown across all timers, worker slots, bounded worker
  pools and the WolfAPI refresh child process. SQLite now closes only after
  background ownership has ended; an overlong operation defers window closure
  and retries safely.
- Added optional desktop-keyring storage for the Steam Web API key with an
  owner-only local fallback, plus centralized support-report redaction for
  credentials, home paths and Steam userdata identifiers.
- Added centralized package metadata, wheel/source builds, Linux desktop
  integration and a `.deb` staging build that bundles the locked Python runtime
  and GameDig 5.3.3 dependency tree with artifact checksums.
- Added repository-wide Ruff formatting/lint enforcement, scoped strict typing,
  locked dependency auditing, immutable GitHub Action pins and Ubuntu 22.04/24.04
  package-build/smoke jobs. Debian artifacts now bundle checksum-verified Node
  20.20.2 and declare their exact compatible system-Python minor line.
- Added a draggable Server Browser table/inspector workspace. The common table
  remains dense and moves Host/port/source/version/last-seen support detail into
  a selected-server panel with endpoint, map, players, ping, truth basis,
  features and transient mod readiness. Its semantic edge distinguishes
  positive, uncertain/checking and confidently offline states; Region and Game
  Time remain explicit unavailable/unknown placeholders pending their planned
  data plumbing. A follow-up identity band gives the selection a stronger name,
  semantic status badge, highlighted endpoint and compact Map/Players/Ping
  facts. An original low-contrast environmental atlas adds honest map-family
  flavour for Namalsk, Chernarus, Enoch/Livonia and Sakhal, with a darker
  neutral fallback rather than pretending to show server-provided banners. It
  expands through the otherwise-unused lower inspector after all operational
  and support information, removing the large dead area without sitting behind
  selectable text. Purpose-composed portrait vistas replace the initial square
  source panels so the narrow inspector retains distant horizons and depth
  instead of cropping into close terrain. A native charcoal vignette fades the
  artwork into the inspector at every edge, with stronger vertical falloff and
  restrained sides that preserve the semantic status border.
- Replaced normal-path **Enrich visible** sweeps with a 450 ms debounced local
  check of only the deliberately selected discovered server. Successful checks
  are reused for two minutes and failures observe a five-minute retry cooldown;
  the bounded bulk check remains available as **Check visible servers** under
  advanced tools.
- Replaced implementation-facing **PROVIDER ONLINE/OFFLINE** Browser labels
  with WolfAPI truth states—Live, Recent, Stale, Offline and Unverified—while
  locally checked rows remain Online/Offline and provider provenance stays in
  tooltips/details. Renamed Flags to Features and Required Mods to Mods.
- Made discovered-server enrichment preserve stable identity, freshness,
  quality and mod metadata that a local status query did not measure.
- Selected-server checks now update only their existing row and preserve the
  current selection and viewport instead of rebuilding and snapping the table
  during ordinary inspection.
- Added a lightweight, session-cached mod-readiness preview after a deliberately
  selected server has been locally confirmed online. The Browser Mods cell can
  show Checking, Ready, a missing count or Unavailable without subscribing to
  anything; successful previews last 15 minutes and failures cool down for five.
- Renamed the secondary Browser action to **View mod details** and made the
  primary action name the selected destination. **Launch [server]** always
  enters the existing authoritative Steam/Workshop pre-flight, which remains
  the only path that can offer installation or updates.
- Restored both Vanilla/Modded and PvE/PvP to the common Browser controls in the
  order Search, Mods, Game Style and Map. Search is the row's elastic control so
  it absorbs width changes without gaps while the categorical controls remain
  compact. Deliberate selected-
  server status and readiness work now uses separate three-runner bounded pools
  with endpoint deduplication, queued overflow and the existing cooldowns.
- Browser readiness previews reuse the latest Settings
  Steam-detection snapshot instead of rescanning Steam libraries on the UI
  thread, and Mods-cell updates preserve selection, sorting and scroll position.
- Fixed **Check visible servers** freezing the Browser by removing per-result
  UI-thread SQLite commits and repeated full-table rebuilds. Bulk results now
  remain in the worker, progress text is throttled, and completion performs one
  transaction followed by one table refresh. Game Style is now self-labelled by
  its **Any game style** dropdown without a separate field label.
- Moved the automatic WolfAPI response-to-SQLite merge off the UI thread into a
  dedicated cache worker with its own connection. Cached results remain usable
  while the transaction runs, followed by one visible-list refresh after commit.
- Isolated the complete WolfAPI refresh pipeline in a helper process after
  desktop testing showed Python-thread JSON parsing/normalization could still
  pause Qt through the shared interpreter lock. HTTP paging, parsing and SQLite
  merge now complete outside the GUI process before one small result handoff.
- Removed the trial automatic refresh on Server Browser tab opening after
  desktop testing found any list replacement disruptive. Opening the Browser
  now renders cached data only; explicit refresh and the existing optional
  once-daily provider refresh remain the update paths.
- Canonicalized Server Browser map filter options case-insensitively so provider
  variants such as `Bitterroot` and `bitterroot` produce one **Bitterroot**
  choice. Filter matching remains case-insensitive and preserves the existing
  Enoch/Livonia display alias.
- Replaced the visible Settings health table with three native grouped
  readiness cards for Launcher, Steam/DayZ and Graphics/launch state. The full
  snapshot remains authoritative for copying and is available through an
  explicit support-details dialog instead of competing with the common view.
- Aligned every Settings health group to the same label/detail guide and added
  bottom breathing room so fourth rows and longer labels remain balanced.
- Closed the direct discovered-server journey across Server Browser and Mods:
  Browser enables its next-step actions only for a real selection, while Mods
  now presents stable server identity, readiness guidance, a contextual mod
  resolution action and a primary Launch action.
- Made the Browser and Mods keyboard path follow their visible layout and made
  row activation with Enter match the existing mouse activation behaviour.
- Added a contextual left-arrow **Back to Server Browser** action beside the
  Mods launch action when mod inspection originated from a discovered row.
- Added a resizable table/inspector Mods workspace. The dense sortable table
  now keeps only Status, Name, Workshop ID and Size, while a selected-mod panel
  on the right shows the asynchronously loaded thumbnail, description, size,
  status and Workshop action. The existing bounded public Steam metadata
  request supplies the optional descriptions and preview URLs.
- Removed hover-only description and hidden Steam-path tooltips from Mods; the
  selected-item card now owns visual Workshop detail, while explicit copied
  reports retain technical Steam and filesystem context.
- Made the right-hand mod inspector scale its thumbnail and local typography
  from the 720p baseline on taller windows, with bounded growth, and removed
  bare URLs from visible Workshop description copy.
- Added a semantic selected-mod inspector edge—green for ready, red for
  missing, amber for update/pending—and a small draggable gutter separating
  the inspector from the dense table.
- Reduced high-resolution inspector typography growth independently of the
  thumbnail, reaching roughly 120% at 1080p with a 122% ceiling.
- Added a deliberately restrained native SVG icon pass for the four primary
  tabs and only the clearest Add, Refresh, Launch and Recheck actions, retaining
  every text label and avoiding decorative table/filter iconography.
- Added the entirely non-operational **Beware of the leopard** Settings
  disclosure, which hides no setting, diagnostic or useful information.
- Fixed Server Browser **Required Mods** sorting when known integer counts and
  unknown placeholder values share the column; sortable items now produce
  type-stable numeric, text and empty keys instead of comparing integers with
  strings.
- Added a compact geometric wolf identity mark for the application/window icon
  and a restrained `WOLF // LAUNCHER` tab-bar lockup, without adding a large
  branded header or reducing workspace height.
- Established WolfLauncher's atmospheric visual direction with an original,
  low-contrast foggy treeline around the workspace perimeter, transparent
  content canvas, and restrained amber lower-edge framing that preserves the
  existing calm, readable interface.
- Made Favourite Servers card-only after desktop approval of the card layout,
  removing the legacy server-table options disclosure and detailed-table view.
- Promoted Steam-managed Workshop subscription and updates from an opt-in
  experiment to the default mod-readiness path. Install/update controls and
  per-mod recovery are always available, while manual missing-page opening now
  lives under Advanced Mod Tools as a fallback.
- Replaced the Connect-time prompt chain with a live pre-flight checklist that
  starts the selected Steam client when necessary, verifies required mods,
  automatically subscribes/updates incomplete Workshop items, rechecks local
  readiness, hands the launch command to Steam and confirms the DayZ process.
- Added a one-time startup check that warns when the selected Steam installation
  is not running or cannot be detected, explaining which Workshop features may
  be incomplete while preserving server browsing.
- Unfavouriting a saved server now offers to remove it from Favourite Servers
  or keep it unstarred, and star changes persist to both the favourites index
  and the user-owned YAML row.
- Changed the add action to the more natural **Add a favourite server** wording.
- Renamed user-facing curated-server wording to the clearer UK English
  **Favourite Servers**, while retaining the existing YAML format and internal
  implementation identifiers.
- Aligned ping presentation with DayZ's documented thresholds: 200–249 ms is
  amber warning latency and 250 ms or higher is red/critical in discovered and
  curated server views.
- Recorded the three-character Server Browser search pause for joint
  Launcher/API profiling without prematurely attributing it to the API.
- Unified the Browser's visible Server Name: fresh locally validated live names take precedence, provider/cache names remain the fallback, and the separate internal Live Name column stays hidden even in the detailed view while provenance remains available in tooltips and copied details.
- Normalized displayed map names with initial capitalization and Enoch shown as Livonia, promoted Flags and Required Mods into the default Browser view, renamed flags to explicit Modded/Vanilla labels, and display zero or unknown mod counts as an en dash while retaining explanatory tooltips.
- Fixed wide-screen Server Browser proportions by bounding the Name column, letting Host absorb surplus table width and keeping common filters contiguous; added a high-contrast themed checkbox with a visible checked and unchecked state.
- Adapted Server Browser and curated Servers to their native redesign references: balanced Name/Host proportions, bounded common filters, concise discovery summaries, and a native curated card list with status edges, two-line metadata, compact player/ping blocks and per-row Connect actions.
- Completed the cohesive native-theme pass with a full Qt palette for partially native controls and dialogs, consistent technical fonts for paths/endpoints/identifiers, quieter dense tables, themed transient UI, and explicit primary, accent, disclosure and destructive action roles.
- Added the first native UI theme pass: central charcoal/amber colour and spacing tokens, application-wide QSS for standard controls, tables, tabs, menus, progress and scrollbars, accessible focus treatment, semantic primary/summary/disclosure roles, portable technical text and quieter data-dense tables.
- Added a cross-platform visual-design brief for the later native Qt polish pass, defining the restrained charcoal/amber direction, accessibility and cognitive-consistency principles, Linux/Windows scaling requirements and a behaviour-preserving implementation sequence.
- Migrated the discovered cache to schema v4 and consume WolfAPI v1
  required-mod status, timestamps, error and manifest hash alongside the
  nullable count. Browser tooltips distinguish ready, stale, failed and unknown
  API evidence while preserving direct inspection as final truth.
- Recorded WolfAPI's observed 4 GB memory exhaustion as a cross-project release blocker and paused further normal-path browser architecture pending API profiling, full-payload removal and mixed 1,000-client load gates.
- Made two-stage local-plus-remote server search and exact advertised-endpoint resolution explicit cross-project requirements, including indexed API search and honest unavailable/not-found states.
- Extended the cross-project handoff with bounded WolfAPI required-mod metadata polling, honest unknown/zero/stale/failure semantics, a manifest detail endpoint and a full launcher-facing enrichment inventory.
- Added a detailed cross-project discovery-freshness handoff defining the WolfAPI contract, validation semantics, launcher migration, rollout gates and acceptance criteria needed to replace fixed startup polling safely.
- Recorded fixed startup server polling as a future discovery-freshness design problem, with viewport demand, validation age, bounded background budgets and stable WolfAPI signals identified as better directions.
- Made explicit visible-row enrichment apply results in top-to-bottom browser order and atomically replace obsolete keys after live port correction, without automatic discovered-server UDP polling.
- Made visible-server enrichment bounded and parallel with incremental progress/cache updates, preventing a 200-row batch from appearing frozen behind sequential query timeouts.
- Clarified blank discovered required-mod counts as provider-unknown values with an **Inspect mods** recovery tooltip.
- Added a final isolated Workshop state query before launch; unavailable or newly unready Steam state cancels handoff instead of trusting an older Mods result.
- Added live Mods-row queued, downloading, percentage-bar and verifying states while retaining the batch dialog and final forced local verification.
- Added optional required-mod counts to discovered rows from provider fields or successful direct mod inspection, preserving blank as unknown.
- Distinguished amber provider-reported discovery status from green/red locally validated status and added status-basis details and tooltips.
- Migrated the discovered-server cache to schema v3, combining optional required-mod/status provenance with WolfAPI v1 identity and freshness fields while preserving both earlier schema-v2 layouts.
- Recorded a follow-up review of Mods-table spacing, alignment and density for the later fonts/theme/icons/branding visual-polish pass.
- Improved Mods-table readability with padded cells and headers, slightly taller rows, centred compact status/ID/size columns and a URL column that uses the remaining width.
- Simplified the Mods table to Status, Name, Workshop ID, Size and Workshop URL; removed duplicate name/notes columns, moved the URL last and now shows published sizes for installed as well as missing mods.
- Added per-mod download sizes from Steam published-file metadata and combined known estimates to experimental Workshop rows and confirmation, switching to live remaining-transfer bytes when available and explicitly identifying genuinely unavailable or partial totals.
- Added a two-minute no-progress boundary for Workshop resolution so Steam states stuck incomplete with no active downloads return an explicit fallback result and release AppID 221100 instead of holding DayZ as running for the full 30-minute timeout.
- Fixed Workshop progress keeping the first unresolved mod name while Steam downloaded later items; current-item text now follows Steam's downloading/progress/pending state and reports an honest waiting state otherwise.
- Silenced repetitive native SteamAPI breakpad, Steam ID and library-load console messages inside disposable Workshop helper processes while preserving structured progress and errors.
- Added isolated batch `ISteamUGC::GetItemState` checks to the experimental normal mod workflow, distinguishing ready, update-required, download-pending and downloading items and preventing reported unready items from passing launch preflight.
- Added an experimental Mods-row **Check/update this mod** recovery action that reuses the isolated Steam resolution and verified post-download recheck flow for one required item.
- Fixed sequential discovered-server mod inspection stalling after several selections by handing the newest queued context forward when the current worker actually finishes, with visible queued feedback and direct navigation to Mods.
- Added a direct discovered-server journey: browser rows can become an in-memory active context for mod inspection, guarded Workshop resolution and launch, while promotion to curated YAML remains optional.
- Recorded the real-world experimental Workshop hardening roadmap: post-download launch readiness, honest stop-monitoring semantics, direct discovered-server checking/launching, update checks, size/progress presentation and discovery-status truth.
- Added an opt-in experimental Steam-native Workshop subscription flow for missing DayZ mods, with explicit account-change confirmation, per-item download monitoring, cancellation of waiting, local-directory verification and manual-link fallback.
- Added a minimal `ctypes` ISteamUGC adapter that dynamically loads Valve's existing 64-bit Steam API redistributable from the selected Steam installation; WolfLauncher does not vendor the proprietary library or create a persistent `steam_appid.txt`.
- Added an early selected-client warning when experimental Workshop subscription is requested while Steam is stopped, before opening the confirmation or progress flow.
- Changed experimental Workshop progress to show the required mod name instead of a numeric Workshop ID when server metadata provides one.
- Renamed the Workshop dialog action to **Stop monitoring**, blocked launch while the Steamworks worker is active, and added a short post-download settling boundary after the Steamworks context is released.
- Added **Install missing mods** to native and external missing-mod launch warnings when the experimental Steam-native subscription control is enabled.
- Moved the experimental Steamworks subscription session into a spawned helper process so the process that initialized as DayZ exits completely before WolfLauncher permits the real DayZ launch.
- Replaced **Stop monitoring** with **Hide monitor** so the original helper continues in the background, and made repeated install actions reopen that monitor instead of starting another Steamworks session.
- Made incomplete Workshop items retry Steam download requests at a bounded interval, identify still-incomplete IDs on timeout, ignore terminal interrupts inside the helper and cancel/join that helper during application shutdown.
- Removed the fixed 10-second post-download cooldown after real-world testing confirmed isolated-helper process exit is a sufficient launch-readiness boundary.
- Kept hidden Workshop monitors hidden by suppressing `QProgressDialog` updates until explicitly reopened, and simplified successful completion text to the downloaded mod count.
- Replaced the successful download dialog's generic confirmation with **Launch server**, deferred until the isolated helper exits and a forced mod recheck confirms the downloaded set.
- Added conservative restart/recovery detection for required items left in Steam's DayZ Workshop download staging area, with honest Mods guidance and guards against duplicate helper sessions or launch until a fresh check confirms readiness.
- Added the staged WolfAPI v1 GUI provider with bounded 100-row background
  pagination, merge-only off-page-safe caching and local-first Server Browser
  search followed by a quiet 450 ms debounced remote directory search.
- Made WolfAPI v1 the provider default for fresh installations after production
  and desktop canaries passed, while preserving saved provider choices and the
  explicit legacy fallback. Exact `host:port` searches now use alias-aware v1
  resolution for either game or query ports.
- Added WolfAPI freshness, validation and provider-observation evidence to the
  existing Status tooltip and copied server details without adding a table
  column; expired cached labels are marked refresh-pending rather than guessed.
- Confirmed the v1 startup boundary: discovered SQLite rows are not
  automatically UDP-probed, HTTP provider refresh remains quiet and bounded,
  and curated/selected/launch-time checks remain local by design.
- Added the opt-in WolfAPI v1 client/cache foundation: strict rollout-contract
  validation, bounded list/search/exact-resolution clients, an additive SQLite
  additive cache migration, stable server IDs, endpoint aliases, freshness and
  validation fields, and duplicate-free port-correction merging. The deployed
  legacy WolfAPI URL remains the default.
- Made native/external launch-engine changes invalidate and quietly recheck the selected server's mods using the newly authoritative Steam/Workshop context, matching Steam install mode changes.
- Made Steam install mode changes deterministically start or queue a quiet forced mod recheck, instead of leaving the Mods tab waiting when the previous lookup had already finished.
- Bound cached mod results to both the selected server and Workshop directory, preventing an in-flight check from an old Steam install mode being accepted after the mode changes and queuing a fresh check for the current context.
- Prevented Mods copy/open actions from using another server's stale result while a new selection is being checked; failed current-server reports remain copyable for support, while Workshop actions require a successful current result.
- Stopped failed cached mod checks from suppressing automatic retry when a curated server is selected again; only successful matching results are reused by the quiet selection refresh.
- Preserved launch argument boundaries in displayed and copied commands by using shell-aware formatting, so paths or player names containing spaces and shell characters remain unambiguous in support reports.
- Converted native fresh required-mod lookup failures into structured `mod lookup` launch errors with recovery guidance, instead of allowing raw API exceptions to escape the GUI launch workflow.
- Fixed native launch reusing an empty required-mod list from a failed cached check; failed or stale results now fall back to the native engine's fresh mod lookup after unchecked-launch confirmation.
- Fixed launches attempted during initial status refresh treating the `Checking...` resolved-IP placeholder as the server host; only valid resolved IPv4 values now replace the configured hostname.
- Fixed failed or stale cached mod checks being treated as authoritative during launch preflight; they now retain the existing explicit unchecked-mod confirmation boundary.
- Extracted ordered launch-preflight policy from the Qt window into `wolflauncher.launch_preflight`, with direct coverage for environment blockers, stopped-Steam continuation, unchecked mods and native/external missing-mod behavior.
- Extracted the automatic discovery-refresh timestamp policy from the Qt window into a pure module, with direct coverage for recent, expired, naive, invalid and UTC-normalized timestamps.
- Started the v0.9 GUI simplification pass by keeping common Server Browser filters and promotion visible while placing version/source/sort/limit and refresh/enrichment tools behind a compact, direction-marked disclosure control.
- Simplified the Mods tab by keeping recheck, missing-page and filter actions visible while retaining native preview, copy and selected-page actions in an advanced tools panel.
- Aligned the Server Browser and Mods hierarchy by placing their information summary first and moving advanced disclosures to the bottom of each tab.
- Aligned the Server Browser bottom actions on one row, with advanced tools on the left and Promote/Reset on the right.
- Simplified Settings with installation health first, persistent health/save actions and a bottom disclosure for discovery configuration, imports and copy-oriented support tools.
- Simplified Servers with status and common controls first, the curated table in the middle and persistent Add/Refresh/Launch actions at the bottom.
- Moved the external launcher path from Servers to an adaptive Settings row that appears beside the engine selector only when the external fallback is selected.
- Completed real-desktop review of the resulting Servers, Server Browser, Mods and Settings hierarchy.
- Added Steam-selection regressions for deterministic complete-install priority, explicit `STEAM_ROOT` selection and empty detection.
- Moved native launch failure-detail assembly into `wolflauncher.native_launcher`, with regression coverage for no-mod-check context, full parity output and secondary report-generation failures.
- Extracted Mods-tab summary and row presentation into `wolflauncher.mod_presenter`, with direct coverage for errors, no-mod servers, installed/missing counts and row metadata.
- Added an explicit v0.9 GUI simplification checkpoint that keeps common workflows calm while preserving advanced discovery, diagnostics, parity and fallback controls.
- Moved copied discovered-server detail formatting into the existing Server Browser presenter and added coverage for live names, flags, unseen dates and source text.
- Extracted curated-server row display construction into `wolflauncher.curated_server_presenter`, with direct tests for unchecked, online, offline and partial live-status states.
- Extracted discovered-server Qt row population into `wolflauncher.server_browser_table`, with focused tests for item roles, sort metadata, tooltips, status colours and row replacement.
- Clarified blank provider ping values in Server Browser tooltips and documentation, and made WolfAPI parsing accept a future additive `ping_ms`, `ping` or `latency` field.
- Moved discovered-server row display/sort metadata into the Server Browser presenter and fixed copied discovered-server details still calling the removed `_players_text` GUI helper.
- Fixed automatic discovery refresh crashing while evaluating its 24-hour throttle after the worker extraction dropped the main GUI's `timezone` import.
- Added a testable Server Browser controller boundary that owns cache queries, result counts, summary snapshots and filter-option loading.
- Extracted pure Server Browser presentation rules for style terms, player counts and cache-summary text into `wolflauncher.server_browser_presenter`, with direct edge-case tests.
- Extracted the Server Browser's data-aware Qt table item into `wolflauncher.table_items`, with direct numeric, text and empty-value sorting tests.
- Extracted curated-server promotion/edit dialogs from the main GUI module into `wolflauncher.curated_dialogs`, with direct field-normalization tests.
- Extracted status, mod-check, discovery and enrichment thread workers from the main GUI module into `wolflauncher.workers`, with focused error-handling and row-selection tests.
- Fixed the main-window startup failure caused by dropping its `QTimer` import during launch-dialog extraction.
- Recorded successful real-desktop smoke testing of Settings health/report copying, native preview actions and a known-working native server handoff after the v0.9 extractions.
- Extracted external and native launch dialogs and post-handoff process watching from the main GUI module into `wolflauncher.launch_dialogs` without changing the launch workflow.
- Added the Qt EGL runtime library to CI so GUI module import checks run on GitHub's headless Ubuntu workers.
- Extracted Settings health snapshot construction from the main GUI module and added direct readiness-row tests.

## v0.8.0 - 2026-07-11

- Added GitHub Actions unit-test coverage for Python 3.10, 3.11 and 3.12.
- Added a release checklist covering automated checks, desktop smoke tests, native and Flatpak Steam launch cases and the external fallback.
- Updated the package version from the stale `0.2.0` value to `0.8.0`.
- Made the validated native launcher the default for fresh installations while preserving existing saved launch-engine choices and retaining the external launcher as a selectable fallback.
- Recorded successful real-world native launch validation for native and Flatpak Steam, Steam running and stopped, and unmodded, fully modded and partially missing-mod servers.
- Preserved detailed native preview errors, including stale `@mod` symlink details, in the preview failure dialog.
- Added selected Steam/install/server context to native launch failure details when a full parity report cannot be built from a cached mod check.
- Added the selected Steam install setting to copied native parity reports so Auto, Native Steam, Flatpak Steam and `STEAM_ROOT` test runs are easier to compare.
- Expanded native missing-mod parity tests for no required mods, all missing mods, mixed installed/missing mods and missing selected-mode Workshop folders.
- Added selected Steam install context to Mods summaries and copied mod reports so native, Flatpak and `STEAM_ROOT` Workshop checks are easier to distinguish.
- Added a native preview **Copy native command** action that is enabled only when the experimental native command is ready.
- Clarified stale native `@mod` symlink failures with copyable expected-vs-actual target details in native failure reports.
- Added a Mods tab **Copy missing links** action for missing Workshop pages.
- Added a Mods tab **Copy mod report** action for timestamped required/missing Workshop ID snapshots.
- Added a Settings **Copy last launch** action backed by `~/.local/share/wolflauncher/last_launch_report.txt`.
- Added a clearer external-vs-native readiness comparison to copied native launch parity reports.
- Added a local last-known status cache for curated server rows so startup can show previous live data while fresh checks run.
- Added tracked `example.servers.yaml`, ignored local `servers.yaml`, and startup seeding for missing local server lists.
- Added curated add/edit handling for pasted `host:port` values, splitting the host and game port before saving YAML.
- Added selected-row curated status refresh, including an automatic one-row refresh after manually adding a curated server.
- Added a curated-server context action for saving a live status connect-port correction back to `servers.yaml`.
- Added a direct **Add curated server** flow on the Servers tab for saving manual YAML server entries without going through discovery first.
- Added Steam command details to selected and Auto Steam readiness text.
- Added Steam command details to the Settings health header summary.
- Documented command-aware Steam install summaries in README and handoff notes.
- Added Steam command details to Auto/selected Steam candidate summaries in Settings health and diagnostics.
- Added Steam command details to the Settings health configured-install summary.
- Clarified copied diagnostics and native parity reports to show Flatpak Steam as a `flatpak run` handoff command.
- Clarified native parity report result text when the external launcher comparison cannot be built.
- Changed native parity reports to build the external comparison from the same resolved server target as the native preview.
- Matched native launch player-name fallback to the external launcher handoff by using `Survivor` when the configured name is blank.
- Marked v0.7 health checks and Linux polish as the current documented baseline after successful real-world server testing.
- Added an explicit Auto Steam row to Settings health so selected Steam mode and automatic install selection can be compared at a glance.
- Added explicit Steam launch-options guidance to diagnostics, Settings health and post-handoff warnings, including a warning for the known bad NVIDIA PRIME option while keeping launch options external to WolfLauncher.
- Clarified diagnostics wording so copied reports show general DayZ process visibility rather than implying a launch handoff just happened.
- Clarified Settings and diagnostics labels for the selected Steam install mode so they are not confused with the selected launch engine.
- Softened copied troubleshooting next-step wording so diagnostics do not imply a launch handoff happened before the report was captured.
- Added generated-at metadata to copied Settings health reports.
- Added generated-at metadata to copied external launch output reports.
- Added generated-at metadata to native launch parity reports.
- Changed diagnostics generation to use a single environment snapshot for PRIME status and launch troubleshooting sections.
- Changed `STEAM_ROOT` detection to reuse the native Steam command and running state when available, and warn when a ready Steam library lacks a launchable Steam command.
- Made post-handoff DayZ process detection case-insensitive so Proton command lines with different executable casing are still recognized.
- Expanded DayZ install detection to read Steam `appmanifest_221100.acf` `installdir` values before falling back to the conventional `steamapps/common/DayZ` path.
- Clarified Proton compatdata diagnostics so missing prefixes are reported as first-run Steam/Proton state rather than a launch blocker, with matching Settings health, diagnostics and native parity report wording.
- Added a Copy button to the external launch output dialog so the generated command and handoff logs can be pasted into support reports.
- Added informational DayZ Proton compatdata detection to Settings health, diagnostics and native launch parity reports.
- Added generated-at and selected launch-engine metadata to copied diagnostics reports.
- Added a Settings diagnostics copy action that copies the full diagnostics report without opening a separate tab.
- Added a Settings health copy action and right-click menu so support snapshots can be copied from the health table.
- Added PRIME helper command visibility to diagnostics and Settings health, showing whether `prime-run` or `switcherooctl` are available without warning non-hybrid systems.
- Improved native launch Steam-library error guidance so missing DayZ installs and missing Workshop folders point to different recovery steps.
- Expanded the native launch preview into a copyable parity report with a validation checklist comparing the external launcher handoff with the experimental native command, selected Steam install, resolved connect target, required mod IDs, prepared mod links and missing Workshop directories.
- Added copyable parity-report details to native launch failures when a cached mod check is available.
- Changed the missing-mod launch prompt so the native experimental engine no longer offers an impossible "Launch anyway" path when required Workshop directories are missing.
- Added at-a-glance native parity report result text and included mod names in required-mod and missing-directory report sections when available.
- Added native parity report counts for created versus reused mod symlinks, and reject stale `@mod` symlinks that point at the wrong Workshop directory.
- Fixed Mods tab recovery when a cached mod result exists but the visible table is empty, and made missing Workshop detection visible during silent startup checks.
- Added a consolidated launch troubleshooting report to diagnostics and Settings health, covering selected Steam mode, detected command/paths, DayZ process visibility, PRIME status and suggested next steps.
- Fixed initial startup mod checks so the restored or default selected server is checked after the Mods tab is ready.
- Added Settings health and diagnostics summaries that show which Steam install Auto selects and what other detected install candidates report.
- Expanded native and Flatpak Steam detection to read Steam `libraryfolders.vdf`, so DayZ and Workshop can be found in secondary Steam libraries.
- Added diagnostics output for all detected Steam library folders.
- Added unit-tested Steam install selection helpers for Auto, Native Steam, Flatpak Steam and `STEAM_ROOT` launch modes.
- Confirmed real-world experimental native launch success through Flatpak Steam, with DayZ detected roughly 10 seconds after handoff.
- Added a native Steam install selector for Auto, Native Steam, Flatpak Steam and `STEAM_ROOT` so experimental native-launch testing can target a specific Steam install.
- Changed native-engine mod checks, launch preview and launch preflight to use the selected Steam install, clearing stale mod results when the selection changes.
- Changed native launch command generation to fail early with mode-specific guidance when native Steam, Flatpak Steam or `STEAM_ROOT` lacks a detected launch command.
- Moved packaging preparation later in the roadmap so native launcher parity and Steam/Proton reliability stay ahead of installer polish.
- Added a Settings health row for visible NVIDIA PRIME / DRI PRIME environment state.
- Expanded diagnostics with structured PRIME status and safer hybrid-GPU troubleshooting steps.
- Clarified that absent visible PRIME variables do not rule out Steam per-game launch options, and expanded no-process post-handoff guidance for the known NVIDIA PRIME option.
- Changed post-handoff DayZ process detection from a single early check to a 45-second watch window to account for slow Steam/Proton startup.
- Added clearer Linux Mint / Ubuntu development setup instructions to the README.
- Added post-handoff DayZ process checks to external and native launch dialogs.
- Added DayZ process visibility to diagnostics for Steam/Proton troubleshooting.
- Clarified launch dialog wording so successful handoff is not presented as proof that Proton or DayZ fully started.
- Added clearer native, Flatpak and `STEAM_ROOT` Steam readiness messages in Settings health and diagnostics.
- Added platform-detection tests for Steam install readiness and complete-install selection.
- Added structured native-launch failure stages with user-facing recovery guidance.
- Added launch dialog handling for command start failures.
- Added a diagnostics warning when WolfLauncher sees the known problematic NVIDIA PRIME offload environment combination.
- Added an experimental native launch action behind the Mods tab preview, with first real-world native Steam handoff confirmed.
- Added a saved launch-engine setting so the main Launch button can opt into the native experimental engine while keeping the external launcher as default.
- Added native launch preview output for prepared mod symlinks, missing Workshop directories and generated Steam commands.
- Added the first native Python launcher-engine foundation for legacy-compatible mod symlink preparation and Steam launch command generation.
- Added data-aware Server Browser sorting for numeric ports, players, ping, status and freshness columns.
- Added fuller NVIDIA PRIME and Steam launch-option troubleshooting guidance.
- Added Server Browser result-limit controls and clearer matching-vs-cached summary text.
- Added WolfAPI as a discovered-server cache provider, backed by `https://api.drakonwolf.ddns.net/api/servers`.
- Added name-derived Server Browser style filtering for PvE and PvP servers.
- Added Server Browser source filtering, reset controls and cache summary counts.
- Added Server Browser double-click promotion and a copy-host context action.
- Added tests that pin WolfLauncher's command generation to the vendored launcher handoff contract.
- Added PRIME-related environment values to diagnostics output for launch-option troubleshooting.
- Added bounded query-port fallback probing when enriching discovered server rows with uncertain port data.
- Added in-app editing for curated YAML server entries.
- Changed discovered-server enrichment to preserve display names while storing differing live names separately.
- Changed live enrichment to update a discovered server's game port from the queried connect address when available.
- Added Server Browser freshness/identity polish with Last Checked and non-duplicated Live Name display.
- Added SQLite cache schema-version checks and migration scaffolding.
- Changed failed provider refreshes to keep existing cached rows while still pruning stale rows after successful refreshes.
- Restored Server Browser map and version filters as cache-populated dropdowns.
- Reduced routine Server Browser completion popups by reporting successful refresh/enrichment results in the status bar.
- Replaced the separate Diagnostics tab with a Settings tab containing compact health checks.
- Moved discovery provider configuration, API key, refresh limit, endpoint overrides and server-list import into Settings.
- Simplified the Server Browser tab to a single configured-provider **Refresh database** button.
- Changed startup discovery refresh from hard-coded BattleMetrics to opt-in refresh for the selected provider.
- Added quiet rate-limited BattleMetrics startup refresh.
- Added BattleMetrics server discovery as a documented no-key discovery source.
- Added Steam Web API server-list discovery as the preferred HTTPS discovery path.
- Changed provider refreshes to sync discovered rows, clearing stale API-backed cache entries and inserting only new server keys.
- Added live enrichment for visible discovered server cache rows.
- Added an in-app Steam master endpoint override field.
- Added explicit Steam master endpoint-list overrides for discovery testing.
- Added fallback/error reporting for Steam master server discovery DNS failures.
- Added an in-app Steam master refresh button for discovered server candidates.
- Added Steam master server candidate discovery import support.
- Added editable promotion details and right-click copy actions for discovered servers.
- Added promotion from discovered cache rows into the curated YAML server list.
- Added YAML/JSON import for discovered server cache rows, including a sample import file.
- Added a read-only Server Browser tab backed by the SQLite discovered-server cache.
- Started v0.6 SQL foundations with a SQLite discovered-server cache module and tests.
- Added the MIT license for WolfLauncher and third-party notices for vendored code.
- Added `AGENTS.md` as the quick project orientation and coding-agent handoff file.
- Vendored the MIT-licensed `dayz-linux-cli-launcher` under `external/dayz-linux-cli-launcher/`.
- Added the vendored launcher as the final default launcher path fallback.
- Added a standard-library unit test suite for launch command generation, launcher path discovery and YAML server loading.
- Added offline unit tests for server status parsing and `gamedig` failure handling.
- Added offline unit tests for DayZSA mod parsing and local Workshop mod scanning.
- Removed tracked Python bytecode files and added `.gitignore` rules for generated caches.
- Expanded diagnostics and Linux Mint install dependencies for the external launcher tools.
- Reorganized project documentation around the end-of-v0.5.2 working baseline.
- Documented the known Steam launch-option issue with `__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia %command%`.
- Clarified that successful external-launcher exit means handoff to Steam, not proof that DayZ fully started.

## v0.5.2
- Fixed launch output dialog QTextCursor crash on PySide6.
- Hardened launch path to pass the resolved IP address to dayz-launcher.sh.
- Reworded successful launch output so exit code 0 is shown as a successful handoff to Steam instead of an alarming finished message.
- Fixed early selection-change traceback by guarding launch button text updates until the button exists.
- Kept v0.5.1 offline/restart status handling fixes.


## v0.5.0 - Launch integration

- Added guarded launch workflow for selected servers.
- Added DayZ/Workshop preflight checks before launch.
- Added Steam-not-running warning with Launch Anyway / Cancel.
- Added missing-mod warning using the latest mod check for the selected server.
- Added Open Workshop / Launch Anyway / Cancel flow when required mods are missing.
- Added launch output dialog using the external `dayz-launcher.sh` command.
- Added launch command display for debugging and support.
- Kept the external MIT-licensed shell launcher as the launch engine.

## v0.4.2 - Mod management hotfix

- Fixed mod table sorting causing blank/incomplete rows.
- Fixed double-click/right-click Workshop page opening regression.

## v0.4.1 - Mod management polish

- Added double-click mod row to open its Steam Workshop page.
- Added right-click context menu on mods with open/copy actions.
- Added mod filter for All, Missing only, and Installed only.
- Added sortable mods table.
- Added copy Workshop ID, mod name, and Workshop URL actions.
- Added right-click server actions to copy connect address, copy server details, and toggle favourite.
- Missing/installed mod status is easier to scan.
- Kept v0.4 mod detection behaviour unchanged.

## v0.4.0 - Mod management foundation

- Added a dedicated Mods tab.
- Added selected-server mod checking through the DayZ SA Launcher style server API.
- Added local DayZ Workshop mod scanning from `steamapps/workshop/content/221100`.
- Added required-vs-installed mod comparison.
- Added missing mod detection.
- Added Steam Workshop links for required mods.
- Added buttons to open the selected Workshop page or all missing Workshop pages.
- Kept v0.3.1 Steam, DayZ, Workshop, diagnostics, favourites and settings behaviour.

## v0.3.1 - Diagnostics cleanup

- Improved diagnostics wording so optional install types do not appear as hard failures.
- Added last refresh timestamp to the server browser.
- Added subtle ONLINE/OFFLINE colour coding.
- Auto-refresh setting now applies and saves immediately.

## v0.3.0 - Local platform detection

- Added native Steam detection.
- Added Flatpak Steam detection.
- Added DayZ install detection.
- Added DayZ Workshop folder detection.
- Added improved Diagnostics tab.
- Added favourites click-to-toggle.
- Added settings persistence.
- Added last selected server persistence.

## v0.2.1 - Project state files

- Added `CHANGELOG.md`.
- Added `ROADMAP.md`.
- Added `ARCHITECTURE.md`.
- Added `PROJECT_STATE.md`.
- Updated README for handoff and continuation.

## v0.2.0 - Server browser refinement

- Added cleaner server table columns.
- Added saved settings.
- Added saved favourites.
- Added clickable favourites star.
- Added double-click server launch.
- Added auto-refresh setting.
- Added improved diagnostics tab.

## v0.1.x - First working GUI

- Added initial PySide6 GUI.
- Added YAML server configuration.
- Added DNS hostname support.
- Added live server status checks through `gamedig`.
- Added launch bridge to `dayz-launcher.sh`.

## v0.5.1
- Fixed launch integration for DNS-based servers by resolving hostnames before calling `dayz-launcher.sh`.
- Improved offline/restarting server detection so incomplete query responses are not shown as ONLINE.
