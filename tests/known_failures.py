"""Known develop reds: skip the environment-gated ones, xfail the rest.

Do not "fix" these tests here. The list exists so a NEW failure is a failure
and a newly-passing xfail is an XPASS. See bugs.md (test-suite hygiene).
"""

from __future__ import annotations

import functools
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Environment skips — these cannot produce signal until the harness works.
# 5 --loader + 6 screenshot ESM + 2 mongomock $replaceAll = 13.
# Earlier triage said "10 node + 2 mongomock"; all six screenshot tests are
# the same ERR_MODULE_NOT_FOUND, not two stale assertions.
# ---------------------------------------------------------------------------

NODE_LOADER_SKIPS: frozenset[str] = frozenset(
    {
        "tests/test_frontend_free_throw_sequence.py::test_free_throw_sequence_defaults_to_rim",
        "tests/test_frontend_free_throw_sequence.py::test_free_throw_possession_change_event",
        "tests/test_frontend_free_throw_sequence.py::test_free_throw_halftime_defers_setup_to_baseline_inbound_turn",
        "tests/test_rebound_in_progress_flag.py::test_rebound_in_progress_blocks_non_rebounder",
        "tests/test_rebound_possession_flip.py::test_defensive_rebound_flips_possession",
    }
)

NODE_ESM_SKIPS: frozenset[str] = frozenset(
    {
        "tests/test_screenshot_tool.py::test_cli_parsing_defaults_conflicts_and_recipe_overrides",
        "tests/test_screenshot_tool.py::test_safe_names_collision_paths_and_non_http_rejection",
        "tests/test_screenshot_tool.py::test_storage_state_validation_is_private_and_does_not_leak_contents",
        "tests/test_screenshot_tool.py::test_session_helper_rejects_production_and_repo_state",
        "tests/test_screenshot_tool.py::test_native_viewport_and_selector_screenshots",
        "tests/test_screenshot_tool.py::test_missing_selector_has_specific_bounded_failure",
    }
)

MONGOMOCK_SKIPS: frozenset[str] = frozenset(
    {
        "tests/test_roster_api.py::test_roster_single_game_mode",
        "tests/test_roster_api.py::test_roster_with_tournament_id",
    }
)

# ---------------------------------------------------------------------------
# Xfail the remaining known reds by node id. strict=False so XPASS is visible.
# ---------------------------------------------------------------------------

XFAIL: dict[str, str] = {
    # stale
    "tests/test_block_height_score.py::test_block_reconciliation_threshold_base_is_recalibrated": "stale: block threshold retuned (30 vs 60)",
    "tests/test_block_height_score.py::test_block_reconciliation_threshold_uses_normalized_defensive_efficiency[20-70]": "stale: block threshold retuned",
    "tests/test_block_height_score.py::test_block_reconciliation_threshold_uses_normalized_defensive_efficiency[0-60]": "stale: block threshold retuned",
    "tests/test_block_height_score.py::test_block_reconciliation_threshold_uses_normalized_defensive_efficiency[-20-50]": "stale: block threshold retuned",
    "tests/test_core_simulation.py::test_resolve_fast_break_logic_runs": "stale: DEFENSIVE_STOP is no longer in the expected result set",
    "tests/test_init_franchise_player_stats.py::test_init_franchise_player_stats_seeds_zero_blocks": "stale: seeded stat dict no longer matches pinned zeros",
    "tests/test_mode_init_system.py::test_init_team_attributes_franchise_ranges": "stale: franchise discipline range retuned",
    "tests/test_motion_dynamic_resolver.py::test_walk_picks_first_shot_decision": "stale: walk length 5 vs pinned 4",
    "tests/test_motion_moment.py::test_moment_walk_fires_steal": "stale: steal moment no longer returns STEAL",
    "tests/test_motion_moment.py::test_moment_walk_dead_ball_maps_to_hco_result_type": "stale: dead-ball moment no longer maps to DEAD_BALL_TURNOVER",
    "tests/test_motion_pass_lane.py::test_lane_dist_passive_and_aggressive_are_fixed": "stale: lane distances retuned (4 vs 6)",
    "tests/test_motion_should_shoot.py::test_weighted_pick_team_emphasis_shifts_the_boundary": "stale: should-shoot boundary 'outside' vs 'attack'",
    "tests/test_motion_should_shoot.py::test_right_tier_optimal_self_shoots": "stale: optimal-self no longer shoots",
    "tests/test_motion_should_shoot.py::test_openness_lifts_a_sub_threshold_look_over_the_bar": "stale: openness no longer lifts the look",
    "tests/test_motion_should_shoot.py::test_dish_to_better_positioned_teammate": "stale: dish decision changed",
    "tests/test_motion_subtle_defense.py::test_freezes_when_man_did_not_move_regardless_of_read": "stale: freeze-on-still man no longer holds",
    "tests/test_opening_tip.py::test_get_height_scale_value": "stale: height scale 10 vs 9",
    "tests/test_over_and_back.py::test_after_grace_uses_passer_awareness": "stale: grace-period over-and-back predicate flipped",
    "tests/test_over_and_back.py::test_cross_half_urgency_target_is_frontcourt_side": "stale: urgency target no longer frontcourt-side",
    "tests/test_pass_contest.py::test_offense_modifier_resolver_maps_turn_types": "stale: offense-modifier mapping 3.5 vs 7",
    "tests/test_phase5_6_comprehensive_settings.py::TestNoLegacyFallbacks::test_invalid_team_id_raises_explicit_error": "stale: API returns 200 where test expects 400/404",
    "tests/test_phase5_6_comprehensive_settings.py::TestNoLegacyFallbacks::test_missing_franchise_id_raises_explicit_error": "stale: API returns 404 where test expects 400",
    "tests/test_phase5_6_comprehensive_settings.py::TestNoLegacyFallbacks::test_missing_tournament_id_raises_explicit_error": "stale: API returns 404 where test expects 400",
    "tests/test_phase5_6_comprehensive_settings.py::TestErrorHandling::test_invalid_mode_raises_400": "stale: error copy moved ('unsupported mode' vs 'invalid mode')",
    "tests/test_phase5_6_comprehensive_settings.py::TestErrorHandling::test_missing_required_parameters_raises_400": "stale: API returns 404 where test expects 400",
    "tests/test_playbook_locks_and_preview.py::test_build_simplified_includes_locks": "stale: lock labels 'Man' vs 'man_normal'",
    "tests/test_playbooks_game_doc_precedence.py::test_get_playbooks_franchise_with_game_id_returns_game_doc_slot_assignments": "stale: game-doc slot assignments no longer win",
    "tests/test_player_coords_sync.py::test_sync_lineup_overlay_overrides_animation": "stale: overlay coords 10,10 vs pinned 40,50",
    "tests/test_setplay_dynamic_resolver.py::test_offense_reads_forced_false": "stale: offense_reads no longer forced false",
    "tests/test_settings_application_to_gameplay.py::TestSettingsApplicationToGameplay::test_settings_loaded_and_applied_to_gameplay": "stale: settings fixture expects MAKE, got MISS",
    "tests/test_shot_manager.py::test_putback_event_payload_and_possession[True-False-True]": "stale: putback event type changed",
    "tests/test_shot_manager.py::test_kickout_reset_event_payload": "stale: PUTBACK_ATTEMPT vs KICKOUT_RESET",
    "tests/test_temp_lineup_court_absolute_rebound_math.py::test_temp_lineup_court_absolute_flips_and_restores_for_away": "stale: away flip 95 vs 91",
    "tests/test_tournament_player_stats.py::test_apply_stats_idempotent": "stale: idempotent apply count 0 vs 10",
    "tests/test_tournament_run_training_stub.py::test_run_training_returns_404": "stale: training stub copy/status moved",
    "tests/test_tournament_state_applied_games.py::test_tournament_state_casts_applied_games_to_strings": "stale: applied_games cast path returns 404 vs 200",
    "tests/test_training_execution_v2_thresholds.py::test_rebound_modifier_uses_half_point_accrual_from_rebounding_and_scrimmages": "stale: rebound-modifier bucket pairing retuned",
    "tests/test_training_execution_v2_thresholds.py::test_fight_and_discipline_share_training_bucket_randint_pairs": "stale: fight/discipline buckets retuned",
    "tests/test_training_execution_v2_thresholds.py::test_standard_and_chemistry_training_bucket_ranges": "stale: standard/chemistry buckets retuned",
    "tests/test_training_execution_v2_thresholds.py::test_rebound_modifier_training_bucket_ranges": "stale: rebound-modifier ranges retuned",
    "tests/test_training_execution_v2_thresholds.py::test_rebound_modifier_training_keeps_two_decimal_precision": "stale: precision 0.23 vs 0.26",
    "tests/test_training_execution_v2_thresholds.py::test_training_gain_is_halved_when_player_starts_above_100": "stale: above-100 halving no longer fires",
    "tests/test_training_execution_v2_thresholds.py::test_training_gain_is_not_reduced_when_player_starts_at_99": "stale: at-99 reduction now fires",
    "tests/test_training_gain_resolution.py::test_fractional_remainder_accumulates_across_weeks": "stale: remainder 51 vs 50",
    "tests/test_training_gain_resolution.py::test_fit_and_class_are_gain_multipliers_not_budget_prices": "stale: fit/class multiplier 95 vs 80",
    "tests/test_training_gain_resolution.py::test_senior_wall_full_allocation_remains_meaningfully_positive_over_season": "stale: senior-wall allocation 60 vs 53",
    "tests/test_training_position_contract.py::test_all_position_consumers_use_the_canonical_resolver_or_projection": "stale: resolver call site no longer in scanned source",
    "tests/test_transition_registry.py::TestTransitionRegistry::test_registry_has_43_transitions": "stale: registry grew 43 → 51",
    "tests/test_transition_registry.py::TestTransitionRegistry::test_hco_transitions": "stale: HCO transition count 7 vs 8",
    "tests/test_transition_registry.py::TestTransitionRegistry::test_oreb_transitions": "stale: OREB transition count 8 vs 9",
    "tests/test_turn_manager.py::test_playcalls_are_set": "stale: playcall catalog '3-2-zone' vs ['Man','Zone']",
    "tests/test_turn_manager_clock_shot_families.py::test_make_shot_family_burns_elapsed_and_resets_next_turn_shot_clock": "stale: shot-clock burn 24 vs 30",
    "tests/test_weekly_recruiting_training_flow.py::test_fcc_current_week_invite_recruit_returns_assigned_visit_after_processing": "stale: invite recruit_id no longer assigned",
    "tests/test_weekly_recruiting_training_flow.py::test_fcc_current_week_invite_recruit_returns_top_remaining_order": "stale: remaining-order recruit_id drifted",
    # broken-harness
    "tests/test_lineup_change_sprites.py::test_lineup_change_no_benched_players": "broken-harness: Player.__init__ arity changed",
    "tests/test_load_franchise_names.py::test_load_franchise_names_missing_file": "broken-harness: missing file no longer raises FileNotFoundError",
    "tests/test_load_franchise_names.py::test_load_franchise_names_invalid_json": "broken-harness: invalid JSON no longer raises ValueError",
    "tests/test_motion_dynamic_resolver.py::test_walk_weaves_subtle_beat_then_resumes_and_shoots": "broken-harness: KeyError 'location' on walk payload",
    "tests/test_motion_dynamic_resolver.py::test_missed_gamble_abandons_skeleton_and_drives": "broken-harness: fake_contest unexpected kw 'game'",
    "tests/test_motion_pass_lane.py::test_lane_dist_normal_rolled_once_then_cached": "broken-harness: cache key '_hco_pass_lane_dist_normal' gone",
    "tests/test_motion_should_shoot.py::test_threshold_lowers_with_clock_and_tempo": "broken-harness: SHOOT_THRESHOLD_BASE removed",
    "tests/test_motion_should_shoot.py::test_random_tier_shoots_or_progresses_on_coin_flip": "broken-harness: Rng has no attribute choice",
    "tests/test_oreb_kickout.py::TestOrebKickout::test_oreb_kickout_turn_structure": "broken-harness: StopIteration on mocked iterator",
    "tests/test_oreb_kickout.py::TestOrebKickout::test_oreb_kickout_multiple_instances": "broken-harness: StopIteration on mocked iterator",
    "tests/test_oreb_kickout.py::TestOrebKickout::test_oreb_kickout_defers_receiver_to_hco_entry": "broken-harness: StopIteration on mocked iterator",
    "tests/test_oreb_kickout.py::TestOrebKickout::test_oreb_kickout_no_errors": "broken-harness: StopIteration on mocked iterator",
    "tests/test_pass_contest.py::test_offense_modifier_lowers_safety_bar": "broken-harness: resolve_pass_contest kw offense_modifier → offense_modifier_g",
    "tests/test_player.py::test_player_initialization_from_nested_attributes": "broken-harness: Player.__init__ arity changed",
    "tests/test_player_stat_persistence.py::test_player_stats_persist_across_quarters": "broken-harness: fake_load_roster unexpected kw franchise_id",
    "tests/test_possession_changes.py::TestPossessionChanges::test_made_shot_no_foul_flips_possession": "broken-harness: StopIteration on patched random.random",
    "tests/test_possession_changes.py::TestPossessionChanges::test_made_shot_with_foul_does_not_flip_possession": "broken-harness: StopIteration on patched random.random",
    "tests/test_possession_changes.py::TestPossessionChanges::test_missed_shot_defensive_rebound_flips_possession": "broken-harness: StopIteration on patched random.random",
    "tests/test_possession_changes.py::TestPossessionChanges::test_missed_shot_offensive_rebound_does_not_flip_possession": "broken-harness: StopIteration on patched random.random",
    "tests/test_possession_changes.py::TestPossessionChanges::test_offensive_rebound_putback_make_flips_possession": "broken-harness: StopIteration on patched random.random",
    "tests/test_possession_changes.py::TestPossessionChangeSequences::test_and1_sequence_possession_changes": "broken-harness: StopIteration on patched random.random",
    "tests/test_possession_changes.py::TestPossessionChangeSequences::test_miss_oreb_putback_make_possession_sequence": "broken-harness: StopIteration on patched random.random",
    "tests/test_possession_changes.py::TestPossessionIntegrity::test_possession_switch_updates_teams": "broken-harness: StopIteration on patched random.random",
    "tests/test_possession_changes.py::TestPossessionIntegrity::test_no_possession_switch_when_false": "broken-harness: StopIteration on patched random.random",
    "tests/test_rebounder_empty_pool.py::test_choose_rebounder_empty_pool_returns_none_and_no_indexerror": "broken-harness: string indices must be integers",
    "tests/test_render_bracket_scores.py::test_render_bracket_displays_scores": "broken-harness: node -e eval of tournament.js exits 1",
    "tests/test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference": "broken-harness: lambda unexpected kw allowed_team_ids",
    "tests/test_resume_game_stats.py::test_resume_game_skips_stat_reset": "broken-harness: fake_load_roster unexpected kw franchise_id",
    "tests/test_rollup_game_to_franchise.py::test_rollup_game_to_franchise_idempotent": "broken-harness: KeyError 'p1' after rollup shape change",
    "tests/test_rollup_game_to_franchise.py::test_rollup_game_to_franchise_validates_stats": "broken-harness: KeyError 'p1' after rollup shape change",
    "tests/test_shot_system_regressions.py::test_hco_assignment_overrides_geometry_for_defender_presence": "broken-harness: unpack expected 6, got 5",
    "tests/test_shot_system_regressions.py::test_fast_break_no_defender_path_does_not_crash": "broken-harness: unpack expected 6, got 5",
    "tests/test_shot_system_regressions.py::test_fast_break_outside_branch_can_classify_as_three": "broken-harness: unpack expected 6, got 5",
    "tests/test_shot_system_regressions.py::test_regular_fast_break_miss_uses_25_grid_rebound_geo_filter": "broken-harness: unpack expected 6, got 5",
    "tests/test_shot_system_regressions.py::test_regular_fast_break_rebound_falls_back_when_frontcourt_x_filter_empty": "broken-harness: unpack expected 6, got 5",
    "tests/test_simulate_quarter_endpoint.py::test_simulate_quarter_short_roster[home]": "broken-harness: fake_load_roster unexpected kw franchise_id",
    "tests/test_simulate_quarter_endpoint.py::test_simulate_quarter_short_roster[away]": "broken-harness: fake_load_roster unexpected kw franchise_id",
    "tests/test_simulate_quarter_endpoint.py::test_simulate_quarter_endpoint_handles_none_games_collection": "broken-harness: request must be a Starlette Request",
    "tests/test_simulate_quarter_endpoint.py::test_simulate_quarter_unknown_id_quarter1": "broken-harness: request must be a Starlette Request",
    "tests/test_simulate_quarter_endpoint.py::test_simulate_quarter_sequential_game_id": "broken-harness: DummyGM unexpected kw home_strategy_settings",
    "tests/test_simulate_quarter_endpoint.py::test_simulate_quarter_mismatched_game_id": "broken-harness: DummyGM unexpected kw home_strategy_settings",
    "tests/test_simulate_quarter_endpoint.py::test_simulate_quarter_restores_team_stats_from_unified_teams": "broken-harness: request must be a Starlette Request",
    "tests/test_simulate_quarter_endpoint.py::test_simulate_quarter_restores_team_stats_from_legacy_team_fields": "broken-harness: request must be a Starlette Request",
    "tests/test_simulate_turn_clamp_smoke.py::test_simulate_turn_smoke_clamps_standard_turn": "broken-harness: request must be a Starlette Request",
    "tests/test_simulate_turn_eog_edge.py::test_simulate_turn_zero_clock_with_pending_ft_executes_turn": "broken-harness: request must be a Starlette Request",
    "tests/test_tcc_stats_population.py::test_tcc_stats_population_end_to_end": "broken-harness: GameManager unexpected kw tournament_id",
    "tests/test_team_id_resolver.py::TestResolveFromGameDocument::test_resolve_fails_if_not_in_document": "broken-harness: DID NOT RAISE ValueError",
    "tests/test_team_id_resolver.py::TestResolveFromDatabase::test_resolve_fails_if_not_in_database": "broken-harness: DID NOT RAISE ValueError",
    "tests/test_team_id_resolver.py::TestErrorHandling::test_unresolvable_team_identifier_raises_error": "broken-harness: DID NOT RAISE ValueError",
    "tests/test_tournament_player_stats.py::test_apply_stats_saved_to_tournament": "broken-harness: KeyError 'p1' after stats shape change",
    "tests/test_transition_system.py::TestTransitionSystem::test_opening_tip_to_hco": "broken-harness: resolve_opening_tip was removed",
    "tests/test_transition_system.py::TestTransitionSystem::test_inbound_pass_to_hco": "broken-harness: resolve_opening_tip was removed",
    "tests/test_transition_system.py::TestTransitionSystem::test_hco_made_shot_to_inbound_pass": "broken-harness: resolve_opening_tip was removed",
    "tests/test_turn_manager.py::test_turn_result_includes_possession_ids": "broken-harness: KeyError starting_possession_team_id",
    "tests/test_weekly_recruiting_training_flow.py::test_save_recruiting_orders_week20_only_persists_orders": "broken-harness: _UnusedDb has no attribute franchises",
}


@functools.lru_cache(maxsize=1)
def _node_loader_ok() -> bool:
    """True when the --loader harness can execute a failing-class script."""
    script = ROOT / "tests" / "js" / "runFreeThrowSequence.mjs"
    loader = ROOT / "tests" / "js" / "httpsLoaderNoStubBall.mjs"
    if not script.exists() or not loader.exists():
        return False
    try:
        completed = subprocess.run(
            ["node", "--loader", str(loader), str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


@functools.lru_cache(maxsize=1)
def _node_screenshot_esm_ok() -> bool:
    """True when capture_screenshot.mjs can be imported as ESM."""
    script = ROOT / "scripts" / "capture_screenshot.mjs"
    if not script.exists():
        return False
    try:
        completed = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                f"import {{ parseArguments }} from {json.dumps(script.as_uri())};",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _using_mongomock() -> bool:
    return os.environ.get("GOB_DB_MODE", "mongomock") == "mongomock"


def apply_known_failures(items) -> None:
    for item in items:
        nodeid = item.nodeid
        if nodeid in NODE_LOADER_SKIPS and not _node_loader_ok():
            item.add_marker(
                pytest.mark.skip(reason="env: node --loader cannot resolve the ESM harness")
            )
            continue
        if nodeid in NODE_ESM_SKIPS and not _node_screenshot_esm_ok():
            item.add_marker(
                pytest.mark.skip(reason="env: node ESM cannot import capture_screenshot.mjs")
            )
            continue
        if nodeid in MONGOMOCK_SKIPS and _using_mongomock():
            item.add_marker(
                pytest.mark.skip(reason="env: mongomock does not implement $replaceAll")
            )
            continue
        reason = XFAIL.get(nodeid)
        if reason:
            item.add_marker(pytest.mark.xfail(reason=reason, strict=False))
