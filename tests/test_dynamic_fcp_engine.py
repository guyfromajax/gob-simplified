"""PR1 Step 2 — dynamic FCP engine loop (shared pressure turn, turn_mode=fcp)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from BackEnd.engine.dynamic_fcp import compute_dynamic_fcp_turn
from BackEnd.engine.fcp_press_plays import StraightPressureFCP


def _mock_player(pid: str, attrs=None):
    base = {k: 55 for k in ("SC", "SH", "OD", "PS", "BH", "RB", "AG", "ST", "IQ", "CH")}
    if attrs:
        base.update(attrs)
    return SimpleNamespace(
        player_id=pid,
        attributes=base,
        coords={"x": 50, "y": 25},
    )


def _build_fcp_game(*, bh_x=15, bh_y=20):
    off_lineup = {
        "PG": _mock_player("off_pg"),
        "SG": _mock_player("off_sg"),
        "SF": _mock_player("off_sf"),
        "PF": _mock_player("off_pf"),
        "C": _mock_player("off_c"),
    }
    def_lineup = {
        "PG": _mock_player("def_pg"),
        "SG": _mock_player("def_sg"),
        "SF": _mock_player("def_sf"),
        "PF": _mock_player("def_pf"),
        "C": _mock_player("def_c"),
    }
    off_xy = {
        "off_pg": {"x": bh_x, "y": bh_y},
        "off_sg": {"x": 15, "y": 30},
        "off_sf": {"x": 3, "y": 25},
        "off_pf": {"x": 50, "y": 25},
        "off_c": {"x": 65, "y": 25},
    }
    def_xy = {
        "def_pg": {"x": 22, "y": 25},
        "def_sg": {"x": 28, "y": 32},
        "def_sf": {"x": 28, "y": 18},
        "def_pf": {"x": 52, "y": 25},
        "def_c": {"x": 73, "y": 25},
    }
    prior = {**off_xy, **def_xy}

    off_team = SimpleNamespace(
        team_id="home",
        lineup=off_lineup,
        team_attributes={
            "team_chemistry": 10,
            "fight": 0,
            "pt_opp_modifier": 0,
        },
        strategy_calls={"aggression_call": "normal"},
    )
    def_team = SimpleNamespace(
        team_id="away",
        lineup=def_lineup,
        team_attributes={
            "team_chemistry": 10,
            "discipline": 0,
            "pt_efficiency": 0,
        },
        strategy_calls={"aggression_call": "normal"},
    )

    game = MagicMock()
    game.offense_team = off_team
    game.defense_team = def_team
    game.away_team = SimpleNamespace(team_id="away")
    game.game_state = {
        "shot_clock_remaining": 24,
        "time_remaining": 600,
        "fcp_press_play": "fcp_straight_pressure",
    }
    game.turns = [
        {
            "final_ball_handler_id": "off_pg",
            "final_coords": prior,
        }
    ]
    return game


def test_fcp_engine_skips_walk_up_and_produces_segments():
    game = _build_fcp_game()
    play = StraightPressureFCP()
    dyn = compute_dynamic_fcp_turn(game, play)

    assert not dyn.get("bail")
    assert dyn.get("skip_walk_up") is True
    assert dyn.get("turn_mode") == "fcp"
    assert dyn.get("result_type") in (
        "HCO",
        "DEAD BALL",
        "STEAL",
        "FOUL",
        "FAST_BREAK_SHOT",
    )
    segments = dyn.get("loop_segments") or []
    assert len(segments) >= 1
    assert segments[0].get("kind") == "hct_converge"


def test_fcp_bh_from_final_ball_handler_not_hardcoded_pg():
    game = _build_fcp_game(bh_x=16, bh_y=22)
    game.offense_team.lineup["SG"] = _mock_player("off_sg")
    game.turns[0]["final_ball_handler_id"] = "off_sg"

    dyn = compute_dynamic_fcp_turn(game, StraightPressureFCP())
    assert dyn.get("bh_pos") == "SG"


def test_sf_at_inbound_spot_excluded_from_pass_pool():
    from BackEnd.engine.dynamic_hct import _sf_at_fcp_inbound_spot

    assert _sf_at_fcp_inbound_spot({"SF": {"x": 3, "y": 25}}, False) is True
    assert _sf_at_fcp_inbound_spot({"SF": {"x": 12, "y": 25}}, False) is False
