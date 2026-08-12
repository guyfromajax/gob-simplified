from BackEnd.models.game_manager import GameManager
from BackEnd.models.turn_manager import TurnManager

from BackEnd.constants import BOX_SCORE_KEYS, POSITION_LIST

class MockPlayer:
    def __init__(self, player_dict):
        self.first_name = player_dict["first_name"]
        self.last_name = player_dict["last_name"]
        self.name = f"{self.first_name} {self.last_name}"
        self.attributes = {
            k: v for k, v in player_dict.items()
            if k not in {"first_name", "last_name", "team", "height"}
        }
        # Match Player._init_stats so simulation tests exercise the real stats
        # contract instead of failing when active code increments a known key.
        self.stats = {
            "game": {stat: 0 for stat in BOX_SCORE_KEYS},
            "season": {stat: 0 for stat in BOX_SCORE_KEYS},
            "career": {stat: 0 for stat in BOX_SCORE_KEYS},
        }
        for level in ("game", "season", "career"):
            self.stats[level]["Outlet_Score_List"] = []
        self.stats["game"]["Shot_Result_List"] = []
        self.team = player_dict["team"]
        self.height = player_dict.get("height", 78)  # Default 6'6" (78 inches)
        self.jersey = player_dict.get("jersey", 0)  # Default jersey number
        self.player_id = player_dict.get("player_id", None)  # Player ID for database operations
        

    def record_stat(self, stat, amount=1):
        self.stats["game"][stat] = self.stats["game"].get(stat, 0) + amount

        # Add PTS calculation like in the real Player class
        if stat in {"FGM", "3PTM", "FTM"}:
            s = self.stats["game"]
            s["PTS"] = (2 * s.get("FGM", 0)) + s.get("3PTM", 0) + s.get("FTM", 0)
        elif stat in ["OREB", "DREB"]:
            s = self.stats["game"]
            s["REB"] = s.get("OREB", 0) + s.get("DREB", 0)

    def get_stat(self, stat, level="game"):
        """Get a stat value, matching Player.get_stat interface."""
        return self.stats.get(level, {}).get(stat, 0)

    def record_shot_result(self, made):
        """Record shot result, matching Player.record_shot_result interface."""
        self.Shot_Result_List = getattr(self, "Shot_Result_List", [])
        self.Shot_Result_List.append(bool(made))

    def add_momentum(self, delta):
        """Apply momentum delta, matching Player.add_momentum interface."""
        current = self.attributes.get("MO", 0)
        self.attributes["MO"] = max(0, min(10, current + delta))

    def get_name(self):
        return self.name


def build_mock_game():
    home_team = "Lancaster"
    away_team = "Bentley-Truman"
    mock_player_template = {
        "first_name": "Test", "last_name": "Player",
        "SC": 5, "SH": 5, "ID": 8, "OD": 3,
        "PS": 8, "BH": 9, "RB": 1, "AG": 4,
        "ST": 9, "ND": 3, "IQ": 1, "FT": 4, "CH": 5,
        
        # ⚡ Energy-related fields
        "NG": 1.0,  # Full energy

        # 🔒 Anchor attributes (baseline values)
        "anchor_SC": 5, "anchor_SH": 5, "anchor_ID": 8, "anchor_OD": 3,
        "anchor_PS": 8, "anchor_BH": 9, "anchor_RB": 1, "anchor_AG": 4,
        "anchor_ST": 9, "anchor_ND": 3, "anchor_IQ": 1, "anchor_FT": 4, "anchor_CH": 5
    }


    def build_lineup(team_name):
        return {
            pos: MockPlayer({**mock_player_template, "first_name": f"{team_name} {pos}", "team": team_name})
            for pos in POSITION_LIST
        }

    game = GameManager(home_team, away_team)
    game.home_team.lineup = build_lineup(home_team)
    game.away_team.lineup = build_lineup(away_team)

    # ✅ Rebuild TurnManager with updated lineups
    game.turn_manager = TurnManager(game)

    game.offense_team = game.home_team
    game.defense_team = game.away_team
    game.game_state["current_playcall"] = "Base"
    game.game_state["defense_playcall"] = "Man"
    game.turn_manager.set_strategy_calls()

    default_team_attrs = {
        "shot_threshold": 100,
        "turnover_modifier": -200,
        "foul_modifier": 70,
        "rebound_modifier": 1.0,
        "momentum_score": 10,
        "offensive_efficiency": 5,
        "team_chemistry": 15,
        "defensive_efficiency": 0,
        "fb_efficiency": 0,
        "pt_efficiency": 0,
        "fb_opp_modifier": 0,
        "pt_opp_modifier": 0
    }

    game.home_team.team_attributes = default_team_attrs.copy()
    game.away_team.team_attributes = default_team_attrs.copy()

    game.home_team.strategy_settings = {
        "defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2
    }
    game.away_team.strategy_settings = {
        "defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2
    }

    return game
