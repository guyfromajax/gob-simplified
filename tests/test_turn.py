
import pytest
from BackEnd.models.player import Player
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.game_manager import GameManager
from tests.test_utils import build_mock_game_state
# from BackEnd.engine.phase_resolution import resolve_half_court_offense  # or resolve_turn if you've renamed

from BackEnd.constants import POSITION_LIST

# Utility: Create mock Player
def mock_player(first, last, team="Lancaster"):
    base = {
        "first_name": first,
        "last_name": last,
        "team": team,
        "SC": 80, "SH": 80, "ID": 60, "OD": 60,
        "PS": 70, "BH": 70, "RB": 50, "ST": 55,
        "AG": 75, "FT": 80, "ND": 65, "IQ": 90,
        "CH": 85, "EM": 0, "MO": 0
    }
    return Player(base)

def test_assign_roles_outputs_player_objects():
    game_state = build_mock_game_state()
    # Convert MockPlayer objects back to raw dicts
    raw_home = {pos: vars(p) for pos, p in game_state["players"]["Lancaster"].items()}
    raw_away = {pos: vars(p) for pos, p in game_state["players"]["Bentley-Truman"].items()}
    gm = GameManager("Lancaster", "Bentley-Truman", raw_home, raw_away)
    # gm = GameManager("Lancaster", "Bentley-Truman", game_state["players"]["Lancaster"], game_state["players"]["Bentley-Truman"])
    roles = gm.turn_manager.assign_roles("Base")


    assert roles["shooter"] is not None
    assert roles["screener"] is not None
    assert roles["ball_handler"] is not None
    assert hasattr(roles["shooter"], "record_stat")

def test_turn_returns_valid_result():
    game_state = build_mock_game_state()
    
    # Convert MockPlayer objects back to raw dicts
    raw_home = {pos: vars(p) for pos, p in game_state["players"]["Lancaster"].items()}
    raw_away = {pos: vars(p) for pos, p in game_state["players"]["Bentley-Truman"].items()}
    gm = GameManager("Lancaster", "Bentley-Truman", raw_home, raw_away)

    # gm = GameManager("Lancaster", "Bentley-Truman", game_state["players"]["Lancaster"], game_state["players"]["Bentley-Truman"])
    result = gm.simulate_turn()


    assert result['result_type'] in {"SHOT", "TURNOVER", "FOUL", "HCO", "MISS", "BLOCK", "MAKE"}
