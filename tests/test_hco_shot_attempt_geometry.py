from types import SimpleNamespace

import pytest

from BackEnd.engine.phase_resolution import _freeze_hco_shot_attempt_geometry
from BackEnd.models.shot_manager import _shot_defender_xy
from BackEnd.utils.shot_attempt_geometry import ShotAttemptGeometry, freeze_coord_rows


def _player(pid, x, y):
    return SimpleNamespace(player_id=pid, coords={"x": x, "y": y})


def _game(*, stamped_defense=None):
    shooter = _player("off-pg", 70, 20)
    defender = _player("def-pg", 5, 5)  # deliberately stale
    game = SimpleNamespace(
        offense_team=SimpleNamespace(lineup={"PG": shooter}),
        defense_team=SimpleNamespace(lineup={"PG": defender}),
    )
    skeleton = {
        "steps": [
            {
                "pos_actions": {"PG": {"action": "shoot", "location": "key"}},
                "_step_state": {"defense": stamped_defense or {}},
            }
        ]
    }
    roles = {
        "shooter": shooter,
        "shooter_pos": "PG",
        "shot_spot": {"x": 70, "y": 20},
    }
    return game, skeleton, roles


def test_geometry_value_object_is_frozen_and_looks_up_by_id_or_position():
    geometry = ShotAttemptGeometry(
        source="test",
        shot_step_index=2,
        shooter_id="off-pg",
        shooter_x=70,
        shooter_y=20,
        defenders_by_id=freeze_coord_rows([("def-pg", {"x": 68, "y": 20})]),
        defenders_by_position=freeze_coord_rows([("PG", {"x": 68, "y": 20})]),
    )

    assert geometry.defender_coord(player_id="def-pg") == {"x": 68.0, "y": 20.0}
    assert geometry.defender_coord(position="PG") == {"x": 68.0, "y": 20.0}
    with pytest.raises(AttributeError):
        geometry.source = "changed"


def test_full_sim_geometry_uses_shot_step_state_not_stale_player_coords():
    game, skeleton, roles = _game(stamped_defense={"PG": {"x": 68, "y": 20}})

    geometry = _freeze_hco_shot_attempt_geometry(
        game, skeleton, roles, emitted_sync_succeeded=False
    )

    assert geometry.source == "hco-stepstate-shot-step"
    assert geometry.shot_step_index == 0
    assert geometry.shooter_coord == {"x": 70.0, "y": 20.0}
    assert geometry.defender_coord(player_id="def-pg") == {"x": 68.0, "y": 20.0}
    assert geometry.defender_coord(player_id="def-pg") != game.defense_team.lineup["PG"].coords


def test_animated_geometry_freezes_emitter_synchronized_player_coords():
    game, skeleton, roles = _game()
    game.defense_team.lineup["PG"].coords = {"x": 69, "y": 21}

    geometry = _freeze_hco_shot_attempt_geometry(
        game, skeleton, roles, emitted_sync_succeeded=True
    )
    game.defense_team.lineup["PG"].coords = {"x": 1, "y": 1}

    assert geometry.source == "hco-emitter-shot-step"
    assert geometry.defender_coord(position="PG") == {"x": 69.0, "y": 21.0}


def test_contract_reader_never_falls_back_to_stale_player_coords():
    defender = _player("def-pg", 5, 5)
    lineup = {"PG": defender}
    geometry = ShotAttemptGeometry(
        source="test",
        shot_step_index=0,
        shooter_id="off-pg",
        shooter_x=70,
        shooter_y=20,
    )

    assert _shot_defender_xy(defender, lineup, geometry) is None
    assert _shot_defender_xy(defender, lineup, None) == (5.0, 5.0)
