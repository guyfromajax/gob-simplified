# UX polish batch D — League (items 13–17) — 2026-09-29

Branch `ux/polish-league` from `origin/develop`.

- `a7fa890bf` Fix late detail load stamping another view's history entry
- `e63b77d3e` League polish: national standings, T1 rankings, 10/5 leaders, one sticky team-stats header with conference scope, schedule game cards

No backend or sim change. Team Stats' Conference tab uses the existing `GET /franchise/team-stats?scope=conference`. Leaders' `limit=10` is the route's own default.

## 0. Regression: app-router › "rankings opens in place, stays cached, and restores history"

**Symptom.** The spec failed at line 258: after Rankings → team page → Back → Forward → Back, the Rankings history entry had turned into `tab=team-view`, so Back landed on a team page.

**Cause.** Team and player detail views call `stampOrigin()` after their data loads. When the URL has no `origin`, it writes one with `history.replaceState` on the *current* entry. If the user had already gone Back before the load finished, the current entry was the Rankings entry. The late stamp overwrote it with `tab=team-view` and switched the tab. The race only showed without a wait after the drill, which is what the spec does. It reproduced on develop with no batch changes.

**Fix (at the source, `detailBar.js`).** `stampOrigin(isUser, tab)` now takes the view's own tab. If the URL's `tab` is no longer that view, it does nothing and tells the caller to drop the load. `teamView.js` and `playerView.js` pass `'team-view'` / `'player-view'`. When the view is shown again, `revalidate()` loads it, since it never finished.

**Result.** app-router, nav-coverage-fix and polish-prep-plan, run together: 32/32 passed. In the full gate: **4/4 passed**, including "rankings opens in place, stays cached, and restores history".

## 1. Standings (item 13)

- The Conference / Region / National segment is gone. The view always shows the whole league, and the only tool is the search.
- Otherwise the layout is unchanged: one card per conference, yours first with "· Yours", the same columns and your row in navy.
- The `gob-view-standings-scope` key is no longer read.

## 2. Rankings (item 14)

- Rebuilt on the T1 template, with the same `.gob-tcard` + `.gob-tbl` treatment as Standings and Team Stats.
- Card title "National Rankings". Columns: `#`, Team (logo and name via `teamLink`), W, L, PF, PA, Last Week, Next.
- Last Week shows the W/L mark in the existing `.gob-wl` data colours, then the stored line ("@ Iowa Academy, 65-59").
- Your row is `tr.me.is-user`, in the shared navy.
- Top 25 / All 128 moved to the page-head tools as a neutral `.stats-toggle` segment. It keeps the `#rankings-toggle-top25` / `#rankings-toggle-all` IDs and the `gob-view-rankings-show-all` key.
- The in-app behaviour and caching from the regression fix are kept: the module view, store `get`/`revalidate` with 304s, the skeleton and retry card, and scroll restore on back/forward. The header pins under the page head.
- The old `.rankings-*` card CSS in `gob-views.css` is removed. Set Lineup's own `.rankings-toggle` rules are untouched.
- **Omitted: rank movement ▲/▼.** The rankings payload has no previous rank. `apply_rank_prestige` overwrites `natl_rank`, and the previous rank is not stored. Per §8 rule 1 (missing field: omit it), there is no movement column. Adding it needs a backend field such as `prev_natl_rank`, which I have not added.

## 3. Leaders (item 15)

- The Conference / National segment is kept. National shows 10 per board (the leader plus 9 rows). Conference shows 5 (the leader plus 4 rows).
- The board request's `limit` matches: `view_scope=national&limit=10`, or `view_scope=conference&limit=5`.
- Also fixed: a pre-existing bug where the segment kept highlighting the old choice after a click, because the tools weren't repainted. Found while checking screenshots.

## 4. Team Stats (item 16)

- **One header row.** The repeated header every 16 teams is gone, and so is the group band ("Shooting / 3PT / …"). The column labels (FGM, 3PTA, DREB …) stand on their own, the group name is each header's `title`, and the shaded groups keep their shade.
- **Sticky.** The table is out of the `.gob-xs` side-scroller, so it never gets the 1760px wide-table floor or the static header. Scoped `#team-stats-view` rules (tokens only) tighten cell padding and the header size. The team name gets an ellipsis cap. That fits all 28 columns inside `.main` at 1280 and 1920, so the shell's page-level sticky header applies and the row stays pinned under the page head.
- **Scope.** A Conference / National segment (the same `tables.segment` Leaders uses) sits before the search. The key is `gob-view-team-stats-scope`, default National. Conference requests `…/team-stats?franchise_id=…&scope=conference`, which the server filters to your conference (8 teams). A slower response for the old scope is ignored.

## 5. League Schedule (item 17)

- The week stepper, the round title, the empty lines, the URL `week` param and team drill-in are unchanged.
- The wide Away | Result | Home | Box score table is replaced by a 4-column grid of compact game cards, dropping to 2 columns below 1100px, like Team Schedule.
- Each card has two lines, away then home: the logo, then the rank only when it is 1–25, then the name (with an ellipsis) and the score. The winner's line is full white and the loser's is dimmed. A quiet footer shows the tournament context or Final / Scheduled, plus a Box score link on played games.
- Your game is the navy card: `.gob-game.me`, with a `color-mix` of `--navy` and `--surface-1`.
- 1920 uses taller lines and slightly larger type.
- Team names are shown exactly as stored. The data is already cased ("IDA", "DeLand", "MiddleTEX", "HA Rushmore"), and nothing upper-cases them.

## Tests

New: `tests/e2e/polish-league.spec.js`, run at 1280×720 and 1920×1080. It uses a mock league built from `base_league.json` (128 teams, 16 conferences).

- **Standings:** no segment and no Conference/Region/National in the tools; 16 cards, 128 rows; one navy your-row; no overflow.
- **Rankings:** one T1 card with a `gob-tbl`; the exact header list; sticky header; 25 → 128 → 25 rows; one `tr.me.is-user` with your name and rank, in navy; no other row navy.
- **Leaders:** National gives 10 entries on all 8 boards, with the National button on; Conference gives 5 on all 8. The request limits are checked too.
- **Team Stats:** exactly one `thead tr`, no repeat or group rows, no `.gob-xs` or wide-wrap, 128 rows. After scrolling 1000px or more, the header is flush under the page head. Conference gives 8 rows and sends `scope=conference`, then National gives 128.
- **League Schedule:** 64 cards; 4 grid columns with 4 cards in the first row; no grid, card or `.main` horizontal overflow. Every `.rk` is 1–25, and no team ranked above 25 shows a rank. Exactly one navy card, containing your team, with its box link.
- `POLISH_SHOTS=1` writes the screenshots.

Updated for the new markup:

- `t1-tables`: Team Stats has one sticky header row and no repeats; Standings has no National click.
- `schedule-views`: League Schedule uses cards.
- `shell-2`: the League Schedule sticky check is replaced by a card-grid check, because there is no header row now.
- `team-schedule-columns`: the reference shot waits for a card.
- `app-router`: the your-row link uses `toContainText`, so a monogram fallback can't break it.

## Gate (UX_System §8)

- pytest (`--ignore=tests/e2e`): **4047 passed, 16 skipped, 109 xfailed, 1 xpassed, 0 failed.**
- Full Playwright (workers=1, port 8791, `CI` unset, started after the other agent's run ended): **581 passed, 3 skipped, 0 failed** (584 tests, 9.1 min).
- **app-router.spec.js:** **4/4 passed**, including "rankings opens in place, stays cached, and restores history".
- Regenerated tracked report images were restored with `git checkout -- reports/`, and generated folders were removed. Only `reports/polish-league/` and this report are added.

## Screenshots and self-check

All are in `reports/polish-league/`, at `-1280` and `-1920`.

- **standings:** A1 Conference "· Yours" comes first, then A2, and at 1920 B3/B4 and C5/C6 sit in two columns.
  - Lancaster's row (2nd) is the only navy row.
  - The tools hold only "Search teams"; there are no scope tabs.
  - The DIFF bars and NEXT marks are unchanged. Nothing is clipped.
- **rankings:** One "National Rankings" card with the header `# · Team · W · L · PF · PA · Last Week · Next`.
  - Rows 1–25 show logos or monograms. Last Week shows a green W or red L mark (win/loss data) and then the line.
  - Top 25 / All 128 is a grey neutral segment, top right.
  - Your team (#46) isn't in the Top 25, so it isn't visible here. The spec checks it on All 128, where its row is the only navy one.
  - At 1920 the table runs the full width like Standings at 1280, with generous gaps between Team and W and between Last Week and Next. Nothing is clipped.
- **leaders-national:** 8 boards (Points, 3-Pointers, Assists, Blocks, then FG%, Rebounds, Steals, DEF%) with 10 entries each. National is highlighted and your LAN rows are navy.
  - At 1280 the second row of boards continues below the fold, which is the normal page scroll.
- **leaders-conference:** The same 8 boards with 5 entries each, and Conference is highlighted. At 1920 all 8 fit above the fold.
  - Your players are navy, including a navy leader card (Marcus Brooks, Lancaster).
- **team-stats-scrolled:** Scrolled about 1400px. The single header row (Team, Rank, W … DEF%) is pinned right under the League page head, and rows scroll beneath it.
  - Every column fits, with no sideways scroll. The 3PT, Rebounding and Defense groups are shaded, and the Rank sort column carries the sort tint.
  - Conference / National sits in the tools with National on. Lancaster's navy row is sliding under the header.
- **league-schedule:** Week 12 with four columns of game cards.
  - Only top-25 teams carry a small grey rank (8 Bentley-Truman, 10 Durham, 2 Chapel Hill, 25 D1 Institute, 14 Amariabi International, 6 Ann Arbor, 20 Columbus, and at 1920 23 Quigley Catholic, 24 Sacred Heart).
  - Unranked teams, such as #46 Lancaster, show no number.
  - Winning lines are white with bold scores. The footers read "Final · Box score".
  - Lancaster vs Little York is the one navy card, top right. Names such as "Long Island Methodist" and "Amariabi International" fit, and nothing is clipped or overflows sideways.

**Colour law.**

- The only green control is the top-bar "Play Next Game". Green elsewhere is data only: Rankings' W marks and Standings' positive DIFF.
- There is no orange; none of these views has a save.
- Navy appears only on your rows and your game card.
- The segments (Top 25/All, Conference/National) and the week stepper are neutral grey.
- There is no gold.

STATUS: COMPLETE
