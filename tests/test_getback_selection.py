"""Tests for HCO offensive get-back selection."""

from types import SimpleNamespace
from unittest.mock import patch

from BackEnd.utils.getback_selection import (
    roll_num_getback,
    select_offense_getback_list,
    try_emergency_getback_vs_poised_fb,
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


def test_shooter_never_gets_back_when_position_is_stale():
    off_lineup = {
        "PG": _player(90, player_id="pg"),
        "SG": _player(80, player_id="sg"),
        "SF": _player(70, player_id="sf"),
        "PF": _player(60, player_id="pf"),
        "C": _player(50, player_id="c"),
    }
    def_lineup = {pos: _player(50, player_id=f"d{pos}") for pos in off_lineup}
    roles = {
        "shooter": off_lineup["PG"],
        "steps": [
            {
                "pos_actions": {
                    pos: {"location": "deep upper wing"}
                    for pos in off_lineup
                }
            }
        ],
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
        shooter_id="pg",
    )

    assert "PG" not in result
    assert "C" not in result
    assert result == ["PF", "SF"]


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

    assert result == ["PF", "SF"]


def _emergency_fixtures():
    off_lineup = {
        "PG": _player(22, player_id="pg"),
        "SG": _player(40, player_id="sg"),
        "SF": _player(45, player_id="sf"),
        "PF": _player(15, player_id="pf"),
        "C": _player(85, player_id="c"),
    }
    def_lineup = {pos: _player(50, player_id=f"d{pos}") for pos in off_lineup}
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
    # Core-8 values are stored on ±20 and normalized to the historical ±10
    # gameplay scale. Stored 16 therefore exercises gameplay fb_opp == 8.
    off_team = SimpleNamespace(team_attributes={"fb_opp_modifier": 16})
    kwargs = dict(
        off_team=off_team,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        game=game,
        roles=roles,
        shooter_pos="C",
        shot_step_index=0,
        is_home_team_shooting=True,
        defense_playcall="man",
        shooter_id="c",
        defense_poised_for_dreb_fb=True,
        current_getback_list=[],
    )
    return kwargs


def test_emergency_getback_skipped_when_defense_not_poised():
    kwargs = _emergency_fixtures()
    kwargs["defense_poised_for_dreb_fb"] = False
    with patch("BackEnd.utils.getback_selection.random.randint", return_value=0):
        assert try_emergency_getback_vs_poised_fb(**kwargs) == []


def test_emergency_getback_skipped_when_roll_too_high():
    kwargs = _emergency_fixtures()
    with patch("BackEnd.utils.getback_selection.random.randint", return_value=9):
        assert try_emergency_getback_vs_poised_fb(**kwargs) == []


def test_emergency_getback_succeeds_when_roll_equals_fb_opp():
    kwargs = _emergency_fixtures()
    with patch("BackEnd.utils.getback_selection.random.randint", return_value=8):
        assert try_emergency_getback_vs_poised_fb(**kwargs) == ["PF"]


def test_emergency_getback_adds_one_player_when_fb_opp_beats_roll():
    kwargs = _emergency_fixtures()
    with patch("BackEnd.utils.getback_selection.random.randint", return_value=5):
        result = try_emergency_getback_vs_poised_fb(**kwargs)
    assert result == ["PF"]


def test_emergency_getback_noop_when_primary_getback_already_assigned():
    kwargs = _emergency_fixtures()
    kwargs["current_getback_list"] = ["PG"]
    with patch("BackEnd.utils.getback_selection.random.randint", return_value=0):
        assert try_emergency_getback_vs_poised_fb(**kwargs) == ["PG"]
