"""Tests for motion offense attack-drive clearance."""

import random
from types import SimpleNamespace
from unittest.mock import patch

from BackEnd.engine.attack_drive_clearance import (
    _is_in_blast_radius,
    _perimeter_offense_threshold,
    _perimeter_defense_threshold,
    _defender_help_threshold,
    _compute_drive_scores,
    READ_THRESHOLD_FLOOR,
    build_attack_drive_sequence,
    build_attack_drive_clearance,
    _shot_type_for_stopped_pullup_coords,
)


def test_blast_radius_upper_half():
    assert _is_in_blast_radius("upper lowPost", "upper midPost", "upper") is True
    assert _is_in_blast_radius("lower lowPost", "upper midPost", "upper") is False
    assert _is_in_blast_radius("upper midPost", "midLane", "central") is False
    assert _is_in_blast_radius("midLane", "midLane", "central") is True


def test_build_clearance_assigns_dish_and_evac():
    random.seed(7)
    selected_step = {
        "pos_actions": {
            "PG": {"location": "upper wing", "action": "handle_ball"},
            "SG": {"location": "upper lowPost", "action": "drift"},
            "SF": {"location": "lower wing", "action": "drift"},
            "PF": {"location": "upper bird", "action": "drift"},
            "C": {"location": "key", "action": "drift"},
        }
    }
    def_lineup = {
        p: SimpleNamespace(
            player_id=f"def-{p}",
            attributes={"IQ": 8, "CH": 8, "OD": 8, "AG": 8, "BH": 8},
        )
        for p in ["PG", "SG", "SF", "PF", "C"]
    }
    off_lineup = {
        p: SimpleNamespace(
            player_id=f"off-{p}",
            attributes={"IQ": 8, "CH": 8, "BH": 8, "AG": 8},
        )
        for p in ["PG", "SG", "SF", "PF", "C"]
    }
    game = SimpleNamespace(
        game_state={"defense_playcall": "man"},
        offense_team=SimpleNamespace(team_attributes={"team_chemistry": 10, "offensive_efficiency": 5}),
        defense_team=SimpleNamespace(
            is_user_team=False,
            team_attributes={"team_chemistry": 10, "defensive_efficiency": 5},
            strategy_calls={"aggression_call": "normal"},
        ),
    )

    with patch(
        "BackEnd.engine.attack_drive_clearance.get_matchups_for_defending_team",
        return_value={"PG": "PG", "SG": "SG", "SF": "SF", "PF": "PF", "C": "C"},
    ), patch(
        "BackEnd.engine.attack_drive_clearance.random.random",
        return_value=0.1,
    ), patch(
        "BackEnd.engine.attack_drive_clearance.player_read",
        return_value=200,
    ):
        result = build_attack_drive_clearance(
            selected_step=selected_step,
            ball_handler_pos="PG",
            destination_location="upper midPost",
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            game=game,
            is_away_offense=False,
        )

    drive = result["drive_pos_actions"]
    assert drive["PG"]["action"] == "drive"
    assert drive["PG"]["location"] == "upper midPost"
    assert sum(1 for p in drive if drive[p]["action"] == "cut") >= 2
    assert all(drive[p]["action"] in ("drive", "cut", "stationary") for p in drive)
    assert result["attack_drive_meta"]["driver_gate"] is True
    assert result["attack_drive_meta"]["gate_driver_pos"] == "PG"
    assert result["attack_drive_meta"]["dish_receiver_pos"] in {"SG", "PF"}
    assert "defender_overrides" in result["attack_drive_meta"]


def test_midlane_drive_skips_dish_slot():
    random.seed(3)
    selected_step = {
        "pos_actions": {
            "PG": {"location": "upper wing", "action": "handle_ball"},
            "SG": {"location": "upper lowPost", "action": "drift"},
            "SF": {"location": "lower wing", "action": "drift"},
            "PF": {"location": "key", "action": "drift"},
            "C": {"location": "lower corner", "action": "drift"},
        }
    }
    off_lineup = {
        p: SimpleNamespace(
            player_id=f"off-{p}",
            attributes={"IQ": 8, "CH": 8, "BH": 8, "AG": 8},
        )
        for p in ["PG", "SG", "SF", "PF", "C"]
    }
    def_lineup = {
        p: SimpleNamespace(
            player_id=f"def-{p}",
            attributes={"IQ": 5, "CH": 5, "OD": 8, "AG": 8},
        )
        for p in ["PG", "SG", "SF", "PF", "C"]
    }
    game = SimpleNamespace(
        game_state={"defense_playcall": "2-3 Zone"},
        offense_team=SimpleNamespace(team_attributes={"team_chemistry": 10, "offensive_efficiency": 5}),
        defense_team=SimpleNamespace(
            is_user_team=False,
            team_attributes={"team_chemistry": 10, "defensive_efficiency": 5},
            strategy_calls={"aggression_call": "normal"},
        ),
    )

    result = build_attack_drive_clearance(
        selected_step=selected_step,
        ball_handler_pos="PG",
        destination_location="midLane",
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        game=game,
        is_away_offense=False,
    )

    assert result["attack_drive_meta"]["dish_receiver_pos"] is None
    assert result["drive_pos_actions"]["PG"]["action"] == "drive"
    assert result["drive_pos_actions"]["PG"]["location"] == "midLane"
    assert all(
        action.get("location") != "midLane"
        for pos, action in result["drive_pos_actions"].items()
        if pos != "PG"
    )


def test_attack_drive_dish_candidate_uses_nested_coords_from_step():
    selected_step = {
        "timestamp": 5400,
        "events": [],
        "pos_actions": {
            "C": {"action": "stationary", "location": "lower corner"},
            "PF": {"action": "cut", "location": "lower lowPost"},
            "PG": {"action": "handle_ball", "location": "lower wing"},
            "SF": {"action": "stationary", "location": "upper corner"},
            "SG": {"action": "stationary", "location": "upper wing"},
        },
    }
    off_lineup = {
        p: SimpleNamespace(
            player_id=f"off-{p}",
            attributes={"IQ": 8, "CH": 8, "BH": 8, "AG": 8},
        )
        for p in ["PG", "SG", "SF", "PF", "C"]
    }
    def_lineup = {
        p: SimpleNamespace(
            player_id=f"def-{p}",
            attributes={"IQ": 8, "CH": 8, "OD": 8, "AG": 8, "BH": 8},
        )
        for p in ["PG", "SG", "SF", "PF", "C"]
    }
    game = SimpleNamespace(
        game_state={"defense_playcall": "man"},
        offense_team=SimpleNamespace(
            team_attributes={"team_chemistry": 10, "offensive_efficiency": 5},
        ),
        defense_team=SimpleNamespace(
            is_user_team=False,
            team_attributes={"team_chemistry": 10, "defensive_efficiency": 5},
            strategy_calls={"aggression_call": "normal"},
        ),
    )

    with patch(
        "BackEnd.engine.attack_drive_clearance.get_matchups_for_defending_team",
        return_value={"PG": "PG", "SG": "SG", "SF": "SF", "PF": "PF", "C": "C"},
    ), patch(
        "BackEnd.engine.attack_drive_clearance.random.random",
        return_value=0.1,
    ), patch(
        "BackEnd.engine.attack_drive_clearance.player_read",
        return_value=200,
    ):
        result = build_attack_drive_sequence(
            selected_step=selected_step,
            ball_handler_pos="PG",
            start_location="lower wing",
            destination_location="lower lowPost",
            timestamp=5700,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            game=game,
            is_away_offense=True,
        )

    assert result["attack_drive_meta"]["dish_receiver_pos"] == "PF"
    assert result["steps"][0]["pos_actions"]["PF"]["location"] == "midLane"


def test_read_thresholds_use_team_efficiency_and_floor():
    off_team = SimpleNamespace(
        team_attributes={"team_chemistry": 7, "offensive_efficiency": -10},
    )
    def_team = SimpleNamespace(
        team_attributes={"team_chemistry": 7, "defensive_efficiency": -10},
    )
    # The EOG structural pass widened stored core-8 attributes to +/-20 and
    # deliberately normalized gameplay reads back to +/-10.  Stored -10 is
    # therefore -5 in gameplay: chemistry 7 + efficiency -5 = 2.
    assert _perimeter_offense_threshold(off_team) == 150 - 2
    assert _perimeter_defense_threshold(def_team) == 125 - 2
    assert _defender_help_threshold(def_team) == 100 - 2

    high_off = SimpleNamespace(
        team_attributes={"team_chemistry": 200, "offensive_efficiency": 200},
    )
    assert _perimeter_offense_threshold(high_off) == READ_THRESHOLD_FLOOR


def test_drive_contest_uses_doubled_def_chem_and_efficiency():
    driver = SimpleNamespace(attributes={"BH": 50, "AG": 50, "IQ": 50, "CH": 50})
    defender = SimpleNamespace(attributes={"OD": 50, "AG": 50, "IQ": 50, "CH": 50})
    off_team = SimpleNamespace(team_attributes={"offensive_efficiency": 0, "team_chemistry": 0})
    def_team = SimpleNamespace(team_attributes={"defensive_efficiency": 5, "team_chemistry": 10})

    with patch("BackEnd.engine.attack_drive_clearance.calculate_ball_handling_score", return_value=100.0), patch(
        "BackEnd.engine.attack_drive_clearance.calculate_defender_pressure_score",
        return_value=100.0,
    ), patch("BackEnd.engine.attack_drive_clearance.random.randint", return_value=1):
        _, _, offense_wins = _compute_drive_scores(driver, defender, off_team, def_team, "man")

    assert offense_wins is False


def test_stopped_pullup_value_uses_release_geometry_home_and_away():
    assert _shot_type_for_stopped_pullup_coords(
        {"x": 70, "y": 25}, False
    ) == ("attack", "Attack")
    assert _shot_type_for_stopped_pullup_coords(
        {"x": 50, "y": 25}, False
    ) == ("outside", "Outside")
    assert _shot_type_for_stopped_pullup_coords(
        {"x": 30, "y": 25}, True
    ) == ("attack", "Attack")
    assert _shot_type_for_stopped_pullup_coords(
        {"x": 50, "y": 25}, True
    ) == ("outside", "Outside")
