"""Cross-turn regression matrix for the universal EOQ contract."""

from types import SimpleNamespace

import pytest

from BackEnd.engine.eoq_perfection import (
    animation_schema_game_seconds,
    calculate_flss_runway,
)
from BackEnd.engine.oreb_step_emitter import fit_buzzer_putback_steps
from BackEnd.models.game_manager import GameManager
from BackEnd.models.turn_manager import TurnManager
from BackEnd.utils import situational_logic as sl
from BackEnd.utils.eoq_clock_progression import (
    apply_post_miss_rebound_routing,
    normalize_quarter_end_after_clock_update,
    schedule_flss_after_dreb,
    should_emit_clock_stopped_inbound,
)
from tests.test_utils import build_mock_game


CLOCKS = (30, 9, 8, 3, 1, 0)
LIVE_ENTRY_STATES = ("HCO", "HCT", "FCP", "FAST_BREAK")
SYNTHESIZED_TURNS = ("BASELINE_INBOUND", "SIDE_INBOUND", "OREB", "DREB")
Q4_MARGIN_ACTIONS = {
    1: "FORCE_FOUL",
    8: "FORCE_FOUL",
    9: "RUN_OUT_CLOCK",
    -3: "FINAL_SHOT",
    -4: "QUICK_SHOT",
    -19: "RUN_OUT_CLOCK",
}


class _Team:
    def __init__(self, name):
        self.name = name
        self.team_id = name
        self.lineup = {}
        self.team_attributes = {"team_chemistry": 15}


def _game(*, quarter=4, margin=0, clock=30):
    offense = _Team("off")
    defense = _Team("def")
    return SimpleNamespace(
        quarter=quarter,
        offense_team=offense,
        defense_team=defense,
        home_team=offense,
        away_team=defense,
        score={"off": 70 + margin, "def": 70},
        game_state={"time_remaining": clock, "shot_clock_remaining": min(30, clock)},
        shot_manager=SimpleNamespace(_block_spot=None),
    )


def _route_result(marker):
    return {
        "result_type": "DEAD BALL",
        "time_elapsed": 0,
        "next_play_type": None,
        "possession_flips": False,
        "route_marker": marker,
    }


def _prepare_live_turn_manager(monkeypatch, *, state, clock, margin, quarter=4):
    game = build_mock_game()
    game.quarter = quarter
    game.score = {
        game.offense_team.name: 70 + margin,
        game.defense_team.name: 70,
    }
    game.game_state.update(
        {
            "score": game.score,
            "offensive_state": state,
            "time_remaining": clock,
            # Keep the shot-clock gate independent from this game-clock matrix.
            "shot_clock_remaining": 30,
        }
    )
    for team in (game.home_team, game.away_team):
        for player in team.lineup.values():
            player.stats["game"].setdefault("MIN", 0)
    tm = game.turn_manager
    monkeypatch.setattr(tm, "_preview_non_hco_eoq_turn", lambda *_: (True, None))
    monkeypatch.setattr(tm, "_emit_pressure_animation_steps", lambda *_: None)
    monkeypatch.setattr(
        tm,
        "_execute_quick_foul_at_possession_start",
        lambda *_: _route_result("FORCE_FOUL"),
    )
    monkeypatch.setattr(tm, "resolve_final_turn_shot", lambda: _route_result("FINAL_SHOT"))
    monkeypatch.setattr(tm, "resolve_half_court_offense", lambda: _route_result("HCO_NORMAL"))
    monkeypatch.setattr(tm, "_execute_forced_shot", lambda *_: _route_result("FORCED_SHOT"))
    monkeypatch.setattr(
        "BackEnd.engine.eoq_perfection.resolve_flss_shot_logic",
        lambda *_: {
            **_route_result("FLSS"),
            "result_type": "MISS",
            "time_elapsed": 1,
            "flss": True,
        },
    )
    monkeypatch.setattr(
        tm,
        "set_playcalls",
        lambda: {
            "offense": "Base",
            "defense": "man",
            "offense_play_type": "motion",
            "offense_focus": "outside",
            "defense_type": "man",
            "defense_focus": None,
            "offense_override_cleared": False,
        },
    )
    monkeypatch.setattr(tm, "calculate_ev", lambda **_: 0)
    monkeypatch.setattr(tm, "_store_ev_score", lambda *_: None)
    monkeypatch.setattr(
        "BackEnd.models.turn_manager.resolve_fast_break_logic",
        lambda *_: _route_result("FAST_BREAK_NORMAL"),
    )
    monkeypatch.setattr(
        "BackEnd.models.turn_manager.resolve_full_court_press_logic",
        lambda *_: _route_result("FCP_NORMAL"),
    )
    monkeypatch.setattr(
        "BackEnd.models.turn_manager.resolve_half_court_trap_logic",
        lambda *_: _route_result("HCT_NORMAL"),
    )
    return game, tm


@pytest.mark.parametrize("state", LIVE_ENTRY_STATES)
@pytest.mark.parametrize("clock", (30, 9, 8, 3, 1))
@pytest.mark.parametrize("margin,expected", Q4_MARGIN_ACTIONS.items())
def test_q4_entry_priority_matrix_runs_each_live_state(
    monkeypatch, state, clock, margin, expected
):
    """Every live state passes through TurnManager's authoritative priority gate."""
    game, tm = _prepare_live_turn_manager(
        monkeypatch, state=state, clock=clock, margin=margin
    )

    result = tm.run_micro_turn()

    if expected == "RUN_OUT_CLOCK":
        assert result["result_type"] == "RUN_OUT_CLOCK"
        assert result["quarter_ends_after"] is True
        assert game.game_state["time_remaining"] == 0
    elif expected == "FORCE_FOUL":
        assert result["route_marker"] == "FORCE_FOUL"
    elif expected == "FINAL_SHOT" and state == "HCO":
        assert result["route_marker"] == "FINAL_SHOT"
    elif expected == "FINAL_SHOT" and clock == 1:
        assert result["route_marker"] == "FLSS"
        assert result["flss"] is True
    else:
        expected_normal = {
            "HCO": "HCO_NORMAL",
            "HCT": "HCT_NORMAL",
            "FCP": "FCP_NORMAL",
            "FAST_BREAK": "FAST_BREAK_NORMAL",
        }[state]
        assert result["route_marker"] == expected_normal


@pytest.mark.parametrize("state", LIVE_ENTRY_STATES)
def test_zero_clock_live_entry_is_inert_for_every_state(monkeypatch, state):
    game, tm = _prepare_live_turn_manager(
        monkeypatch, state=state, clock=0, margin=-3
    )
    game.game_state["final_turn_shot_this_turn"] = True
    game.game_state["flss_possession_pending"] = True

    result = tm.run_micro_turn()

    assert result["result_type"] == "RUN_OUT_CLOCK"
    assert result["clock_expired_no_action"] is True
    assert result["quarter_ends_after"] is True
    assert result["time_elapsed"] == 0
    assert game.game_state["time_remaining"] == 0
    assert "route_marker" not in result


@pytest.mark.parametrize("quarter", (1, 2, 3))
@pytest.mark.parametrize("state", LIVE_ENTRY_STATES)
@pytest.mark.parametrize("clock", CLOCKS)
def test_q1_q3_tied_entry_matrix_runs_each_live_state(
    monkeypatch, quarter, state, clock
):
    game, tm = _prepare_live_turn_manager(
        monkeypatch,
        state=state,
        clock=clock,
        margin=0,
        quarter=quarter,
    )

    result = tm.run_micro_turn()

    if clock == 0:
        assert result["clock_expired_no_action"] is True
        assert result["quarter_ends_after"] is True
    elif state == "HCO":
        assert result["route_marker"] == "FINAL_SHOT"
    elif clock == 1:
        assert result["route_marker"] == "FLSS"
        assert result["flss"] is True
    else:
        expected_normal = {
            "HCT": "HCT_NORMAL",
            "FCP": "FCP_NORMAL",
            "FAST_BREAK": "FAST_BREAK_NORMAL",
        }[state]
        assert result["route_marker"] == expected_normal


@pytest.mark.parametrize("turn_type", SYNTHESIZED_TURNS)
@pytest.mark.parametrize("clock", CLOCKS)
def test_synthesized_turn_terminal_matrix(turn_type, clock):
    game = _game(clock=clock)

    def update_clock(turn):
        game.game_state["time_remaining"] = max(
            0,
            game.game_state["time_remaining"] - int(turn.get("time_elapsed") or 0),
        )

    game.turn_manager = SimpleNamespace(update_clock_and_possession=update_clock)
    turn = {
        "current_turn": turn_type,
        "result_type": turn_type,
        "next_play_type": "HCO",
        "next_turn": "HCO",
        "next_defensive_setup": "FCP",
        "possession_flips": True,
        "time_elapsed": clock,
        "clock_start": clock,
        "clock_end": -2,
        "animation_steps": [
            {
                "start": {
                    "clock": {
                        "clock_remaining": clock,
                        "shot_clock_remaining": clock,
                    }
                },
                "end": {
                    "clock": {
                        "clock_remaining": -2,
                        "shot_clock_remaining": -2,
                    }
                },
            }
        ],
    }

    ended = GameManager._finalize_synthesized_clock_turn(game, turn)

    assert ended is True
    assert game.game_state["time_remaining"] == 0
    assert turn["quarter_ends_after"] is True
    assert turn["next_play_type"] is None
    assert "next_turn" not in turn
    assert "next_defensive_setup" not in turn
    assert turn["possession_flips"] is False
    for step in turn["animation_steps"]:
        for boundary in ("start", "end"):
            values = (step[boundary].get("clock") or {}).values()
            assert all(value >= 0 for value in values)


@pytest.mark.parametrize("clock", CLOCKS)
@pytest.mark.parametrize("inbound_type", ("BASELINE_INBOUND", "SIDE_INBOUND"))
def test_clock_stopped_inbound_matrix(inbound_type, clock):
    game = _game(clock=clock)
    source = {"result_type": "MAKE" if inbound_type == "BASELINE_INBOUND" else "FOUL"}

    assert should_emit_clock_stopped_inbound(game, source) is (clock > 0)


@pytest.mark.parametrize("clock", CLOCKS)
def test_free_throw_zero_clock_exception_matrix(clock):
    game = _game(clock=clock)
    game.game_state["free_throws_remaining"] = 2
    turn = {
        "result_type": "FREE_THROW",
        "free_throws_remaining": 2,
        "next_play_type": "FREE_THROW",
        "next_turn": "FREE_THROW",
        "time_elapsed": 0,
    }

    normalize_quarter_end_after_clock_update(game, turn)

    assert turn["time_elapsed"] == 0
    assert turn["next_play_type"] == "FREE_THROW"
    assert turn.get("quarter_ends_after") is not True


def _schema_step(start, end, seconds):
    return {
        "start": {
            "clock": {"clock_remaining": start, "shot_clock_remaining": start},
            "advance_trigger": {"T_game_seconds": seconds},
        },
        "end": {
            "time_elapsed": seconds,
            "clock": {"clock_remaining": end, "shot_clock_remaining": end},
            "next": {"kind": "next_step", "index": 1},
        },
    }


@pytest.mark.parametrize("clock", (30, 9, 8, 3, 1))
def test_oreb_release_and_nonnegative_clock_matrix(clock):
    normal = [
        _schema_step(clock, clock - 1.5, 1.5),
        _schema_step(clock - 1.5, clock - 2, 0.5),
        _schema_step(clock - 2, clock - 4, 2),
    ]

    fitted = fit_buzzer_putback_steps(normal, time_remaining=clock)

    assert len(fitted) == len(normal)
    assert animation_schema_game_seconds(fitted) <= clock
    assert fitted[1]["end"]["clock"]["clock_remaining"] >= 0
    for step in fitted:
        for boundary in ("start", "end"):
            assert step[boundary]["clock"]["clock_remaining"] >= 0


@pytest.mark.parametrize("clock", (3, 1, 0))
def test_dreb_terminal_and_flss_ownership_matrix(clock):
    rebounder = SimpleNamespace(player_id="r1")
    game = _game(clock=clock)
    game.game_state["late_clock_eoq_chain_active"] = True
    result = {"late_clock_eoq": True}

    apply_post_miss_rebound_routing(game, result, rebounder, "DREB")

    if clock > 2:
        assert result["flss_after_dreb"] is True
        game.game_state["time_remaining"] = clock
        schedule_flss_after_dreb(game, result, rebounder)
        assert game.game_state["last_ball_handler"] is rebounder
        assert game.game_state["flss_possession_pending"] is True
    elif clock > 0:
        assert result["terminal_dreb_eoq"] is True
    else:
        assert result["quarter_ends_after"] is True
        assert result["next_play_type"] is None


@pytest.mark.parametrize("clock", CLOCKS)
def test_flss_release_reserve_matrix(clock):
    runway = calculate_flss_runway(clock, projected_originating_turn_seconds=40)

    assert runway.shot_reserve_seconds == (0 if clock == 0 else 1)
    assert runway.originating_turn_budget == max(0, clock - 1)
    assert runway.originating_turn_budget + runway.shot_reserve_seconds == clock


def test_final_turn_worst_case_reserve_is_deterministic():
    from BackEnd.engine.shot_micro_movements import worst_case_final_turn_micro_reserve

    first = worst_case_final_turn_micro_reserve("Outside")

    assert worst_case_final_turn_micro_reserve("Outside") == first
    assert worst_case_final_turn_micro_reserve("Outside") == first


def test_synthesized_finalizer_reports_terminal_without_continuation():
    game = _game(clock=1)

    def update_clock(turn):
        game.game_state["time_remaining"] = max(
            0, game.game_state["time_remaining"] - turn["time_elapsed"]
        )

    game.turn_manager = SimpleNamespace(update_clock_and_possession=update_clock)
    turn = {
        "result_type": "OREB",
        "time_elapsed": 1,
        "next_play_type": "OREB",
        "next_turn": "OREB",
        "possession_flips": True,
    }

    assert GameManager._finalize_synthesized_clock_turn(game, turn) is True
    assert turn["quarter_ends_after"] is True
    assert turn["next_play_type"] is None
    assert turn["possession_flips"] is False
