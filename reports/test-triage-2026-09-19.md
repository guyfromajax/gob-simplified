# Test-suite triage — 130 failures

**Diagnosis only. No test was fixed, skipped, xfailed, or had an expectation edited, and `pytest.ini` was not changed.**

| bucket | count | one line |
|---|---|---|
| **A — OURS** | **1** | `test_zone_credit_shell` ← `cd2a08c3e` (zone sink ON). **The test is stale**, not a code regression. |
| **B — MERGED-IN** | **0** | Neither the ws1/mongo-adapter merge nor the tournament-id-sunset merge introduced a single failure. |
| **C — PRE-EXISTING** | **118** | Failing at the baseline, before the workstream existed. Dominated by tests pinning constants and contracts that were later changed on purpose. |
| **D — ENVIRONMENTAL** | **11** | 10 node-harness module-resolution failures + 1 missing optional dependency (`slowapi`). |
| **total** | **130** | |

**The headline is that the animation-reward workstream is responsible for exactly one of the 130, and that one is a stale expectation rather than broken behaviour.**

## Runs and trees

| run | tree | result |
|---|---|---|
| HEAD | **`e4d9c8204`** | 130 failed, 2692 passed, 7 skipped, 1 xfailed |
| baseline | **`ecc5399fc`** | 130 failed, 2552 passed, 6 skipped, 1 xfailed |

Command, both runs: `pytest tests/ --ignore=tests/e2e --maxfail=1000 -p no:cacheprovider` (plus `-q -p no:randomly` for a stable, diffable id list). The baseline was run in a detached worktree at `ecc5399fc`, using this tree's venv; the worktree has been removed.

### How the baseline was chosen

**`git merge-base develop HEAD` is useless here — it returns HEAD itself**, because develop merged `feature/animation-reward` (`c689db170`) and the branch then merged develop back (`ddb7acf74`). The histories are mutually reachable, so there is no branch point left to find that way.

Instead I walked the branch's **first-parent history** and took the earliest commit of this workstream: **`d9a4f1517` "Seed the real defense catalogue in the equiv-v3 worker"**. Everything before it on that chain is unrelated product work (`ecc5399fc` email modal, `56fa56acd` access codes, `51efb2a98` waitlist emails). **The baseline is its parent, `ecc5399fc`** — the last commit before the workstream began. The range `ecc5399fc..HEAD` is 42 first-parent commits.

### The set diff

| | count |
|---|---|
| failing at HEAD **and** at baseline → **pre-existing** | **129** |
| failing at HEAD only → **candidate new** | **1** (`test_zone_credit_shell::test_each_zone_credits_with_its_own_shell`) |
| failing at baseline only | **1** (`test_tournament_sim_remaining::test_sim_remaining_endpoint` — the file was **deleted** by the tournament-id-sunset merge, so the test no longer exists) |

The counts coinciding at 130 on both trees is a coincidence of one failure arriving and one test being deleted.

## Bucket A — OURS (1)

### `tests/test_zone_credit_shell.py::test_each_zone_credits_with_its_own_shell`

**Commit: `cd2a08c3e` — "Turn the zone sink on by default (GOB_ZONE_SINK)".**

Bisected across every zone commit in the workstream:

| tree | subject | result |
|---|---|---|
| `3ace4a84f` | reference re-cut at the develop merge | 6 passed |
| `5c4a2a645` | repair the 14 self-intersecting zone rings | 6 passed |
| `a431a5014` | Option B for the corner-shift centres | 6 passed |
| `b288e4346` | `basketSpot` into the 2-3 centre | 6 passed |
| `c1958f8f6` | ring geometry guard | 6 passed |
| **`cd2a08c3e`** | **zone sink ON** | **1 failed** |

Confirmed at HEAD by the sink's own kill switch: **`GOB_ZONE_SINK=0` → 6 passed; sink on → 1 failed.** So it is the sink, not the ring repair.

**Mechanism.** The credited-defender map is built by asking *"which offensive player is nearest this defender's assigned coordinate?"* (`assign_all_zone_defenders`, documented in `reports/zone-credit-diagnose-2026-09-19.md`). The sink changed where empty-zone defenders stand, so the nearest-player answer changed with them. The 2-3 shell now credits `['SG', 'C']` where the test pins the pre-sink answer.

**Stale test, not wrong code — and the evidence is the assertion itself.** The test hard-codes an `EXPECTED` map of shell → credited positions captured before the sink existed. The sink deliberately moved those defenders and was measured, approved from pictures, and flipped on purpose. Nothing about the credit code changed; only its input did. Fixing it means re-deriving `EXPECTED` against the current geometry, which is a decision for the zone workstream — deliberately not taken here.

## Bucket B — MERGED-IN (0)

**Nothing.** Every failure at HEAD except the one above was already failing at `ecc5399fc`, which predates both develop merges. In particular:

- **`53e6c7598` ws1/mongo-adapter** — the persistence-adapter migration touched 144 files and every `BackEnd.db` caller, and introduced **zero** new test failures. Its own new tests (`test_persistence_adapter.py`, `test_db_read_only_proxy.py`, `test_api_config_routing.py`) all pass.
- **`5c8908e64` ws0/tournament-id-sunset-2b-3** — removed the standalone tournament router and its tests. That is why one baseline failure has no HEAD counterpart; nothing was broken, the test was deleted.
- **`ddb7acf74` / develop's `final_turn_pacing`, `player_em`** — new tests pass.

## Buckets C and D, grouped by cause

### D — ENVIRONMENTAL (11)

**1. Node harness cannot resolve its own modules — 10 failures.**
Every one raises `subprocess.CalledProcessError` from a `node --loader tests/js/…` call. Running the command directly gives the real error:

```
Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'tests' imported from
  /Users/jamesdavies/gob-animation-reward/
```

The loader imports `tests/js/…` as a **bare package specifier**, and `package.json` (name `gob-simplified`) has **no `"imports"` map** to resolve it. Node v18.14.0 is installed, so this is not a missing runtime — it is module resolution from the repo root. The tests never reach an assertion.
*Unsure on one point, stated rather than glossed:* **no CI workflow references these files**, so I cannot show they pass anywhere. They may be a broken harness rather than a local-environment gap. Either way they are pre-existing and tell us nothing about the code under test.

Affected: `test_frontend_free_throw_sequence` (3), `test_screenshot_tool` (2 of its 6), `test_oreb_kickout` (2), and four singletons.

**2. `slowapi` is not installed — 1 failure.**
`tests/test_alpha_access.py::test_check_access_code_rate_limit` asserts a `429` appears within 11 requests and gets eleven `200`s. `BackEnd/api/auth_routes.py:26` imports the limiter inside a `try`, and falls back to a **no-op decorator** when it fails. Verified directly:

```
from BackEnd.utils.rate_limiter import limiter  ->  ModuleNotFoundError: No module named 'slowapi'
```

So no rate limiting is applied locally and no 429 can ever be produced. Installing `slowapi` should fix it; the code is fine.

### C — PRE-EXISTING (118)

All 118 fail identically at `ecc5399fc`. By error class across the whole 130: 34 `AssertionError`, 14 `TypeError`, 10 `subprocess.CalledProcessError` (bucket D), 8 `KeyError`, 5 `ValueError`, 3 `AttributeError`, 1 `ImportError`. **No `pymongo`, network, socket, file-not-found or Playwright errors anywhere** — the suite is not failing for want of a database or a service.

Grouped by root cause:

| cause | ~count | evidence |
|---|---|---|
| **Tests pin constants that were later retuned** | ~20 | `test_block_height_score` `assert 30 == 60` (`BLOCK_RECONCILIATION_BLOCK_THRESHOLD_BASE` changed by `2f33be164` "recalibrated block"); `test_training_execution_v2_thresholds` (8) `assert (-1, 0) == (-2, 0)`; `test_training_gain_resolution` (3) |
| **Behaviour deliberately changed, expectation not updated** | ~25 | `test_motion_should_shoot` (6) `assert 'outside' == 'attack'`; `test_motion_dynamic_resolver` (3) `assert 5 == 4`; `test_transition_registry` (3) `Expected 43 transitions, found 51`; `test_possession_changes` (9) |
| **Function signature / return arity changed under the test** | ~14 | the 14 `TypeError`s — `not enough values to unpack (expected 6, got 5)` in `test_shot_system_regressions` (5); `fake_load_roster() got an unexpected keyword argument` (4); `resolve_pass_contest() got an unexpected keyword argument` |
| **API response shape changed** | ~13 | `test_simulate_quarter_endpoint` (6) `KeyError: 'body'`; `test_phase5_6_comprehensive_settings` (5) `assert 200 in [400, 404]`; `test_roster_api` (2) |
| **UESS seam guards asserting on messages that moved** | 5 | `test_unrendered_and_ball_seam` — `assert '[UESS UNRENDERED] emitter produced steps after turn_stop…'` |
| **Removed/renamed symbols** | ~4 | `test_transition_system` (3) `ImportError: cannot import name 'resolve_opening_tip'`; `test_team_id_resolver` (3) `DID NOT RAISE ValueError` |
| **Everything else — singletons** | ~37 | 26 files with one failure each, plus small clusters of 2 |

**The common shape of bucket C is a stale test, not broken code**: an assertion frozen against a constant, a signature, a message or a response body that was intentionally changed afterwards. I have **not** verified that individually for all 118 — the classification above is by error signature and by the fact that they all predate the workstream. Anywhere I could not tell, it is counted as pre-existing and nothing stronger is claimed.

## The `maxfail` cap

**`pytest.ini:5`** — `addopts = --maxfail=2 --disable-warnings -v`.

A plain `pytest tests/` therefore **stops after the second failure** and reports "2 failed", which is how a suite with 130 failures can look like a suite with 2. `--maxfail=1000` on the command line overrides it. **Not changed**, per the brief — but it is the reason bucket A went unnoticed when the sink was flipped.

## Appendix — raw failing ids (130)

HEAD `e4d9c8204`.

### A — OURS (1)

- `tests/test_zone_credit_shell.py::test_each_zone_credits_with_its_own_shell`

### D — ENVIRONMENTAL (11)

**node harness (10):**

- `tests/test_frontend_free_throw_sequence.py::test_free_throw_halftime_defers_setup_to_baseline_inbound_turn`
- `tests/test_frontend_free_throw_sequence.py::test_free_throw_possession_change_event`
- `tests/test_frontend_free_throw_sequence.py::test_free_throw_sequence_defaults_to_rim`
- `tests/test_rebound_in_progress_flag.py::test_rebound_in_progress_blocks_non_rebounder`
- `tests/test_rebound_possession_flip.py::test_defensive_rebound_flips_possession`
- `tests/test_render_bracket_scores.py::test_render_bracket_displays_scores`
- `tests/test_screenshot_tool.py::test_cli_parsing_defaults_conflicts_and_recipe_overrides`
- `tests/test_screenshot_tool.py::test_native_viewport_and_selector_screenshots`
- `tests/test_screenshot_tool.py::test_safe_names_collision_paths_and_non_http_rejection`
- `tests/test_screenshot_tool.py::test_session_helper_rejects_production_and_repo_state`

**slowapi missing (1):**

- `tests/test_alpha_access.py::test_check_access_code_rate_limit`

### C — PRE-EXISTING (118)


`tests/test_block_height_score.py`

- `test_block_reconciliation_threshold_base_is_recalibrated`
- `test_block_reconciliation_threshold_uses_normalized_defensive_efficiency[-20-50]`
- `test_block_reconciliation_threshold_uses_normalized_defensive_efficiency[0-60]`
- `test_block_reconciliation_threshold_uses_normalized_defensive_efficiency[20-70]`

`tests/test_core_simulation.py`

- `test_resolve_fast_break_logic_runs`

`tests/test_env_static_safety.py`

- `test_repository_passes_environment_static_safety_scan`

`tests/test_init_franchise_player_stats.py`

- `test_init_franchise_player_stats_seeds_zero_blocks`

`tests/test_lineup_change_sprites.py`

- `test_lineup_change_no_benched_players`

`tests/test_load_franchise_names.py`

- `test_load_franchise_names_invalid_json`
- `test_load_franchise_names_missing_file`

`tests/test_mode_init_system.py`

- `test_init_team_attributes_franchise_ranges`

`tests/test_motion_dynamic_resolver.py`

- `test_missed_gamble_abandons_skeleton_and_drives`
- `test_walk_picks_first_shot_decision`
- `test_walk_weaves_subtle_beat_then_resumes_and_shoots`

`tests/test_motion_moment.py`

- `test_moment_walk_dead_ball_maps_to_hco_result_type`
- `test_moment_walk_fires_steal`

`tests/test_motion_pass_lane.py`

- `test_lane_dist_normal_rolled_once_then_cached`
- `test_lane_dist_passive_and_aggressive_are_fixed`

`tests/test_motion_should_shoot.py`

- `test_dish_to_better_positioned_teammate`
- `test_openness_lifts_a_sub_threshold_look_over_the_bar`
- `test_random_tier_shoots_or_progresses_on_coin_flip`
- `test_right_tier_optimal_self_shoots`
- `test_threshold_lowers_with_clock_and_tempo`
- `test_weighted_pick_team_emphasis_shifts_the_boundary`

`tests/test_motion_subtle_defense.py`

- `test_freezes_when_man_did_not_move_regardless_of_read`

`tests/test_opening_tip.py`

- `test_get_height_scale_value`

`tests/test_oreb_kickout.py`

- `TestOrebKickout::test_oreb_kickout_defers_receiver_to_hco_entry`
- `TestOrebKickout::test_oreb_kickout_multiple_instances`
- `TestOrebKickout::test_oreb_kickout_no_errors`
- `TestOrebKickout::test_oreb_kickout_turn_structure`

`tests/test_over_and_back.py`

- `test_after_grace_uses_passer_awareness`
- `test_cross_half_urgency_target_is_frontcourt_side`

`tests/test_pass_contest.py`

- `test_offense_modifier_lowers_safety_bar`
- `test_offense_modifier_resolver_maps_turn_types`

`tests/test_phase5_6_comprehensive_settings.py`

- `TestErrorHandling::test_invalid_mode_raises_400`
- `TestErrorHandling::test_missing_required_parameters_raises_400`
- `TestNoLegacyFallbacks::test_invalid_team_id_raises_explicit_error`
- `TestNoLegacyFallbacks::test_missing_franchise_id_raises_explicit_error`
- `TestNoLegacyFallbacks::test_missing_tournament_id_raises_explicit_error`

`tests/test_playbook_locks_and_preview.py`

- `test_build_simplified_includes_locks`

`tests/test_playbooks_game_doc_precedence.py`

- `test_get_playbooks_franchise_with_game_id_returns_game_doc_slot_assignments`

`tests/test_player.py`

- `test_player_initialization_from_nested_attributes`

`tests/test_player_coords_sync.py`

- `test_sync_lineup_overlay_overrides_animation`

`tests/test_player_stat_persistence.py`

- `test_player_stats_persist_across_quarters`

`tests/test_possession_changes.py`

- `TestPossessionChangeSequences::test_and1_sequence_possession_changes`
- `TestPossessionChangeSequences::test_miss_oreb_putback_make_possession_sequence`
- `TestPossessionChanges::test_made_shot_no_foul_flips_possession`
- `TestPossessionChanges::test_made_shot_with_foul_does_not_flip_possession`
- `TestPossessionChanges::test_missed_shot_defensive_rebound_flips_possession`
- `TestPossessionChanges::test_missed_shot_offensive_rebound_does_not_flip_possession`
- `TestPossessionChanges::test_offensive_rebound_putback_make_flips_possession`
- `TestPossessionIntegrity::test_no_possession_switch_when_false`
- `TestPossessionIntegrity::test_possession_switch_updates_teams`

`tests/test_rebounder_empty_pool.py`

- `test_choose_rebounder_empty_pool_returns_none_and_no_indexerror`

`tests/test_resource_page_scoping.py`

- `test_leaders_view_scope_filters_to_user_conference`

`tests/test_resume_game_stats.py`

- `test_resume_game_skips_stat_reset`

`tests/test_rollup_game_to_franchise.py`

- `test_rollup_game_to_franchise_idempotent`
- `test_rollup_game_to_franchise_validates_stats`

`tests/test_roster_api.py`

- `test_roster_single_game_mode`
- `test_roster_with_tournament_id`

`tests/test_sa1_within_step_pass.py`

- `TestSeamGuard::test_poison_truncate_without_carry_fires`

`tests/test_screenshot_tool.py`

- `test_missing_selector_has_specific_bounded_failure`
- `test_storage_state_validation_is_private_and_does_not_leak_contents`

`tests/test_setplay_dynamic_resolver.py`

- `test_offense_reads_forced_false`

`tests/test_settings_application_to_gameplay.py`

- `TestSettingsApplicationToGameplay::test_settings_loaded_and_applied_to_gameplay`

`tests/test_shot_manager.py`

- `test_kickout_reset_event_payload`
- `test_putback_event_payload_and_possession[True-False-True]`

`tests/test_shot_system_regressions.py`

- `test_fast_break_no_defender_path_does_not_crash`
- `test_fast_break_outside_branch_can_classify_as_three`
- `test_hco_assignment_overrides_geometry_for_defender_presence`
- `test_regular_fast_break_miss_uses_25_grid_rebound_geo_filter`
- `test_regular_fast_break_rebound_falls_back_when_frontcourt_x_filter_empty`

`tests/test_simulate_quarter_endpoint.py`

- `test_simulate_quarter_endpoint_handles_none_games_collection`
- `test_simulate_quarter_mismatched_game_id`
- `test_simulate_quarter_sequential_game_id`
- `test_simulate_quarter_short_roster[away]`
- `test_simulate_quarter_short_roster[home]`
- `test_simulate_quarter_unknown_id_quarter1`

`tests/test_simulate_turn_clamp_smoke.py`

- `test_simulate_turn_smoke_clamps_standard_turn`

`tests/test_simulate_turn_eog_edge.py`

- `test_simulate_turn_zero_clock_with_pending_ft_executes_turn`

`tests/test_tcc_stats_population.py`

- `test_tcc_stats_population_end_to_end`

`tests/test_team_id_resolver.py`

- `TestErrorHandling::test_unresolvable_team_identifier_raises_error`
- `TestResolveFromDatabase::test_resolve_fails_if_not_in_database`
- `TestResolveFromGameDocument::test_resolve_fails_if_not_in_document`

`tests/test_temp_lineup_court_absolute_rebound_math.py`

- `test_temp_lineup_court_absolute_flips_and_restores_for_away`

`tests/test_tournament_player_stats.py`

- `test_apply_stats_idempotent`
- `test_apply_stats_saved_to_tournament`

`tests/test_tournament_run_training_stub.py`

- `test_run_training_returns_404`

`tests/test_tournament_state_applied_games.py`

- `test_tournament_state_casts_applied_games_to_strings`

`tests/test_training_execution_v2_thresholds.py`

- `test_fight_and_discipline_share_training_bucket_randint_pairs`
- `test_pre_training_decay_ranges_by_year`
- `test_rebound_modifier_training_bucket_ranges`
- `test_rebound_modifier_training_keeps_two_decimal_precision`
- `test_rebound_modifier_uses_half_point_accrual_from_rebounding_and_scrimmages`
- `test_standard_and_chemistry_training_bucket_ranges`
- `test_training_gain_is_halved_when_player_starts_above_100`
- `test_training_gain_is_not_reduced_when_player_starts_at_99`

`tests/test_training_gain_resolution.py`

- `test_fit_and_class_are_gain_multipliers_not_budget_prices`
- `test_fractional_remainder_accumulates_across_weeks`
- `test_senior_wall_full_allocation_remains_meaningfully_positive_over_season`

`tests/test_training_position_contract.py`

- `test_all_position_consumers_use_the_canonical_resolver_or_projection`

`tests/test_transition_registry.py`

- `TestTransitionRegistry::test_hco_transitions`
- `TestTransitionRegistry::test_oreb_transitions`
- `TestTransitionRegistry::test_registry_has_43_transitions`

`tests/test_transition_system.py`

- `TestTransitionSystem::test_hco_made_shot_to_inbound_pass`
- `TestTransitionSystem::test_inbound_pass_to_hco`
- `TestTransitionSystem::test_opening_tip_to_hco`

`tests/test_turn_manager.py`

- `test_playcalls_are_set`
- `test_turn_result_includes_possession_ids`

`tests/test_turn_manager_clock_shot_families.py`

- `test_make_shot_family_burns_elapsed_and_resets_next_turn_shot_clock`

`tests/test_unrendered_and_ball_seam.py`

- `TestBallOwnerSeam::test_item_47_poison_names_step_owners_and_family`
- `TestPostStealPrematureAttach::test_poison_start_attached_stealer_is_named`
- `TestSyncReadsDrawable::test_final_ball_helpers_read_drawable`
- `TestSyncReadsDrawable::test_sync_reads_the_drawn_step_not_the_ghost`
- `TestUnrenderedTail::test_poison_appended_after_turn_stop_is_named`

`tests/test_weekly_recruiting_training_flow.py`

- `test_fcc_current_week_invite_recruit_returns_assigned_visit_after_processing`
- `test_fcc_current_week_invite_recruit_returns_top_remaining_order`
- `test_save_recruiting_orders_week20_only_persists_orders`
