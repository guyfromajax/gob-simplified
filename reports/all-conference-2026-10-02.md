# All-Conference teams — 2026-10-02

Branch `feature/all-conference`, from `origin/develop` b24564e67. Develop had not moved when the gates started; it moved while the full suite ran (f5bc9b66f: `polish/player-dev-grid`, `polish/office-followups`). That develop merges cleanly and the only file both touched is `UX_System.md` (different paragraphs), so I did not re-run the suite for it. Final tree: 041e01db6 plus this report.

**Status: ready for review.** Built as asked, with the two answers you gave on the way (Trophy Case: data paths only; team part: win percentage straight). Two things to know and two questions at the end.

## Your three answers, applied

| | Answer | Done |
|---|---|---|
| 1 | Keep "Class strength" | Nothing to change. |
| 2 | Drop the "Week 26" line under the final All-Americans story | Done. "end of the regular season" in a headline now counts as naming week 26, so neither that story nor the All-Conference final carries the line. |
| 3 | Keep the card copy | Nothing to change. |

## The "IDA upset Lancaster 20-14" line

It is real stored data, from the scratch offline season, and the score is low because of the **test harness, not the sim**.

| | |
|---|---|
| Game | `6ac0138292973bedadff26cd`, week 9, Lancaster (the user's team) at IDA, on my scratch save (franchise `6abfdc26…`). |
| Stored game | quarter 2, clock 0:00, `is_final: false`, score IDA 20, Lancaster 14. A halftime score. |
| Why | `scripts/ws2_loopback_season.py` plays the user's game with one `POST /api/simulate-quarter` (`full_sim`, "sim rest of game"). That call returned at halftime (the harness log shows it took 2.1 s), and the harness then closed the week with the score on the board (`finish_open_week`). So every harness-played Lancaster game on that save is a half-game score (18-16, 26-19, 20-14). The one game I played to the buzzer by hand (63-58) is full length. CPU-against-CPU games are full games. |
| Sim | Not touched. Nothing here says anything about the engine. |

The fixtures recorded from that save (`boxscore-real-game.json`'s week-1 and week-2 rows, `upset-report-real-stories.json`'s IDA line) carry those half-game scores. They serve their purpose (links and story shapes), but they are not scores to reason about.

## What All-Conference is

| | |
|---|---|
| Teams | First and second team per conference, one player per position (PG, SG, SF, PF, C). |
| Position | The listed position, as All-American: the training position on the user's team, the best position rating elsewhere. |
| Compared against | The conference's own players only. Each conference is scored on its own, so the attribute and stat parts are relative to that conference's position groups. |
| Score | The All-American scorer: same attribute and stat weights, same ramp (week 1: ratings only → week 26: 70% stats, 30% team), same 70%-of-games rule and defensive-attempts floor. |
| Team part | The team's **conference win percentage** (conference wins over conference games, regular season), as you chose. Both teams in the same conference make a conference game; ties count for neither side. This was not tracked; `franchise_standings.conference_records` now derives it from stored results. |
| Timing | Projected weekly from the preseason, on the same reads as All-American (command center and Awards). Locked after week 26: the first read after week 26 completes writes the final. No tournament bonus. |
| Final second team | Rank 2 or rank 3 by a seeded coin (franchise + season + conference + position), decided at the final only. Projections show rank 2. Rank 3 is stored on the projection for the coin and never sent. |
| Hidden | The response carries status, label, week, the user's conference, the conference labels and the two teams per conference, each pick cut to who, team, year, position, rating, games and stat line. No weights, scores, ranks, bonus or alternates. CH is never on a pick. |

**Not a fork.** `score_players` gained one optional argument (`team_scores`, a 0–100 value per team in place of the national rank); `select_teams`, `_pick`, `_team_lines`, `public_teams`, the ramp and the games rule are the All-American functions. The seeded coin is one shared helper; the All-American third-team coin hashes the same string as before, so stored finals do not move.

## Awards page

- An **All-Conference** block under the All-American teams: its own head ("Projected All-Conference" / "All-Conference", with the plain status), a row of the sixteen conferences (A1 … H16) in the app's segment control, then the first and second team in the same table as above.
- The user's conference is the default and is cued ("Yours"). Switching repaints the block only; the choice is remembered for the session.
- From week 27 the block says "Final" while the All-American head still says "Not final" (that final comes at week 35).
- Nothing on the page is green, orange or gold beyond the RT ramp.

## News

Stories for the user's conference only, type `all_conference`:

| Week | Headline | "Week N" line |
|---|---|---|
| 1 (preseason) | "Preseason All-Conference A2 teams" | Shown ("Week 1") |
| 7, 13, 19 | "Projected All-Conference A2: week 7" | No |
| 26 (the final) | "All-Conference A2: end of the regular season" | No |

Names only (position, player, team, year), as the All-American stories. A franchise first seen mid-tournament locks what it has and gets no late story.

## Trophy Case and career

As you chose: the data paths All-American uses. User-team picks on the final are appended to the coach's trophy log (kinds `all_conference_1`, `all_conference_2`, one entry per player, idempotent) and tagged in the season review's Best Players and Awards (`all_conference` beside `all_american`; the Awards sub-line names both when both appear). A player on an All-American team and an All-Conference team carries both.

**Gap, flagged:** the Trophy Case page draws titles, milestones and season records. It draws neither All-American nor All-Conference entries, though both are in its data.

## Decisions I made (say if any is wrong)

| Decision | Why |
|---|---|
| The whole response carries all sixteen conferences (about 32 KB). | The picker switches instantly and the read is cached with an ETag. |
| Conference games are regular-season games only (weeks 1–26). | The score locks after week 26 and the tournament brackets are not conference play. |
| A franchise first seen after week 26 (no projection stored yet) locks a projection built from stats to date, which include tournament games, and gets no late story. | The same rule All-American applies to its freeze. |
| The second-team coin's two candidates are the week-26 ranks 2 and 3. | "Decided at the final only": the projection shows rank 2 until then. |

## Questions for Jamie

1. **Trophy Case page.** Should it draw All-American and All-Conference honours? Today it draws neither (above).
2. **Preseason story week line.** "Preseason All-Conference A2 teams" keeps "Week 1" under it, like the preseason All-American story. Drop it on both?

## Things to know

| Topic | Note |
|---|---|
| Reads | The first command-center or Awards read after a week advance now also builds the All-Conference projection: one more pass over the franchise's players (a logged `[ALL-CONFERENCE]` line with its time), once a week. |
| Week completion | Not touched. No sim, finalize, `cpu_week_pool` or `sim_rng` change. |
| Stored size | A projection stores 16 conferences × 15 picks (first, second and the rank-3 alternates) once a week; the final 16 × 10. |
| Real data | The real scratch save (week 10) built a projection on its first read: sixteen conferences, the user's conference A1 by default, no formula key in the response. `after-awards-all-conference-real-*.png` is that payload. There is no real final yet (the save is at week 10), so the final shot is the spec's fixture. |
| One pytest wobble | One early combined run of five test files had a single failure that two immediate re-runs and the full suite did not reproduce; I could not name the test. |
| Scratch season | The private offline engine on port 8791 with its scratch save. Stopped. Nothing touched staging or production. |

## Files

| Area | Files |
|---|---|
| Server | `BackEnd/utils/all_american.py` (All-Conference section; `score_players(team_scores=)`, `seeded_coin`, `load_league` conferences), `BackEnd/utils/franchise_standings.py` (`conference_records`), `BackEnd/utils/trophy_log.py`, `BackEnd/utils/career_data.py`, `BackEnd/api/franchise_routes.py` (`_ensure_all_conference` on the two reads) |
| Page | `js/shared/views/awardsView.js`, `css/gob-views.css`, `js/shared/views/newsView.js` (the week line), `js/shared/seasonPeak.js` (tags) |
| Docs | `End_Of_Season_System.md` (All-Conference logic, stored keys, tunables), `UX_System.md` (Awards), `News_System.md` |
| Tests | New `tests/e2e/all-conference.spec.js`; new tests in `tests/test_all_american.py` (records, scorer, per-conference comparison, team part, weekly then lock, the coin, payload, stories, mid-tournament, trophies and career, the route); `tests/e2e/news-followups.spec.js` (week-line rows); `tests/test_browse_rev.py` (one more stub) |

## Tests

New tests against the code before this branch (product files stashed, then restored): 24 pytest tests fail; 4 e2e tests fail (the three All-Conference page tests and the "Week N" table). The "no All-Conference data" page test passes on both, by design.

Gates on the final tree (041e01db6 = branch on `origin/develop` b24564e67; develop moved to f5bc9b66f during the Playwright run, see the top):

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | 4468 passed, 14 skipped, 108 xfailed, 2 xpassed. No FAILED / ERROR. |
| `tests/test_all_american.py` alone | 83 passed |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | exit 0 (Gate A 0 imports; Gate B 133 lines in 43 files) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | 1219 tests: 1173 passed, 46 skipped, **0 failed** (21.8 min). Nothing to re-run. |

The two XPASS are the same two as on the earlier branches, outside this branch's area. The known-failures list is untouched.

## Shots

`reports/all-conference/`, at 1280 and 1920: `after-awards-all-conference-real` (the real week-10 projection), `after-awards-all-conference-projected` (fixture: your team's row on the first team), `after-awards-all-conference-final` (fixture: "Final" under All-Conference, "Not final" above).

## Left behind

- `tests/e2e/zz-tl-debug.spec.js`: my scratch spec, untracked and uncommitted (it skips itself). Deleting files is blocked for me here.
