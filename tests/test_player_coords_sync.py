"""sync_lineup_coords_from_turn and apply_coords_from_animations_list."""

from unittest.mock import MagicMock

from BackEnd.utils.shared import (
    apply_coords_from_animations_list,
    sync_lineup_coords_from_turn,
)

POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def _fake_player(pid, x, y):
    p = MagicMock()
    p.player_id = pid
    p.coords = {"x": x, "y": y}
    return p


def _game_five_five():
    home_players = [_fake_player(f"h{i}", float(i), 10.0) for i in range(5)]
    away_players = [_fake_player(f"a{i}", 50.0 + i, 50.0) for i in range(5)]
    gm = MagicMock()
    gm.home_team = MagicMock()
    gm.home_team.lineup = {POSITIONS[j]: home_players[j] for j in range(5)}
    gm.away_team = MagicMock()
    gm.away_team.lineup = {POSITIONS[j]: away_players[j] for j in range(5)}
    return gm


def test_apply_coords_from_animations_list_updates_matching_player():
    gm = _game_five_five()
    h0 = gm.home_team.lineup["PG"]
    h1 = gm.home_team.lineup["SG"]
    apply_coords_from_animations_list(
        gm,
        [{"playerId": "h0", "end": {"x": 33, "y": 44}}],
    )
    assert h0.coords == {"x": 33.0, "y": 44.0}
    assert h1.coords == {"x": 1.0, "y": 10.0}


def test_sync_lineup_carry_forward_and_animation():
    gm = _game_five_five()
    h0 = gm.home_team.lineup["PG"]
    turn = {"animations": [{"playerId": "h0", "end": {"x": 99, "y": 11}}]}
    sync_lineup_coords_from_turn(gm, turn)
    assert h0.coords == {"x": 99.0, "y": 11.0}
    assert gm.home_team.lineup["SG"].coords == {"x": 1.0, "y": 10.0}


def test_sync_lineup_overlay_overrides_animation():
    gm = _game_five_five()
    h0 = gm.home_team.lineup["PG"]
    turn = {
        "animations": [{"playerId": "h0", "end": {"x": 10, "y": 10}}],
        "defense_release_coords": {"h0": {"x": 20, "y": 30}},
        "offense_getback_coords": {"h0": {"x": 40, "y": 50}},
    }
    sync_lineup_coords_from_turn(gm, turn)
    assert h0.coords == {"x": 40.0, "y": 50.0}


def test_sync_movement_coords_fallback():
    gm = _game_five_five()
    p = gm.home_team.lineup["PG"]
    turn = {
        "animations": [
            {
                "playerId": "h0",
                "movement": [
                    {"timestamp": 0, "coords": {"x": 1, "y": 2}},
                    {"timestamp": 1, "coords": {"x": 7, "y": 8}},
                ],
            }
        ]
    }
    sync_lineup_coords_from_turn(gm, turn)
    assert p.coords == {"x": 7.0, "y": 8.0}
