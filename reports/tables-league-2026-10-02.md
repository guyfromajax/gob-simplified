# Tables and League polish (S1–S16) — 2026-10-02

Branch `polish/tables-league`, from `origin/develop` b3eb1fb25. Merged `origin/develop` 6ef3d58df before the gates (merge commit cd44969f9; one doc conflict in the UX_System section map, resolved as develop's Player Training row plus the Practice Squads move).

**Status: ready for review.** 15 of 16 items done. S12 is not changed: the tab is already wired on develop and I could not reproduce the fault (question 1).

## Item by item

| # | Item | Status | What shipped |
|---|---|---|---|
| S1 | Attribute pairs | Done | Six pairs, SC SH / ID OD / PS BH / RB ST / AG ND / IQ FT. The two values of a pair sit against their shared edge; the between-pair gap is the old one; WT to SC is wider. Row zebra and pair shade kept. On Team › Roster, the team page roster and news story roster tables. Rows still 44px. |
| S2 | Stat families | Done | Player Stats, Team Stats, Standings, Rankings: tight inside a family, a gutter between families. A wide card puts its slack in the gutters, never inside a family. |
| S3 | Rank beside the title | Done | "Offense (1st of 128)". |
| S4 | Team Attributes order | Done | Columns read down: Shooting, Rebounding, Chemistry / Offense, Defense, Discipline / Fast Break, Fast Break Defense, Fight / P/T Offense, P/T Defense. |
| S5 | Practice Squads to League | Done | League sub-tab "Practice Squads", last in the row. Gone from Team. The Varsity / Practice Squad segment on Team › Roster is untouched. See question 3. |
| S6 | Team pages | Done | Roster above Schedule. Full roster, all twelve attributes. Attributes / Stats segment in the roster card; both sort from their headers. Schedule is Results and Upcoming side by side. |
| S7 | "1 points over budget" | Done | "1 point over budget" / "2 points over budget". |
| S8 | Scouting Report | Done | Pos is the first column, left of the headshot (both modes). HT and WT after YR. "Spider Chart Comparison" under the plays: your team left, opponent right. |
| S9 | Standings layout | Done | Eight regions stacked, sister conferences side by side, your region first, your conference on the left. Card under 640px drops DIFF and its pill; region row under 1060px stacks (and DIFF returns). |
| S10 | Standings spacing | Done, with a question | Rankings has exactly the columns you listed, so it is done there as written. Standings has no Last Week column; it got the same rule on its own columns. See question 2. |
| S11 | Leaders, way back | Done | "← Leaders" bar above the full list, the same bar the team and player pages use. |
| S12 | Tournament brackets | **Skipped: cannot reproduce** | Test added. See question 1. |
| S13 | "Scheduled" container | Done | An unplayed regular-season game has no footer. Played games keep "Final" and the box score; tournament games keep their round. |
| S14 | Week 30 byes | Done | A bye is a card in the game style: team on top, "Bye" underneath. The week reads region by region, A to H. Needed one server field (below). |
| S15 | News | Done | One section per week ("Week 12 · 7 stories"). Three columns at 1920, two at 1280, as before. The card no longer repeats the week. |
| S16 | Recruiting Results | Done | "Your class" first. Then every conference as one full-width card: eight teams, two rows of four, highest class score first. Order: yours, sister, then A1, A2, B3 … |

## Questions for Jamie

1. **S12, what did you see?** On develop the Tournament tab already draws the bracket: the view, the route, the sub-tab, `brackets.html` and the bracket-reveal "Full bracket" link all reach it. The before shot (`before-s12-tournament-*.png`) is develop, drawing a Week 27 bracket in the exact shape the server stores at the draw (unplayed, no scores, later rounds empty). The older spec only covered played brackets, so I added that case as a guard. Which week, which build (web or desktop), and what was on screen: an empty tab, "This bracket has not been drawn yet", the lock, or a link that went nowhere?
2. **S10: Standings or Rankings?** Your groups, (Team, W, L), (PF, PA), Last Week, Next Week, are Rankings' columns. Standings has #, Team, W, L, PCT, PF, PA, DIFF, STRK, NEXT. I did Rankings as written and gave Standings (#, Team, W, L, PCT), (PF, PA, DIFF), STRK, NEXT. Do you want Last Week / Next Week added to Standings? At 1280 two-up there is not room for both and DIFF.
3. **S5: "It shows every team's practice squad."** I read that as why it belongs in League. The view is unchanged: the regional practice-squad league (five tiers, every region, schedule, brackets). If you meant a new list of every varsity team's practice-squad roster, that is a new view and I have not built it.
4. **S1: two rosters not changed.** Assign Practice Squad (`cut-players`, week 1) and the Practice Squad training report still list the twelve attributes flat, in the old AG-before-ST order. They are flow pages on a different table system. The standalone roster page (`team-roster-view.html`) already pairs them. Say if you want those two done.

## Things to know

| Topic | Note |
|---|---|
| Server change (S14) | `GET /franchise/schedule/week` now returns `byes` (week 30 only: `{team, region, is_user, tournament_context}`) and a `region` on each game, and sorts week 30 by region. `BackEnd/utils/schedule_browse.py` only. A bye is a team in a region `final` and in no `round1`. Not sim, finalize, cpu_week_pool or sim_rng. |
| Shell file (S5) | `gobShell.js`: the sub-tab list and section map only (four lines). No top-strip code touched. |
| Class score (S16) | The signed recruits' RT, summed: the number the Signing Day boards already show. The score is printed beside each team so the order is legible. A team that signed nobody still has its place ("No signings"). |
| Dev focus (S6) | Only stored for your own players, so another team's roster has no Dev focus column rather than an empty one. |
| Player Stats families (S2) | Kept as they were: PTS sits in Scoring with FGM FGA FG%. Team Stats' "Other" (AST F TO SCRA SCR%) is unchanged. |
| Top strip, weeks 27+ | "Week 27" is clipped above the tier emblem (see `after-s12-tournament-1280.png`). Top strip is audit's; not touched. |
| Team Attributes ties | UX_System said a tie reads "T-34th"; the code never did, and a test asserts no "T-". Left as is. |
| Dead code | The compact five-attribute roster path in `rosterView.js` has no caller now. Left in place (no drive-by). |
| Auth / ownership | Not touched. |

## Files

| Area | Files |
|---|---|
| Views | `js/shared/views/`: `rosterView`, `teamView`, `playerStatsView`, `teamStatsView`, `standingsView`, `rankingsView`, `leadersView`, `leagueScheduleView`, `newsView`, `teamAttributesView`, `scoutingView`, `practiceSquadView` |
| Shared | `js/shared/newsStory.js`, `gobViews.js`, `gobShell.js` (section list) |
| CSS | `css/gob-tables.css`, `css/gob-views.css`, `css/prep-v2-scouting.css`, `recruiting-results-hub.css` |
| Recruiting | `recruiting-hub.js` (plural; results render functions only, not the load path) |
| Server | `BackEnd/utils/schedule_browse.py` |
| Docs | `Styleguide.md` (Tables: column grouping, the pair rule, the family rule), `UX_System.md` |
| New tests | `tests/e2e/tables-league.spec.js`, `tests/e2e/helpers/tablesLeagueFixtures.js`, three tests in `tests/test_schedule_week.py`, two in `tests/e2e/signing-day.spec.js` |
| Tests updated to the new design | `polish-team`, `schedule-views`, `shell-1b`, `t1-tables`, `t2-roster`, `t3-detail` |

`franchise-command-center.css` is untouched (1779 lines, 230 rules).

## Tests

New guards fail on the old code: with the product files stashed, every S-test in `tables-league.spec.js` failed except S12 (which must pass on develop: that is the finding), the singular over-budget test failed, and the three new `test_schedule_week.py` tests failed.

Gates on the final merged tree (cd44969f9 = branch + `origin/develop` 6ef3d58df):

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4316 passed, 14 skipped, 108 xfailed, 2 xpassed. No FAILED / ERROR. |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | exit 0 (Gate A 0 imports; Gate B 134 lines in 43 files, unchanged) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | 933 tests: 916 passed, 15 skipped, 2 failed (18.7 min). Both explained below. |

The two XPASS are not from this branch's area: `test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference` and `test_settings_application_to_gameplay.py::…::test_settings_loaded_and_applied_to_gameplay`. Not checked against develop; the known-failures list is untouched.

Playwright failures, each re-run alone with `--repeat-each=5`:

| Test | Cause | Re-run |
|---|---|---|
| `subtabs.spec.js` "switching, ink, overflow, keyboard, lock, and search" | Mine. It pressed End and expected the locked Tournament tab; Practice Squads is now the last League tab. Test updated (End lands on Practice Squads; the lock is reached from Schedule). No product change. | 5 of 5 pass |
| `t3-detail.spec.js` "the roster header sits under the title on the offline save" | Environment. It only runs when a desktop loopback answers on `127.0.0.1:8766`; another session's was up, and its local database does not hold the franchise id hard-coded in the test, so the page is "This Franchise No Longer Exists" and never reaches the team view. It skips itself when no loopback is running. Not caused by this branch. | 5 of 5 fail while that loopback is up. Its API answers `{"detail":"Franchise not found"}` for the test's franchise id. |

The `subtabs` fix is a test file only, so the full run above still describes the product tree.

Sub-tab order is a choice you can flip: League reads Standings, Rankings, Leaders, Team Stats, Schedule, Tournament, Practice Squads. Tournament is locked until Week 27 and now sits second to last.

## Shots

`reports/tables-league/`, `before-*` on develop and `after-*` on this branch, 1280 and 1920 for every item.

| Item | Files |
|---|---|
| S1 | `s01-roster`, `s01-news-story-roster` |
| S2 | `s02-player-stats`, `s02-team-stats` (Standings and Rankings under S9, S10) |
| S3, S4 | `s03-s04-team-attributes` |
| S5 | `s05-practice-squads` |
| S6 | `s06-team-page` (whole page), `after-s06-team-page-stats` |
| S7 | `s07-over-budget` (the Your Orders rail) |
| S8 | `s08-scouting` (whole page) |
| S9, S10 | `s09-s10-standings`, `s10-rankings`, plus `s09-standings-1100` and `-900` |
| S11 | `s11-leaders-full-list` |
| S12 | `s12-tournament` |
| S13 | `s13-schedule-unplayed` |
| S14 | `s14-schedule-week-30` |
| S15 | `s15-news` (whole page) |
| S16 | `s16-recruiting-results` |

## Left behind

- `tests/e2e/zz-tl-debug.spec.js`: my scratch screenshot spec. Untracked, not committed. Deleting it was blocked by the permission system; it is safe to delete.
- Six `chk-*.mjs` syntax-check copies in `/tmp/claude-501/`, same reason.
