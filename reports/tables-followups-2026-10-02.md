# Tables follow-ups — 2026-10-02

Branch `polish/tables-followups`, from `origin/develop` f56d9ec29 (contains the `polish/tables-league` merge). Merged `origin/develop` a4285e7e8 before the gates (merge commit 37cd64494, no conflicts); develop had not moved again when the gates ran. Final product tree: a4cc768ba.

**Status: ready for review.** All seven items done (the five in the brief and the two added during the work). Nothing skipped. Three questions at the end.

## Item by item

| # | Item | Status | What shipped |
|---|---|---|---|
| 1 | Attribute pairs on the two flagged screens | Done | Assign Practice Squad (week 1) and the Practice Squad training report show SC SH / ID OD / PS BH / RB ST / AG ND / IQ FT: tight inside a pair, a gutter between pairs, the widest gap before SC. On the report, CH follows the six pairs on its own, in both Changes and Absolute. Row heights unchanged (44.55px and 30.55px, measured on develop and again after). |
| 2 | Tournament tab | Done: reproduced, fixed, tested | The tab's request carried no login token, so the hosted server refused it. Details below. |
| 3 | "Half-Court Traps" | Done | Renamed on the playbook report, the box score and Set Lineup. It fits on one line in all three. Nothing kept as "HC Traps" except `court.html` (below). |
| 4 | Styleguide, training movement marks | Done | "Exactly 0 is a dash in every week, camp and in season. In season, a dip down to −0.5 other than 0 reads as one up." The in-season row of the table now says `n ≠ 0`. Checked against `describeTrainingChange()`. |
| 5 | `office-frontend.spec.js:932` | Done: the product was wrong | A load-order race in the Office. Details below. |
| 6 | Team Attributes rank-movement arrows | Done | The ▲N / ▼N marks are gone. The view is one surface (Team › Team Attributes); nothing else draws `rank_delta`. The server field is untouched. The gauge now runs to the value. |
| 7 | Result click lands on the Office | Done: reproduced, fixed, tested | A real bug on develop, not staging being behind. Details below. |

## Item 2: the Tournament tab

**What Jamie saw.** "Tournament could not be opened." with a Retry button, in every tournament week (`before-tournament-real-week-27-1280.png`).

**Why.** `gobStore.js` only attaches the `Authorization` header to routes on its browse list (`BROWSE_PREFIXES`). `/franchise/tournament/brackets` was never added. The tab's request went out with no session, the hosted server answered `401 Not authenticated`, and the view showed its error card. The view, the route and the bracket renderer were all correct.

**Why nothing caught it.** Every spec stubbed the route and answered whatever was asked, and the route's own tests run behind the suite-wide auth override. The offline engine does not check the session either.

**How it was reproduced with real data.**

| Check | Result |
|---|---|
| Online, real franchise | Read-only against `gob-staging` (the one franchise past week 26: Morristown, week 30). Its stored brackets are sound, and the real payload builder returns a complete payload for it. Fed to the tab, that payload draws the Conference and Region brackets. So the data and the view were never the problem. |
| Online, real server code | The real route with the real auth dependency: `401 {"detail":"Not authenticated"}` without the token, `200` with it. The tab on the old store against a server that enforces this: the error card. With the fix: the bracket. |
| Offline, real season | A real 26-week season on the offline engine (`scripts/ws2_loopback_season.py`, a scratch SQLite save), then the real week-27 game, then the rest of the tournament. On that save the tab drew the bracket at week 27, at week 28 ("Eliminated, Quarterfinal") and after the tournament (Conference, Region and National), with the old store and the new one. Offline was never affected: the engine answered 200 to a request with no session. |

I could not call the hosted staging API itself from this sandbox (no outbound HTTP); the 401 is from the same route code run locally with its real dependency.

**The fix.** `/franchise/tournament/brackets` is on the browse list (session and ETag, like every other browse view). An uncached `GOBStore.get` now carries the session too, so a route missing from the list is slower, not broken.

**This touches how the client attaches auth.** No server auth or ownership code changed. The real dependency is tested explicitly: `test_route_needs_the_session_and_serves_a_real_season_shape` removes the suite's override and checks 401 without the token, 200 with it, and 403 with someone else's token.

**Tests.** `tables-followups.spec.js` feeds the tab the real route's answers from the real offline season (weeks 27, 28 and 35) through a stub that refuses any request with no `Authorization` header, and asserts the header was sent and the bracket drew. UX_System "Client store" now says a new browse route must be added to the list in the same change, and why stubbed specs miss it.

## Item 7: a result's box score

**Reproduced on current develop with a real game**, in the desktop profile and the web profile: a game played to the final buzzer through the real API (Lancaster 63, Little York 58, week 3), the week closed (week 4), then the result clicked on Team › Schedule. The box score opened and the page sent itself back, ending on the Office.

**Why.** `box-score.js` runs `GOBNav.guardClosedFranchiseGame()` on load. That guard returns a finished game's flow pages to the Office when the game is final, it is the franchise's last game, and the week has moved on. It exists so Back / Forward cannot re-enter a finished game. But "final, last game, week moved on" is exactly last week's result, so any link to it bounced. It was not only Team › Schedule:

| Link | Before | After |
|---|---|---|
| Team › Schedule result | Office | Box score; Back returns to Team › Schedule |
| League › Schedule "Box score" | Office | Box score; Back returns to that week |
| Office weekly card "Box score" | Office | Box score; Back returns to the Office |
| News game-result headline | Office | Box score; Back returns to News |
| Tournament bracket score | Same exposure | Marked as a read the same way |
| Team page schedule (another team's page) | Results there are plain text, not links | Unchanged (question 2) |
| The post-game flow page (no `return_url`) | Guarded | Still guarded (tested) |

**Why my first click did not reproduce it.** The season harness quick-sims the user's games, and the engine does not report those as final (they stop in quarter 1). Only a game played through four quarters trips the guard, which is what a player does.

**The fix.** The app already has a rule for this: a box score opened to read carries `return_url` (Practice Squads links already did). Those five links now carry it (`data-return`, which GOBNav fills in on the click), and `box-score.js` skips the guard when it is present. Back on such a box score returns to the tab you came from; it used to force the Office.

**Not staging lag.** The guard, and links without `return_url`, are both on develop today.

**Tests.** Recorded responses of that real game (`fixtures/boxscore-real-game.json`): click the result on Team › Schedule, League › Schedule, the Office card and News, and land on the box score and stay there; Back returns to the schedule; the flow page with no `return_url` is still sent to the Office.

## Item 5: Office "attribute chips group, order, and cap"

Run alone ×5 on develop f56d9ec29: 5 of 5 pass. But the failure as reported (expects 5 rows at 1920, gets 3) is real and I reproduced it on demand.

| | |
|---|---|
| Cause | The Office picks its row caps from the `.gob-1920` class. The shell adds that class from a dynamic import, which can land after the Office has rendered. When it does, a 1920 window gets the 1280 caps (3 weekly rows instead of 5; also 5 movers instead of 8, 8 recruits instead of 12) and nothing re-renders. |
| Reproduction | New test: hold `gobDensity.js` back 1.5s at 1920. On develop it shows 3 rows, exactly as reported. |
| Verdict | Product bug, not a bad test. No product decision needed. |
| Fix | `officeHome.js`: until the class lands, the caps read the same media query the shell binds. Once it lands, the class wins, as before. |
| After | Both tests ×5: 10 of 10 pass. |

## Item 3: where "HC Traps" stays

| Surface | Now |
|---|---|
| Playbook report section heading | Half-Court Traps |
| Box score, Special Situations line | Half-Court Traps: (fits with three-figure counts) |
| Set Lineup, playbooks modal section | Half-Court Traps |
| `court.html` (two stat-table rows, lines 4622 and 4836) | Still "HC Traps". Not edited: audit is working on court screens. |

Playbooks and the Scouting Report already said "Half-Court Traps".

## Questions for Jamie

1. **Box score chrome.** A box score opened from a schedule, the Office card or News now shows the browse chrome (the rail, with League highlighted) instead of the bare post-game page, because that is what `return_url` means in this app. Say if you want the bare page for any of them.
2. **Team page schedule.** On another team's page the results are plain text. Do you want them to be box-score links too?
3. **Desktop only, pre-existing.** After visiting a box score on the desktop build, the Office URL keeps `game_id` and `mode` in its query (the session context absorbs them). I saw no effect, and left it.

## Things to know

| Topic | Note |
|---|---|
| Migration gate | My first version of the item 7 fix added three URL reads and failed Gate B. I did not allow-list them; the links use `data-return` and GOBNav instead. Gate B is back to 134 lines in 43 files. |
| Set Lineup | The rename is one label constant in `set-lineup.js`; the modal itself is untouched. |
| Practice Squad report page | A legacy page with inline styles and no tokens. The pair spacing there is plain pixel padding; no colour was added. |
| Staging | Read-only only (`connect_script_database(target="gob-staging", access="read")`). Nothing written. No staging data is committed: both fixtures are from my own offline season. |
| Scratch season | A private offline engine on port 8791 with a scratch SQLite save. It had no remote database connection (checked with `lsof`). Stopped. |
| Top strip | "Week 27" is still clipped above the tier emblem in tournament weeks (visible in the Tournament shots). Top strip is audit's. |

## Files

| Area | Files |
|---|---|
| Item 1 | `cut-players.html`, `cut-players.js`, `cut-players.css`, `training-squad-report.html`, `training-squad-report.js` |
| Item 2 | `js/shared/gobStore.js` |
| Item 3 | `playbook-report.html`, `box-score.js`, `set-lineup.js` |
| Item 4 | `Styleguide.md` |
| Item 5 | `js/shared/officeHome.js` |
| Item 6 | `js/shared/views/teamAttributesView.js`, `css/gob-views.css` |
| Item 7 | `box-score.js`, `js/shared/views/teamScheduleView.js`, `leagueScheduleView.js`, `tournamentView.js`, `newsView.js`, `js/shared/officeHome.js` |
| Docs | `UX_System.md` (client store rule, box score link rule, Team Attributes) |
| Tests | `tests/e2e/tables-followups.spec.js` (new), `tests/e2e/fixtures/tournament-real-season.json` and `boxscore-real-game.json` (new, both recorded from the real offline season), `tests/e2e/office-frontend.spec.js` (one new test), `tests/test_tournament_browse.py` (one new test), `tests/e2e/t2-roster.spec.js` (the arrows assertion now asserts none) |

No Python product code changed.

## Tests

New tests fail on the old code: with the product files stashed, the pairs tests, the three rename tests, the three Tournament tests, the Office race test, the four box-score link tests and the arrows test all failed. The flow-page guard test passes on both, by design.

Gates on the final merged tree (a4cc768ba = branch + `origin/develop` a4285e7e8; develop re-fetched after the run and had not moved). Every gate ran after items 6 and 7 were in, so the full Playwright run covers them too.

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4368 passed, 14 skipped, 108 xfailed, 2 xpassed. No FAILED / ERROR. |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | exit 0 (Gate A 0 imports; Gate B 134 lines in 43 files, unchanged) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | 988 tests: 969 passed, 19 skipped, 0 failed (17.3 min). Nothing to re-run. |

The two XPASS are the same two as on `polish/tables-league`, outside this branch's area: `test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference` and `test_settings_application_to_gameplay.py::…::test_settings_loaded_and_applied_to_gameplay`. The known-failures list is untouched.

Of the 19 skips, 2 are my scratch spec (below) and 1 is the `t3-detail` offline-save test, which skips itself when no desktop engine is running on port 8766 (it failed for that reason on the last branch's run; nothing was running this time).

## Shots

`reports/tables-followups/`, all at 1280.

| Item | Files |
|---|---|
| 1 | `after-assign-practice-squad`, `after-practice-squad-report-changes`, `after-practice-squad-report-absolute` |
| 2 | `before-tournament-real-week-27` (the old store: the error card), `after-tournament-real-week-27`, `-28`, `-35` |
| 3 | `after-playbook-report-half-court-traps`, `after-box-score-half-court-traps`, `after-set-lineup-half-court-traps` |
| 6 | `after-team-attributes-no-arrows` |
| 7 | `after-box-score-from-team-schedule` |

## Left behind

- `tests/e2e/zz-tl-debug.spec.js`: my scratch spec (it skips itself unless an env var is set). Untracked, not committed; deleting files is blocked for me here, so it is yours to remove.
- `reports/tables-followups/before-tournament-real-week-30-1280.png`: an early before shot drawn from the staging franchise's payload. Untracked and not committed, for the same reason.
