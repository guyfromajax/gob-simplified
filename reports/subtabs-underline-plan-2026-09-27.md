# Underline sub-tabs — plan (no code yet)

Branch `ux/subtabs-underline` is at `e38d5d07a`, the same commit as `origin/develop`. No product files have been changed.

The handoff is not in this worktree. It is untracked in the main checkout at `_documentation_master/projects/design_handoff_subtabs_underline/` (and a copy on the Desktop). This plan follows that README, `PROMPT.md`, and `reference/Subtab Underline.html`. Implementation, when approved, will take only the shared `.sx` rules and the `.dA` rules from `reference/subtabs.css`.

The shipped shell wins over the reference top bar (team-name text, uppercase button). Reference tab lists, crumbs, counts, tooltip copy, and names are illustrative.

## 1. Who owns the head, the tabs, the cards, the tools, and the sticky offset

**Section page head.** `FrontEnd/static/js/shared/gobShell.js` builds `.pg-head` in two places: `mount()` for the command center, and `mountBrowse()` for standalone pages (schedule, practice squad, brackets, awards, recruiting, news, and the other `PAGES` entries). Both write the same shape: an `h1` in `.pg-title` (the section title only) and `#gob-subtabs.subtabs`. `sync()` chooses the section from the active tab, or from `?origin=` on `player-view` / `team-view`.

**Parallelogram sub-tabs.** `renderSubtabs()` and `markSubtabs()` in `gobShell.js` paint `.stab` buttons and anchors. The clip-path, height (40px), min-width (118px), and the 2px top bar on `.stab.on` live in `FrontEnd/static/css/gob-components.css` (`.gob .pg-head`, `.gob .subtabs`, `.gob .pg-head .stab`). Locked-tab overrides are in `FrontEnd/static/css/gob-shell.css` (`.stab.is-locked`). `button-font.css` excludes `.stab` from the global button font.

**Rounded outer card.** The historical outer card is `#franchise-container::before` in `FrontEnd/static/franchise-command-center.css`: a 24px-radius, 1px-border panel with a shadow. Under `html.gob-shell`, `gob-shell.css` already kills that pseudo-element and sets the container’s own border, radius, and background to none. The page head is a sibling of `#franchise-container` inside `.main`. It is not inside that card.

**Inner bordered card.** Tables built by the shared views sit in `<section class="gob-tcard">`. That card is `FrontEnd/static/css/gob-tables.css`: surface, 1px `--line`, radius 12. Older panels still use `.fcc-data-card` (`franchise-command-center.css`, radius 14, its own gradient and shadow). Rankings still wraps itself in `fcc-data-card rankings-page-card` (`rankingsView.js`). Prep, player stats, schedule, and scouting still ship `.fcc-data-card` markup in `franchise-command-center.html`.

The spec’s “remove the outer and inner cards around the head, keep one table card” maps to: leave the shell’s already-flat `#franchise-container` alone, keep `.gob-tcard` as the single table card, and do not add a second wrapper around the head. Legacy `.fcc-data-card` shells on the five sections are the remaining inner cards to flatten only where they wrap a section page, without restyling the tables inside them.

**Page tools.** `FrontEnd/static/js/shared/gobTables.js` `placeTools()` appends `.pg-tools` into `#gob-subtabs`. Production class names are not `.seg` / `.search`:

| View | Tools | Source |
|---|---|---|
| Roster | `.stats-toggle`: Varsity / Practice Squad, each with an `<em>` count | `rosterView.js` `paintTools` |
| Standings | `.stats-toggle`: Conference / Region / National, plus `.gob-search` “Search teams” | `standingsView.js` |
| Leaders | `.stats-toggle`: Conference / National, plus `.gob-search` “Search players” | `leadersView.js` |
| Team Stats | `.gob-search` “Search teams” only | `teamStatsView.js` |

Tool chrome is `gob-shell.css` (`.stats-toggle`) and `gob-tables.css` (`.pg-tools`, `.gob-search`). Copy, counts, and the existing white segment treatment stay as they are. There is no `/` shortcut and no Esc-to-clear on `.gob-search` today. The README’s “Esc clears (existing behaviour)” is not present in production.

**Sticky offset.** `--gob-stick-top` is set at runtime by `syncStickTop()` in `gobShell.js` from the measured `.pg-head` height (`0` in focus mode). `watchStickTop()` observes the head and `.main`. CSS consumers:

- `gob-shell.css`: `html.gob-shell .main thead th { top: var(--gob-stick-top) }`, and the second header row uses `calc(var(--gob-stick-top) + var(--gob-stick-row))`. Same for `#roster-table`.
- `gob-tables.css`: `.gob-tbl th` uses the same variable.
- `gob-components.css`: the design token `--dsz-118` is the fixed `.pg-head` height, and legacy `.rtab th` still uses `top: var(--dsz-118)`. The shell overrides `.pg-head` to `height: auto`, so the measured variable is the one that matters.

**Compact / static override (this week’s detail-polish, commit `e38d5d07a`).** `gob-shell.css`:

```css
html.gob-shell .main .gob-wide-wrap thead th,
html.gob-shell .main .gob-xs thead th,
html.gob-shell .main .gob-roster.is-compact thead th {
  position: static !important;
  top: auto !important;
}
```

`.gob-wide-wrap` and `.gob-xs` scroll horizontally with `overflow-y: clip`. The compact team-page roster header stays static inside its card. A new head height must only change `--gob-stick-top`. It must not remove this override.

## 2. Production sub-tab lists, and the Tournament lock

One shared list, `SECTIONS` in `gobShell.js`. These lists win over the reference.

| Section | Production tabs | vs reference |
|---|---|---|
| Team | Roster, Player Stats, Team Attributes, Schedule | Same |
| Prep | Training, Game Plan, Playbooks, Scouting Report | Same |
| League | Standings, Rankings, Leaders, Team Stats, Schedule (`link: schedule`), Practice Squad (`link: practice`), Tournament (`link: brackets`, `lock: tournament`) | Same labels and order |
| News | News (`press-tab`), Awards (`link: awards`) | Same |
| Recruiting | `tabs: []`, `go: 'recruiting'` | **Different.** The shell draws no sub-tab row. The reference’s Pool · Leans · Visits are not production tabs. |

Recruiting’s in-page controls (`spool-tab` “Leaning to you” / “All”, the hub anchor “Recruit Pool”, the visit calendar) are page content, not section sub-tabs. Office has no labeled tabs and hides `.pg-head`.

**Locked state today.** `tournamentLockWeek()` in `gobShell.js` returns a week only when `currentWeek` is set and `currentWeek` is below `firstTournamentWeek()`. `firstTournamentWeek()` scans weeks 1–40 and returns the first week where `GOBTierEmblem.tierForWeek(w)` is truthy, else 0. `currentWeek` is the command-center week (`paintWeek`, from `data.week` or the `#fcc-season-label` text).

`renderSubtabs()` then, for `lock: 'tournament'` and a non-zero lock week, paints `<button class="stab is-locked" aria-disabled="true" tabindex="-1" title="Opens Week N">`. Click, Enter, and Space are swallowed. The tooltip is the native `title`. The tab is not in the tab order.

**Unlock week.** There is no franchise field for it. `tierForWeek` in `FrontEnd/static/js/shared/tierEmblem.js` returns null when `w < 27 || w > 34`, so the scan always lands on 27. The backend mirror is constants, not a document field: `REGULAR_SEASON_WEEKS = 26` and `EOS_CONFERENCE_WEEKS = (27, 28, 29)` in `BackEnd/tournament/franchise_tournament.py` (also `ScheduleManager.REGULAR_SEASON_WEEKS`). The reference copy “Locked until Week 27” and “Tournament opens when the regular season ends” is illustrative. Production copy is `Opens Week N` from that scan.

I will not hardcode 27, and I will not invent a stored unlock week. See the question below.

## 3. Data behind the README’s “Data needed”

| README item | What exists |
|---|---|
| Tab list per section | `SECTIONS` above. Recruiting’s list is empty. |
| Locked state | `tournamentLockWeek()` plus `item.lock === 'tournament'`. Real UI, derived from the week constants. |
| Unlock week | **No stored field.** Derived as “first week `tierForWeek` is non-null”, which the constant makes 27. |
| Crumb text | **Not rendered.** `.pg-title .crumb` exists in `gob-components.css`, and `gobShell.js` never creates that node. The head is the section `h1` only (“Team”, “Prep”, “League”, “Recruiting”, “News”). There is no “Week 22 · next game Saturday” field on the section head. |
| Segment counts | Roster only: `body.players.length` and `training_squad` + `practice_squad_recruits` lengths, painted as `<em>` inside the existing toggle. Standings and Leaders segments have labels and no counts. |

Nothing else on that list will be invented. The new row will not grow a crumb, a Recruiting tab list, or a Team Stats second segment to match the reference.

**Fit checks the reference assumes, against production tools.** The reference’s “League › Team Stats collapses search” assumes two segments plus search. Production Team Stats has search only, so at 1280 it may fit with the search expanded. The production page that matches “two segments + search” is Leaders. Standings is three segments (Conference / Region / National) plus search, which is wider than the reference’s standings tools. Those three checks stay in the test plan; the screenshots will show what the real tools do.

## 4. Detail views inside the section head

`player-view` and `team-view` are command-center panels, registered in `gobViews.js` with `subtab: ''`. They are not entries in `SECTIONS.tabs`.

`gobShell.js` `detailOrigin()` keeps the rail on `?origin=` (`team`, `league`, `office`, `prep`; default `league`). `detailMark()` reads `?return_tab=` and `markSubtabs()` adds `.stab.on` to that tab. When `return_tab` is absent, no tab is `.on`. When it is present (the normal drill-in from Roster, Standings, or Leaders), that sub-tab stays selected and would get the ink.

The section `.pg-head` stays mounted above the panel. The detail chrome is not in the head. `detailBar.js` `barHtml()` writes `.gob-dt-bar` (← back `#back-button`, `.gob-dt-crumb`, optional `.gob-pager`) as the first node inside `#player-view` or `#team-view`, which live in `#tournament-tabs` inside `#franchise-container`. `playerView.js` and `teamView.js` then render `.gob-hero` and one or more `.gob-tcard` sections (Attributes, Recent changes, Development focus, Stats; or Roster and Schedule).

`.gob-dt-bar` is `position: sticky; top: 0` in `gob-tables.css`. It sticks to `.main`, the same scrollport as `.pg-head`, so it competes with the head instead of sitting under a hairline.

Requested behavior after go-ahead, from this task (it overrides the README line that says detail pages are unaffected): drop the outer/inner wrapper cards on these views too; keep the section tab row; paint no ink when no tab is current; place the existing detail bar under the hairline. The bar’s copy, back target, crumb, and pager stay on the fields `detailBar.js` already reads (`origin`, `return_tab`, `up`, pager session storage).

## Shared implementation (after go-ahead)

One module, called from `renderSubtabs()` for both `mount()` and `mountBrowse()`. No per-page copies. Neutral white only. Overflow by `ResizeObserver`: collapse `.gob-search` to an icon first, then fold trailing tabs into More; the selected tab never folds. Keyboard: roving tabindex, ←/→ with automatic activation, Home/End, a focusable locked tab with its tooltip, More menu keys, and `/` to focus search. `--gob-stick-top` keeps measuring the new head. The compact-roster static override stays.

Existing shell, rail, top bar, tables, `.stats-toggle` / `.gob-search` copy and counts, and colour scales (RT, tiers, energy, shot weight) stay.

Tests that assert `.stab` (`shell-1`, `shell-1b`, `shell-2`, `t2-roster`, and any navigation spec that clicks a sub-tab) will need their selectors updated to the shared row. That is part of the implementation pass, not this plan.

## Questions before any code

1. **Tournament unlock week.** There is no stored field. The lock the shell shows today is the first week `tierForWeek` allows, which the constant fixes at 27, with tooltip `Opens Week N`. May the new row keep that existing derivation and the existing `Opens Week N` copy, or should the locked tab wait until a real field exists?
2. **Recruiting.** Production has no sub-tab row. Confirm the underline row stays absent there, rather than adding Pool / Leans / Visits.
3. **Detail selection.** Drill-ins currently mark `return_tab` with `.stab.on`. Confirm player-view and team-view clear that mark so the row shows no ink.

STATUS: AWAITING GO-AHEAD
