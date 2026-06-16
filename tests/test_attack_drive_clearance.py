"""Tests for motion offense attack-drive clearance."""

import random
from types import SimpleNamespace
from unittest.mock import patch

from BackEnd.engine.attack_drive_clearance import (
    _is_in_blast_radius,
    build_attack_drive_clearance,
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
    assert result["drive_pos_actions"]["SG"]["action"] == "cut"
