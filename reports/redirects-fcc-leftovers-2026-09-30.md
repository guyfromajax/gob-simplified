# Redirects + FCC leftover HTML/JS + freeze live — 2026-09-30

Branch `chore/redirects-fcc-leftovers` from `origin/develop` (includes `chore/fcc-css-peel`). Jamie Q7 A plus leftover FCC panels/JS, a second FCC.css peel, and UX_System §16 freeze flipped from pending to live.

## Redirects (Jamie Q7 A)

Same stub pattern as `standings.html`: one `URLSearchParams(window.location.search)` read, copy existing params (`franchise_id`, `team_id`, `week`, …), `params.set('tab', …)`, `location.replace` to FCC. Gate B allow-list hand-raised to **1** on each new stub file (not `--write-allowlist`).

| Old URL | Now | Replaced |
|---|---|---|
| `/stats.html` | FCC `?tab=team-stats-view` | League › Team Stats (`team-stats-view` / gob-tables). Was a standalone resource page (`stats.css` + inline filter CSS). |
| `/team-traits.html` | FCC `?tab=team-attributes-view` | Team › Team Attributes (`team-attributes-view` / gob-measures + `buildTeamMeasuresRadarMarkup`). Was a standalone resource page (shared FCC.css + `resource-pages.css`; those sheets stay because other pages load them). |

**Dead page assets**

- `FrontEnd/static/stats.css` **deleted**. Develop `stats.html` was the only `<link href="/stats.css">`. Grep of `FrontEnd/` after the stub: no remaining `stats.css` loaders.
- No `stats.js` / `team-traits.js` page files existed. Team-traits used shared sheets only.

**Callers updated so nothing treats them as real pages**

- `gobShell.js` `PAGES`: `/stats.html` → `{ kind: 'browse', section: 'league', sub: 'team-stats-view' }`; added `/team-traits.html` → `{ kind: 'browse', section: 'team', sub: 'team-attributes-view' }`.
- `authGuard.js` `shellPages`: `/team-traits.html` added (same stub family as `/stats.html` / `/standings.html`).
- UX_System §7: Team Attributes notes `team-traits.html` redirect; League Team Stats notes `stats.html` + `team-stats.html`.
- UX_System §9: both listed as redirects.
- Coverage map md/csv: both rows are `REDIRECT STUB` (Jamie Q7 A).

## Stub list (docs only)

UX_System §9 already listed `schedule.html`. Added the already-redirecting files:

- `game-plans.html` → `tutorial-game-plans.html`
- `scouting.html` → `tutorial-scouting.html`
- `player-attributes.html` → `tutorial-player-attributes.html`
- `team-attributes.html` → `tutorial-team-attributes.html`
- `index.html` → `homepage.html`

No product changes on those files.

## Leftover FCC HTML

`commandCenterTabs.canonicalTab` remaps leftover tab ids to live views. Those panels never become `.active`. Removed from `franchise-command-center.html`:

| Removed panel | Remap | Live surface |
|---|---|---|
| `#roster-tab` | `roster-view` | gob-tables roster-view |
| `#recruits-tab` | `home-tab` (added this remap; gobShell already mapped it) | Recruiting is `/recruiting.html`; Office is `#home-tab` |
| `#schedule-tab` | `team-schedule-view` | team-schedule-view |
| `#team-stats-tab` / `fcc-team-measures` | `team-attributes-view` | team-attributes-view + radar |
| `#game-plan-tab` | `game-plan-view` | game-plan-view |
| `#playbooks-tab` | `playbooks-view` | playbooks-view |
| `#fcc-recruiting-btn-tab` / `#fcc-recruiting-live-copy-tab` | not URL tabs | leftover Recruiting-tab footnote; `updateFccRecruitingFootnote` no-ops when the nodes are missing. Office still has `-home` slots. |

Runtime: web + desktop capture of every coverage-map FCC tab (same peel list). `querySelector` on the removed ids is null; `canonicalTab` still lands on the live view. Pixel-diff of those live views is 0.000% except the documented empty-state/settings flicker below.

Leftover `.tab-buttons` **kept** (hidden chrome). `isKnown` + remaps still need the leftover `data-tab` values so old URLs work. `fcc-recruiting-layout` / player-development-grid tests still read that row.

## Leftover FCC JS

`franchise-command-center.js` **5729 → 2742** lines. **92 functions removed** (184 → 92). Each had no remaining caller after the panel remap. Restored `upcomingOpponent` / `upcomingOpponentId` / `upcomingOpponentByKey` (strip ate the declarations; `GOBFccPrep.peekUpcomingOpponent` still needs them — scouting-view throws without them).

Removed families (evidence: only called from removed panels / `onTabShow` leftover branches / `renderHomeTab` leftovers):

- **Old home cards:** `renderHomeMatchupCard`, `renderHomeNewsCard`, `renderHomeRankingsCard`, `renderHomeRecruitingWire`, `renderHomeTeamStatsCard`, `createEmptyHomeState`, `bindHomeTeamLeaderButtons`, plus the `.fcc-home-list-*` / `-matchup-*` / `-team-stats-*` class strings. Live `renderHomeTab` is `GOBOffice.render` + `renderRecruitingTabBadge` only.
- **Leftover Team Measures:** `buildTeamMeasuresLinearCardMarkup`, `createMetricBar`, `createPill`, `createTeamAttrItem`, `formatTeamAttrDisplayValue`, `getTeamAttrVisualConfig`, `renderTeamTraits`, `renderTeamTraitsTop10`, `sortTeamTraitsTable`, `bindStatsAndTraitsScopeButtons`.
- **Leftover roster:** `fccRosterRowHtml`, `fccPositionCellHtml`, `fccPosChipHtml`, `fccRtLockupHtml`, `fccFocusCellHtml`, `fccIdentityCellHtml`, `fccRosterFlagsHtml`, `renderFccRosterBody`, `renderFccRosterAttrHeader`, `sortRosterTable`, `bindFccRosterScope`, `updateFccRosterCounts`, `fccRosterSortBy`, `fccShownAttr`, `fccNormalizePracticePlayer`, `fccPracticeSquadPlayers`, `renderPracticeSquad`, `renderPlayerStatsTable`, `playerStatsScopePlayers`, `updatePlayerStatsScopeControls`, `getDisplayPlayerNameForStats`, …
- **Leftover schedule / standings / leaders / rankings / team-stats / recruits / game-plan / playbooks / training-results** renderers listed in the function dump (e.g. `applyScheduleTabMode`, `buildScheduleColumnMarkup`, `renderLeaders`, `renderRankings`, `renderTeamStats`, `renderFccRecruits`, `renderGamePlanSummary`, `buildFccPlaybooksSectionMarkup`, `renderTrainingResults`, `renderTeamReport`).

**Kept and why**

| Kept | Why a live URL can still hit it |
|---|---|
| `#home-tab` | Default Office panel. `GOBOffice.render`. |
| `#standings-tab` | **Not remapped.** `?tab=standings-tab` still opens the leftover panel. Shared `.fcc-data-card` / standings table CSS stays. |
| `#awards-tab` | **Not remapped.** `?tab=awards-tab` still opens leftover Leaders. |
| `#fcc-team-stats-summary-tab` | **Not remapped.** `?tab=fcc-team-stats-summary-tab` still opens leftover Team Stats summary. |
| `buildTeamMeasuresRadarMarkup` + `TEAM_MEASURES_RADAR_*` | Live Team Attributes calls `window.buildTeamMeasuresRadarMarkup` (`teamAttributesView.js`). Classic-script function declaration is on `window`. |
| `.tm-radar-*` CSS | Emitted by that radar. `gob-views.css` only sizes the wrap. |
| `openRecruitingSurface` / `buildRecruitingUrl` / Office recruiting footnote (`-home`) | Live Office → `/recruiting.html`. |
| `upcomingOpponent*` / `disableLegacyFccScoutingModal` | Still called from FCC init; scouting-view is the live Prep surface. |
| `renderFccLeadersSummary` / `renderFccTeamStatsSummary` / `renderStandings` | Served by the three leftover URL-activatable panels above. |
| `.fcc-tb-*` / tournament Surface A | Live JS (`fcc-tournament-style-a.js`). |
| `.fcc-season-advance` | Live season-advance chrome. |
| Leftover `.tab-buttons` | `isKnown` + remaps + tests. |

`initFccRecruits` slimmed to week + `renderHomeTab`. `renderTeam` is cache-only. `onTabShow` leftover branches for removed panels are gone; awards-tab + fcc-team-stats-summary-tab remain.

## `tests/e2e/fcc-roster-tab.spec.js`

**Retired (deleted).** It mounted leftover `#roster-tab` in isolation. Live Roster is `roster-view` (gob-tables), covered by `tests/e2e/t2-roster.spec.js` (including `?tab=roster-tab` remap).

Source-string pytest that parsed leftover FCC roster HTML/JS (`test_development_focus_surfaces.py` POS/Focus/mappers/practice-scope; `test_fcc_team_measures_radar_scale.py` leftover `radarHost` caller) was retargeted to `rosterView.js` + `teamAttributesView.js`. Same contracts, live files.

`tests/e2e/attr-tiles.spec.js` leftover `GOB_AttrTiles.groupedTilesHtml` / `groupedHeaderHtml` counts retargeted to live roster-view + recruiting-hub. `tests/e2e/fcc-roster-data.spec.js` leftover mapper/practice-scope strings retargeted to `rosterView.js` / `playerStatsView.js`. `tests/e2e/fcc-recruiting-layout.spec.js` leftover `.fcc-newlean-*` wire-card geometry **retired** (those FCC.css rules were peeled with the leftover card).

## FCC.css peel 2 + freeze ceilings

After leftover HTML/JS left, a second dead-rule pass (static identifier miss **and** runtime miss on every live tab).

| | After Task C (develop) | After this leftover peel |
|---|---|---|
| Lines | 3234 | **2261** |
| Style rules | 448 | **293** |

Dropped **155** style rules (448 → 293). Families that became dead once their HTML/JS left: leftover `#roster-tab` / `#recruits-tab` sticky bits, `.fcc-home-list-*` / `-matchup-*` / `-team-stats-*`, leftover `.fcc-game-plan-*` / `.fcc-playbooks-*` (live Prep views have their own CSS; those files were not touched), leftover `.fcc-invite*` in this sheet (Recruiting hub CSS is separate; recruiting-entry pixel 0.000%). Mixed comma-lists trimmed.

`scripts/check_ui_tokens.py`: `FCC_CSS_MAX_LINES = 2261`, `FCC_CSS_MAX_RULES = 293`.

## UX_System §16

§16 is **Cross-cutting rules**. The `franchise-command-center.css` freeze block is flipped from **pending** to **live**, with the ceiling numbers (2261 / 293).

## Pixel-diff (1280, web + desktop)

Same peel view list. Capture: Chrome for Testing (`chromium-1200`) + `document.fonts.ready` (real webfont load, not the isolated stub fallback). Before = develop FCC trio; after = this branch. Shots: `reports/redirects-fcc-leftovers/shots/`.

| View | web % | desktop % |
|---|---|---|
| Office | 0.000 | 0.000 |
| Team Roster | 0.000 | 0.000 |
| Team Player Stats | 0.000 | 0.129 |
| Team Attributes | 0.000 | 0.000 |
| Team Schedule | 0.000 | 0.000 |
| Practice Squad | 0.000 | 0.000 |
| Prep Game Plan | 0.000 | 0.000 |
| Prep Playbooks | 0.000 | 0.000 |
| Prep Scouting | 0.000 | 0.000 |
| Prep Training | 0.000 | 0.000 |
| League Standings | 0.000 | 0.000 |
| League Rankings | 0.000 | 0.000 |
| League Leaders | 0.000 | 0.000 |
| League Team Stats | 0.000 | 0.000 |
| League Schedule | 0.000 | 0.000 |
| League Tournament | 0.000 | 0.000 |
| News | 0.000 | 0.000 |
| News Awards | 0.000 | 0.000 |
| Settings | 0.365 | 0.049 |
| Feedback | 0.000 | n/a (hidden) |
| Recruiting entry | 0.000 | 0.000 |

**41 pairs, max 0.365%. Nothing > 0.5%.**

- **Settings 0.365% / 0.049%:** same class as the peel (panel chrome / focus), not FCC leftover rules.
- **desktop Team Player Stats 0.129%:** table paint / chrome flicker on the desktop profile only (web 0.000%). Not a restyle.
- First after-pass of scouting showed 0.211% (“Unable to load…”) because `upcomingOpponentByKey` was missing. Declarations restored; recaptured after-shots are **0.000%**. `scoutingView.js` was not edited.

Bebas/Barlow still look tight in some labels; before/after used the same loader so the diffs are the pixel change, not a font swap.

## Files touched

- `FrontEnd/static/stats.html` — redirect stub.
- `FrontEnd/static/team-traits.html` — redirect stub.
- `FrontEnd/static/stats.css` — deleted (page-only).
- `FrontEnd/static/franchise-command-center.html` — leftover remapped panels removed.
- `FrontEnd/static/franchise-command-center.js` — leftover-only functions removed; radar kept.
- `FrontEnd/static/franchise-command-center.css` — second dead-rule peel.
- `FrontEnd/static/js/shared/gobShell.js`, `authGuard.js`, `commandCenterTabs.js` (`recruits-tab` → `home-tab`).
- `scripts/check_ui_tokens.py` — ceilings 2261 / 293.
- `scripts/ci/migration_gates_allowlist.json` — `stats.html` + `team-traits.html` at 1 each (hand).
- `_documentation_master/11_Design_Systems/UX_System.md` — §7 / §9 stubs + §16 freeze live.
- `reports/coverage-map-2026-09-29.md` + `.csv` — stub rows.
- `tests/e2e/fcc-roster-tab.spec.js` — retired.
- `tests/test_development_focus_surfaces.py`, `tests/test_fcc_team_measures_radar_scale.py` — retargeted to live roster-view / Team Attributes.
- This report + `reports/redirects-fcc-leftovers/shots/`.

Did not touch: set-lineup, playbooks / training **files**, recruiting **files**, `office-home.*`, `court.html`, Phaser, the sim, `uiSfx`.

## Gates

- `.venv/bin/python -m pytest --ignore=tests/e2e -q` — **4197 passed**, 16 skipped, 109 xfailed, **1 xpassed** (`tests/test_resource_page_scoping.py` / `test_leaders_view_scope_filters_to_user_conference` — pre-existing on develop; `known_failures.py` not edited), **0 failed**.
- Full Playwright (`env -u CI`, `PORT=8186`, `workers=1`, `PLAYWRIGHT_BROWSERS_PATH=$HOME/Library/Caches/ms-playwright`) — **755 passed**, 4 skipped, **0 failed** (11.9m). First full run (8180) had 19 leftover-source / scouting reds; specs retargeted and `upcomingOpponentByKey` restored, then this run.
- `.venv/bin/python scripts/check_ui_tokens.py --strict --no-write` — exit 0. Freeze 2261 / 293.
- `.venv/bin/python scripts/ci/check_migration_gates.py` — pass. Gate A: 0 imports in 0 files. Gate B: **138 lines in 46 files** (two new stub files at 1). Never `--write-allowlist`.

## Unsure / notes

- Leftover `.tab-buttons` still name remapped tabs. That is intentional so `canonicalTab` + `isKnown` keep old URLs working after the panel nodes are gone.
- `updateFccRecruitingFootnote` still lists the removed `-tab` copy/button ids; the loop `continue`s when they are missing.
- Isolated e2e shots can still look tight on Bebas; this proof pair used `document.fonts.ready` + Chrome for Testing.
