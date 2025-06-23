import random
from tests.test_utils import build_mock_game_state

# Mock player class for use in tests
class MockPlayer:
    def __init__(self, name, attributes):
        self.name = name               
        self.attributes = attributes
        self.stats = {"game": {}}

    def record_stat(self, stat):
        self.stats["game"][stat] = self.stats["game"].get(stat, 0) + 1

# Test: ShotManager.resolve_shot
def test_resolve_shot_basic():
    from BackEnd.models.shot_manager import ShotManager

    game_state = build_mock_game_state()

    shot_manager = ShotManager(game_state)
    roles = {
        "shooter": game_state["players"]["Lancaster"]["PG"],
        "screener": game_state["players"]["Lancaster"]["SG"],
        "passer": game_state["players"]["Lancaster"]["SF"],
        "defender": game_state["players"]["Bentley-Truman"]["PG"]
    }

    result = shot_manager.resolve_shot(roles)
    assert "result_type" in result
    assert result["result_type"] in ["MAKE", "MISS"]


# Test: phase_resolution.resolve_fast_break_logic
def test_resolve_fast_break_logic_runs():
    from BackEnd.models.shot_manager import ShotManager
    from BackEnd.engine.phase_resolution import resolve_fast_break_logic

    home_team = "Lancaster"
    away_team = "Bentley-Truman"

    game_state = build_mock_game_state()


    fb_roles = {
        "offense": ["SG", "SF"],
        "defense": [
            game_state["players"]["Bentley-Truman"]["SF"],
            game_state["players"]["Bentley-Truman"]["PF"]
        ],
        "ball_handler": game_state["players"]["Lancaster"]["PG"],
        "outlet_passer": game_state["players"]["Lancaster"]["C"],
        "shooter": game_state["players"]["Lancaster"]["SF"],  # ✅ add this
        "passer": game_state["players"]["Lancaster"]["PG"],
        "screener": None
    }

    shot_manager = ShotManager(game_state)
    result = shot_manager.resolve_fast_break_shot(fb_roles)

    assert "result_type" in result
    assert result["result_type"] in ["MAKE", "MISS", "FOUL", "TURNOVER"]


# Test: TurnManager.assign_roles
def test_assign_roles_outputs_roles_dict():
    from BackEnd.models.turn_manager import TurnManager
    from BackEnd.models.game_manager import GameManager

    home_team = "Lancaster"
    away_team = "Bentley-Truman"

    players = {
        "Lancaster": {
            "PG": {"first_name": "Ervin", "last_name": "Miller", "team": home_team, "SC": 5, "SH": 5, "ID": 8, "OD": 3, 
                    "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
            "SG": {"first_name": "Norris", "last_name": "Khan", "team": home_team, "SC": 5, "SH": 5, "ID": 8, "OD": 3, 
                    "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
            "SF": {"first_name": "Wilbert", "last_name": "Struthers", "team": home_team, "SC": 5, "SH": 5, "ID": 8, "OD": 3, 
                    "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
            "PF": {"first_name": "Damom", "last_name": "Martin", "team": home_team, "SC": 5, "SH": 5, "ID": 8, "OD": 3, 
                    "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
            "C": {"first_name": "Roger", "last_name": "Henrich", "team": home_team, "SC": 5, "SH": 5, "ID": 8, "OD": 3, 
                    "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5}},
        "Bentley-Truman": {
            "PG": {"first_name": "Xenon", "last_name": "Fletcher", "team": away_team, "SC": 5, "SH": 5, "ID": 8, "OD": 3, 
                    "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
            "SG": {"first_name": "Trent", "last_name": "Athens", "team": away_team, "SC": 5, "SH": 5, "ID": 8, "OD": 3, 
                    "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
            "SF": {"first_name": "Clint", "last_name": "Workman", "team": away_team, "SC": 5, "SH": 5, "ID": 8, "OD": 3, 
                    "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
            "PF": {"first_name": "CJ", "last_name": "Castleman", "team": away_team, "SC": 5, "SH": 5, "ID": 8, "OD": 3, 
                    "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},   
            "C": {"first_name": "Kermit", "last_name": "Prospect", "team": away_team, "SC": 5, "SH": 5, "ID": 8, "OD": 3, 
                    "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5}}}

    gm = GameManager(home_team, away_team, players[home_team], players[away_team])
    gm.game_state["current_playcall"] = "Base"
    gm.game_state["defense_playcall"] = "Man"
    roles = gm.turn_manager.assign_roles("Base")
    assert isinstance(roles, dict)
    assert "shooter" in roles
    assert "pass_chain" in roles
    assert "defender" in roles
