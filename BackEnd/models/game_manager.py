from BackEnd.models.player import Player
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.constants import POSITION_LIST
from copy import deepcopy

class GameManager:
    def __init__(self, home_team, away_team, home_players, away_players, scouting_data):
        self.home_team = home_team
        self.away_team = away_team
        self.scouting_data = scouting_data

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
            "strategy_calls": {
                self.home_team: {"tempo_call": "normal", "aggression_call": "normal"},
                self.away_team: {"tempo_call": "normal", "aggression_call": "normal"}
            },
            "team_attributes": {
                self.home_team: {"momentum": 0, "fatigue": 0, "bonus": False},
                self.away_team: {"momentum": 0, "fatigue": 0, "bonus": False}
            },
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
