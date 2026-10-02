# All-American redesign — 2026-10-02

Branch `feature/all-american`, from `origin/develop`. Ready for review; not merged.

## Questions first (I did not guess silently: each has a default that is one constant or one function to change)

| # | Question | What I built |
|---|---|---|
| 1 | **What does "week N" mean in the weights table?** "Preseason (week 1, before games)" and "store the week-26 scores" (which must include game 26) cannot both be "the week about to be played". | Week = regular-season weeks **completed**. 0 completed = Preseason, scored at the week-1 row. The week-26 row is after all 26 games. After week 1's game the mix is still 100 / 0 / 0. |
| 2 | **"One player per position per team."** Per All-American team, or per school? | Per All-American team: each of the three teams has one PG, SG, SF, PF, C. A school is not capped. |
| 3 | **"Listed position."** No position is stored for a franchise player. | The position the roster page shows (`leaders_snapshot._roster_position`): CPU teams = best position rating; **your team = Development Focus training position**. So moving a player's training position moves his All-American position. |
| 4 | **How each component gets to 0-100.** The brief gives the scale, not the mapping. | Attributes: min-max within the position. Stats: each stat is distance above the position average as a share of the leader's distance (average or below = 0, leader = 1), then weighted. Team: linear in national rank (1 = 100, 128 = 0). |
| 5 | **Where the weekly update runs.** Finalize was off limits, and the news hook inside it runs before the national-rank update. | On the first command-center (or Awards) read after a week advance. See "Timeline" for what that implies. |
| 6 | **Individual tournament bonus barely separates the top players.** In the simulated season all 15 final picks got +5: the best players are also the best tournament performers. The team bonus did the reordering. | Built as specified. Flagging the effect. |
| 7 | Defensive rate floor. | 5 defensive attempts per team game (130 / 26). Leaders uses 6. One constant. |

## What I built

| Part | Where |
|---|---|
| All selection logic | `BackEnd/utils/all_american.py` (new) |
| `franchise_routes.py` | 4 small touch points, +22 / −62 lines: `_compute_all_american_teams` delegates; `_persist_week_35_awards_if_needed` merges instead of replaces; `command_center_data` calls `ensure_projection` below week 35; `GET /franchise/awards` answers all season. `_season_awards_score` deleted. |
| Awards page | `FrontEnd/static/js/shared/views/awardsView.js`, plus the Awards block of `css/gob-views.css` |
| Docs | `End_Of_Season_System.md` (rules, stored shape, Tunable Constants), `UX_System.md` (Awards view) |

No sim / finalize / cpu_week_pool / sim_rng change. The third-team coin is a SHA-256 of franchise + season + position.

### Fields used

| Component | Field |
|---|---|
| Attributes | `franchise_players_data.position_ratings[listed position]` (the RT number, per franchise, updated by weekly training) |
| Listed position | Derived (question 3). `meta.position` is read first but nothing writes it. |
| Stats | `franchise_players_data.season`: `PTS`, `REB` (or `OREB` + `DREB`), `AST`, `STL`, `BLK`, `DEF_S` / `DEF_A`, divided by `season.GP` |
| Games rule | `season.GP` ≥ 70% of the team's regular-season games (W + L from `franchise.results`, weeks 1-26) |
| Team success | `franchise_team_data.natl_rank` (frozen by the game after week 26) |
| Pool | Active roster: FTD `players` minus `training_squad_players` |
| Tournament line | Season totals now minus the frozen week-26 totals. There is no postseason stat bucket. |

### Postseason bonus and the bracket

The table fits the bracket. The national tournament is the 8 region champions: `round1` is the quarterfinal, **`round2` is the national semifinal**, then `final`.

| Bonus | Read from |
|---|---|
| Conference tournament champion +1 | `conference_tournaments[c].champion` |
| Region tournament champion +2 | `region_tournaments[r].final[0].winner` |
| Reached the national semifinals +2 | both teams of each `national_tournament.bracket.round2` matchup |
| National champion +5 | `national_tournament.champion` |
| Individual +5 / +3 / +1 | Top 10% / 25% / 50% of the position's players with ≥ 2 tournament games, by the same stats score on tournament per-game numbers. One tier. |

A region champion need not be a conference tournament champion (the regular-season #1 also qualifies), so the national champion in the sample got +9, not +10.

### Timeline

| When | What happens |
|---|---|
| Weeks 1-26 | Rebuilt once per completed week, on the first command-center or Awards read after the advance. Every other read is a no-op. |
| Week 26 | The same read freezes each player's score and season totals on his FPD doc (`aa_w26`). |
| Weeks 27-34 | No updates. The page shows the week-26 projection, marked not final. |
| Week 35 | Final = frozen week-26 score + bonus. Computed once, by the existing `_persist_week_35_awards_if_needed`. |

Consequence of question 5: a headless script that never loads the command center gets no weekly update. In the app every advance returns to the Office, which loads it. The loopback season harness does not, so I ran a watcher beside it that loads it once per week.

### Stored shape

`awards.all_american_teams.{first_team, second_team, third_team}` is unchanged and is the **final only**; each pick now adds `position`, `rating`, `rank`, `score`, `components`, `bonus`. The projection is beside it in `awards.all_american_projection`. `trophy_log.py` and `career_data.py` are untouched and tested against the new picks.

### News stories

Type `all_americans`, after weeks 0 (shown as week 1), 7, 13, 19, 26. Week 1: "Preseason All-Americans announced". Week 26 says the teams are not final and tournament performance can still change them. All five published in the simulated season. The News list is untouched, so the type label is its default ("All Americans").

### Online and offline

One code path through the persistence adapter. Tests run on both stores (mongomock and SQLite). The simulated season below ran on the offline path (loopback + SQLite).

## What a franchise already mid-season sees (no migration)

| It is in | It sees |
|---|---|
| Weeks 2-26 | The projection for the weeks completed so far, on its next command-center load. No back-dated stories; the next story is at the next publishing week. |
| Weeks 27-34 | An "End of regular season" projection built from stats that already include some tournament games (stored as `includes_tournament_games`). No late story. Its final uses that as the base, and its tournament line is only the games after that point. |
| Week 35+ with awards stored | Its old picks, unchanged: the final never recomputes. The page shows them without position or score. |
| Week 35 with no freeze at all | A final from season-to-date stats at the week-26 weights, team bonus applied, no individual bonus (`basis: season_to_date`). |

## Added time per week advance

Measured on a copy of the simulated season's save, quiet machine, offline (SQLite), 128 teams / 1,539 active players.

| Step | Time |
|---|---|
| Weekly update, weeks 1-25 (read, score, one franchise write) | median 422 ms (409-621) |
| Week-26 update (adds the freeze: one bulk write of 1,539 player docs) | median 1,011 ms |
| Every other read (already current) | under 1 ms |
| Final at week 35 | median 305 ms |

- It is paid once per week, on the first command-center load after the advance, not inside the advance request.
- During the season run the same load was slower (up to 5 s late in the season, 8.2 s at the freeze), because the harness was already writing the next week to the same SQLite file. Frozen weeks, which do no All-American work, took 0.5-1.5 s in the same conditions.
- **Hosted (Mongo) was not measured**: I did not touch staging. It is two reads (128 team docs, about 1,900 player docs with a projection) and one write. On a full-size league in mongomock the read and score took 76 ms, so the hosted cost is network time for those reads.

## Sample from a real simulated season

One full season on the offline path: `python -m BackEnd.loopback` + `scripts/ws2_loopback_season.py --weeks 35` (real engine, 128 teams, `SEASON_COMPLETE`). Recomputing the final in a separate process gave the same players, scores and third-team ranks.

**Preseason** (franchise week 1, no games). Weights 100 / 0 / 0. Score is the attributes component.

| Team | Pos | Player | School | Score |
|---|---|---|---|---|
| 1st | PG | Jamien Duran | Hyde Methodist | 100.0 |
| 1st | SG | Milton Curtis | Lawrence | 100.0 |
| 1st | SF | Nazir Dahlke | Empire City | 100.0 |
| 1st | PF | Cade Carlson | Lawrence | 100.0 |
| 1st | C | Chauncey Aquaviva | Durham | 100.0 |
| 2nd | PG | Steve Enders | Mahala Alou | 81.25 |
| 2nd | SG | Wilber Cervantes | Two Rivers | 78.75 |
| 2nd | SF | Lester Client | Biloxi | 93.9 |
| 2nd | PF | Kiki Christensen | Crimson County | 100.0 |
| 2nd | C | Dewey Martz | Biloxi | 86.81 |
| 3rd | PG | Ricky Chang | Durham | 78.75 |
| 3rd | SG | Harley Cole | Border Academy | 75.0 |
| 3rd | SF | Carl Miles | Harding Central | 92.68 |
| 3rd | PF | Gage West | Melbourne Americas | 90.91 |
| 3rd | C | Brycen Nathanson | Rodeo Circuit | 84.62 |

**After week 10.** Weights 30 / 70 / 0. Stats are per game.

| Team | Pos | Player | School | PTS | REB | AST | STL | BLK | DEF% | Attr | Stats | Team | Score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1st | PG | Jamien Duran | Hyde Methodist | 28.3 | 7.9 | 4.8 | 2.8 | 1.4 | 67 | 100.0 | 80.94 | 88.98 | 86.66 |
| 1st | SG | Milton Curtis | Lawrence | 41.7 | 6.5 | 0.9 | 1.7 | 0.6 | 55 | 100.0 | 57.82 | 100.0 | 70.47 |
| 1st | SF | Nazir Dahlke | Empire City | 30.0 | 7.4 | 4.2 | 2.1 | 1.3 | 62 | 100.0 | 74.3 | 83.46 | 82.01 |
| 1st | PF | Gage West | Melbourne Americas | 24.1 | 18.0 | 1.6 | 0.0 | 0.7 | 65 | 90.48 | 64.93 | 81.1 | 72.59 |
| 1st | C | Woodrow Holmes | Cupertino | 19.3 | 13.8 | 1.1 | 0.4 | 1.6 | 82 | 83.33 | 61.87 | 71.65 | 68.31 |
| 2nd | PG | Steve Enders | Mahala Alou | 22.2 | 4.0 | 3.6 | 3.3 | 0.8 | 64 | 80.77 | 54.51 | 69.29 | 62.39 |
| 2nd | SG | Wilber Cervantes | Two Rivers | 33.7 | 4.4 | 2.6 | 1.1 | 1.1 | 66 | 80.25 | 61.33 | 90.55 | 67.0 |
| 2nd | SF | Lester Client | Biloxi | 24.6 | 3.5 | 4.6 | 0.6 | 0.8 | 69 | 94.2 | 57.38 | 76.38 | 68.43 |
| 2nd | PF | Mateo Montgomery | San Jose | 19.4 | 23.4 | 1.4 | 0.4 | 0.7 | 68 | 80.95 | 64.1 | 53.54 | 69.16 |
| 2nd | C | Chauncey Aquaviva | Durham | 22.1 | 14.9 | 0.7 | 0.2 | 1.6 | 67 | 100.0 | 52.98 | 96.85 | 67.09 |
| 3rd | PG | Ernest Jefferson | Templeton-Wesley | 13.8 | 5.0 | 4.4 | 1.3 | 0.9 | 68 | 76.92 | 43.34 | 22.83 | 53.42 |
| 3rd | SG | Salvatore Albotti | Pacific All-Stars | 37.4 | 4.3 | 1.3 | 4.0 | 0.8 | 57 | 77.78 | 56.99 | 92.13 | 63.23 |
| 3rd | SF | Keyode Randall | Grayson Ranch | 25.7 | 3.5 | 2.9 | 1.4 | 1.6 | 57 | 89.86 | 48.89 | 67.72 | 61.18 |
| 3rd | PF | Andre Walters | Falls Academy | 22.0 | 20.6 | 0.7 | 0.8 | 1.0 | 52 | 87.3 | 58.92 | 96.06 | 67.44 |
| 3rd | C | Jagger Sutton | Circus Circus | 26.7 | 17.1 | 0.6 | 0.3 | 0.9 | 70 | 83.33 | 59.42 | 35.43 | 66.59 |

**After week 26 (frozen).** Weights 0 / 70 / 30. Stats are per game.

| Team | Pos | Player | School | PTS | REB | AST | STL | BLK | DEF% | Attr | Stats | Team | Score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1st | PG | Jamien Duran | Hyde Methodist | 25.3 | 6.2 | 5.5 | 3.0 | 1.0 | 63 | 100.0 | 79.94 | 73.23 | 77.93 |
| 1st | SG | Milton Curtis | Lawrence | 38.5 | 5.8 | 2.5 | 1.2 | 0.9 | 57 | 100.0 | 66.09 | 96.06 | 75.08 |
| 1st | SF | Nazir Dahlke | Empire City | 31.0 | 6.3 | 4.7 | 1.7 | 1.6 | 57 | 100.0 | 76.78 | 87.4 | 79.96 |
| 1st | PF | Gage West | Melbourne Americas | 28.9 | 17.6 | 1.3 | 0.0 | 1.1 | 59 | 93.65 | 69.04 | 79.53 | 72.19 |
| 1st | C | Chauncey Aquaviva | Durham | 25.4 | 15.2 | 0.9 | 0.4 | 1.7 | 69 | 100.0 | 66.08 | 97.64 | 75.55 |
| 2nd | PG | Steve Enders | Mahala Alou | 23.4 | 3.8 | 3.7 | 3.4 | 0.8 | 55 | 81.32 | 56.8 | 68.5 | 60.31 |
| 2nd | SG | Wilber Cervantes | Two Rivers | 33.2 | 3.2 | 2.1 | 1.3 | 1.3 | 59 | 83.52 | 57.22 | 88.98 | 66.74 |
| 2nd | SF | Lester Client | Biloxi | 29.7 | 3.2 | 4.1 | 0.6 | 0.7 | 66 | 95.45 | 64.16 | 92.91 | 72.78 |
| 2nd | PF | Charles Amiriabi | IDA | 24.0 | 15.0 | 1.0 | 0.6 | 1.3 | 50 | 84.13 | 57.58 | 100.0 | 70.31 |
| 2nd | C | Woodrow Holmes | Cupertino | 19.4 | 11.8 | 1.2 | 0.2 | 1.8 | 74 | 86.02 | 57.09 | 74.02 | 62.17 |
| 3rd | PG | Shawn Dunlap | Toronto Limited | 14.4 | 3.0 | 6.0 | 3.5 | 0.8 | 57 | 73.63 | 48.81 | 77.17 | 57.32 |
| 3rd | SG | Ethan Krueger | Huntington Canyon | 33.5 | 1.9 | 1.9 | 1.0 | 0.9 | 54 | 78.02 | 43.91 | 95.28 | 59.32 |
| 3rd | SF | Hayden Holmes | Kenton | 24.5 | 3.2 | 2.3 | 1.3 | 2.3 | 61 | 68.18 | 54.16 | 93.7 | 66.02 |
| 3rd | PF | Andre Walters | Falls Academy | 22.8 | 17.5 | 0.7 | 0.5 | 1.2 | 53 | 87.3 | 54.0 | 90.55 | 64.97 |
| 3rd | C | Dewey Martz | Biloxi | 20.6 | 16.2 | 0.8 | 0.3 | 1.2 | 60 | 89.25 | 45.9 | 92.91 | 60.0 |

**Final** (after the National Tournament). Week-26 score + bonus.

| Team | Pos | Player | School | Rank | Week-26 score | Team bonus | Individual bonus | Final |
|---|---|---|---|---|---|---|---|---|
| 1st | PG | Jamien Duran | Hyde Methodist | 1 | 77.93 | +0 | +5 | 82.93 |
| 1st | SG | Milton Curtis | Lawrence | 1 | 75.08 | +5 | +5 | 85.08 |
| 1st | SF | Nazir Dahlke | Empire City | 1 | 79.96 | +0 | +5 | 84.96 |
| 1st | PF | Charles Amiriabi | IDA | 1 | 70.31 | +5 | +5 | 80.31 |
| 1st | C | Chauncey Aquaviva | Durham | 1 | 75.55 | +0 | +5 | 80.55 |
| 2nd | PG | Timmy Robertson | Crimson County | 2 | 54.66 | +9 | +5 | 68.66 |
| 2nd | SG | Wilber Cervantes | Two Rivers | 2 | 66.74 | +1 | +5 | 72.74 |
| 2nd | SF | Lester Client | Biloxi | 2 | 72.78 | +3 | +5 | 80.78 |
| 2nd | PF | Gage West | Melbourne Americas | 2 | 72.19 | +0 | +5 | 77.19 |
| 2nd | C | Dewey Martz | Biloxi | 2 | 60.0 | +3 | +5 | 68.0 |
| 3rd | PG | Shawn Dunlap | Toronto Limited | 4 | 57.32 | +0 | +5 | 62.32 |
| 3rd | SG | Ethan Krueger | Huntington Canyon | 4 | 59.32 | +1 | +5 | 65.32 |
| 3rd | SF | Keyode Randall | Grayson Ranch | 4 | 65.92 | +0 | +5 | 70.92 |
| 3rd | PF | Kiki Christensen | Crimson County | 3 | 60.83 | +9 | +5 | 74.83 |
| 3rd | C | Giovani Stevenson | Swoosh | 4 | 59.44 | +0 | +5 | 64.44 |

In the final the third team took rank 4 at PG, SG, SF and C and rank 3 at PF (the coin for this franchise and season). Second-team PG went to the national champion's point guard on a +14 bonus.

## Awards page

Shots at 1280 in `reports/all-american/`, from the season above:

| Shot | State |
|---|---|
| `awards-preseason-1280.png` | Preseason: no stat columns, because nobody has a line yet |
| `awards-week-10-1280.png` | After week 10 |
| `awards-week-26-1280.png` | End of regular season, marked not final |
| `awards-final-1280.png` | Final, with the Bonus column |
| `awards-*-lower-1280.png` | The same pages scrolled to the third team |
| `awards-projected-fixture-1280.png` | The test fixture (shows the navy "yours" row) |

- The preseason and week-10 shots have no RT column: the season server started before I added `rating` to each pick. The week-26 and final payloads were rebuilt from the save with the current module (checked identical apart from that field).
- Colour: RT uses the canonical ramp; position and score are neutral; your team's row is navy. Nothing is green, orange or gold.
- Stats show per game. The stored final used to hold season totals.

## Tests

| File | Covers |
|---|---|
| `tests/test_all_american.py` (47 cases, both stores) | Weights at weeks 1, 5, 10, 18, 26; one per position per team; the 70% games rule; the DEF floor; team and individual bonus; final = week-26 score + bonus; third team stable across recomputes and rank 3 in projections; freeze through the tournaments; stories at 1 / 7 / 13 / 19 / 26; mid-season franchises; the stored shape against `trophy_log` and `career_data` |
| `tests/e2e/all-american-awards.spec.js` | The Awards page: projected, preseason, final, empty |
| `tests/test_browse_rev.py` | One existing test now stubs the projection so it still tests the reconcile write alone |

## Gates (final tree = this branch merged with `origin/develop` `4046ff480`)

The merge had one conflict, a one-line doc clash in `UX_System.md` (the empty-states list), resolved by keeping both edits.

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | exit 0: **4364 passed, 14 skipped, 108 xfailed, 2 xpassed** (248s) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | exit 0 (Gate A 0 imports; Gate B 134 lines in 43 files, unchanged) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | **926 passed, 17 skipped, 1 failed** (4.5 min) |

- The 2 XPASS are the same two as on develop before this branch (`test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`, `test_settings_application_to_gameplay.py::...::test_settings_loaded_and_applied_to_gameplay`). Not from this work.
- The Playwright failure: `fcc-fresh-after-game.spec.js:256` (after a game in an invite week). Its sampler of Advance states saw nothing in the full run. Re-run alone with `--repeat-each=5`: **5 / 5 pass**. A load flake in a spec that arrived with the develop merge; it does not touch Awards.
- The lock was held by another agent's serial run when I got to it; mine waited and ran after.

## Unsure about

- Every row of "Questions first".
- Hosted timing is reasoned, not measured.
- `tests/conftest.py` overrides auth for every test. Nothing here touches auth or ownership; `GET /franchise/awards` keeps its existing ownership check.
- Scratch files from the season run (save, logs, watcher) are in the session scratchpad, not in the repo.

