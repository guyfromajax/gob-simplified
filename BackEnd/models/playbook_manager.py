import random
from BackEnd.constants import STRATEGY_CALL_DICTS
from BackEnd.utils.shared import weighted_random_from_dict

class PlaybookManager:
    def __init__(self, scouting_data, team_name):
        self.scouting = scouting_data[team_name]
        self.playcalls = self.scouting.get("playcalls", {})
        self.fast_break_tendency = self.scouting.get("fast_break_tendency", 0.0)

    def get_offensive_playcall(self):
        return self.playcalls.get("offense", "Base")

    def get_defensive_playcall(self):
        return self.playcalls.get("defense", "Man")

    def get_fast_break_tendency(self):
        return self.fast_break_tendency
    
    def get_playcalls(self, game_state):
        off_team = game_state["offense_team"]
        def_team = game_state["defense_team"]

        # OFFENSIVE PLAYCALL
        off_weights = game_state["playcall_weights"][off_team]
        chosen_playcall = weighted_random_from_dict(off_weights)

        # DEFENSIVE PLAYCALL
        def_setting = game_state["strategy_settings"][def_team]["defense"]
        defense_options = STRATEGY_CALL_DICTS["defense"].get(def_setting, ["Man"])
        chosen_defense = random.choice(defense_options)

        # Track usage
        game_state["playcall_tracker"][off_team][chosen_playcall] += 1
        game_state["defense_playcall_tracker"][def_team][chosen_defense] += 1

        return {
            "offense": chosen_playcall,
            "defense": chosen_defense
        }
