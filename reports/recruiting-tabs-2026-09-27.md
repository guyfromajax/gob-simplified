# Recruiting sub-tabs — Pool · Leans · Visits

Branch `ux/recruiting-tabs`. Mechanics are unchanged: no recruiting logic, lean math, invite firing, or signing resolution changes.

## What shipped

Recruiting is still one page. The underline row is Pool, Leans, and Visits. A tab click writes `hub=pool|leans|visits` with `history.replaceState` and calls `RecruitingHub.show`. It does not call `GOBNav.replace` (that reloads the document) and it does not call `fccHref`. Reload and `popstate` read `hub` into `pageMode.sub`. Back still leaves Recruiting, because the three views share one history entry.

Weeks 35 and 36 hide the row. The sign board or the results body is the page. Focus mode (`ordersAreFocus`, including `action=run`) still hides `.pg-head`. That was not changed.

Search moved to `.pg-tools` as `.gob-search` ("Search name…", `/` to focus). Region, position, year, Watchlist, Unranked by me, and "Showing N of M" stay in the pool toolbar. "Leans to me" is gone. There is no crumb, no count on a tab, and no new frame-only field.

## Phase mapping

| Weeks | Pool | Leans | Visits |
| --- | --- | --- | --- |
| 1–19 | Story strip and the pool, as today | Same stack, pool limited to leans | Calendar preview. Heading "Invite window opens Week 20". Seven upcoming tiles from the existing states. |
| 20–26 | Today's full invite stack: weekly results when it shows, visit calendar, invite board, pool | Same stack, pool limited to leans. The board stays. | Calendar plus the weekly results panel. The board and the pool stay on Pool. |
| 27–34 | Story strip and the pool | Same stack, pool limited to leans | `visit_history` for weeks 20–26. Filled tiles show name and lean. Missed tiles stay missed. Title stays "Invite Visits". |
| 35, 36 | Row hidden. Sign board / results body unchanged, including the sign board's own "Leaning to you" / All. | | |

A fresh arrival with no `hub` query selects Leans when `viewCounts().leans` is greater than 0, otherwise Pool with region = `team_region`. An explicit `hub` (reload) is honored. Region, position, year, search, and Watchlist / Unranked stick for the visit, including back/forward.

## Tests

`recruiting-tabs.spec.js`: 4 passed (invite week 22 Pool / Leans / Visits, weeks 7 and 30 Visits, weeks 35 and 36 row hidden, focus still hides the head).

Hub specs after the landing change (`&hub=pool` where the assertion needs the full pool): `recruits-pool`, `invite-board`, `invite-board-layout`, `invite-visit-calendar`, `invite-seed-modal`, `recruiting-draft`, `recruiting-button-state`, `signing-day`, `signing-day-hub`, `signing-reveal`, `attr-tiles`, `fcc-recruiting-layout`. Shell: `shell-1`, `shell-1b` (fresh arrival follows the tab), `subtabs`, `navigation-history`. This pass: `shell-2` and `office-frontend` — 20 passed, 1 skipped.

Python (`GOB_PERSISTENCE=sqlite` `GOB_DB_MODE=mongomock`): `test_recruiting_watchlist`, `test_recruiting_wire_payload`, `test_weekly_recruiting_training_flow`, `test_recruiting_lean_events`, `test_recruiting_week36` — 87 passed, 3 xfailed (the existing weekly-training xfails).

Three specs failed and are not from this change (the files they load were not edited): `fcc-invite-step` and `fcc-recruiting-buttons` evaluate `updatePlayButton` without `GOBAdvance` (the button string now lives in `gobAdvance.js`); `recruit-visit-modal` never sees `.wow-roster`.

## Screenshots

`reports/recruiting-tabs/` at 1280×720 and 1920×1080.

Real save, Lancaster Johnnies, week 3, a copy of `tmp/stats-audit-live.sqlite` on loopback (the Application Support database was not opened): `passive-landed-*` (Leans, 2 of 450), `passive-pool-*`, `passive-visits-*` ("Invite window opens Week 20", seven upcoming).

Fixtures: `pool-w22-*`, `leans-w22-*`, `visits-w22-*`, `visits-w7-*`, `visits-w30-*`, `signing-w35-*`, `results-w36-*`.

UX_System.md §6, §7, and §9 describe the row, the `hub` replace, the search, the fresh-arrival rule, and the hidden row on Signing Day and Results.

## Follow-up

The black rectangle on the 1280 pool was the wide-table edge fade. `classifyTables` puts `.gob-wide-wrap` on `.pool-scroll`, and that mask's transparent end painted a hole over the phase strip, the story, and the filter row, including "Showing N of M". It was not a leftover search field. `.pool-scroll` still scrolls horizontally. It no longer takes the mask, and it no longer uses `contain: inline-size` (that collapsed the column so the story and filters stopped short of the phase strip). `recruiting-tabs.spec.js` rejects any mask inside the hub and checks `elementFromPoint` on the Showing count. That runs for every phase fixture at 1280 and 1920.

The section h1 is the only title. The outer hub card and the "Recruiting Hub" heading are gone, and the phase strip is the first content under the row hairline. Pool, Leans, and Visits do not show a Recruit Pool jump; the pool is on the page for the first two, and Visits has no pool. Signing Day keeps the Recruit Pool / My Orders switch, because My Orders replaces the pool. Results does not need a jump.

`fcc-invite-step`, `fcc-recruiting-buttons`, and `recruit-visit-modal` were run on a clean `origin/develop` worktree (`eb53dae7d`). All three fail there too (28 failed, 9 passed). They are pre-existing and were not changed here.

Re-ran `recruiting-tabs`, `recruits-pool`, `invite-board`, `invite-visit-calendar`, `signing-day-hub`, `subtabs`, and `shell-1b`: 87 passed, then the three seed-notice clicks that the Sammy note was covering. Those clicks use `{ force: true }`, the same way the notice's own dismiss already did, and those three passed on the re-run. Screenshots in `reports/recruiting-tabs/` were retaken, including the Lancaster week-3 save.

STATUS: COMPLETE
