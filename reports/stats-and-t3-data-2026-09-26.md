# Stats gap and T3 data — 2026-09-26

Read-only investigation on `audit/stats-and-t3-data`. No product code was changed. The only code added is `tests/test_user_week_stats_gap.py`, which fails on purpose.

Evidence files (not modified): a read-only copy of `~/Library/Application Support/GOB/local.sqlite` at `tmp/stats-audit-live.sqlite`, and `tmp/offline-parity.sqlite`. Mongo was not running. The writer is the same Python on both stores; the test was run on mongomock and on a throwaway SQLite file (`GOB_PERSISTENCE=sqlite`, `GOB_DB_MODE=mongomock`).

## Part 1 — User-team season stats missing offline

### What the saves show

Active franchise `6ab284847ab3853ae89a1184`, user team Lancaster (`69a6fcb68d2c56aa82e48a54`).

Week 1 was a real full sim. The games document has `bulk_sim_used`, quarter 5, `is_final`, a 12-and-12 box score, canonical ids `LANCASTER` / `CASINO_ROW`, and claim `1:CASINO_ROW:LANCASTER`. That is the only Lancaster game that incremented `franchise_players_data` (max season GP 1, 62 FGA).

Week 2 reused that same games document. `_save_game_result` set `week` to 2, `team1_id` to Appalachia, and the score to 63–51, and left the Casino Row box score in place. `finalize_game` saw the id already in `applied_games` and returned. Phase A still wrote `results["2"]`. Appalachia never received a box for that game, so Appalachia is also one GP short.

On the week-5 parity copy, weeks 3 and 4 are new score-only games documents (no `home_team_id`, no box). Finalize claimed them with ObjectId matchup keys, ran end-of-game side effects, processed zero players, and left season GP at 1.

The other franchise in the live file (Chapel Hill, week 1, no results) has no mismatch. Comparing it to the Lancaster franchise's player rows is a false alarm.

### Live-save mismatches

Compared within one franchise: games in `franchises.results` versus the max `season.GP` on that team's `franchise_players_data` rows.

| Save | Team | id | Record | Games in results | Max season GP | Season FGA |
|---|---|---|---|---|---|---|
| Live week 3 | Lancaster | `69a6fcb68d2c56aa82e48a54` | 1–1 | 2 | 1 | 62 |
| Live week 3 | Appalachia | `69a6fcb68d2c56aa82e48a5e` | 3–0 | 3 | 2 | 119 |
| Parity week 5 | Lancaster | `…a54` | 3–1 | 4 | 1 | 62 |
| Parity week 5 | Appalachia | `…a5e` | — | 4 | 3 | 174 |
| Parity week 5 | Little York | `…a58` | — | 4 | 3 | 139 |
| Parity week 5 | IDA | `…a60` | — | 4 | 3 | 142 |

Casino Row (`…a5f`), the week-1 opponent, is not short. It got the only real box score.

### Path table

Every user-facing path ends in the same HTTP handlers. Desktop and the loopback do not have a second writer. SQLite and Mongo share `stat_updater.finalize_game`. CPU games on the same SQLite file did increment season lines, so the store's `$inc` works.

| Path | Writes `franchises.results`? | Writes FPD season stats? | Mongo / SQLite |
|---|---|---|---|
| Live, quarter by quarter. Last quarter returns `final_game_document`. `finalizeGame.js` POSTs `/franchise/complete-week/phase-a` with that new `game_id`. | Yes, in phase A, before finalize. | Yes, when the id is new and the doc has a box. `finalize_game` is the only season `$inc`. | Same function both stores. |
| Set Lineup "Sim Full Game" / "Sim Rest". `bootGame.js` runs `simulate-quarter` with `full_sim` and `advance_method` `sim_full_game` or `sim_rest_of_game`, then the same phase-A call. Week 1 on the live save is this path (`bulk_sim_used`). | Yes. | Yes, on a fresh id with a box. | Same. |
| Advance phase A (`POST /franchise/complete-week/phase-a`). This is the call the two rows above make. `_complete_week_process_user_game_block` writes the result first, then calls `finalize_game` only if `game_id` is set. | Always, including when finalize no-ops. | Only if that id is not already in `applied_games` and the doc has a box with players. A reused id returns immediately. A new id with no box is claimed and processes nobody. | Same. Reproduced on mongomock and on SQLite. |
| Phase B / monolith `complete-week` / `start-cpu-sims`. CPU matchups only. The user pair is skipped when it matches `team1`/`team2`. Each CPU sim calls `finalize_game` on a fresh id with a full summary. | Yes, for CPU games. | Yes, for those CPU games. A sim exception writes a random 50–90 score and does not finalize (fallback only; not the Lancaster case). | Same. |
| EOS "Sim Next Round" (`sim-rest-of-tournament`) and `sim-championship`. Full summary, then `finalize_game`. | Yes (bracket / result row). | Yes, when the summary has a box and the id is new. A user who plays the EOS game live still goes through phase A, so the reused-id bug applies there too. | Same. |
| `POST /franchise/save-result`. | No. The handler says wins and losses live in `results`, which phase A writes. | Yes, after it verifies a box. | Same. |
| `franchise_manager.simulate_game` success. | Yes. | Yes, `finalize_game` when a franchise id is set. On exception it saves scores only. | Same. |
| Commented `dev_sim_regular_season`. | Not live. | Not live. | — |

Phase A does not advance the week. Phase B and monolith `complete-week` do, and they do not re-finalize the user game. The box-score "Go To Locker Room" button posts phase B from pending `{franchise_id, week}` only.

### Root cause

`_complete_week_process_user_game_block` persists the user result before `finalize_game`, and it still persists it when finalize applies nothing.

1. Reused `game_id` (live week 2). The id is already in `franchises.applied_games`, so `finalize_game` returns at the claim check. `_save_game_result` has already `$set` week, team ids, and scores onto the old gameplay document and left the old box in place. Phase A then stores `results.{week}`.
2. New `game_id` with no box (parity weeks 3 and 4). The upsert creates a score stub. Finalize claims `applied_matchups` from `team1_id`/`team2_id` (ObjectId strings, because `home_team_id`/`away_team_id` are absent), processes zero players, and writes no `$inc`.

The client can do either: `finalizeGame.js` sends `simData.game_id || simData._id`, and it attaches `game_document` only when `final_game_document` is present. A second week that still holds the previous game id hits case 1. A score posted before a box exists hits case 2.

### Proposed fix (not implemented)

Do not append a user result, and do not mutate a games document that already has a finalized box, unless `finalize_game` applied a new box for this week (new claim and `players_processed > 0`).

- If `game_id` is already in `applied_games`, reject phase A instead of writing another week's result.
- If the games doc has no box score, do not claim the matchup and do not write the result.
- `_save_game_result` must not `$set` week or team ids onto a document whose box is a different matchup.

### Sim Perf Capstone

Not involved. The capstone batches the FPD `bulk_write` inside `finalize_game`. Both failures happen before that write: the claim short-circuit, or an empty player list. CPU weeks use the same batch and their season lines are complete.

### Failing test

`tests/test_user_week_stats_gap.py` finalizes a week-1 Lancaster box (GP becomes 1, FGA 8), then POSTs phase A for week 2 with that same `game_id` and an Appalachia 63–51 score. The week-2 result row is present and season GP stays 1. The assertion `GP == 2` fails.

Log line on both stores: `Game … already in applied_games, skipping (idempotent)`.

- mongomock: failed, `assert 1 == 2`
- SQLite (`GOB_SQLITE_PATH=/tmp/stats-gap-test.sqlite`): failed the same way

Healthy paths (fresh id plus a box) were traced to this same phase-A call and match week 1 on the live file. They were not re-simmed through a full 63-game CPU week in the desktop UI. The task was to stop once a result-without-stats path was reproduced.

## Part 2 — Data behind the T3 player and team pages

Same documents on Mongo and SQLite. Nothing below exists on only one store. The live file's training-report shape is older than the current writer; the fields are the same collection.

| Item | Status | Source | Notes |
|---|---|---|---|
| a. Recent attribute changes | Exists, current season | `franchise_team_data.training_reports.{week}` | Written by user training (`franchise_routes` training persist) and CPU autotrain (`cpu_autotrain_week`). Kept for every trained week so far, user and all CPU teams (live save: weeks 1–3 on all 128 teams). Season rollover sets `training_reports` back to `{}` (~19133), so history is this season only. `session_type` is `in-season` after camp; camp is week ≤ 1. Current writer (`training_execution_v2`) stores `player_attribute_display_movements[player_id] = {name, ATTR: {from, to}}` with display buckets (`raw // 10`). `player_logs` / `player_changes` stay name → raw delta. The live week-3 file still has the older shape: name → `{ATTR: signed delta}` (sample Roger Henrich SC −0.24, SH +1.11). End-of-game player EM is attitude, not the twelve attributes, and is not this history. There is no separate week-by-week log of absolute attribute values; current values are `franchise_players_data.attributes`. |
| b. Development focus | Exists. The "trains one attribute" mapping does not. | FPD `training_focus`, `training_position`. Also `meta.training_focus`. | Sample Lancaster player: `training_focus` `"standard"`, `training_position` `"SG"`. Written by `POST /franchise/player/development-focus` for the user's own team, checked against `POSITIONS` and `TRAINING_FOCUSES`. Focuses: standard, offensive, defensive, athletic, fundamentals, rebounding (`BackEnd/constants/training_shape.py`). `TRAINING_FOCUS_PERCENTAGES[position][focus][attr]` is a weight table (each profile totals 808; FT, IQ, ND stay 100). `standard` aliases `TRAINING_GAIN_PERCENTAGES`. Lookup is `training_attr_gain_multiplier`. The mock "Focus Strength / Trains ST" does not match: there is no strength focus, and ST is one column, raised by the athletic and rebounding profiles. |
| c. Season line and game log | Season totals exist. Rates are derivable. Per-game log exists only inside game documents. | `franchise_players_data.season` and `.career`. Per game: `games.teams[canonical_id].box_score` or top-level `box_score`. | Counting stats stored: GP, PTS, REB, AST, MIN (minutes; finalize divides seconds by 60), FGM/FGA, 3PTM/3PTA, FTM/FTA, DEF_S/DEF_A, and the other box columns. FG%, 3PT%, FT%, DEF% are not stored; derive makes/attempts the way the leaders snapshot does. DEF% is DEF_S/DEF_A. GP is absent, not zero, when finalize never ran. A player's game log means scanning every `games` doc for the franchise (live copy: 293 games, all with a box). No per-player game-log collection. |
| d. Identity fields | Portrait partial. Position derivable. Height, weight, year, jersey exist. Hometown missing. | FPD `meta` | Portrait is `meta.image_id`. On the live Lancaster franchise, 156 of 1920 FPD rows have it; the sampled Lancaster players do not. Walk-ons get one from `walk_on_roster_identity`. Position uses the leaders rule (`leaders_snapshot._roster_position`): stored `meta.position` unless empty or `"--"`; else the user team's resolved/training position; else `_best_position` (highest `position_ratings`, ties keep `POSITION_ORDER`). Sample Lancaster meta has no `position`; the doc has `position_intent`, `position_ratings`, `training_position`. Sample meta: jersey 6, year `"freshman"`, height 71, weight 174. Those are copied from core `players` at FPD init. Hometown: no field in BackEnd (`hometown`, `home_town`, `birth_city` not stored). It would have to be written onto `players` and FPD `meta` when the roster is generated. |
| e. Pager "4 of 12" | Derivable. The roster API order is not the Roster page order. | `GET /franchise/roster` returns `franchise_team_data.players` order, then FPD-filtered. `build_roster_players` keeps that id list. | The Roster page (`team-roster-view.js`) re-sorts in the client. Default is rating descending (`rosterSortColumn = 'RT'`, `rosterSortDirection = 'desc'`). "4 of 12" as shown on that page is the client sort, not the API array, unless the user is looking at the default rating sort applied in the page. |
| f. Team detail (`t3-team-1280`) | Record, national rank, conference label, results rows, and the user team's next game exist. Calendar tip times, a stored W/L letter, a stored conference rank, opponent rank on the result row, and a generic any-team "next game" do not. | `franchises.results.{week}` (`away_id`, `home_id`, scores). FTD `natl_rank`. Core `teams.conference`. User next game: `_find_user_next_game`. Schedule route returns the franchise schedule plus the user team's `training_reports`. | W/L is counted from scores. Conference rank is standings order (wins, then `natl_rank`), not a stored "1st in A2" field. Opponent national rank is that opponent's FTD `natl_rank`, not a field on the result row. Sample Lancaster `natl_rank` 52. "Fri 7:00 PM", "Sat 1:00 PM", and "at York, Fri 7:00 PM" are not stored. A team page for a non-user team would have to join results, `natl_rank`, conference, and schedule; that joined route does not exist. Nothing here is Mongo-only or SQLite-only. |
