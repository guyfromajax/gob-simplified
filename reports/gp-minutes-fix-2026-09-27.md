# GP and MIN accumulation fix — 2026-09-27

Branch `fix/gp-minutes` (off `develop` 9684b8dbf), worktree `~/gob-stats`. Fix commit **`f8b7b6640`**. Develop has since moved to 38e1506a4, but none of those commits touch `BackEnd/` or `FrontEnd/`, so the "before" arm below is the same code as the branch base.

## Result

- A player listed in a box score with **0 game seconds no longer gets season/career GP**. His other stats are all 0, so he adds nothing.
- Season/career **MIN is now unrounded minutes** (`seconds / 60`, a float). The old `// 60` lost the sub-minute part of every game (13:59 became 13; under 60 s became 0). The unit is still minutes. Game box MIN is still seconds.
- The same two rules now apply on every rollup path, including tournament and practice squad.
- Sim perf capstone: only the values placed into the existing `inc_doc` changed. The single FPD `bulk_write`, both claims (`applied_games`, `applied_matchups`), `cpu_week_pool`, `sim_rng`, and the engine are untouched. No new DB round trips.

On a real save (Lancaster, seeded two-week advance), the before and after runs differ **only** in GP and MIN. Exactly 24 season GP drops, matching the 24 zero-second box rows, and every MIN delta equals that player's sub-minute remainders. All other stats are identical across 2,370 players.

## Paths changed

Two helpers in `BackEnd/utils/stat_updater.py` hold the rules:

- `played_in_game(stat_block)`: true only when box `MIN` (seconds) is a number > 0.
- `season_minutes(seconds)`: `seconds / 60`.

| Path | Before | After |
|---|---|---|
| `_finalize_game_impl`, franchise branch (the batched FPD write in `finalize_game`) | `MIN // 60`; GP +1 season and career for every box row | `season_minutes`; GP only if `played_in_game` |
| `_finalize_game_impl`, tournament branch | `MIN // 60`; season GP 1 for every row | same rules |
| `rollup_game_to_franchise` (legacy franchise doc) | `MIN // 60`; GP +1 season and career | same rules |
| `apply_stats_from_summary`, tournament branch | `MIN // 60`; season GP 1 | same rules (see the dead-code note below) |
| `BackEnd/practice_squad/stats.py` `apply_ps_game_stats` (`ps_season_stats`) | `MIN > 300 ? MIN // 60 : MIN`, so a player with 5 minutes or less got his **seconds** credited as minutes; GP whenever any stat was non-zero | `MIN` and GP only if `played_in_game`, MIN via `season_minutes` |

Other GP/MIN writers I searched for and found none that do arithmetic:

- `backfill_franchise_player_stats` only copies existing totals.
- The EOS rollover (`franchise_manager.py`, `franchise_routes.py` ~19305) carries `career` forward and zeroes `season`.
- `backfill_ps_season_stats` replays `apply_ps_game_stats`, so it inherits the fix.
- `update_game_stats` writes the per-game box only.
- No script under `scripts/` writes season/career GP or MIN.

## Consumers checked

**Backend (all unchanged; none `int()`-cast MIN, and every GP reader guards `gp <= 0`):**

| Consumer | Reads | Finding |
|---|---|---|
| `leaders_snapshot.py` (snapshot + live scan) | GP (float), no MIN | Unaffected. Rate qualification uses team games (`qualifies(stat, attempts, team_games)`), confirmed. Career FG%/DEF% keep `attempts >= 5 × player GP`, which is now a slightly tighter floor for players with DNP games. |
| `t3_detail.stat_line` / `season_bases` (player-stats route, player detail) | GP, MIN via `_num` → float, `_whole` keeps floats | Unaffected. Per-game is `null` at GP 0 (kept). |
| `team_stats_aggregator.py` | Sums a fixed key set that excludes GP and MIN | Unaffected. |
| `franchise_league_news.py`, `community_highlights.py`, `scouting_utils.py`, `api.py` scouting starters, `franchise_routes.py` top scorer/rebounder | `int(GP)`, guarded | Unaffected. GP stays an integer. |
| `senior_tribute.py` | `career.GP` via `_stat_int` | Unaffected. |
| `recompute_tournament_leaders` | MIN only as a sort tiebreaker | Unaffected (float tiebreak is fine). |
| pgpc qualification / slot / template substitution, `office_digest._player_stat_line`, `player_em.box_minutes`, `models/player.py` | **Game** box MIN (seconds) | Not season/career data, so unaffected. |

**Frontend:**

| Consumer | Change |
|---|---|
| `views/playerStatsView.js` (Team › Player Stats) | Unchanged. Totals already `Math.round`, per-game one decimal, "—" for null. |
| `views/playerView.js` (drill-in) | Unchanged. `oneDecimal`, "—" for null. |
| `player-detail.js` current-season row | **Changed**: `Math.round(MIN)` (would have printed `412.38333`). |
| `franchise-command-center.js` player stats table | **Changed**: `Math.round(MIN)`. `formatPerGame` is only a sort key, left as is. |
| `js/shared/rosterStatsRenderer.js` | **Changed**: `Math.round(MIN)`. |
| `js/shared/scoutingReport.js` `formatScoutingSeasonStat` | **Changed**: `MIN` case rounds. |
| `training-report.js` `formatTrainingSeasonStat` | **Changed**: `MIN` case rounds. |
| `team-roster-view.js` `trStatValue` | **Changed**: per-game at GP 0 now "—" (was `0`). Sorting maps "—" to 0. |
| `set-lineup.js`, `box-score.js`, `pageLoadOverlay.js`, `officeHome.js` | Game seconds, unchanged. |
| PS stats table (`franchise-command-center.js` ~2928) | No MIN column, unchanged. |

## Equivalence proof

Harness: `scripts/gp_minutes_week_equiv.py`. It follows `season_advance_harness.advance_regular_week` (user game, `finalize_game`, `complete_week`; training skipped) on a **copy** of `~/Library/Application Support/GOB/local.sqlite`. The franchise is Lancaster (`6ab284847ab3853ae89a1184`), advanced week 3 → 5 under the loopback SQLite profile. Every CPU game is seeded from its matchup (`seed=20260927 + crc32(week:teams)`), with one thread and `PYTHONHASHSEED=0`. The "before" arm ran develop's `BackEnd` exported with `git archive develop` into `tmp/gob-before`. Week 3's 63 CPU games were already simmed and finalized in the save (identical in both arms), so week 3 rolls up only the user game. Week 4 is a full 64-game week.

| Check | Result |
|---|---|
| before vs before (reproducibility) | 2,370 players, **0 changed** |
| Players compared (FPD + FRD; season, career, `ps_season_stats`) | 2,370 |
| Players changed | **1,512** (season and career, GP/MIN only) |
| Stats other than GP/MIN changed | **0** |
| Season GP drops | **24**; 24 zero-second box rows in the new games; **0 mismatches** by player |
| Career GP drops | 24 (same players) |
| Max MIN delta per player | **1.4833** min over two games (max single-game remainder 0.9833 = 59 s) |
| MIN delta vs expected remainder | **0 mismatches** (tolerance 1e-6) |
| Mean remainder per played row | 0.491 min (about 30 s per game, matching the reported drift) |
| Rows under 60 s (old code credited 0 MIN) | 5 |
| `ps_season_stats` | 0 changes; no PS games were simmed in weeks 3–4. The PS rule is covered by unit test. |

## Unit tests

`tests/test_gp_minutes_accumulation.py` (6 tests), passing on mongomock and `GOB_PERSISTENCE=sqlite` (verified `SqliteStore` / `SqliteCollection` under pytest):

- a 0-second bench player gets GP 0 and MIN 0 in season and career; the starter gets GP 1;
- 839 s (13:59) gives 13.983 MIN, not 13;
- two 59 s games give GP 2 and MIN 1.967 (rounds to 1.97);
- re-finalizing the same game leaves all FPD docs byte-identical (claims unchanged);
- the tournament `finalize_game` branch follows the same rules and re-finalizing is a no-op;
- practice squad: 250 s gives 4.167 MIN and GP 1 (the old code credited 250 **minutes**); a 0-second row gets no `ps_season_stats`.

Existing fixture updates: `tests/test_user_week_stats_gap.py` and `tests/test_rollup_game_to_franchise.py` box rows had no `MIN`. Real engine rows always carry `MIN` (from `BOX_SCORE_KEYS`, accumulated per turn), so I added `MIN: 1200`.

## Tests run

Pytest, run identically on mongomock and on `GOB_PERSISTENCE=sqlite`: **113 passed, 4 xfailed** each. The xfails are pre-existing in `tests/known_failures.py` (the two rollup tests, broken harness, and two others).

Files: `test_gp_minutes_accumulation`, `test_franchise_complete_week`, `test_user_week_stats_gap`, `test_leaders_snapshot`, `test_franchise_leaders_endpoint`, `test_player_stats`, `test_t3_detail`, `test_office_digest`, `test_persistence_adapter`, plus `test_rollup_game_to_franchise`, `test_franchise_game_idempotency`, `test_franchise_finalize_matchup_idempotency`, `test_tournament_player_stats`, `test_franchise_stats`, `test_practice_squad_training_job`, `test_backfill_franchise_player_stats`.

Playwright (`seed_and_serve` on port 8137; port 8000 was held by another process):

| Spec | Result |
|---|---|
| `player-stats.spec.js` | 5 passed, 1 failed: `player cell matches the roster row` (row height 46 > 44). **Pre-existing on develop**: it fails the same way with all my frontend changes stashed. Likely from 9684b8dbf "Line the Player Stats name up beside the portrait." Not fixed here. `per game and totals, sort, and null versus zero` passes. |
| `t1-tables.spec.js` | all passed (one timeout under parallel load passed on a serial rerun) |
| `t3-detail.spec.js` | all passed (1 skipped by the spec) |
| `t2-roster.spec.js` (touches `team-roster-view.js`) | all passed (one load flake passed on a serial rerun) |
| `standalone-roster.spec.js`, `attr-tiles.spec.js` | 20 passed |

## Timing (SQLite, desktop engine, 5 runs each, interleaved before/after)

The harness ran with `--engine desktop` (shipped spawn pool, `FRANCHISE_CPU_SIM_POOL_WORKERS=8`, unseeded). The figure is the full week-4 advance (user game, 63 CPU games, 64 finalizes, week wrap-up).

| Arm | Week-4 advance (s) | Median | 64 × `finalize_game` (s) | Median |
|---|---|---|---|---|
| before | 126.7, 344.8, 173.0, 358.2, 421.9 | **344.8** | 14.8, 27.1, 18.0, 61.9, 74.2 | **27.1** |
| after | 164.5, 257.1, 180.4, 410.6, 241.9 | **241.9** | 24.5, 16.8, 15.5, 32.7, 20.9 | **20.9** |

No growth, but other agents were loading the machine, so the spread within each arm (127–422 s) is far larger than any code effect. For a precise number, an in-process A/B of just the changed computation over the real 1,560 box rows of the equivalence run costs 11.9–12.7 ms per week (old) vs 13.6–16.8 ms (new). That is about **1–5 ms per 64-game week (15–75 µs per game)**, under 0.05% of finalize time.

## Existing saves: no backfill

Totals written before this commit keep floored minutes and a GP for every 0-second box appearance, and new games accumulate under the new rules. A season that spans the change therefore mixes both, and per-game MIN for those seasons still reads slightly low.

The task premise was that the per-game seconds aren't stored. That's only partly true: `games` docs (with box seconds) are not purged. A rebuild from them still isn't reliable, though:

- FPD totals don't record which docs fed them.
- Saves hold duplicate docs for one matchup; this save has 126 docs for week 2's 63 CPU games.
- Random-score fallbacks have no box.
- Career spans seasons.

Documented in `_documentation_master/06_Gameplay_Systems/Box_Score_System.md` §1 and §5, with matching updates in `04_Franchise_Mode_Systems/Statistics_System.md` (MIN storage/display) and a pointer in `06_Gameplay_Systems/End_Of_Game_System.md`.

Practice squad: `ps_season_stats` written before this commit keep the old `> 300` rule (short stints credited as seconds). `backfill_ps_season_stats` would rebuild them correctly from stored PS games, but it runs once per franchise (flag `ps_season_stats_backfilled`), and I did not re-trigger it.

## Found, not fixed (out of scope)

- `apply_stats_from_summary` tournament branch references `query_pid`, which is never assigned, so reaching it raises `NameError` on develop. Its only production caller (`franchise_manager.py:1077`) passes no `tournament_id`, so the branch is unreachable. I applied the rules there for consistency but did not test it.
- `BackEnd/data/tutorial_rosters.py` overlays `MIN` in **minutes** (e.g. 21) into the tutorial game's `stats["game"]`, where MIN means seconds.
- `pgpc_template_substitution` puts game `MIN` **seconds** into `{player_min}`, and `pgpc_qualification` `limited_minutes_high_rt` compares seconds with `max_minutes`. Both are game-level, not season.

## Files

- Code: `BackEnd/utils/stat_updater.py`, `BackEnd/practice_squad/stats.py`
- Frontend: `player-detail.js`, `franchise-command-center.js`, `js/shared/rosterStatsRenderer.js`, `js/shared/scoutingReport.js`, `training-report.js`, `team-roster-view.js`
- Tests: `tests/test_gp_minutes_accumulation.py` (new), `tests/test_user_week_stats_gap.py`, `tests/test_rollup_game_to_franchise.py`
- Harness: `scripts/gp_minutes_week_equiv.py` (measurement only)
- Docs: `Box_Score_System.md`, `Statistics_System.md`, `End_Of_Game_System.md`
- Not touched: `main`, `FrontEnd/static/sounds/`, `.DS_Store` (pre-existing local modification, not committed)

Commit: `f8b7b6640` (fix), plus this report.

STATUS: COMPLETE
