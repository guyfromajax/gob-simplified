# Minutes units — 2026-09-28

Branch `fix/minutes-units` off `origin/develop` (`a8eac84ce`). Game box `MIN` is seconds (`stat_updater.played_in_game` / `season_minutes`). Season and career `MIN` are unrounded minutes (`seconds / 60`). The box score shows whole minutes with `floor(seconds / 60)` (`FrontEnd/static/js/shared/formatMinutes.js`, and `player_em.box_minutes`).

## Audit

### a. `{player_min}`

`pgpc_template_substitution.build_pgpc_substitutions` reads the slot player's game `stats["MIN"]` and used to stringify it. That value is the box-score seconds (the same row `stat_updater` divides by 60). The question bank says "played only {player_min} minutes", so the old string was seconds. Confirmed wrong.

### b. `limited_minutes_high_rt`

The bank (`press_conference_questions.py`, `benched_star_01`–`04`) sets `filters.max_minutes` to 20 and `min_rt` to 75. Nothing else evaluates that condition.

`get_qualifying_pgpc_questions` calls `_condition_holds`. For `limited_minutes_high_rt` it took `_stat_row(row, "MIN")` (the raw game integer) and compared it to `max_minutes`. A player who played 19 minutes is stored as 1140, and `1140 <= 20` is false, so the trigger did not fire. Confirmed wrong: seconds compared with a minute threshold.

`pgpc_player_slot` `benched_star` sorts by raw `MIN`. Order is the same in seconds or minutes, so that picker was left alone.

### c. Tutorial

`tutorial_rosters.py` listed MIN as design minutes (PG 21, team sum 140 for Q1–Q3). `_row` wrote that number straight into `stats["game"]["MIN"]`. `tutorial_game._apply_stat_overlay_to_team` copies the overlay onto the live game stat block and does not rescale it.

Shared readers of that field, live and tutorial:

| Reader | Assumes | Tutorial minutes in that field |
|---|---|---|
| `set-lineup.js` `formatMinutesRosterStats` | seconds, floor / 60 | showed 0 |
| `box-score.js` `formatMinutes` | seconds, floor / 60 | showed 0 |
| `office_digest._player_stat_line` then `officeHome.wholeMinutes` | seconds, floor / 60 | showed 0 |
| `player_em.box_minutes` | seconds, floor / 60 | EM saw 0 minutes |
| `stat_updater.season_minutes` / practice-squad rollup | seconds / 60 into season minutes | would store a fraction of a minute |
| `turn_manager` adds elapsed seconds onto `stats["game"]["MIN"]` | seconds | 21 plus a few seconds of Q4 |
| PGPC `{player_min}` and the trigger, before this fix | treated the number as minutes | accidentally close to the design minutes |

No tutorial page prints `MIN` as already-minutes. The lineup and the box score already divide by 60. Converting the overlay to seconds is the source fix. The tutorial lineup then shows the design minutes (21, 24, …) instead of 0. No tutorial HTML or JS was edited. The sim engine was not edited; it already adds seconds.

### d. Other game-level MIN readers

| Reader | Class |
|---|---|
| `formatMinutes.js`, `box-score.js`, `set-lineup.js` | seconds-correct (floor / 60) |
| `officeHome.wholeMinutes` on the digest `min` (copied from game `MIN`) | seconds-correct |
| `player_em.box_minutes` | seconds-correct |
| `stat_updater.season_minutes`, `practice_squad/stats.py` | seconds-correct (season total is minutes) |
| `pgpc_template_substitution` `{player_min}` | was wrong; now floor minutes |
| `pgpc_qualification` `limited_minutes_high_rt` | was wrong; now minutes vs minutes |
| `tutorial_rosters` overlay | was minutes in a seconds field; now seconds |
| `pgpc_player_slot` `benched_star` sort | seconds-correct (order only) |
| Season tables: `franchise-command-center.js` player stats, `rosterStatsRenderer.js`, `player-detail.js`, `scoutingReport.js` | minutes-correct (`Math.round` of season minutes) |
| `t3_detail.stat_line` `min_per_game`, `playerStatsView`, `playerView` | minutes-correct (season total / GP, formatted as sent) |

`franchise-command-center.js` around the `Math.round(stats.MIN)` cell is `getPlayerSeasonStats`, not the game box.

## Fix

`display_minutes` in `BackEnd/utils/minutes_display.py` is `floor(seconds / 60)`, the same whole minute the box score shows (`Math.floor(seconds / 60)`). `stat_updater` re-exports it beside `season_minutes` (that one stays unrounded `seconds / 60` for season totals). `box_minutes` calls it.

`{player_min}` is `str(display_minutes(stats["MIN"]))`. 720 seconds renders `"12"`.

The trigger compares `display_minutes(MIN)` to `max_minutes`. 19×60 fires `benched_star_01`. 21×60 does not. 20×60 still fires (`<=`).

Tutorial `_row` stores `minutes * 60`. The import-time sum check expects 8400 seconds. The literals in the tables are still the design minutes.

## Tests

`tests/test_minutes_units.py`: display floor, `{player_min}` 720 → `"12"`, trigger at 19 minutes and not at 21, tutorial stored seconds match the design minutes through `display_minutes`. Related PGPC, slot, and EM tests still pass (55 in that run).

## Suite

Full Playwright suite, UX §8, workers=1, port 8010 (not 8070–8076): 501 passed, 2 skipped, 7.3m, exit 0. The web server on 8010 stopped with the run.

STATUS: COMPLETE
