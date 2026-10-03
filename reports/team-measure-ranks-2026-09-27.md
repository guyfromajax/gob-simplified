# Team measure ranks — 2026-09-27

Branch `api/team-measure-ranks`, off develop. Backend only. The sim engine, `cpu_week_pool`, `sim_rng`, and `finalize_game` were not touched. The week-advance snapshot writer was not touched, and Chemistry was not added to it.

## `measures[]` is not on develop

`GET /franchise/team-data` on develop returns `team_attributes`, `plays_data`, and `scouting_data`. The roster-page `measures[]` (family, meter, description) lives on `app/t2-roster` and is not in this tree. This branch does not copy that code.

`BackEnd/utils/team_measure_ranks.py` is the rank field set. The team-data route attaches it as `measures` and stays `@browse_cached`. When the roster rows land, they should merge these rank fields onto their own objects. The stored `value` is the team's attribute for the current week, the same `franchise_team_data.team_attributes` Office already reads. A missing key stays null. The route's zero-fill (missing attribute → 0 on `team_attributes`) does not enter the ranking.

## Direction

Read from the sim, not from the label. Rank 1 is the best end. Fight and Discipline are two-sided, so they are not ranked. `direction` is null and `rank`, `rank_of`, `percentile`, and `rank_delta` are null. The value is still returned. Setting a direction on those two in `MEASURE_SPECS` is the only change required once that call is made.

| Measure | Direction | Why |
|---|---|---|
| `team_chemistry` (Chemistry, scale 25) | `higher_better` | The team's own chemistry raises its rebound score (`_team_rebound_bonus` in `select_rebounder_by_score`, `BackEnd/utils/shared.py`), wins a rebound tie, raises the opponent's fast-break shot threshold when two defenders are back (`rim_runner_fast_break.py`, `shot_threshold = base + 100 + def_chemistry - off_fight`), and is added into the HCO recovery score for whichever side has it (`_hco_recovery_roll` in `phase_resolution.py`). |
| `shot_threshold` (Shooting) | `lower_better` | A make is `shot_score >= shot_threshold` (`shared.py` putback, `after_steal_drive_integration.py`, and the uncontested fallback in `uncontested_shot.py`). `shot_threshold_scale.py` states it: lower raw values are easier makes, and tournament seed 1 (best shooters) is the low end of the scale. |
| `rebound_modifier` (Rebounding) | `higher_better` | `_team_rebound_bonus` multiplies chemistry by `rebound_modifier` and adds that to the rebound score. A tie keeps the higher modifier (`select_rebounder_by_score`, `shared.py`). |
| `defensive_efficiency` | `higher_better` | `resolve_defense_pass_modifier` (`pass_contest.py`) maps half-court to this key. `resolve_pass_contest` adds it to the intercept score and subtracts it from the completion bar, so a higher value deflects more passes. HCO execution is `d_score = defensive_efficiency + roll` and `o_score - d_score` (`phase_resolution.py`), so a higher value lowers the offense's result. |
| `fight` | two-sided | Higher fight causes more fouls: `calculate_foul_turnover` (`phase_resolution.py`) fouls the defense when `d_foul_score < fight * 1.2` and the offense when `o_foul_score < fight * 0.8`. `turn_manager.py` uses the same shape. Higher offensive fight also lowers the fast-break shot threshold (`rim_runner_fast_break.py`, subtracted as `off_fight`), and higher defensive fight lowers the opponent's uncontested make threshold (`compute_uncontested_inside_attack_make_threshold`, `uncontested_shot.py`). One end is not better. |
| `discipline` | two-sided | `check_defensive_foul_on_shot` (`shot_manager.py`) says higher discipline means fewer shooting fouls, and the putback check (`shared.py`) widens the no-foul window the same way. Higher offensive discipline also raises the uncontested make threshold. The turnover check does the opposite: `is_turnover = turnover_score < discipline` in `calculate_foul_turnover`, and the same comparison in `turn_manager.py`, so a higher value turns the ball over more often. |

## Ranks

For each directed measure, every franchise team with a numeric stored value is ranked. Ties share a place and the next place skips (1, 2, 2, 4). `rank_of` is that count. A missing value is left out of it.

`percentile` is 0–100, 100 at the best end: `100 × (teams strictly worse) / (teams strictly better + teams strictly worse)`. A tie for best is 100. A tie for worst is 0. One team, or a measure where every stored value is equal, is 100.

`rank_delta` is places climbed since the latest earlier `office_week_snapshots` `team_measures` for this season (`latest_snapshot` / `TEAM_MEASURE_KEYS`). Positive means the rank number got smaller. The snapshot stores the user team's values only, so the prior place is that prior value re-ranked against the current league, and every other team gets null. Chemistry is not in `TEAM_MEASURE_KEYS`, so its `rank_delta` stays null even if a snapshot happens to carry the key.

Each object is `key`, `label`, `value`, `scale_max` (25 for Chemistry, otherwise null), `direction`, `rank`, `rank_of`, `percentile`, `rank_delta`.

The league read is one projected scan: `franchise_id` plus `team_id` and `team_attributes.<key>` for the six keys. On SQLite that is `projected_tuples` (compiled `g_franchise_id` filter, scalar `json_extract`, no document decode). `json_extract` of an ObjectId `team_id` returns the `{"$oid": ...}` text, and the reader turns that back into the id string. Mongo uses the same dotted inclusion.

## League distribution

Read-only copy of the Lancaster save, `tmp/stats-audit-live.sqlite`, timed from `/tmp/team-measure-cold.sqlite`. Franchise `6ab284847ab3853ae89a1184`, 128 teams, week 3, season 1. This franchise has no `office_week_snapshots`, so every `rank_delta` on the sample is null.

Median is the average of the two middle values. No measure puts a majority of the league on one value. Chemistry is the coarsest ranked scale: 13 distinct values, and the largest tie is 18 teams.

| Measure | Min | Median | Max | Distinct | Largest tie |
|---|---|---|---|---|---|
| Chemistry | 7 | 11 | 19 | 13 | 18 at 10 |
| Fight | −9 | −1 | 7 | 16 | 16 at −1 |
| Discipline | −9 | 3 | 11 | 21 | 19 at 6 |
| Shooting | 67 | 87 | 122 | 44 | 9 at 87 |
| Rebounding | 0.12 | 0.48 | 0.86 | 74 | 5 at 0.36 |
| Defensive efficiency | −10 | 0.5 | 11 | 20 | 13 at −4 |

## Lancaster

Team `69a6fcb68d2c56aa82e48a54`.

| Measure | Value | Rank | Percentile |
|---|---|---|---|
| Chemistry | 9 | 92nd of 128 | 20.9 |
| Fight | −1 | not ranked | |
| Discipline | −4 | not ranked | |
| Shooting | 87 | 64th of 128 | 47.1 |
| Rebounding | 0.48 | 64th of 128 | 49.6 |
| Defensive efficiency | 3 | 36th of 128 | 69.6 |

## Timings

`GET /franchise/team-data` for Lancaster, direct call, save copy under `/tmp`.

| Call | Time |
|---|---|
| First call on a freshly copied file | 155.9 ms |
| Second call, same process | 28.1 ms |
| Route on a file already resident | 30.2 ms, then 29.2 ms, then 26.9 ms |
| The six-key extract alone, file resident | 17 ms in sqlite3 |

The first call sits on the cold page cache: the extract still has to parse each team's document (about 67 KB, 128 rows, ~8.6 MB) to pull `team_attributes`. Once the file is resident the route is under the ~100 ms target. Repeat browse GETs stay on `@browse_cached` and do not run the handler. The one-team plays/scouting read is still a full document, as it was before this change.

## Tests

`tests/test_team_measure_ranks.py`: direction table, ties (1, 2, 2, 4), Shooting ranks the smallest value 1st, percentile ends (best 100, worst 0, including ties at either end), `rank_delta` from a snapshot (positive when the team climbs, including a `lower_better` measure), Chemistry delta stays null, missing values excluded from `rank_of`, Fight and Discipline unranked, and the team-data route on the user team and on another team.

Passed on mongomock (8) and on `GOB_PERSISTENCE=sqlite` with `GOB_DB_MODE=mongomock` and `GOB_SQLITE_PATH` pointed at a temp file (8). Also passed on both stores: `test_office_digest`, `test_persistence_adapter`, `test_t3_detail` (66 total on each run).

Fields are in `UX_System.md` §15, Team attributes.

## Commit

`68208f648` on `api/team-measure-ranks`: Rank team attribute measures across the league on team-data.

## Follow-up

Fight and Discipline are `higher_better`. Jamie's call: that is the net effect as the game is coded. They rank with the others. A missing value is still the only unranked case.

`origin/develop` is merged. develop's `app/t2-roster` already returned `measures[]` (`family`, `family_label`, `key`, `label`, `value`, `scale_max`, `meter_pct`, `delta`, `description`) and `updated_after_week`. There is one list: those objects, plus `direction`, `rank`, `rank_of`, `percentile`, `rank_delta`, and `tied`. Family grouping and labels stay T2's. `meter_pct` stays on Chemistry only (value / 25). The bar reads `percentile`. The league read is still the projected scan. The route stays `@browse_cached`. The snapshot week is the franchise `week` field, which is what the rest of the app stores; `current_week` is the fallback.

The Team Attributes view shows the label, then Chemistry's `9/25`, then the place (`34th of 128`, or `T-34th of 128` when `tied`). The bar is the neutral DIFF white, filled to the percentile. An empty rank is an em dash and an empty bar. `rank_delta` is ▲ in `--delta-up` or ▼ in `--delta-down`. Null and 0 draw no chip. Fight, Discipline, Shooting, Rebounding, and Defensive efficiency do not show the raw engine number.

Lancaster on the save copy, week 3, no office snapshot, so no chips:

| Measure | Place |
|---|---|
| Chemistry 9/25 | T-92nd of 128 |
| Fight | T-61st of 128 |
| Discipline | T-112th of 128 |
| Shooting | T-64th of 128 |
| Rebounding | T-64th of 128 |
| Defensive efficiency | T-36th of 128 |

Shots, pointer in `.main`: `reports/team-measure-ranks/team-attributes-1280x720.png` and `team-attributes-1920x1080.png`.

Tests. Backend on mongomock and on `GOB_PERSISTENCE=sqlite` / `GOB_DB_MODE=mongomock`: `test_team_measure_ranks`, `test_team_attribute_measures`, `test_office_digest`, `test_persistence_adapter`, `test_t3_detail` (69 passed on SQLite). Playwright, workers 1: `t2-roster`, `shell-1`, `shell-2`, `office-frontend` — 34 passed, 1 skipped (the live mid-season office digest).

`UX_System.md` §15 Team attributes describes this single shape.
