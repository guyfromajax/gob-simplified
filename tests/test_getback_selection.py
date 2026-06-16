"""Tests for HCO offensive get-back selection."""

from types import SimpleNamespace

from BackEnd.utils.getback_selection import (
    roll_num_getback,
    select_offense_getback_list,
)


def _player(x: float, y: float = 25.0, player_id: str = "p"):
    return SimpleNamespace(coords={"x": x, "y": y}, player_id=player_id)


def test_roll_num_getback_slider_zero_always_none():
    assert roll_num_getback(0, 0.0) == 0
    assert roll_num_getback(0, 0.99) == 0


def test_roll_num_getback_slider_four_always_two():
    assert roll_num_getback(4, 0.0) == 1
    assert roll_num_getback(4, 0.99) == 2


def test_select_farthest_back_by_x_not_hardcoded_positions():
    off_lineup = {
        "PG": _player(22, player_id="pg"),
        "SG": _player(40, player_id="sg"),
        "SF": _player(45, player_id="sf"),
        "PF": _player(15, player_id="pf"),
        "C": _player(85, player_id="c"),
    }
    def_lineup = {
        "PG": _player(50, player_id="dpg"),
        "SG": _player(50, player_id="dsg"),
        "SF": _player(50, player_id="dsf"),
        "PF": _player(50, player_id="dpf"),
        "C": _player(50, player_id="dc"),
    }
    roles = {
        "steps": [
            {
                "pos_actions": {
                    "PG": {"location": "upper wing"},
                    "SG": {"location": "deep upper wing"},
                    "SF": {"location": "deep lower wing"},
                    "PF": {"location": "deep upper baseline"},
                    "C": {"location": "key"},
                }
            }
        ]
    }
    game = SimpleNamespace(zone_defender_assignments_by_step={})

    result = select_offense_getback_list(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        game=game,
        roles=roles,
        shooter_pos="C",
        num_getback=2,
        shot_step_index=0,
        is_home_team_shooting=True,
        defense_playcall="man",
    )

    assert result == ["PF", "PG"]


def test_shooter_never_gets_back():
    off_lineup = {
        "PG": _player(90, player_id="pg"),
        "SG": _player(70, player_id="sg"),
        "SF": _player(60, player_id="sf"),
        "PF": _player(50, player_id="pf"),
        "C": _player(50, player_id="c"),
    }
    def_lineup = {pos: _player(50, player_id=f"d{pos}") for pos in off_lineup}
    roles = {
        "steps": [
            {
                "pos_actions": {
                    pos: {"location": "deep upper wing"}
                    for pos in off_lineup
                }
            }
        ]
    }
    game = SimpleNamespace(zone_defender_assignments_by_step={})

    result = select_offense_getback_list(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        game=game,
        roles=roles,
        shooter_pos="PG",
        num_getback=2,
        shot_step_index=0,
        is_home_team_shooting=True,
        defense_playcall="man",
    )

    assert "PG" not in result
    assert len(result) == 2


def test_matchup_must_be_at_qualifying_spot():
    off_lineup = {
        "PG": _player(90, player_id="pg"),
        "SG": _player(80, player_id="sg"),
        "SF": _player(70, player_id="sf"),
        "PF": _player(50, player_id="pf"),
        "C": _player(50, player_id="c"),
    }
    def_lineup = {pos: _player(50, player_id=f"d{pos}") for pos in off_lineup}
    roles = {
        "steps": [
            {
                "pos_actions": {
                    "PG": {"location": "low post"},
                    "SG": {"location": "deep upper wing"},
                    "SF": {"location": "deep lower wing"},
                    "PF": {"location": "key"},
                    "C": {"location": "key"},
                }
            }
        ]
    }
    game = SimpleNamespace(zone_defender_assignments_by_step={})

    result = select_offense_getback_list(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        game=game,
        roles=roles,
        shooter_pos="C",
        num_getback=2,
        shot_step_index=0,
        is_home_team_shooting=True,
        defense_playcall="man",
    )

    assert result == ["SG", "SF"]
