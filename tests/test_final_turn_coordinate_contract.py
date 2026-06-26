"""Final Turn backend coordinate ownership and home/away parity."""

import random
from types import SimpleNamespace

import pytest

from BackEnd.engine import phase_resolution
from BackEnd.engine.skeleton_step_emitter import _variant_flight_end
from BackEnd.models.turn_manager import TurnManager


POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _alignment_manager(*, away_offense):
    home = SimpleNamespace(
        team_id="home",
        lineup={pos: SimpleNamespace(player_id=f"home_{pos}") for pos in POSITIONS},
    )
    away = SimpleNamespace(
        team_id="away",
        lineup={pos: SimpleNamespace(player_id=f"away_{pos}") for pos in POSITIONS},
    )
    game = SimpleNamespace(
        home_team=home,
        away_team=away,
        offense_team=away if away_offense else home,
        defense_team=home if away_offense else away,
    )
    manager = TurnManager.__new__(TurnManager)
    manager.game = game
    return manager


def _build_alignments(*, away_offense, seed):
    manager = _alignment_manager(away_offense=away_offense)
    random.seed(seed)
    offense, _, _ = manager._build_final_turn_offense_alignment()
    defense, zone = manager._build_final_turn_defense_alignment()
    return offense, defense, zone


def _assert_mirror(home_coords, away_coords):
    assert away_coords.keys() == home_coords.keys()
    for key in home_coords:
        assert away_coords[key]["x"] == 100 - home_coords[key]["x"]
        assert away_coords[key]["y"] == home_coords[key]["y"]


def test_final_turn_alignment_payloads_are_display_oriented():
    home_offense, home_defense, home_zone = _build_alignments(
        away_offense=False,
        seed=9173,
    )
    away_offense, away_defense, away_zone = _build_alignments(
        away_offense=True,
        seed=9173,
    )

    assert away_zone == home_zone
    _assert_mirror(home_offense, away_offense)
    _assert_mirror(home_defense, away_defense)


def test_final_turn_defense_pg_uses_top_lane_not_key():
    from BackEnd.constants import HCO_STRING_SPOTS

    manager = _alignment_manager(away_offense=False)
    random.seed(42)
    d_dest, _zone = manager._build_final_turn_defense_alignment()
    assert d_dest["PG"] == HCO_STRING_SPOTS["topLane"]
    assert d_dest["PG"] != HCO_STRING_SPOTS["key"]


@pytest.mark.parametrize(
    ("shot_variant", "result_type"),
    [
        ("SWISH", "MAKE"),
        ("CLANK", "MISS"),
        ("BANK_MAKE", "MAKE"),
        ("AIRBALL", "MISS"),
    ],
)
def test_final_turn_ball_flight_targets_preserve_home_away_parity(
    shot_variant,
    result_type,
):
    home = _variant_flight_end(shot_variant, result_type, False, {})
    away = _variant_flight_end(shot_variant, result_type, True, {})

    assert away["x"] == 100 - home["x"]
    assert away["y"] == home["y"]


def test_final_turn_block_target_uses_backend_display_oriented_bounce_spot():
    home = _variant_flight_end(
        None,
        "BLOCK",
        False,
        {"ball_bounce_x": 84, "ball_bounce_y": 28},
    )
    away = _variant_flight_end(
        None,
        "BLOCK",
        True,
        {"ball_bounce_x": 16, "ball_bounce_y": 28},
    )

    assert home == {"x": 84.0, "y": 28.0}
    assert away == {"x": 16.0, "y": 28.0}
    assert away["x"] == 100 - home["x"]


def test_final_turn_attack_shot_unwraps_attack_drive_steps(monkeypatch):
    lineup = {
        pos: SimpleNamespace(
            player_id=f"home_{pos}",
            attributes={
                "SC": 10 if pos == "PG" else 1,
                "AG": 10 if pos == "PG" else 1,
                "SH": 1,
            },
        )
        for pos in POSITIONS
    }
    defense_lineup = {
        pos: SimpleNamespace(player_id=f"away_{pos}", attributes={})
        for pos in POSITIONS
    }
    home = SimpleNamespace(team_id="home", lineup=lineup)
    away = SimpleNamespace(team_id="away", lineup=defense_lineup)
    captured = {}

    game = SimpleNamespace(
        quarter=2,
        game_state={
            "defense_playcall": "man",
            "time_remaining": 7,
        },
        home_team=home,
        away_team=away,
        offense_team=home,
        defense_team=away,
        turn_manager=SimpleNamespace(
            assign_roles=lambda off_call, def_call, skeleton: captured.setdefault(
                "roles",
                {
                    "shooter": lineup["PG"],
                    "shooter_pos": "PG",
                },
            )
        ),
        shot_manager=SimpleNamespace(resolve_shot=lambda roles: {"result_type": "MISS"}),
    )

    monkeypatch.setattr(
        "BackEnd.utils.situational_logic.get_score_delta",
        lambda game: 0,
    )
    random_values = iter([0.99, 0, 0, 0, 0, 0, 0])
    monkeypatch.setattr(random, "random", lambda: next(random_values, 0))
    monkeypatch.setattr(random, "choice", lambda values: values[0])
    monkeypatch.setattr(random, "shuffle", lambda values: None)
    monkeypatch.setattr(
        phase_resolution,
        "set_shooter_coords_from_skeleton_last_step",
        lambda game, skeleton, roles: None,
    )
    monkeypatch.setattr(
        phase_resolution,
        "build_skeleton_pre_resolve_shot_snapshot",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        phase_resolution,
        "attach_position_snapshots",
        lambda *args, **kwargs: None,
    )

    result = phase_resolution.resolve_final_turn_shot_logic(
        game,
        o_destinations={},
        d_destinations={},
        position_to_spot={pos: "key" for pos in POSITIONS},
        bh_pos="PG",
    )

    assert result["final_turn"] is True
    assert result["time_elapsed"] == 7
    assert isinstance(result["skeleton"]["steps"], list)
    assert len(result["skeleton"]["steps"]) == 4
    assert result["skeleton"]["steps"][2]["pos_actions"]["PG"]["action"] == "drive"
    assert result["skeleton"]["steps"][3]["pos_actions"]["PG"]["action"] == "shoot"
    assert result["skeleton"]["steps"][0]["_step_t_floor_game_seconds"] == pytest.approx(3.0)


def test_final_turn_outside_step0_floor_stamps_hold(monkeypatch):
    lineup = {
        pos: SimpleNamespace(
            player_id=f"home_{pos}",
            attributes={"SH": 10 if pos == "SG" else 1, "SC": 1, "AG": 1},
        )
        for pos in POSITIONS
    }
    defense_lineup = {
        pos: SimpleNamespace(player_id=f"away_{pos}", attributes={})
        for pos in POSITIONS
    }
    home = SimpleNamespace(team_id="home", lineup=lineup)
    away = SimpleNamespace(team_id="away", lineup=defense_lineup)
    game = SimpleNamespace(
        quarter=2,
        game_state={
            "defense_playcall": "man",
            "time_remaining": 29,
        },
        home_team=home,
        away_team=away,
        offense_team=home,
        defense_team=away,
        turn_manager=SimpleNamespace(
            assign_roles=lambda off_call, def_call, skeleton: {
                "shooter": lineup["SG"],
                "shooter_pos": "SG",
            }
        ),
        shot_manager=SimpleNamespace(resolve_shot=lambda roles: {"result_type": "MISS"}),
    )

    monkeypatch.setattr(
        "BackEnd.utils.situational_logic.get_score_delta",
        lambda game: 0,
    )
    random_values = iter([0.01, 0, 0, 0, 0, 0, 0])
    monkeypatch.setattr(random, "random", lambda: next(random_values, 0))
    monkeypatch.setattr(random, "choice", lambda values: values[0])
    monkeypatch.setattr(random, "shuffle", lambda values: None)
    monkeypatch.setattr(
        phase_resolution,
        "set_shooter_coords_from_skeleton_last_step",
        lambda game, skeleton, roles: None,
    )
    monkeypatch.setattr(
        phase_resolution,
        "build_skeleton_pre_resolve_shot_snapshot",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        phase_resolution,
        "attach_position_snapshots",
        lambda *args, **kwargs: None,
    )

    result = phase_resolution.resolve_final_turn_shot_logic(
        game,
        o_destinations={},
        d_destinations={},
        position_to_spot={pos: "key" for pos in POSITIONS},
        bh_pos="PG",
    )

    assert result["final_turn"] is True
    assert result["time_elapsed"] == 29
    assert result["skeleton"]["steps"][0]["_step_t_floor_game_seconds"] == pytest.approx(26.0)


def test_final_turn_attack_step0_floor_stamps_hold(monkeypatch):
    lineup = {
        pos: SimpleNamespace(
            player_id=f"home_{pos}",
            attributes={
                "SC": 10 if pos == "PG" else 1,
                "AG": 10 if pos == "PG" else 1,
                "SH": 1,
            },
        )
        for pos in POSITIONS
    }
    defense_lineup = {
        pos: SimpleNamespace(player_id=f"away_{pos}", attributes={})
        for pos in POSITIONS
    }
    home = SimpleNamespace(team_id="home", lineup=lineup)
    away = SimpleNamespace(team_id="away", lineup=defense_lineup)
    game = SimpleNamespace(
        quarter=2,
        game_state={"defense_playcall": "man", "time_remaining": 29},
        home_team=home,
        away_team=away,
        offense_team=home,
        defense_team=away,
        turn_manager=SimpleNamespace(
            assign_roles=lambda off_call, def_call, skeleton: {
                "shooter": lineup["PG"],
                "shooter_pos": "PG",
            }
        ),
        shot_manager=SimpleNamespace(resolve_shot=lambda roles: {"result_type": "MISS"}),
    )

    monkeypatch.setattr("BackEnd.utils.situational_logic.get_score_delta", lambda game: 0)
    random_values = iter([0.99, 0, 0, 0, 0, 0, 0])
    monkeypatch.setattr(random, "random", lambda: next(random_values, 0))
    monkeypatch.setattr(random, "choice", lambda values: values[0])
    monkeypatch.setattr(random, "shuffle", lambda values: None)
    monkeypatch.setattr(
        phase_resolution,
        "set_shooter_coords_from_skeleton_last_step",
        lambda game, skeleton, roles: None,
    )
    monkeypatch.setattr(
        phase_resolution,
        "build_skeleton_pre_resolve_shot_snapshot",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        phase_resolution,
        "attach_position_snapshots",
        lambda *args, **kwargs: None,
    )

    result = phase_resolution.resolve_final_turn_shot_logic(
        game,
        o_destinations={},
        d_destinations={},
        position_to_spot={pos: "key" for pos in POSITIONS},
        bh_pos="PG",
    )

    assert result["skeleton"]["steps"][0]["_step_t_floor_game_seconds"] == pytest.approx(25.0)
