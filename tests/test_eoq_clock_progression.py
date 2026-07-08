"""Clock-driven EOQ progression helpers."""

from types import SimpleNamespace

from BackEnd.utils.eoq_clock_progression import (
    activate_late_clock_eoq_chain,
    apply_eoq_final_free_throw_routing,
    apply_post_make_late_clock_routing,
    apply_post_miss_rebound_routing,
    clear_late_clock_eoq_chain,
    ensure_quarter_end_clock_drain,
    finalize_flss_post_emit,
    infer_eoq_trace_role,
    is_late_clock_eoq_chain_active,
    resolve_late_clock_bip_runoff,
    roll_anchor_clock,
    schedule_flss_after_dreb,
    schedule_flss_after_inbound,
    scrub_timeout_fields_from_snapshot,
    should_force_eoq_last_shot,
    should_force_oreb_putback,
    should_route_eoq_rebound,
    should_route_final_turn_to_flss,
    should_route_post_dreb_flss,
)
from BackEnd.engine.final_turn_pacing import evaluate_final_turn_pacing


POSITIONS = ("PG", "SG", "SF", "PF", "C")


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


def test_should_route_final_turn_to_flss_only_at_low_clock():
    assert should_route_final_turn_to_flss(20) is False
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
    }
    clear_late_clock_eoq_chain(gs)
    assert is_late_clock_eoq_chain_active(gs) is False
    assert "flss_possession_pending" not in gs
