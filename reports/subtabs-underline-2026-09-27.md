# Underline section sub-tabs — 2026-09-27

One shared row, `window.GOBSubtabs`, paints Team, Prep, League, and News. Recruiting stays a section with an empty `tabs` list, so the row is absent. Adding Pool · Leans · Visits later is a `SECTIONS` entry only.

Branch `ux/subtabs-underline`.

## What the row does

The host is `#gob-subtabs.nav-row`. Tabs are `role="tab"` buttons (`.tb`). The selected tab is `aria-selected="true"`. Ink is placed from the selected tab’s box against `.tabs`, and it moves with `--dur-tab` after the first paint.

Overflow is measured with a `ResizeObserver`. The search collapses to an icon first. Trailing tabs then fold into More. The selected tab stays in the row. Keyboard: roving tabindex, ←/→ activate, Home/End, More menu keys. `/` focuses the search and expands it if it is collapsed. Esc clears the search and blurs it.

The locked Tournament tab stays in the tab order (`aria-disabled="true"`, no native `title`). Hover and focus show the tooltip. The week is the existing derivation: `firstTournamentWeek()` walks `GOBTierEmblem.tierForWeek`, which is empty before week 27 and matches `REGULAR_SEASON_WEEKS` (26) plus `EOS_CONFERENCE_WEEKS`. Title: “Opens Week N”. Body: “Tournament opens when the regular season ends.” The More line says “Unlocks Week N”.

A detail view keeps ink on `return_tab`. With no `return_tab`, nothing is selected and the ink width is 0. `.gob-dt-bar` is `position: static` and sits under the head. The head’s bottom padding is `--dsp-8` (8px). On the Lancaster save the measured gap from the row to the bar was 8px, and Roster stayed selected for Ervin Miller opened from the roster.

Production tools are unchanged: `.stats-toggle` and `.gob-search`, with the counts and labels those views already paint. No crumbs. No new segments.

The compact-roster static header override is unchanged (`html.gob-shell .main .gob-wide-wrap thead th`, `.gob-xs thead th`, and `.gob-roster.is-compact thead th` stay `position: static !important`).

## Frames flattened

The second frame was `#franchise-container .tab-content` in `franchise-command-center.css`: 18px/22px padding, a 1px border, radius 20, a gradient, and a shadow. Under `html.gob-shell:not(.gob-office)` that chrome is removed (padding, border, radius, background, shadow). The cards inside the panel are not restyled.

Panels that rule covers:

- `#standings-tab`, `#rankings-view`, `#standings-view`, `#leaders-view`, `#team-stats-view`
- `#roster-view`, `#team-attributes-view`, `#player-view`, `#team-view`, `#roster-tab`, `#player-stats-tab`
- `#game-plan-tab`, `#playbooks-tab`, `#coaches-tab`, `#schedule-tab`, `#training-tab`
- `#press-tab`, `#recruits-tab`, `#team-stats-tab`, `#fcc-team-stats-summary-tab`, `#awards-tab`

`#home-tab` keeps its office card. The rule is off while `html.gob-office` is set, and the office hides `.pg-head`.

No `.fcc-data-card` was a second frame around an already-carded section page. None were flattened. `.gob-tcard` tables are unchanged.

## Where production differs from the reference

- Recruiting has no tab row. The hub still paints (Pool is a later `SECTIONS` change).
- League › Team Stats has a search and no second segment. At 1280×720 the search stays expanded (“Search teams”) and More is hidden. Search collapses first at a narrower measured width. More is not a 1280 breakpoint.
- On the Lancaster save at 680×720, League folds Practice Squad and Tournament into More. Team Stats stays underlined. The search is an icon. The menu meta is “Unlocks Week 27”.
- Fixture overflow (stubbed league) reaches More around a 680px viewport, after search has already collapsed. The selected tab is not folded.
- Standings at 1280 and 1920 keeps Conference / Region / National and the expanded team search. Nothing collapses.
- Tooltip copy is the agreed two lines, not a native `title`.
- No crumbs.

Sticky headers: `--gob-stick-top` is the measured head height. On standings, once the page scrolls, the header’s top meets the head’s bottom (gap 0). Wide tables and the compact roster header stay static inside their own scrollers.

## Checks

Fixture shots (stubbed API) and offline shots (copy of the Lancaster save, `tmp/stats-audit-live.sqlite` served from `/tmp/subtabs-offline.sqlite` on loopback `127.0.0.1:8766`, desktop profile, pointer parked in `.main`) are in `reports/subtabs-underline/`.

Offline franchise `6ab284847ab3853ae89a1184`, team Lancaster `69a6fcb68d2c56aa82e48a54`, week 3. Tournament is locked. The loopback was stopped after the shots. The live Application Support database was not opened.

| | 1280 | 1920 |
|---|---|---|
| Team › Roster | underline, Varsity 12 / Practice Squad 3 | same |
| Prep › Training | shot | shot |
| League › Standings | search expanded, no More | same |
| League › Team Stats | search expanded, no More | same |
| Recruiting | row hidden, hub visible | same |
| News | News underlined, Awards beside it | same |
| Tournament tooltip | Opens Week 27 | same |
| More | 680px, Team Stats kept, Practice Squad + Tournament | — |
| Player from Roster | Roster ink, static bar, 8px under the row | — |

## Tests

`tests/e2e/subtabs.spec.js` covers switching, ink position, the overflow ladder (search collapses before More; the selected tab stays), keyboard, the locked tooltip, `/` and Esc, and the detail bar.

Updated assertions in `shell-1`, `shell-1b`, `shell-2`, `t1-tables`, `t2-roster`, and `app-router` read `role="tab"` / `aria-selected` and the tooltip text. The tab row height assertion is 44px at 1280 and 52px at 1920.

Workers=1, in four runs so the server stayed up:

| Suite | Result |
|---|---|
| subtabs, t1-tables, t2-roster, navigation-history, app-router | 20 passed |
| t3-detail, shell-1, shell-1b | 27 passed, 1 skipped |
| office-frontend | 9 passed, 1 skipped |
| shell-2 | 11 passed |

67 passed, 2 skipped. The skips are the suites’ existing skips. An earlier office failure at 1440 (“win” standings window 4, expected ≥ 5) did not repeat.

STATUS: COMPLETE
