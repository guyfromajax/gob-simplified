from BackEnd.models.player import Player
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.models.team_manager import TeamManager

from BackEnd.constants import POSITION_LIST, PLAYCALLS, BOX_SCORE_KEYS
from copy import deepcopy
import random

class GameManager:
    def __init__(self, home_team_name, away_team_name):
        self.home_team = TeamManager(home_team_name)
        self.away_team = TeamManager(away_team_name)

        self.score = {home_team_name: 0, away_team_name: 0}
        self.quarter = 1
        self.turns = []
        
        self.offense_team = self.home_team #vary based on opening tip
        self.defense_team = self.away_team

        self.game_state = self._init_game_state()

        self.turn_manager = TurnManager(self)
        self.shot_manager = ShotManager(self)
        
        # Add counters for function calls
        self.macro_turn_count = 0
        self.micro_turn_count = 0

    
    def _init_game_state(self):
        return {
            "offense_team": self.offense_team.name,
            "defense_team": self.defense_team.name,
            "score": self.score,
            "points_by_quarter": {
                self.home_team.name: self.home_team.points_by_quarter,
                self.away_team.name: self.away_team.points_by_quarter
            },
            "quarter": self.quarter,
            "time_remaining": 480,
            "clock": "8:00",
            "time_elapsed": 0,
            "turns": self.turns,
            "current_playcall": "Outside",
            "defense_playcall": "Zone",
            "offensive_state": "HCO",
            "box_score": {
                self.home_team.name: {},
                self.away_team.name: {}
            }
        }


    def simulate_macro_turn(self): #run_simulation
        # Increment macro turn counter
        self.macro_turn_count += 1
        
        # print("Starting new turn")
        # print(f"offense_team: {self.offense_team}")
        result = self.turn_manager.run_micro_turn()
        self.turns.append(result)
        
        # Update team stats after each turn
        self.update_team_stats()
        
        print("End of simulate_macro_turn")
        print(f"result: {result}")
        
        return result

    def switch_possession(self):
        self.offense_team, self.defense_team = self.defense_team, self.offense_team
        self.game_state["offense_team"] = self.offense_team.name
        self.game_state["defense_team"] = self.defense_team.name
        self.game_state["current_playcall"] = ""
        self.game_state["defense_playcall"] = ""

    def get_box_score(self):
        return {
            team.name: {
                pos: {
                    "name": player.get_name(),
                    **player.stats["game"]
                }
                for pos, player in team.lineup.items()
            }
            for team in [self.home_team, self.away_team]
        }

    def to_dict(self):
        output = deepcopy(self.game_state)
        flat_box_score = []

        for team in [self.home_team, self.away_team]:
            for player in team.players:
                flat_box_score.append({
                    "team": team.name,
                    "name": player.get_name(),
                    "stats": player.stats["game"]
                })

        output["box_score"] = flat_box_score
        output["team_totals"] = {
            self.home_team.name: self.home_team.get_team_game_stats(),
            self.away_team.name: self.away_team.get_team_game_stats()
        }

        return output

    @property
    def home_team_name(self):
        return self.home_team.name

    @property
    def away_team_name(self):
        return self.away_team.name
    
    @property
    def team_totals(self):
        return {
            self.home_team.name: self.home_team.get_team_game_stats(),
            self.away_team.name: self.away_team.get_team_game_stats()
        }

    def print_function_counts(self):
        """Print the number of times each function was called."""
        print(f"=== FUNCTION CALL COUNTS ===")
        print(f"simulate_macro_turn() called: {self.macro_turn_count} times")
        print(f"run_micro_turn() called: {self.micro_turn_count} times")
        print(f"Total turns: {len(self.turns)}")
        print(f"=============================")

    def update_team_stats(self):
        """Calculate and populate team stats by aggregating all player stats."""
        from BackEnd.constants import BOX_SCORE_KEYS
        
        # Initialize team stats dictionaries
        self.home_team.stats = {stat: 0 for stat in BOX_SCORE_KEYS}
        self.away_team.stats = {stat: 0 for stat in BOX_SCORE_KEYS}
        
        # Aggregate home team stats from lineup players
        for player in self.home_team.lineup.values():
            for stat in BOX_SCORE_KEYS:
                self.home_team.stats[stat] += player.stats["game"].get(stat, 0)
        
        # Aggregate away team stats from lineup players
        for player in self.away_team.lineup.values():
            for stat in BOX_SCORE_KEYS:
                self.away_team.stats[stat] += player.stats["game"].get(stat, 0)

    def print_game_statistics(self):
        """Print all game statistics including defense score stats."""
        # Print function call counts
        self.print_function_counts()
        
        # Print defense score statistics
        self.shot_manager.print_defense_score_stats()





