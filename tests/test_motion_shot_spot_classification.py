"""Dynamic HCO 2PT/3PT classification: coord-based shoot steps must drive
``roles["shot_spot"]`` from their exact final coords (not a defaulted "key"),
and explicit coords are display-oriented so they are used verbatim — never
re-mirrored for away offense. Named-spot steps keep the legacy lookup + mirror.
"""
import types

from BackEnd.engine.phase_resolution import set_shooter_coords_from_skeleton_last_step
from BackEnd.utils.shot_geometry import is_three_point_shot_from_coords
from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.utils.shared import get_away_player_coords


class _Shooter:
    def __init__(self):
        self.coords = None


def _game(is_away_offense):
    off = types.SimpleNamespace(team_id=("AWAY" if is_away_offense else "HOME"), lineup={})
    deff = types.SimpleNamespace(team_id="DEF", lineup={})
    away = types.SimpleNamespace(team_id="AWAY")
    return types.SimpleNamespace(offense_team=off, defense_team=deff, away_team=away)


def _roles():
    return {"shooter": _Shooter(), "shooter_pos": "PG"}


def _skeleton(shoot_action):
    return {"steps": [
        {"pos_actions": {"PG": {"action": "handle_ball", "location": "key"}}},
        {"pos_actions": {"PG": dict(shoot_action, action="shoot")},
         "events": [{"type": "shot", "by": "PG"}]},
    ]}


# --- coord-based (Freelance-style) shoot steps -------------------------------

def test_coord_based_beyond_arc_registers_three():
    game, roles = _game(is_away_offense=False), _roles()
    coords = {"x": 50.0, "y": 25.0}  # display-oriented, behind the home arc
    set_shooter_coords_from_skeleton_last_step(game, _skeleton({"coords": coords}), roles)
    assert roles["shot_spot"] == coords           # exact coords, not "key"
    assert roles["shooter"].coords == coords
    assert is_three_point_shot_from_coords(roles["shot_spot"], is_away_offense=False) is True


def test_coord_based_inside_arc_registers_two():
    game, roles = _game(is_away_offense=False), _roles()
    coords = {"x": 85.0, "y": 25.0}  # near the home basket
    set_shooter_coords_from_skeleton_last_step(game, _skeleton({"coords": coords}), roles)
    assert roles["shot_spot"] == coords
    assert is_three_point_shot_from_coords(roles["shot_spot"], is_away_offense=False) is False


def test_coord_based_away_used_verbatim_not_remirrored():
    game, roles = _game(is_away_offense=True), _roles()
    coords = {"x": 36.0, "y": 25.0}  # already display-oriented for away
    set_shooter_coords_from_skeleton_last_step(game, _skeleton({"coords": coords}), roles)
    assert roles["shot_spot"] == coords  # verbatim — NOT get_away_player_coords(coords)
    assert is_three_point_shot_from_coords(roles["shot_spot"], is_away_offense=True) is True


# --- named-spot fallback (unchanged behavior) --------------------------------

def test_named_spot_fallback_home():
    game, roles = _game(is_away_offense=False), _roles()
    set_shooter_coords_from_skeleton_last_step(game, _skeleton({"location": "upper wing"}), roles)
    assert roles["shot_spot"] == HCO_STRING_SPOTS["upper wing"]
    assert is_three_point_shot_from_coords(roles["shot_spot"], is_away_offense=False) is True


def test_named_spot_fallback_away_is_mirrored():
    game, roles = _game(is_away_offense=True), _roles()
    set_shooter_coords_from_skeleton_last_step(game, _skeleton({"location": "upper wing"}), roles)
    assert roles["shot_spot"] == get_away_player_coords(HCO_STRING_SPOTS["upper wing"])
