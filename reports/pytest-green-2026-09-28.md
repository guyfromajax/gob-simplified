# Pytest green + merge gate — 2026-09-28

Branch: `fix/pytest-green-audit` in `~/gob-audit`, based on `ux/recruit-results-week`, with `origin/develop` merged in.

## Result

- `.venv/bin/python -m pytest --ignore=tests/e2e -q`: **3864 passed, 16 skipped, 109 xfailed, 1 xpassed, 0 failed.**
- Playwright, full suite (`tests/e2e`, port 8010, `--workers=1`, `CI` unset, no other Playwright running): **542 passed, 3 skipped, 0 failed (8.2 min).**
- The sim engine, `cpu_week_pool`, `sim_rng` and finalize are untouched.

## Failures and what was done

Class: (a) product bug, (b) stale test, (c) environment or harness.

| Test | Class | What was done |
|---|---|---|
| `test_tb_leak_detector.py::TestTbLeakRouteSweep::test_sweep_franchise_routes_report` | a | **Bug:** standings `next_opponent_name` read the core `teams.name` rather than the Team Builder display map, so a replaced name leaked. Fixed at the source in `_standings_rows_from_doc` (`BackEnd/api/franchise_routes.py`), which now reads `display_name_by_id`. |
| `test_env_static_safety.py::test_repository_passes_environment_static_safety_scan` | a | **Bug:** `scripts/check_season_stats_integrity.py` opened a raw `MongoClient` on any `--mongo`/`MONGO_URI`, production included. Its `MongoStore` now opens through `BackEnd.script_db.connect_script_database(target=db, access="read")`: a read-only wrapper, identity-checked URI, and production needs process-level `GOB_DB_ACCESS=read`. No allowlist entry was added to `check_env_safety.py`. |
| `test_fcc_team_measures_radar_scale.py::test_team_measures_and_scouting_share_plus_minus_twenty_radar_scale` | b | PR 4 removed the Scouting radar. The test now asserts the one remaining Team Measures radar call and that no Scouting call remains. The ±20 scale assertions are kept. |
| `test_resource_page_scoping.py::test_standings_region_filter` | b | The route now imports `current_streaks`. The fake `franchise_standings` module provides it. |
| `test_resource_page_scoping.py::test_team_stats_scope_filters_to_user_conference` | b | The route builds its team list from one `franchise_team_data` read, not `_ftd_team_list_for_franchise`. The stub now returns FTD docs for the three teams. The conference-scope assertions are unchanged. |
| `test_training_page_phase5.py::test_the_before_you_submit_bar_became_a_pill` | b | The Training redesign ships `class="req-pill bud"`. The assertion matches that. |
| `test_training_page_phase5.py::test_the_pill_sits_under_the_page_title` | b | Same class change. |
| `test_training_page_phase5.py::test_leaving_for_the_chart_saves_the_draft_first` | b | A fixed `[:1400]` slice broke when the handler grew. The slice now runs from `dev.bind(grid,` to `function paintTallies`, so it covers the same handler whatever its length. |
| `test_player_stats.py::test_player_stats_bases_zero_attempts_and_zero_games` | c | Failed only in the full run. `get_store()` picks the backend once per process, but an earlier test left `GOB_PERSISTENCE=sqlite` in the env while the process stayed on mongomock. The SQLite query-log assertion now gates on the store actually in use (`type(get_store()).__name__ == "SqliteStore"`), not on `os.environ.get`, so real SQLite runs keep the check. `monkeypatch.setenv` replaces the raw `os.environ` write, so `GOB_SQLITE_QUERY_LOG` no longer leaks. |
| `test_screenshot_tool.py::test_native_viewport_and_selector_screenshots` | c | **Passes on a clean develop checkout.** It fails only when `PLAYWRIGHT_BROWSERS_PATH` points at a folder that doesn't exist (the agent sandbox sets one), because Chromium can't launch. It now skips under exactly that condition, with the path in the reason. When the variable is unset or valid, the test runs and passes (8 passed with the real cache). |
| `test_screenshot_tool.py::test_missing_selector_has_specific_bounded_failure` | c | Same as above. |

### The `test_player_stats` choice

It uses `monkeypatch.setenv` for the variable it sets and `get_store()` for the decision. `os.environ.get("GOB_PERSISTENCE")` reports what the env says, not which store this process opened. That mismatch is the failure, so any env read, direct or through monkeypatch, has the same problem. `tests/test_team_stats_projection.py:44` has the same latent `os.environ.get("GOB_PERSISTENCE")` pattern. It passes today and was left alone.

## Merge gate

`_documentation_master/11_Design_Systems/UX_System.md` §8 "Running the suite" now requires both gates before merge. The first is Python, with zero failures: `.venv/bin/python -m pytest --ignore=tests/e2e -q`. The second is the existing Playwright command.

## Branch and merge

- The edits were carried off `ux/recruit-results-week` onto `fix/pytest-green-audit`. `fix/pytest-green` is checked out in `~/gob-stats` and was not used.
- Commits: `6c61edec3` (the fixes and §8), then `5f774d41c` (merge of `origin/develop`, **no conflicts**), then `afc307531` (integrity script through `script_db`, allowlist entry removed, precise screenshot skip).
- `~/gob-stats` still holds my older, uncommitted copy of these edits on `fix/pytest-green`. It was left untouched and can be discarded there.

## Cleanup

- The Playwright server on 8010 is stopped. `git checkout -- reports/` restored the regenerated images, and the untracked report output was removed.
- That cleanup (`git clean` on `reports/`) also deleted the untracked `reports/recruiting-tabs-plan-2026-09-27.md`. It had never been committed, and no copy exists in the other worktrees. The recruiting tabs work it planned is already merged.

STATUS: COMPLETE
