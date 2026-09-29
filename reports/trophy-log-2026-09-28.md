# Trophy log — 2026-09-28

Branch `feat/trophy-log` (from `origin/develop` @ 8db71deef).

## Summary

The coach now carries an append-only `trophies` list: every title, every user-team
All-American and one season result per season. Online it lives on the `users` doc;
on the desktop (`local-desktop-user`) it lives on the save's `save_meta` `local_coach`
doc. Both go through one helper, `BackEnd/utils/trophy_log.py::append_trophy`, and share one shape.
`GET /franchise/coach-career` returns the list newest first. The counts
(`championships_total`, `championships_by_team`, FPD titles) are unchanged.

## Entry shape

```json
{
  "key": "<franchise_id>:<season>:<kind>:<team_id>[:<player_id>]",
  "season": 2,
  "kind": "national",
  "team_id": "<team ObjectId string>",
  "team_name": "Lancaster",
  "franchise_id": "<franchise ObjectId string>",
  "at": "2026-09-28T21:04:11Z",
  "detail": { }
}
```

- `kind` is one of `conf_rs | conf_t | region | national | all_american_1 | all_american_2 | all_american_3 | season_record`.
- `team_name` is the Team Builder display name at award time. It comes from `resolve_team_name_map` (the overlay for the replaced slot) and falls back to the franchise's `user_team_id` for the user team. It is never the core `teams.name`. The tests assert that a Team Builder franchise (core "Providence", shown as "Lancaster") never writes "Providence" into any entry.
- `detail` is present only on All-American entries (`{player_id, player_name}`) and on `season_record`.
- `at` is stored as a UTC datetime and serialised by coach-career as ISO-8601 with a `Z` suffix.
- Entries hold the franchise id and name, not a reference, so they survive a franchise being deleted. Nothing in the delete cascade touches `users` or `save_meta`. A test deletes the franchise and still reads the trophies back.

## Write points

| Kind | file::function |
|---|---|
| conf_rs, conf_t, region, national | `BackEnd/utils/franchise_championships.py::_inc_championship` calls `trophy_log.record_title_trophy` right after the count `$inc`, on the same call path. It is reached through `maybe_award_conference_rs_championship` (week 26→27, #1 seed) and `maybe_award_franchise_eos_title_championship` (conference, region and national finals). |
| all_american_1/2/3 | `BackEnd/api/franchise_routes.py::_persist_week_35_awards_if_needed` calls `trophy_log.record_all_american_trophies` for USER-team players only. It runs whether the awards were just computed or were already stored. The key guard makes the repeat calls (command-center reads at week 35+, the awards route) no-ops. |
| season_record | `BackEnd/api/franchise_routes.py::finish_season` calls `trophy_log.record_season_record_trophy(franchise_doc)` straight after the single-use season-transition token is consumed. That is before the `$set` that resets `results`, `conference_tournaments`, `region_tournaments`, `national_tournament` and `awards`. |

The coach-career read is at `BackEnd/api/franchise_routes.py::get_coach_career`. It adds `trophies` to the online projection and returns `{...coach_career_payload, "trophies": trophies_newest_first(...)}`, sorted by season descending, then `at` descending.

Every trophy write is wrapped in `try/except` with `logger.exception`, so a trophy failure can never break a title count, the awards or the season transition.

Nothing changed in the sim engine, `cpu_week_pool`, `sim_rng`, `stat_updater`/finalize or `_complete_week_finish_cpu_and_persist`. A guard test asserts that the sim modules and `_complete_week_finish_cpu_and_persist` never mention `trophies` or `trophy_log`.

## Idempotency guard

Each append is one guarded update, not a read-then-write:

```python
coll.update_one(
    {"_id": doc_id, "trophy_keys.<key>": {"$exists": False}},
    {"$set": {"trophy_keys.<key>": True}, "$push": {"trophies": entry}},
)
```

- **Why a key map and not `trophies.key`:** the SQLite query engine (`BackEnd/persistence/sqlite_query.py`) does not traverse arrays, so `{"trophies.key": {"$ne": key}}` would not work on the desktop save. `trophy_keys.<key>` is a dict path, which `$exists` supports on both stores. In the map key, `.` and `$` are replaced with `_`.
- **Local coach:** a separate `$setOnInsert` upsert creates the doc first. Upsert can't share the guard, because a guard miss on an existing doc would try to insert a second doc with the same `_id`.
- **Online:** there is no upsert, so the `users` doc must already exist. A missing user is a no-op.
- **Existing championship guard:** `_inc_championship` doesn't have one. The count is a plain `$inc`, and the callers rely on the week flow running once. So there was nothing to reuse, and the trophy key is its own guard. If a title call is ever replayed, the count moves and the trophy doesn't. That count behaviour is pre-existing and unchanged, as the task required.
- **`finish_season`:** additionally protected by its existing single-use transition token, so a double call returns 409 before reaching the write.

## season_record fields

`detail` = `{wins, losses, conf_finish?, furthest_round?}`, all read from the franchise doc before the reset. Nothing new is computed in the sim.

| Field | Status | Source |
|---|---|---|
| `wins`, `losses` | exists | `calculate_franchise_standings(franchise_doc.results)` for the user team. This is the same function and source the command center uses for `team_record`, so it's the full season, including tournament games. FTD `season_wins`/`season_losses` only cover the regular season, so they weren't used. |
| `conf_finish` | exists (omitted if absent) | The user team's seed in `conference_tournaments[conf].seeds`, which is the regular-season conference finish (1–8). |
| `furthest_round` | exists (omitted if there are no brackets) | The deepest stored bracket round containing the user team: `national_final`, `national_semis`, `national_quarters`, `region_final`, `region_semis`, `conference_final`, `conference_semis`, `conference_quarters`, or `missed` when brackets exist but the team is in none. |

Left out: nothing the task named was missing. Conference placement below the 8 bracket seeds isn't stored on the doc, so `conf_finish` is omitted when the team isn't seeded. National and conference titles already have their own entries, so `season_record` doesn't repeat a "champion" flag.

## No backfill

Seasons finished before this shipped can't be itemised: `finish_season` wiped their brackets and awards. For those seasons the counts (`championships_total`, `championships_by_team`, FPD `titles`) remain the only history.

## Tests

`tests/test_trophy_log.py` has 15 tests. The store tests run on mongomock and SQLite, and where relevant for both an offline and an online owner, giving 30 cases. They cover:

- each title kind appends once with the right shape and the display name;
- repeat and replay calls don't duplicate;
- keys containing dots still guard;
- an offline owner writes to `local_coach` and an online owner to `users`, never the other;
- a missing online user isn't created;
- All-Americans are recorded for user-team players only, and replay safely;
- the season_record detail is right, and fields that can't be read are omitted;
- `furthest_round` labels;
- `finish_season` writes season_record after the token is consumed and before the reset;
- coach-career returns trophies newest first, locally (after the franchise is deleted) and online, and is clean under the TB leak scanner;
- sim modules never mention trophies.

`tests/test_home_base_data.py`: the coach-career `/me`-shape assertion now allows the new `trophies` key.

The task lists `tests/test_user_game_commit.py`, but it doesn't exist in the repo. Its coverage (`user_game_commit`) runs in `test_home_base_data` and `test_franchise_finalize_matchup_idempotency`, which were run in its place.

Targeted run: trophy_log, home_base_data, franchise_championships, tb_leak_detector and franchise_finalize_matchup_idempotency, **70 passed**.

## Merge gate

- `pytest --ignore=tests/e2e -q`: **3906 passed, 0 failed**, 20 skipped, 109 xfailed, 1 xpassed.
- Playwright (workers=1, port 8157, CI unset, full suite once, after `ps` showed the `~/gob-ux` run had finished): **544 passed, 0 failed, 3 skipped** (7.7 min). The server was stopped (nothing listening on 8157), and the regenerated report images were restored or removed.

## Deviations

- The worktree has no `.venv`, so pytest ran with `~/gob-simplified/venv/bin/python` (same as earlier tasks).
- `git checkout develop` fails because `develop` is checked out in the `~/gob-simplified` worktree. The branch was created from a freshly fetched `origin/develop` instead (the same commit).

STATUS: COMPLETE
