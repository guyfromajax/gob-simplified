"""Clock-driven EOQ progression helpers."""

from types import SimpleNamespace

from BackEnd.utils.eoq_clock_progression import (
    apply_post_miss_rebound_routing,
    roll_anchor_clock,
    schedule_flss_after_inbound,
    should_force_oreb_putback,
    should_route_eoq_rebound,
)
from BackEnd.engine.final_turn_pacing import evaluate_final_turn_pacing


POSITIONS = ("PG", "SG", "SF", "PF", "C")


def test_should_force_oreb_putback_under_six():
    assert should_force_oreb_putback(5) is True
    assert should_force_oreb_putback(6) is False


def test_late_clock_dreb_routes_terminal():
    rebounder = SimpleNamespace(player_id="r1")
    game = SimpleNamespace(
        game_state={"time_remaining": 8, "final_turn": True},
        shot_manager=SimpleNamespace(_block_spot=None),
    )
    result = {"flss": True}
    assert should_route_eoq_rebound(game, result) is True
    flips = apply_post_miss_rebound_routing(game, result, rebounder, "DREB")
    assert flips is True
    assert result["terminal_dreb_eoq"] is True
    assert result["next_play_type"] == "DREB"


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


def test_schedule_flss_after_inbound():
    game = SimpleNamespace(game_state={"time_remaining": 3, "offensive_state": "FCP"})
    schedule_flss_after_inbound(game, {"late_clock_eoq": True})
    assert game.game_state["flss_possession_pending"] is True
    assert game.game_state["offensive_state"] == "HCO"


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
