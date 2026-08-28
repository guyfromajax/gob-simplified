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


def _beaten_gamble_drive(primary_beaten_via, seed, cutoff=None):
    """Build one man-defense attack drive under the 3-tier posture.

    `primary_beaten_via` is None (normal contest), "param" (explicit kwarg) or
    "game_state" (the flag the HCO walk sets when a defender's gamble on the pass
    to this receiver missed). The primary contest is pinned to a defense win so
    any Tier A is attributable to the bypass, not to a roll; `cutoff` pins the
    S2c help-cutoff return so the two stages can be judged independently.
    """
    random.seed(seed)
    selected_step = {
        "pos_actions": {
            "PG": {"location": "upper wing", "action": "handle_ball"},
            "SG": {"location": "upper bird", "action": "drift"},
            "SF": {"location": "lower wing", "action": "drift"},
            "PF": {"location": "lower bird", "action": "drift"},
            "C": {"location": "key", "action": "drift"},
        }
    }
    def_lineup = {
        p: SimpleNamespace(player_id=f"def-{p}",
                           attributes={"IQ": 12, "CH": 12, "OD": 12, "AG": 12, "BH": 12, "ST": 12})
        for p in ["PG", "SG", "SF", "PF", "C"]
    }
    off_lineup = {
        p: SimpleNamespace(player_id=f"off-{p}",
                           attributes={"IQ": 12, "CH": 12, "BH": 12, "AG": 12, "ST": 12})
        for p in ["PG", "SG", "SF", "PF", "C"]
    }
    game_state = {"defense_playcall": "man", "_hco_defense_posture": "man"}
    if primary_beaten_via == "game_state":
        game_state["_hco_primary_beaten"] = True
    game = SimpleNamespace(
        game_state=game_state,
        offense_team=SimpleNamespace(team_attributes={"team_chemistry": 12, "offensive_efficiency": 12}),
        defense_team=SimpleNamespace(
            is_user_team=False,
            team_attributes={"team_chemistry": 12, "defensive_efficiency": 12},
            strategy_calls={"aggression_call": "normal"},
        ),
    )
    with patch(
        "BackEnd.engine.attack_drive_clearance.get_matchups_for_defending_team",
        return_value={"PG": "PG", "SG": "SG", "SF": "SF", "PF": "PF", "C": "C"},
    ), patch(
        "BackEnd.engine.attack_drive_clearance._resolve_hco_drive_contest",
        return_value=("C", 0.25, None),
    ), patch(
        "BackEnd.engine.attack_drive_clearance._resolve_hco_help_cutoff",
        return_value=(cutoff or (None, "A", 1.0, None, None)),
    ):
        return build_attack_drive_sequence(
            selected_step=selected_step,
            ball_handler_pos="PG",
            start_location="upper wing",
            destination_location="rim",
            timestamp=0,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            game=game,
            is_away_offense=False,
            primary_beaten=(primary_beaten_via == "param"),
        )["attack_drive_meta"]


def test_beaten_primary_forces_tier_a_via_param_and_game_state():
    """A receiver whose own defender gambled and missed drives against nobody.

    Both entry points must override the primary contest to Tier A (full drive, no
    path-stop): the explicit kwarg, and the `_hco_primary_beaten` game_state flag
    the HCO walk sets — the walk uses the flag so `_create_attack_drive_shoot_steps`
    keeps its signature (a shared-signature change is what broke `previous_step`).
    """
    for seed in range(8):
        assert _beaten_gamble_drive(None, seed)["drive_tier"] == "C", seed
        for via in ("param", "game_state"):
            meta = _beaten_gamble_drive(via, seed)
            assert meta["drive_tier"] == "A", (via, seed, meta["drive_tier"])
            assert meta["drive_stop_fraction"] == 1.0, (via, seed)


def test_beaten_primary_still_subject_to_help_cutoff():
    """The bypass beats the PRIMARY, not the whole defense: S2c still demotes.

    `_resolve_hco_help_cutoff` excludes the beaten primary from the help race, so
    the gambler is out of both roles without any special-casing — but a rotating
    help defender must still be able to wall off the blow-by.
    """
    meta = _beaten_gamble_drive("game_state", 3, cutoff=("C", "C", 0.4, None, None))
    assert meta["drive_tier"] == "C"
    assert meta["drive_stop_fraction"] == 0.4
