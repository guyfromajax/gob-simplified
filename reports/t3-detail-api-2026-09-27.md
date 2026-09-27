# T3 detail API — 2026-09-27

Branch `api/t3-detail`. Backend only. `player-detail.html` still calls `GET /player/{id}`; that response is unchanged. The T3 pages read two new browse GETs. The sim engine, `cpu_week_pool`, `sim_rng`, and `finalize_game` were not touched.

`design_handoff_browse_templates/frames/t3-player-1280.html` and `t3-team-1280.html` are not in this tree. The field list follows the task and Part 2 of `reports/stats-and-t3-data-2026-09-26.md`.

## Routes

Both are `@browse_cached` (tag `franchise:season:week:browse_rev:BUILD:signature`).

- `GET /franchise/player-detail?franchise_id&player_id`
- `GET /franchise/team-detail?franchise_id&team_id` for any team in the franchise

The team page's roster table stays on `GET /roster/{team}`. There is no server pager.

Reads use inclusion projections on indexed equality (`franchise_id`, `player_id`, `team_id`, `_id` `$in`). SQLite logs those queries as fully compiled and not decoded (`decoded=False`).

## Player response

`player_id`, `name`, `team_id`, `team_name`, `team_primary_color`, `position` (roster rule), `year` (abbrev), `height_in`, `weight`, `jersey`, `is_user_team`, `rt` (highest position rating), `potential` (`potential_rt_ratcheted`), `attributes` (six groups, each attr `{attr, raw, display}` with `display = floor(raw/10)`), `season` and `career` (per-game lines, percentages null at 0 attempts, plus `totals`), `recent_changes`, `development`.

`recent_changes` is newest week first: `{week, session_type, changes}`. The current writer stores display buckets, so a change is `{attr, from, to}`. The live week-3 save still has the older shape, name → signed raw delta (`player_changes`). That shape has no from/to, so the change is `{attr, delta}` only. Zero changes are dropped. `development.emphasises` is the attributes weighted above `standard`, at most three. `standard` emphasises nothing. `editable` is true only for the user's team.

Sample, Lancaster player Cedric Buckles on the read-only copy `tmp/stats-audit-live.sqlite`, franchise `6ab284847ab3853ae89a1184`. Weeks 1–3 are the old delta shape. `def_pct` is the unrounded ratio × 100; the page formats it.

```json
{
  "player_id": "0df15c02-a4d1-437b-b102-45f42b25e50b",
  "name": "Cedric Buckles",
  "team_id": "69a6fcb68d2c56aa82e48a54",
  "team_name": "Lancaster",
  "team_primary_color": "#d24a1b",
  "position": "PF",
  "year": "SO",
  "height_in": 77,
  "weight": 200,
  "jersey": 43,
  "is_user_team": true,
  "rt": 50,
  "potential": 71,
  "attributes": [
    {"id": "offense", "label": "Offense", "attrs": [{"attr": "SC", "raw": 41, "display": 4}, {"attr": "SH", "raw": 30, "display": 3}]},
    {"id": "defense", "label": "Defense", "attrs": [{"attr": "ID", "raw": 38, "display": 3}, {"attr": "OD", "raw": 27, "display": 2}]},
    {"id": "skills", "label": "Skills", "attrs": [{"attr": "PS", "raw": 17, "display": 1}, {"attr": "BH", "raw": 19, "display": 1}]},
    {"id": "grit", "label": "Grit", "attrs": [{"attr": "RB", "raw": 76, "display": 7}, {"attr": "ST", "raw": 53, "display": 5}]},
    {"id": "body", "label": "Body", "attrs": [{"attr": "AG", "raw": 41, "display": 4}, {"attr": "ND", "raw": 39, "display": 3}]},
    {"id": "mind", "label": "Mind", "attrs": [{"attr": "IQ", "raw": 30, "display": 3}, {"attr": "FT", "raw": 28, "display": 2}]}
  ],
  "season": {
    "gp": 1,
    "min_per_game": 17,
    "pts_per_game": 3,
    "reb_per_game": 8,
    "ast_per_game": 0,
    "stl_per_game": 0,
    "blk_per_game": 1,
    "fg_pct": 20,
    "tp_pct": null,
    "ft_pct": 50,
    "def_pct": 57.14285714285714,
    "totals": {"GP": 1, "MIN": 17, "PTS": 3, "REB": 8, "AST": 0, "STL": 0, "BLK": 1, "FGM": 1, "FGA": 5, "3PTM": 0, "3PTA": 0, "FTM": 1, "FTA": 2, "DEF_S": 4, "DEF_A": 7}
  },
  "career": {
    "gp": 1,
    "min_per_game": 17,
    "pts_per_game": 3,
    "reb_per_game": 8,
    "ast_per_game": 0,
    "stl_per_game": 0,
    "blk_per_game": 1,
    "fg_pct": 20,
    "tp_pct": null,
    "ft_pct": 50,
    "def_pct": 57.14285714285714,
    "totals": {"GP": 1, "MIN": 17, "PTS": 3, "REB": 8, "AST": 0, "STL": 0, "BLK": 1, "FGM": 1, "FGA": 5, "3PTM": 0, "3PTA": 0, "FTM": 1, "FTA": 2, "DEF_S": 4, "DEF_A": 7}
  },
  "recent_changes": [
    {"week": 3, "session_type": "in-season", "changes": [{"attr": "SC", "delta": 0.28}, {"attr": "SH", "delta": -0.88}]},
    {"week": 2, "session_type": "in-season", "changes": [{"attr": "SC", "delta": 0.28}]},
    {"week": 1, "session_type": "preseason", "changes": [{"attr": "SC", "delta": 1.1}]}
  ],
  "development": {"focus": "standard", "focus_label": "Standard", "emphasises": [], "editable": true}
}
```

The live weeks include every non-zero attribute, not only SC. Week 3's full list is SC +0.28, SH −0.88, ID +0.51, OD +0.27, PS −0.46, BH +0.32, RB +0.51, ST +0.76, AG −0.77, ND −0.75, IQ +0.76, FT +0.27. Career totals match season on this player.

## Team response

`team_id`, `name`, `primary_color`, `conference` (label `A1`…`H16`), `region`, `record` `{wins, losses}`, `natl_rank`, `conference_place` (`5th of 8`, `standings_display_sort_key` only), `streak`, `next_game`, `results` (newest first), `upcoming`. Opponent rank on a result is that team's current `natl_rank`. `site` is `home` or `away`. A tie leaves `result` null.

Same save, Lancaster at week 3:

```json
{
  "team_id": "69a6fcb68d2c56aa82e48a54",
  "name": "Lancaster",
  "primary_color": "#d24a1b",
  "conference": "A1",
  "region": "A",
  "record": {"wins": 1, "losses": 1},
  "natl_rank": 52,
  "conference_place": "5th of 8",
  "streak": "L1",
  "next_game": {
    "week": 3, "site": "away",
    "opponent_id": "69a6fcb68d2c56aa82e48a58",
    "opponent_name": "Little York",
    "opponent_primary_color": "#65308e",
    "opponent_natl_rank": 66
  },
  "results": [
    {
      "week": 2, "site": "home", "team_score": 51, "opp_score": 63, "result": "L",
      "opponent_id": "69a6fcb68d2c56aa82e48a5e",
      "opponent_name": "Appalachia",
      "opponent_primary_color": "#0f3d2e",
      "opponent_natl_rank": 41
    }
  ],
  "upcoming": [
    {
      "week": 4, "site": "away",
      "opponent_id": "69a6fcb68d2c56aa82e48a60",
      "opponent_name": "IDA",
      "opponent_primary_color": "#f2f2f2",
      "opponent_natl_rank": 69
    }
  ]
}
```

Results also include week 1 (a win). Upcoming continues in the same shape through week 26 (23 games after next).

## Timings

Copy of the live save at `/tmp/t3-timing.sqlite` (`GOB_PERSISTENCE=sqlite`, `GOB_DB_MODE=mongomock`). First call is a cold read of that process; the second is the same process.

| Call | Time |
|---|---|
| Player detail, Cedric Buckles | 8.6 ms, then 5.3 ms |
| Team detail, Lancaster | 158.7 ms, then 41.4 ms |
| Team detail, opponent | 42.7 ms |

The projected queries themselves, once the file is warm, are about 15 ms for the franchise schedule and results, 22 ms for 128 team ranks, and 4 ms for the team documents. The first team read sits on the cold page cache of the 67 MB file, just past the ~150 ms target. The repeat read is under it.

## What the frames ask for that this data does not have

- Hometown. No field on the player or on FPD `meta`.
- Tip time and calendar day (`Fri 7:00 PM`). Not stored.
- Neutral site. `site` is only `home` or `away`.
- Opponent rank as it was on game day. The result row carries the current `natl_rank`.
- A portrait for most players. `meta.image_id` is missing on the sampled Lancaster players, and this payload does not invent one.
- Pager `4 of 12`. The client keeps the roster list order. The route does not return an index.

## Checker

`scripts/check_season_stats_integrity.py` takes the Mongo database from the URI path when `--db` is omitted, and exits if neither is set. The first output line is `database <name>` (the file name on SQLite). Box and stored team refs are resolved to names before the comparison, so an ObjectId on one side and that team's name on the other is not a disagreement. A real mismatch still prints. On the Lancaster copy:

```
database t3-timing.sqlite
box/matchup game raw:"6ab284bf976adac9fc705b62" ... box=['Casino Row', 'Lancaster'] stored_teams=['Appalachia', 'Lancaster']
SUMMARY gp_mismatches=2 box_disagreements=1 franchises=1
```

## Tests

`tests/test_t3_detail.py`: user player with an old-shape week and a new-shape week, a CPU player (not editable, standard focus), a player with 0 attempts (percentages null), a team with no remaining games. Passed on mongomock and on `GOB_PERSISTENCE=sqlite` with `GOB_DB_MODE=mongomock`.

`tests/test_season_stats_integrity.py`: URI path parsing, and an ObjectId box that matches stored names while a real Casino Row / Appalachia mismatch still counts.

Also passed: `test_leaders_snapshot`, `test_franchise_leaders_endpoint`, `test_office_digest`, `test_persistence_adapter` (65).

Shapes are written up in `UX_System.md` §15.
