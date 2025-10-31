from BackEnd.models.player import Player
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.models.team_manager import TeamManager

from BackEnd.constants import POSITION_LIST, PLAYCALLS, BOX_SCORE_KEYS
from copy import deepcopy
import random

from BackEnd.utils.stat_updater import update_game_stats

class GameManager:
    def __init__(self, home_team_name, away_team_name, home_strategy_settings=None, away_strategy_settings=None, home_team_attributes=None, away_team_attributes=None, home_scouting_data=None, away_scouting_data=None):
        self.home_team = TeamManager(home_team_name, is_home_team=True, strategy_settings=home_strategy_settings, team_attributes=home_team_attributes, scouting_data=home_scouting_data)
        self.away_team = TeamManager(away_team_name, is_home_team=False, strategy_settings=away_strategy_settings, team_attributes=away_team_attributes, scouting_data=away_scouting_data)

        # Recalculate position ratings for all players (attributes may have changed)
        self._update_position_ratings()

        self.score = {home_team_name: 0, away_team_name: 0}
        self.quarter = 1
        self.turns = []
        self.text_log = []
        
        # Set default offense/defense teams (will be updated by opening tip)
        self.offense_team = self.home_team
        self.defense_team = self.away_team

        self.game_state = self._init_game_state()

        self.turn_manager = TurnManager(self)
        self.shot_manager = ShotManager(self)

        # Add counters for function calls
        self.macro_turn_count = 0
        self.micro_turn_count = 0

        # optional database identifier for live games
        self.game_id: str | None = None

    def _update_position_ratings(self):
        """Recalculate position ratings for all players based on current attributes."""
        from BackEnd.utils.position_ratings import compute_position_ratings
        from BackEnd.db import players_collection
        
        for team in [self.home_team, self.away_team]:
            for player in team.get_all_players():
                # Convert player object to dict for rating calculation
                player_dict = {
                    "attributes": player.attributes,
                    "height": player.height,
                    "name": player.name
                }
                
                # Recalculate ratings
                new_ratings = compute_position_ratings(player_dict)
                
                # Update player object
                player.ratings = new_ratings
                
                # Update database
                if hasattr(player, 'player_id') and player.player_id:
                    players_collection.update_one(
                        {"_id": player.player_id},
                        {"$set": {"position_ratings": new_ratings}}
                    )
    
    def setup_opening_tip(self):
        """Execute opening tip logic and update offense/defense teams."""
        from BackEnd.utils.opening_tip import execute_opening_tip
        
        offense_team, defense_team, turn_result = execute_opening_tip(self)
        
        # Update offense/defense teams
        self.offense_team = offense_team
        self.defense_team = defense_team
        
        # Update game_state to reflect the correct teams
        self.game_state["offense_team"] = offense_team.name
        self.game_state["defense_team"] = defense_team.name
        
        print(f"Opening tip winner: {offense_team.name}")

    
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
            "team_fouls": {
                self.home_team.name: 0,
                self.away_team.name: 0,
            },
            "box_score": {
                self.home_team.name: {},
                self.away_team.name: {}
            },
            "shooter": None,
            "free_throws": 0,
            "free_throws_remaining": 0,
            "one_and_one": False,
            "last_ball_handler": None,
            "foul_team": None,
            "foul_type": None,
            "foul_player": None,
            "last_ball_handler": None,
            "last_rebounder": None,
            "last_rebound": None,
            "last_stealer": None,
            "last_turnover_player": None
        }


    def simulate_macro_turn(self): #run_simulation
        # Increment macro turn counter
        self.macro_turn_count += 1
        
        # print("Starting new turn")
        # print(f"offense_team: {self.offense_team}")
        result = self.turn_manager.run_micro_turn()
        self.turns.append(result)
        self.text_log.append(result["text"])

        # If the turn ended with an offensive rebound, create a separate OREB turn
        if self.game_state.get("pending_oreb"):
            print(f"📦 OREB detected - creating separate OREB turn")
            oreb_turn = self.turn_manager.resolve_offensive_rebound_turn()
            if oreb_turn:
                print(f"📦 OREB turn created: {oreb_turn.get('result_type')} - {oreb_turn.get('text')}")
                self.turns.append(oreb_turn)
                self.text_log.append(oreb_turn["text"])
                
                # Handle possession flip for OREB turn (doesn't go through run_micro_turn)
                if oreb_turn.get("possession_flips"):
                    print(f"📦 OREB turn flipping possession")
                    self.switch_possession()
                
                # Clear the pending OREB
                self.game_state["pending_oreb"] = None
                
                # If OREB turn also resulted in another OREB, it will have set pending_oreb again
                # The next simulate_macro_turn will handle it (recursive OREBs)
            else:
                print(f"⚠️ OREB turn returned None!")

        # If the turn ended with a dead-ball turnover or a non-shooting foul
        # that does not result in free throws, prepare a sideline inbound
        # sequence and append its payload so the front end can animate it.
        if (
            (result.get("result_type") == "FOUL" and self.game_state.get("free_throws_remaining", 0) == 0)
            or result.get("result_type") == "DEAD BALL"
        ):
            inbound_payload = self.turn_manager.setup_side_inbound()
            self.turns.append(inbound_payload)
            # Reset offensive state to HCO after side inbound (FCP/HCT only apply after made shots)
            self.game_state["offensive_state"] = "HCO"

        # Update team stats after each turn
        self.update_team_stats()

        # Log steal-to-score sequences if applicable
        self._log_steal_to_points(result)

        # Persist incremental stats for active games
        deltas = result.get("deltas")
        if self.game_id and deltas:
            update_game_stats(self.game_id, deltas, dict(self.score))

        # print("End of simulate_macro_turn")
        # print(f"result: {result}")

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

    def _find_player_by_name(self, name):
        for team in [self.home_team, self.away_team]:
            for player in team.get_all_players():
                if player.get_name() == name:
                    return player
        return None

    def _log_steal_to_points(self, result):
        last_stealer = self.game_state.get("last_stealer")
        points = result.get("points")
        scoring_team = result.get("scoring_team")
        if last_stealer and points and scoring_team == getattr(last_stealer, "team", None):
            scorer = self._find_player_by_name(result.get("shooter"))
            turnover_player = self.game_state.get("last_turnover_player")
            team_tot_after = self.score.get(scoring_team, 0)
            scorer_pts_after = scorer.stats["game"].get("PTS", 0) if scorer else 0
            stealer_stl_after = last_stealer.stats["game"].get("STL", 0)
            to_player_to_after = turnover_player.stats["game"].get("TO", 0) if turnover_player else 0
            log_line = f"{result.get('turn_count')}, {result.get('result_type')}, {getattr(scorer, 'player_id', '')}, {points}, {last_stealer.player_id}, {getattr(turnover_player, 'player_id', '')}, {team_tot_after}, {scorer_pts_after}, {stealer_stl_after}, {to_player_to_after}"
            print(log_line)
            self.game_state["last_stealer"] = None
            self.game_state["last_turnover_player"] = None

    def print_function_counts(self):
        """Print the number of times each function was called."""
        print(f"=== FUNCTION CALL COUNTS ===")
        print(f"simulate_macro_turn() called: {self.macro_turn_count} times")
        print(f"run_micro_turn() called: {self.micro_turn_count} times")
        print(f"Total turns: {len(self.turns)}")
        print(f"=============================")

    def update_team_stats(self):
        """Update team totals based on all rostered players."""
        # Delegate aggregation to each team, which sums over all players
        self.home_team.update_team_stats()
        self.away_team.update_team_stats()

    def print_game_statistics(self):
        """Print all game statistics including defense score stats."""
        # Print function call counts
        self.print_function_counts()
        
        # Print defense score statistics
        self.shot_manager.print_defense_score_stats()





