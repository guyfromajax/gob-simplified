"""Final Turn backend coordinate ownership and home/away parity."""

import random
from types import SimpleNamespace

import pytest

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
