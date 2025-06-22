from BackEnd.models.player import Player
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.constants import POSITION_LIST
from copy import deepcopy
import random

class GameManager:
    def __init__(self, home_team, away_team, home_players, away_players):
        self.home_team = home_team
        self.away_team = away_team
        self.scouting_data = self.initialize_scouting_data(home_team, away_team)

        self.players = {
            home_team: {pos: Player(p) for pos, p in home_players.items()},
            away_team: {pos: Player(p) for pos, p in away_players.items()}
        }

        self.score = {home_team: 0, away_team: 0}
        self.points_by_quarter = {home_team: [0, 0, 0, 0], away_team: [0, 0, 0, 0]}
        self.quarter = 1
        self.clock = "8:00"
        self.turns = []
        self.offense_team = home_team
        self.defense_team = away_team

        self.game_state = self._init_game_state()

        self.turn_manager = TurnManager(self)
        self.shot_manager = ShotManager(self.game_state)

    @staticmethod
    def initialize_team_attributes(home_team, away_team):
        settings = {}
        for team in [home_team, away_team]:
            settings[team] = {
                "shot_threshold": random.randint(150, 250),
                "ft_shot_threshold": random.randint(150, 250),
                "turnover_threshold": random.randint(-250, -150),
                "foul_threshold": random.randint(40, 90),
                "rebound_modifier": random.choice([0.8, 0.9, 1.0, 1.1, 1.2]),
                "momentum_score": random.randint(0, 20),
                "momentum_delta": random.choice([1, 2, 3, 4, 5]),
                "offensive_efficiency": random.randint(1, 10),
                "offensive_adjust": random.randint(1, 10),
                "o_tendency_reads": random.randint(1, 10),
                "d_tendency_reads": random.randint(1, 10),
                "team_chemistry": random.randint(7, 25),
            }
        return settings
    
    @staticmethod
    def initialize_strategy_calls(home_team, away_team):
        calls = ["offense_playcall", "defense_playcall", "tempo_call", "aggression_call"]
        settings = {
            home_team: {call: "" for call in calls},
            away_team: {call: "" for call in calls},
        }
        return settings

    @staticmethod
    def initialize_strategy_settings(home_team, away_team):
        strategies = ["defense", "tempo", "aggression", "fast_break"]
        settings = {}

        for team in [home_team, away_team]:
            team_settings = {s: random.randint(0, 4) for s in strategies}
            team_settings["half_court_trap"] = 0
            team_settings["full_court_press"] = 0
            settings[team] = team_settings

        return settings
    
    @staticmethod
    def initialize_scouting_data(home_team, away_team):
        playcalls = ["Base", "Freelance", "Inside", "Attack", "Outside", "Set"]

        return {
            team: {
                "offense": {
                    "Fast_Break_Entries": 0,
                    "Fast_Break_Success": 0,
                    "Playcalls": {call: {"used": 0, "success": 0} for call in playcalls},
                },
                "defense": {
                    "Man": {"used": 0, "success": 0},
                    "Zone": {"used": 0, "success": 0},
                    "vs_Fast_Break": {"used": 0, "success": 0},
                }
            }
            for team in [home_team, away_team]
        }
    
    def _init_game_state(self):
        return {
            "players": self.players,
            "offense_team": self.offense_team,
            "defense_team": self.defense_team,
            "score": self.score,
            "points_by_quarter": self.points_by_quarter,
            "quarter": self.quarter,
            "clock": self.clock,
            "turns": self.turns,
            "scouting_data": self.scouting_data,
            "strategy_calls": self.initialize_strategy_calls(self.home_team, self.away_team),
            "strategy_settings": self.initialize_strategy_settings(self.home_team, self.away_team),
            "team_attributes": self.initialize_team_attributes(self.home_team, self.away_team),
            "offensive_state": {
                "pass_count": 0,
                "initial_possession_player": None
            },
            "box_score": {
                self.home_team: {},
                self.away_team: {}
            }
        }

    def simulate_turn(self):
        result = self.turn_manager.run_turn()
        self.turns.append(result)
        self._switch_possession()
        return result

    def _switch_possession(self):
        self.game_state["offense_team"], self.game_state["defense_team"] = (
            self.game_state["defense_team"], self.game_state["offense_team"]
        )

    def get_box_score(self):
        return {
            team: {
                pos: self.players[team][pos].stats["game"] for pos in POSITION_LIST
            } for team in [self.home_team, self.away_team]
        }

    def to_dict(self):
        return deepcopy(self.game_state)
