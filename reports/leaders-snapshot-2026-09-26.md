# Leaders snapshot — 2026-09-26

Implementation commit: `06fe60985`

The first open of Leaders for a week is a read of one small document, then the same Python ranker the live scan uses. Repeat opens in the same `browse_rev` are still a 304 through `@browse_cached`. This change is the first open.

## Design

`GET /franchise/leaders` used to aggregate `franchise_players_data` once per category. On SQLite each aggregate decodes every player document in the save, eight times.

The replacement stores one row per player in `leaders_snapshots` (one document, `_id` = the franchise id). The row is the identity fields plus the eleven season totals and eleven career totals the eight categories read: GP, PTS, REB, AST, 3PTM, BLK, STL, FGM, FGA, DEF_S, DEF_A. The route filters that list for national, conference, or region scope and sorts it in Python. Limit, per-game versus total, and season versus career are applied at read time, so the document does not precompute boards.

`rank_lines` is the only ranker. The live scan and the snapshot path both call it, including `qualifies` from `BackEnd/constants/leader_qualification.py` for season FG% and DEF%. Career FG% and DEF% still use attempts ≥ 5 × the player's own GP. Counting-stat ties keep aggregate `$match` order (SQLite rowid). Value, then volume, then that order. Response fields are unchanged: `player_id`, `name`, `team`, `value`, `conference`, `region`.

The snapshot is not a field on the franchise document. A week-15 document is about 326 KB, and folding that into `franchises` would make every franchise read carry it. `office_week_snapshots` can live on the franchise `$set` because that blob is small and the finalize already writes the franchise. This cache is a side collection so a stale mark is an update of a few bytes. It is not part of `FranchiseBundle`. An imported save with no snapshot falls through to the live scan. `delete_franchise` removes the cache row.

SQLite reads the lines with `json_extract` of those scalars (`projected_tuples`), including `3PTM`, ordered by rowid so ties match the old full-table aggregate. Mongo and mongomock use the same dotted inclusion projection and the same ranker. The route does not branch on the store.

### Freshness

The snapshot is fresh only when its week and season match the franchise and it is not marked stale. A miss (old save, week 1, never built, week changed, or stale) runs the live scan, returns that result, and stores a new snapshot. It does not error.

`browse_rev` is the wrong key. Player season totals land in `finalize_game` before `browse_rev` moves: CPU games between heartbeats, and the user game before phase A returns. A snapshot tagged only with `browse_rev` would still be served in that window.

Chosen instead: mark the snapshot stale at the season-stat write (`note_season_stats_written`). The first call in a process sets `stale: true` on the small snapshot document. Later calls in that same stretch skip the update until a rebuild clears the id, so a CPU week does not pay a write per game. This process also counts those writes. A snapshot it built is not treated as fresh if another game has committed since the load that produced it. Week-advance finalize rebuilds the rows once, after every game for the week is already on `franchise_players_data`, inside the same SQLite transaction as the franchise `$set` (no second commit). Phase B still runs once. The sim engine, `cpu_week_pool`, end-of-game persistence, and `sim_rng` are untouched.

A 304 can still hide a newer body until `browse_rev` bumps (heartbeats, phase A, week finalize). That behavior is unchanged. When the handler runs, it does not serve a stale snapshot.

## Writers

| Writer | What it changes | Handling |
| --- | --- | --- |
| `stat_updater.finalize_game` FPD `bulk_write` (`season.*` / `career.*` `$inc`), including a user game or a CPU game mid-week. The same function may `insert_one` a new zeroed FPD row before that bulk write. | Season and career box score | `note_season_stats_written` after the bulk write. Next Leaders read live-scans and stores a new snapshot. |
| `_finalize_franchise_week_after_cpu_games` | Results and the week the user will open, after FPD is already updated | `refresh_leaders_snapshot` for that next week, current season, and the in-memory results, in the franchise `$set` transaction |
| EOS sim-rest week persist (`franchise_routes`, the path that logs `[EOS-SIM-REST]`) | Same: week advance after `finalize_game` | Same rebuild, same transaction |
| Season rollover `delete_many` + `insert_many` of next year's FPD (season zeroed, career carried) | Season totals reset; season number on the franchise changes in the same flow | `note_season_stats_written`. A week/season mismatch would also miss. |
| Team builder roster replace (`team_builder_roster.insert_many`, then `meta.team` rewrite) | New season lines and the team name on the row | `note_season_stats_written` after the rewrite |
| Franchise creation `insert_many` of FPD | Initial zeros | No snapshot yet. First open is the live scan. |
| Tournament `finalize_game` | `tournament.players`, not FPD season lines | Left alone |
| `backfill_franchise_player_stats` | Legacy `franchise.players`, not FPD | Left alone |
| CPU autotrain, user training, training-squad progression | Attributes and position ratings | Left alone |
| Portrait / uniform stamp (`meta.image_painted`, `meta.uniform_key`) | Image flags | Left alone |
| Walk-on jersey and `meta.image_id` | Identity display fields Leaders does not read | Left alone |
| Practice squad `ps_season_stats` | A different block | Left alone |
| Championship `titles.*` `$inc` | Titles, not the box score | Left alone |

## Size

Week 15, Lancaster franchise `6ab284847ab3853ae89a1184`, 128 teams, 1920 players, season and career on every row: **334,006 bytes** of JSON (the stored document).

## Timings

SQLite file: `tmp/leaders-w15.sqlite` (a copy). National season, limit 10. Mongo was not running (`127.0.0.1:27017` connection refused), so there is no Mongo timing. Mongomock is the second store in the tests.

Interleaved old eight-aggregate scan vs the snapshot open, five pairs, one warmup of each first:

| Pair | Before (s) | After (s) |
| --- | ---: | ---: |
| 1 | 16.551 | 0.150 |
| 2 | 17.780 | 0.174 |
| 3 | 14.679 | 0.036 |
| 4 | 3.387 | 0.031 |
| 5 | 9.028 | 0.037 |
| Median | 14.679 | 0.037 |

The snapshot open median is 37 ms, under the 300 ms budget. A separate five-run sample of the no-snapshot fallback (live extract, rank, store) was 0.711, 0.285, 0.294, 0.291, 0.280 s, median 0.291 s.

Week-advance cost is the rebuild inside the franchise `$set` transaction, minus that `$set` alone. Five pairs: deltas 0.052, 0.065, 0.060, 0.055, 0.053 s, median **55 ms**. The rebuild by itself was 0.054, 0.051, 0.049, 0.049, 0.052 s, median 51 ms. That is inside the ~100 ms allowance. Full `complete-week` sims were not re-run; 55 ms is not visible against a multi-minute week, and the isolated delta is the number that can actually be measured.

The national season limit-10 body on that save matches `tmp/leaders-live-before.json` for all eight categories (same players, order, ties, and values), including the fully tied counting stats.

## Tests

`tests/test_leaders_snapshot.py`: snapshot-served body equals the live scan for national and conference, season and career, all eight categories (per-game PTS/REB/AST and raw 3PTM/BLK/STL); a mid-week `season.PTS` write plus `note_season_stats_written` shows up on the next read; a missing snapshot returns the live scan and does not error.

Also run: `test_leader_qualification`, `test_franchise_leaders_endpoint`, `test_office_digest`, `test_persistence_adapter`, `test_franchise_league_news`.

- mongomock (`GOB_DB_MODE=mongomock`): 76 passed
- SQLite (`GOB_PERSISTENCE=sqlite`, `GOB_DB_MODE=mongomock`): 76 passed

STATUS: COMPLETE
