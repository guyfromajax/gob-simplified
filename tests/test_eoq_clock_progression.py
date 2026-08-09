"""Clock-driven EOQ progression helpers."""

from types import SimpleNamespace

from BackEnd.utils.eoq_clock_progression import (
    activate_late_clock_eoq_chain,
    apply_eoq_final_free_throw_routing,
    apply_post_make_late_clock_routing,
    apply_post_miss_rebound_routing,
    clear_late_clock_eoq_chain,
    ensure_quarter_end_clock_drain,
    eoq_first_gate_open,
    finalize_flss_post_emit,
    infer_eoq_trace_role,
    is_late_clock_eoq_chain_active,
    normalize_quarter_end_after_clock_update,
    resolve_late_clock_bip_runoff,
    schedule_flss_after_dreb,
    schedule_flss_after_inbound,
    scrub_timeout_fields_from_snapshot,
    should_emit_clock_stopped_inbound,
    should_arm_final_shot_execute_flags,
    should_force_eoq_last_shot,
    should_force_oreb_putback,
    should_route_eoq_rebound,
    should_route_final_turn_to_flss,
    should_route_post_dreb_flss,
)
from BackEnd.engine.final_turn_pacing import evaluate_final_turn_pacing, roll_anchor_clock
from BackEnd.engine.eoq_perfection import (
    animation_schema_game_seconds,
    calculate_flss_runway,
    combine_eoq_origin_prefix,
    compute_flss_drive_plan,
    select_eoq_origin_prefix,
)
from BackEnd.engine.oreb_step_emitter import fit_buzzer_putback_steps


POSITIONS = ("PG", "SG", "SF", "PF", "C")


def test_eoq_first_gate_ownership_split():
    # Fresh window — any half-court entry may evaluate.
    assert eoq_first_gate_open(
        state="HCT", chain_active=False, final_shot_ran_this_chain=False
    )
    assert eoq_first_gate_open(
        state="HCO", chain_active=False, final_shot_ran_this_chain=False
    )
    # Window opened by HCT without an EOQ shot → only HCO may still arm Final Shot.
    assert eoq_first_gate_open(
        state="HCO", chain_active=True, final_shot_ran_this_chain=False
    )
    assert not eoq_first_gate_open(
        state="HCT", chain_active=True, final_shot_ran_this_chain=False
    )
    # After an EOQ shot ran → first gate closed (follow-up §6b owns routing).
    assert not eoq_first_gate_open(
        state="HCO", chain_active=True, final_shot_ran_this_chain=True
    )
    assert should_arm_final_shot_execute_flags("HCO") is True
    assert should_arm_final_shot_execute_flags("HCT") is False
    assert should_arm_final_shot_execute_flags("FCP") is False


def test_should_force_oreb_putback_under_six():
    assert should_force_oreb_putback(5) is True
    assert should_force_oreb_putback(6) is False


def test_should_route_post_dreb_flss():
    assert should_route_post_dreb_flss(3) is True
    assert should_route_post_dreb_flss(2) is False
    assert should_route_post_dreb_flss(1) is False


def test_should_force_eoq_last_shot_state_and_clock_gates():
    game = SimpleNamespace(game_state={}, quarter=2)
    # Only HCT / FCP / FAST_BREAK are forced (HCO owns its own routing).
    assert should_force_eoq_last_shot(game, 5, "HCO") is False
    assert should_force_eoq_last_shot(game, 5, "FREE_THROW") is False
    # Clock bounds: <=0 is Path A's job; >8 has runway for a normal possession.
    assert should_force_eoq_last_shot(game, 0, "HCT") is False
    assert should_force_eoq_last_shot(game, 9, "HCT") is False
    # Q1-3: always attempt a last shot inside the runway window.
    assert should_force_eoq_last_shot(game, 5, "HCT") is True
    assert should_force_eoq_last_shot(game, 8, "FCP") is True
    assert should_force_eoq_last_shot(game, 1, "FAST_BREAK") is True


def test_should_force_eoq_last_shot_pending_flss_any_quarter():
    game = SimpleNamespace(game_state={"flss_possession_pending": True}, quarter=4)
    # A scheduled FLSS that landed on a pressure/transition state still fires.
    assert should_force_eoq_last_shot(game, 4, "FCP") is True


def test_should_force_eoq_last_shot_q4_uses_final_shot_gate():
    # Q4 with an armed final-shot flag → would_take_final_shot True → force FLSS.
    armed = SimpleNamespace(game_state={"final_shot_possession_active": True}, quarter=4)
    assert should_force_eoq_last_shot(armed, 5, "HCT") is True


def test_flss_runway_reserves_terminal_shot_window():
    plan = calculate_flss_runway(9, projected_originating_turn_seconds=12)

    assert plan.time_remaining == 9
    assert plan.shot_reserve_seconds == 1
    assert plan.originating_turn_budget == 8
    assert plan.originating_turn_fits is False
    assert plan.requires_shortened_turn is True


def test_flss_runway_keeps_complete_turn_when_it_fits():
    plan = calculate_flss_runway(9, projected_originating_turn_seconds=7)

    assert plan.originating_turn_budget == 8
    assert plan.originating_turn_fits is True
    assert plan.requires_shortened_turn is False


def test_flss_runway_handles_subsecond_and_expired_clock():
    subsecond = calculate_flss_runway(0.4, projected_originating_turn_seconds=1)
    expired = calculate_flss_runway(0, projected_originating_turn_seconds=1)

    assert subsecond.shot_reserve_seconds == 0.4
    assert subsecond.originating_turn_budget == 0
    assert subsecond.requires_shortened_turn is True
    assert expired.shot_reserve_seconds == 0
    assert expired.originating_turn_budget == 0


def test_flss_drive_uses_shared_runway_budget():
    shooter = SimpleNamespace(attributes={"AG": 5})
    drive = compute_flss_drive_plan(
        shooter,
        50,
        25,
        6,
        is_home_offense=True,
    )

    assert drive.drive_budget == 5
    assert drive.shot_window_seconds == 1


def test_short_oreb_putback_releases_at_zero_and_keeps_post_release_steps():
    steps = [
        _schema_step(1, 0.2, 0.8),
        _schema_step(0.2, -0.3, 0.5),
        _schema_step(-0.3, -0.8, 0.5),
        _schema_step(-0.8, -1.1, 0.3, terminal=True),
    ]
    for step in steps[:2]:
        step["start"]["advance_trigger"] = {"T_game_seconds": step["end"]["time_elapsed"]}

    fitted = fit_buzzer_putback_steps(steps, time_remaining=1)

    assert len(fitted) == 4
    assert fitted[1]["end"]["clock"]["clock_remaining"] == 0
    assert fitted[2]["start"]["clock"]["clock_remaining"] == 0
    assert fitted[3]["end"]["clock"]["clock_remaining"] == 0
    assert fitted[2]["end"]["time_elapsed"] == 0
    assert animation_schema_game_seconds(fitted) == 1


def test_oreb_putback_schema_is_unchanged_when_release_fits():
    steps = [
        _schema_step(3, 2.5, 0.5),
        _schema_step(2.5, 2, 0.5),
        _schema_step(2, 1, 1, terminal=True),
    ]

    fitted = fit_buzzer_putback_steps(steps, time_remaining=3)

    assert fitted == steps


def test_short_oreb_preserves_release_beats_then_clamps_late_flight():
    steps = [
        _schema_step(2, 1.5, 0.5),
        _schema_step(1.5, 1, 0.5),
        _schema_step(1, -1, 2, terminal=True),
    ]

    fitted = fit_buzzer_putback_steps(steps, time_remaining=2)

    assert fitted[0]["end"]["time_elapsed"] == 0.5
    assert fitted[1]["end"]["time_elapsed"] == 0.5
    assert fitted[2]["end"]["time_elapsed"] == 1
    assert fitted[2]["end"]["clock"]["clock_remaining"] == 0
    assert animation_schema_game_seconds(fitted) == 2


def _schema_step(start, end, seconds, *, terminal=False):
    return {
        "start": {
            "clock": {"clock_remaining": start, "shot_clock_remaining": start},
        },
        "end": {
            "time_elapsed": seconds,
            "clock": {"clock_remaining": end, "shot_clock_remaining": end},
            "next": (
                {"kind": "turn_stop", "event": "MAKE"}
                if terminal
                else {"kind": "next_step", "index": 99}
            ),
        },
    }


def test_eoq_prefix_selects_only_complete_nonterminal_steps():
    steps = [
        _schema_step(9, 6, 3),
        _schema_step(6, 2, 4),
        _schema_step(2, -1, 3, terminal=True),
    ]

    prefix, burn = select_eoq_origin_prefix(steps, budget_seconds=8)

    assert animation_schema_game_seconds(steps) == 10
    assert len(prefix) == 2
    assert burn == 7


def test_eoq_prefix_does_not_commit_terminal_step_even_inside_budget():
    steps = [_schema_step(5, 4, 1, terminal=True)]

    prefix, burn = select_eoq_origin_prefix(steps, budget_seconds=4)

    assert prefix == []
    assert burn == 0


def test_combine_eoq_prefix_rebases_flss_clock_and_next_indices():
    result = {
        "eoq_origin_prefix_steps": [_schema_step(9, 6, 3)],
        "animation_steps": [
            _schema_step(9, 6, 3),
            _schema_step(6, 5, 1, terminal=True),
        ],
    }

    combine_eoq_origin_prefix(result)

    assert len(result["animation_steps"]) == 3
    assert result["animation_steps"][1]["start"]["clock"]["clock_remaining"] == 6
    assert result["animation_steps"][2]["end"]["clock"]["clock_remaining"] == 2
    assert result["animation_steps"][0]["end"]["next"] == {
        "kind": "next_step",
        "index": 1,
    }
    assert result["eoq_shortened_turn"] is True


def test_non_hco_preview_discards_speculative_outcome_and_hands_prefix_to_flss(monkeypatch):
    from BackEnd.models.turn_manager import TurnManager
    import BackEnd.models.turn_manager as turn_manager_module

    offense_player = SimpleNamespace(
        player_id="o-pg",
        coords={"x": 20, "y": 25},
    )
    defense_player = SimpleNamespace(
        player_id="d-pg",
        coords={"x": 70, "y": 25},
    )
    offense = SimpleNamespace(
        team_id="off",
        lineup={"PG": offense_player},
        scouting_data={"offense": {}, "defense": {}},
    )
    defense = SimpleNamespace(
        team_id="def",
        lineup={"PG": defense_player},
        scouting_data={"offense": {}, "defense": {}},
    )
    game = SimpleNamespace(
        offense_team=offense,
        defense_team=defense,
        home_team=offense,
        away_team=defense,
        quarter=2,
        score={"off": 0, "def": 0},
        game_state={"time_remaining": 5, "last_ball_handler": offense_player},
    )
    manager = TurnManager.__new__(TurnManager)
    manager.game = game
    game.turn_manager = manager

    prefix_step = {
        "start": {
            "coords": {"o-pg": {"x": 20, "y": 25}},
            "clock": {"clock_remaining": 5, "shot_clock_remaining": 5},
        },
        "end": {
            "coords": {"o-pg": {"x": 42, "y": 24}},
            "ball": {"owner_player_id": "o-pg"},
            "time_elapsed": 2,
            "clock": {"clock_remaining": 3, "shot_clock_remaining": 3},
            "next": {"kind": "next_step", "index": 1},
        },
    }
    terminal_step = {
        "start": {"clock": {"clock_remaining": 3, "shot_clock_remaining": 3}},
        "end": {
            "time_elapsed": 4,
            "clock": {"clock_remaining": -1, "shot_clock_remaining": -1},
            "next": {"kind": "turn_stop", "event": "MAKE"},
        },
    }

    def speculative_resolver(preview_game):
        preview_game.score["off"] = 99
        return {
            "result_type": "MAKE",
            "fast_break_play": "triangle",
            "animation_steps": [prefix_step, terminal_step],
        }

    monkeypatch.setattr(turn_manager_module, "resolve_fast_break_logic", speculative_resolver)
    monkeypatch.setattr(turn_manager_module, "resolve_full_court_press_logic", speculative_resolver)
    monkeypatch.setattr(turn_manager_module, "resolve_half_court_trap_logic", speculative_resolver)
    monkeypatch.setattr(TurnManager, "_emit_pressure_animation_steps", lambda *args: None)
    monkeypatch.setattr(TurnManager, "_commit_shortened_non_hco_entry_costs", lambda *args: None)
    monkeypatch.setattr(
        "BackEnd.engine.eoq_perfection.resolve_flss_shot_logic",
        lambda game, state, time_remaining_override=None: {
            "result_type": "MISS",
            "flss": True,
            "skeleton": {"steps": []},
            "time_elapsed": time_remaining_override,
        },
    )

    for state in ("HCT", "FCP", "FAST_BREAK"):
        game.score["off"] = 0
        offense_player.coords = {"x": 20, "y": 25}
        completed, result = manager._preview_non_hco_eoq_turn(state, 5)

        assert completed is True
        assert result["result_type"] == "MISS"
        assert result["eoq_origin_state"] == state
        assert result["eoq_origin_prefix_seconds"] == 2
        assert result["eoq_flss_budget_seconds"] == 3
        assert len(result["eoq_origin_prefix_steps"]) == 1
        assert game.score["off"] == 0
        assert offense_player.coords == {"x": 42.0, "y": 24.0}


def test_late_clock_dreb_routes_terminal_at_low_clock():
    rebounder = SimpleNamespace(player_id="r1")
    game = SimpleNamespace(
        game_state={"time_remaining": 2, "final_turn": True},
        shot_manager=SimpleNamespace(_block_spot=None),
    )
    result = {"flss": True}
    assert should_route_eoq_rebound(game, result) is True
    flips = apply_post_miss_rebound_routing(game, result, rebounder, "DREB")
    assert flips is True
    assert result["terminal_dreb_eoq"] is True
    assert result["next_play_type"] == "DREB"
    assert "flss_after_dreb" not in result


def test_late_clock_dreb_routes_flss_when_clock_remains():
    rebounder = SimpleNamespace(player_id="r1")
    game = SimpleNamespace(
        game_state={"time_remaining": 8, "late_clock_eoq_chain_active": True},
        shot_manager=SimpleNamespace(_block_spot=None),
    )
    result = {"late_clock_eoq": True, "final_turn": True}
    flips = apply_post_miss_rebound_routing(game, result, rebounder, "DREB")
    assert flips is True
    assert result.get("terminal_dreb_eoq") is not True
    assert result["flss_after_dreb"] is True
    assert result["next_play_type"] == "DREB"
    assert game.game_state["_flss_after_dreb_rebounder_id"] == "r1"


def test_late_clock_oreb_sets_pending():
    rebounder = SimpleNamespace(player_id="r1")
    game = SimpleNamespace(
        game_state={"time_remaining": 4},
        shot_manager=SimpleNamespace(_block_spot=None),
    )
    result = {"late_clock_eoq": True}
    flips = apply_post_miss_rebound_routing(game, result, rebounder, "OREB")
    assert flips is False
    assert game.game_state["pending_oreb"]["rebounder_id"] == "r1"
    assert result["next_play_type"] == "OREB"
    assert is_late_clock_eoq_chain_active(game.game_state) is True


def test_early_clock_oreb_does_not_arm_eoq_chain():
    """OREB at 5:00 must not block the first Final Shot at <=30s."""
    rebounder = SimpleNamespace(player_id="r1")
    game = SimpleNamespace(
        game_state={"time_remaining": 295},
        shot_manager=SimpleNamespace(_block_spot=None),
    )
    result = {"result_type": "MISS"}
    flips = apply_post_miss_rebound_routing(game, result, rebounder, "OREB")
    assert flips is False
    assert game.game_state["pending_oreb"]["rebounder_id"] == "r1"
    assert result["next_play_type"] == "OREB"
    assert is_late_clock_eoq_chain_active(game.game_state) is False
    assert "late_clock_eoq" not in result


def test_late_clock_oreb_without_chain_does_not_arm():
    rebounder = SimpleNamespace(player_id="r1")
    game = SimpleNamespace(
        game_state={"time_remaining": 25},
        shot_manager=SimpleNamespace(_block_spot=None),
    )
    result = {"result_type": "MISS"}
    flips = apply_post_miss_rebound_routing(game, result, rebounder, "OREB")
    assert flips is False
    assert result["next_play_type"] == "OREB"
    assert is_late_clock_eoq_chain_active(game.game_state) is False
    assert "late_clock_eoq" not in result


def test_infer_eoq_trace_role_not_final_shot_for_late_clock_tag_only():
    assert infer_eoq_trace_role({"late_clock_eoq": True, "result_type": "MISS"}) == "EOQ_CHAIN"
    assert infer_eoq_trace_role({"final_turn": True, "result_type": "MISS"}) == "FINAL_SHOT"
    assert infer_eoq_trace_role({"next_play_type": "OREB", "result_type": "MISS"}) == "OREB"


def test_schedule_flss_after_inbound():
    game = SimpleNamespace(game_state={"time_remaining": 3, "offensive_state": "FCP"})
    schedule_flss_after_inbound(game, {"late_clock_eoq": True})
    assert game.game_state["flss_possession_pending"] is True
    assert game.game_state["offensive_state"] == "HCO"
    assert is_late_clock_eoq_chain_active(game.game_state) is True


def test_schedule_flss_after_inbound_uses_active_chain_without_source_tag():
    """FOUL→SIP historically lacked late_clock_eoq; chain-active must still arm FLSS."""
    from BackEnd.utils.eoq_clock_progression import activate_late_clock_eoq_chain

    game = SimpleNamespace(game_state={"time_remaining": 4, "offensive_state": "HCO"})
    activate_late_clock_eoq_chain(game.game_state)
    foul = {"result_type": "FOUL", "next_play_type": "SIDE_INBOUND"}
    schedule_flss_after_inbound(game, foul)
    assert foul["late_clock_eoq"] is True
    assert game.game_state["flss_possession_pending"] is True
    assert game.game_state["offensive_state"] == "HCO"


def test_tag_result_if_late_clock_eoq_chain():
    from BackEnd.utils.eoq_clock_progression import (
        activate_late_clock_eoq_chain,
        tag_result_if_late_clock_eoq_chain,
    )

    game = SimpleNamespace(game_state={})
    foul = {"result_type": "FOUL"}
    assert tag_result_if_late_clock_eoq_chain(game, foul) is False
    assert foul.get("late_clock_eoq") is None
    activate_late_clock_eoq_chain(game.game_state)
    assert tag_result_if_late_clock_eoq_chain(game, foul) is True
    assert foul["late_clock_eoq"] is True


def test_schedule_flss_after_dreb():
    rebounder = SimpleNamespace(player_id="r9")
    dreb_turn = {"late_clock_eoq": True, "flss_after_dreb": True}
    game = SimpleNamespace(game_state={"time_remaining": 5, "offensive_state": "HCO"})
    schedule_flss_after_dreb(game, dreb_turn, rebounder)
    assert game.game_state["flss_possession_pending"] is True
    assert game.game_state["flss_from_dreb"] is True
    assert game.game_state["last_ball_handler"] is rebounder
    assert dreb_turn["flss_possession_pending"] is True


def test_roll_anchor_clock_ranges(monkeypatch):
    monkeypatch.setattr("BackEnd.engine.final_turn_pacing.random.randint", lambda a, b: a)
    assert roll_anchor_clock("Outside") == 1.0
    assert roll_anchor_clock("Attack") == 2.0


def test_pacing_uses_rolled_anchor(monkeypatch):
    monkeypatch.setattr("BackEnd.engine.final_turn_pacing.random.randint", lambda a, b: 1)
    home = SimpleNamespace(team_id="home", lineup={})
    away = SimpleNamespace(team_id="away", lineup={})
    game = SimpleNamespace(
        quarter=2,
        game_state={"time_remaining": 29, "shot_clock_remaining": 14},
        home_team=home,
        away_team=away,
        offense_team=home,
        defense_team=away,
        turns=[],
    )
    plan = evaluate_final_turn_pacing(
        game,
        skeleton={"steps": [{"pos_actions": {"PG": {"action": "shoot", "location": "upper wing"}}}]},
        o_destinations={},
        position_to_spot={pos: "deep upper wing" for pos in POSITIONS},
        bh_pos="PG",
        shooter_pos="PG",
        shot_type="Outside",
        bh_is_shooter=True,
        prior_turn=None,
    )
    assert plan.anchor_clock == 1.0


def test_failed_final_turn_pacing_routes_flss_at_every_clock():
    assert should_route_final_turn_to_flss(30) is True
    assert should_route_final_turn_to_flss(20) is True
    assert should_route_final_turn_to_flss(9) is True
    assert should_route_final_turn_to_flss(8) is True
    assert should_route_final_turn_to_flss(0) is True


def test_post_make_tags_only_inside_active_chain():
    game = SimpleNamespace(game_state={"time_remaining": 20})
    result = {"result_type": "MAKE", "next_play_type": "BASELINE_INBOUND"}
    apply_post_make_late_clock_routing(game, result)
    assert "late_clock_eoq" not in result

    activate_late_clock_eoq_chain(game.game_state)
    game.game_state["final_turn"] = True
    apply_post_make_late_clock_routing(game, result)
    assert result.get("late_clock_eoq") is True


def test_late_clock_bip_runoff():
    assert resolve_late_clock_bip_runoff({"late_clock_eoq": True}, 17) == 2
    assert resolve_late_clock_bip_runoff({"late_clock_eoq": True}, 1) == 1
    assert resolve_late_clock_bip_runoff({"late_clock_ft_resolution": True}, 17) == 2
    assert resolve_late_clock_bip_runoff({}, 17) == 0


def test_final_ft_routing_does_not_start_chain_on_make():
    game = SimpleNamespace(game_state={"time_remaining": 28})
    result = {"result_type": "FREE_THROW"}
    apply_eoq_final_free_throw_routing(game, result, makes_shot=True)
    assert result.get("late_clock_ft_resolution") is True
    assert "late_clock_eoq" not in result
    assert is_late_clock_eoq_chain_active(game.game_state) is False
    assert result["next_play_type"] == "BASELINE_INBOUND"
    schedule_flss_after_inbound(game, result)
    assert "flss_possession_pending" not in game.game_state


def test_final_ft_routing_does_not_start_chain_on_oreb_miss():
    game = SimpleNamespace(game_state={"time_remaining": 28, "last_rebound": "OREB"})
    rebounder = SimpleNamespace(player_id="r1")
    game.game_state["last_rebounder"] = rebounder
    result = {"result_type": "FREE_THROW", "rebound_type": "OREB"}
    apply_eoq_final_free_throw_routing(game, result, makes_shot=False)
    assert result.get("late_clock_ft_resolution") is True
    assert is_late_clock_eoq_chain_active(game.game_state) is False
    assert result["next_play_type"] == "OREB"
    assert game.game_state["pending_oreb"]["rebounder_id"] == "r1"


def test_final_ft_dreb_terminal_only_when_chain_active():
    rebounder = SimpleNamespace(player_id="r1")
    game = SimpleNamespace(
        game_state={
            "time_remaining": 2,
            "last_rebound": "DREB",
            "last_rebounder": rebounder,
        }
    )
    result = {"result_type": "FREE_THROW", "rebound_type": "DREB"}
    apply_eoq_final_free_throw_routing(game, result, makes_shot=False)
    assert result["next_play_type"] == "DREB"
    assert "terminal_dreb_eoq" not in result
    assert "flss_after_dreb" not in result

    activate_late_clock_eoq_chain(game.game_state)
    result2 = {"result_type": "FREE_THROW", "rebound_type": "DREB"}
    apply_eoq_final_free_throw_routing(game, result2, makes_shot=False)
    assert result2["terminal_dreb_eoq"] is True


def test_final_ft_make_at_zero_is_terminal_without_inbound():
    game = SimpleNamespace(game_state={"time_remaining": 0})
    result = {
        "result_type": "FREE_THROW",
        "next_play_type": "BASELINE_INBOUND",
        "next_turn": "BASELINE_INBOUND",
    }

    apply_eoq_final_free_throw_routing(game, result, makes_shot=True)

    assert result["quarter_ends_after"] is True
    assert result["next_play_type"] is None
    assert "next_turn" not in result
    assert should_emit_clock_stopped_inbound(game, result) is False


def test_final_ft_miss_at_zero_does_not_schedule_rebound_turn():
    rebounder = SimpleNamespace(player_id="r1")
    game = SimpleNamespace(
        game_state={
            "time_remaining": 0,
            "last_rebound": "OREB",
            "last_rebounder": rebounder,
        }
    )
    result = {"result_type": "FREE_THROW", "rebound_type": "OREB"}

    apply_eoq_final_free_throw_routing(game, result, makes_shot=False)

    assert result["quarter_ends_after"] is True
    assert result["next_play_type"] is None
    assert "pending_oreb" not in game.game_state


def test_clock_stopped_inbound_gate_rejects_terminal_sip_source():
    live_game = SimpleNamespace(game_state={"time_remaining": 3})
    expired_game = SimpleNamespace(game_state={"time_remaining": 0})

    assert should_emit_clock_stopped_inbound(
        live_game, {"result_type": "FOUL"}
    ) is True
    assert should_emit_clock_stopped_inbound(
        expired_game, {"result_type": "FOUL"}
    ) is False
    assert should_emit_clock_stopped_inbound(
        live_game,
        {"result_type": "FOUL", "quarter_ends_after": True},
    ) is False


def test_finalize_flss_burns_last_second_on_make():
    game = SimpleNamespace(game_state={"time_remaining": 1})
    result = {
        "flss": True,
        "result_type": "MAKE",
        "next_play_type": "BASELINE_INBOUND",
        "animation_steps": [],
        "time_elapsed": 0,
    }
    finalize_flss_post_emit(game, result)
    assert result["time_elapsed"] == 1


def test_ensure_quarter_end_clock_drain():
    game = SimpleNamespace(game_state={"time_remaining": 3})
    result = {"quarter_ends_after": True, "result_type": "MISS"}
    ensure_quarter_end_clock_drain(game, result)
    assert result["time_elapsed"] == 3
    assert result["clock_end"] == 0


def test_ensure_quarter_end_clock_drain_when_clock_already_zero():
    game = SimpleNamespace(game_state={"time_remaining": 0})
    result = {"result_type": "MISS", "next_play_type": None}
    ensure_quarter_end_clock_drain(game, result)
    assert result["quarter_ends_after"] is True
    assert result["clock_end"] == 0
    assert "time_elapsed" not in result or result.get("time_elapsed") is None


def test_normalize_quarter_end_after_clock_update_clears_impossible_followup():
    game = SimpleNamespace(game_state={
        "time_remaining": 0,
        "free_throws_remaining": 0,
        "flss_possession_pending": True,
        "late_clock_eoq_chain_active": True,
        "pending_oreb": {"rebounder_id": "r1"},
    })
    result = {
        "result_type": "MAKE",
        "next_play_type": "BASELINE_INBOUND",
        "next_turn": "BASELINE_INBOUND",
        "next_defensive_setup": "FCP",
        "possession_flips": True,
        "flss_after_dreb": True,
        "animation_steps": [{
            "start": {"clock": {"clock_remaining": 1, "shot_clock_remaining": 1}},
            "end": {"clock": {"clock_remaining": -2, "shot_clock_remaining": -2}},
        }],
    }

    normalize_quarter_end_after_clock_update(game, result)

    assert result["quarter_ends_after"] is True
    assert result["next_play_type"] is None
    assert "next_turn" not in result
    assert result["clock_end"] == 0
    assert result["possession_flips"] is False
    assert "next_defensive_setup" not in result
    assert result["animation_steps"][0]["end"]["clock"] == {
        "clock_remaining": 0,
        "shot_clock_remaining": 0,
    }
    assert "flss_after_dreb" not in result
    assert "flss_possession_pending" not in game.game_state
    assert "late_clock_eoq_chain_active" not in game.game_state
    assert "pending_oreb" not in game.game_state


def test_normalize_quarter_end_after_clock_update_preserves_pending_free_throws():
    game = SimpleNamespace(game_state={"time_remaining": 0, "free_throws_remaining": 2})
    result = {
        "result_type": "FOUL",
        "free_throws_remaining": 2,
        "next_play_type": "FREE_THROW",
        "next_turn": "FREE_THROW",
    }

    normalize_quarter_end_after_clock_update(game, result)

    assert result.get("quarter_ends_after") is not True
    assert result["next_play_type"] == "FREE_THROW"
    assert result["next_turn"] == "FREE_THROW"


def test_synthesized_turn_finalizer_applies_clock_then_normalizes():
    from BackEnd.models.game_manager import GameManager

    game = SimpleNamespace(game_state={"time_remaining": 2, "free_throws_remaining": 0})

    def update_clock(turn):
        game.game_state["time_remaining"] = max(
            0,
            game.game_state["time_remaining"] - int(turn.get("time_elapsed") or 0),
        )

    game.turn_manager = SimpleNamespace(update_clock_and_possession=update_clock)
    turn = {
        "result_type": "DREB",
        "time_elapsed": 3,
        "next_play_type": "HCO",
        "next_turn": "HCO",
        "possession_flips": True,
    }

    ended = GameManager._finalize_synthesized_clock_turn(game, turn)

    assert ended is True
    assert game.game_state["time_remaining"] == 0
    assert turn["quarter_ends_after"] is True
    assert turn["next_play_type"] is None
    assert turn["possession_flips"] is False


def test_synthesized_bip_finalizer_can_normalize_preapplied_runoff():
    from BackEnd.models.game_manager import GameManager

    game = SimpleNamespace(
        game_state={
            "time_remaining": 0,
            "free_throws_remaining": 0,
            "flss_possession_pending": True,
        },
        turn_manager=SimpleNamespace(
            update_clock_and_possession=lambda _turn: (_ for _ in ()).throw(
                AssertionError("clock update must not run twice")
            )
        ),
    )
    turn = {
        "result_type": "BASELINE_INBOUND",
        "next_play_type": "FCP",
        "next_turn": "FCP",
        "next_defensive_setup": "FCP",
    }

    ended = GameManager._finalize_synthesized_clock_turn(
        game,
        turn,
        apply_clock_update=False,
    )

    assert ended is True
    assert turn["next_play_type"] is None
    assert "next_defensive_setup" not in turn
    assert "flss_possession_pending" not in game.game_state


def test_scrub_timeout_fields_from_snapshot():
    snapshot = {
        "timeout_next_play_type": "SIDE_INBOUND",
        "timeout_trace_id": "abc",
        "game_state": {"timeout_next_play_type": "SIDE_INBOUND"},
    }
    scrub_timeout_fields_from_snapshot(snapshot)
    assert "timeout_next_play_type" not in snapshot
    assert "timeout_next_play_type" not in snapshot["game_state"]


def test_clear_late_clock_eoq_chain():
    gs = {
        "late_clock_eoq_chain_active": True,
        "flss_possession_pending": True,
        "final_shot_possession_active": True,
        "_debug_final_hold_streak": 2,
    }
    clear_late_clock_eoq_chain(gs)
    assert is_late_clock_eoq_chain_active(gs) is False
    assert "flss_possession_pending" not in gs
    assert "_debug_final_hold_streak" not in gs
