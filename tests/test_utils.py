# tests/test_utils.py
class MockPlayer:
    def __init__(self, player_dict):
        self.first_name = player_dict["first_name"]
        self.last_name = player_dict["last_name"]
        self.name = f"{self.first_name} {self.last_name}"
        self.attributes = {k: v for k, v in player_dict.items() if k not in {"first_name", "last_name", "team"}}
        self.stats = {"game": {}}
        self.team = player_dict["team"]

    def record_stat(self, stat):
        self.stats["game"][stat] = self.stats["game"].get(stat, 0) + 1

def build_mock_game_state():
    game_state = {
        "players": {
            "Lancaster": {
                "PG": {"first_name": "Ervin", "last_name": "Miller", "team": "Lancaster", "SC": 5, "SH": 5, "ID": 8, "OD": 3,
                       "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
                "SG": {"first_name": "Norris", "last_name": "Khan", "team": "Lancaster", "SC": 5, "SH": 5, "ID": 8, "OD": 3,
                       "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
                "SF": {"first_name": "Wilbert", "last_name": "Struthers", "team": "Lancaster", "SC": 5, "SH": 5, "ID": 8, "OD": 3,
                       "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
                "PF": {"first_name": "Damom", "last_name": "Martin", "team": "Lancaster", "SC": 5, "SH": 5, "ID": 8, "OD": 3,
                       "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
                "C": {"first_name": "Roger", "last_name": "Henrich", "team": "Lancaster", "SC": 5, "SH": 5, "ID": 8, "OD": 3,
                      "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5}},
            "Bentley-Truman": {
                "PG": {"first_name": "Xenon", "last_name": "Fletcher", "team": "Bentley-Truman", "SC": 5, "SH": 5, "ID": 8, "OD": 3,
                       "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
                "SG": {"first_name": "Trent", "last_name": "Athens", "team": "Bentley-Truman", "SC": 5, "SH": 5, "ID": 8, "OD": 3,
                       "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
                "SF": {"first_name": "Clint", "last_name": "Workman", "team": "Bentley-Truman", "SC": 5, "SH": 5, "ID": 8, "OD": 3,
                       "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
                "PF": {"first_name": "CJ", "last_name": "Castleman", "team": "Bentley-Truman", "SC": 5, "SH": 5, "ID": 8, "OD": 3,
                       "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5},
                "C": {"first_name": "Kermit", "last_name": "Prospect", "team": "Bentley-Truman", "SC": 5, "SH": 5, "ID": 8, "OD": 3,
                      "PS": 8, "BH": 9, "RB": 1, "AG": 4, "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "EM": 8, "CH": 5}
            }},
        "offense_team": "Lancaster",
        "defense_team": "Bentley-Truman",
        "offensive_state": "HALF_COURT",
        "offense_playcall": "Base",
        "defense_playcall": "Man",
        "current_playcall": "Base",
        "strategy_calls": {
            "Lancaster": {"defense_playcall": "Man", "tempo_call": "normal", "aggression_call": "normal"},
            "Bentley-Truman": {"defense_playcall": "Man", "tempo_call": "normal", "aggression_call": "normal"}
        },
        "strategy_settings": {
            "Lancaster": {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2},
            "Bentley-Truman": {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2}
        },
        "score": {"Lancaster": 0, "Bentley-Truman": 0},
        "team_attributes": {
            "Lancaster": {"shot_threshold": 100, "rebound_modifier": 1.0},
            "Bentley-Truman": {"rebound_modifier": 1.0}
        },
        "quarter": 1,
        "points_by_quarter": {"Lancaster": [0, 0, 0, 0], "Bentley-Truman": [0, 0, 0, 0]},
        "team_fouls": {"Lancaster": 0, "Bentley-Truman": 0},
        "clock": 600,
        "box_score": {"Lancaster": {}, "Bentley-Truman": {}},
        "game_log": [],
        "playcall_weights": {},
        "playcall_tracker": {},
        "defense_playcall_tracker": {},
        "scouting_data": {},
        "free_throws": 0,
        "free_throws_remaining": 0,
        "last_ball_handler": None,
        "bonus_active": False
    }

        # Wrap all player dicts with MockPlayer
    for team in game_state["players"]:
        for pos in game_state["players"][team]:
            game_state["players"][team][pos] = MockPlayer(game_state["players"][team][pos])
    
    return game_state


