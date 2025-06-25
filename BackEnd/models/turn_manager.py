from BackEnd.models.logger import Logger
from BackEnd.models.rebound_manager import ReboundManager
from BackEnd.models.playbook_manager import PlaybookManager
from BackEnd.models.animation_manager import AnimationManager
import random
import json
from BackEnd.db import players_collection, teams_collection
from BackEnd.models.player import Player
# from BackEnd.models.game_manager import GameManager
from BackEnd.constants import PLAYCALL_ATTRIBUTE_WEIGHTS, POSITION_LIST, STRATEGY_CALL_DICTS, TEMPO_PASS_DICT, MALLEABLE_ATTRS
from BackEnd.utils.shared import (
    weighted_random_from_dict, 
    generate_pass_chain, 
    get_team_thresholds, 
    get_random_positions,
    get_name_safe
)
from BackEnd.engine.phase_resolution import (
    resolve_fast_break_logic, 
    resolve_free_throw_logic, 
    resolve_turnover_logic, 
    calculate_foul_turnover
)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from BackEnd.models.game_manager import GameManager

class TurnManager:
    def __init__(self, game_manager: "GameManager"):
        self.game = game_manager
        self.logger = Logger()
        self.rebound_manager = ReboundManager(self.game.game_state)
        self.playbook_manager = PlaybookManager(
            self.game.scouting_data, 
            self.game.game_state["offense_team"]
        )
        self.animator = AnimationManager()

    def run_turn(self):
        # STEP 1: Set strategy calls (tempo + aggression)
        self.set_strategy_calls()

        # STEP 2: Set playcalls (offense + defense)
        calls = self.set_playcalls()
        self.game.game_state["current_playcall"] = calls["offense"]
        self.game.game_state["defense_playcall"] = calls["defense"]

        # STEP 3: Route based on offensive state
        state = self.game.game_state["offensive_state"]
        if state == "FREE_THROW":
            result = self.resolve_free_throw()
        elif state == "FAST_BREAK":
            result = self.resolve_fast_break()
        else:
            result = self.resolve_half_court_offense()

        # STEP 4: Final updates (clock, logs, animation)
        self.update_clock_and_possession(result)
        self.logger.log_turn_result(result)
        self.animator.capture(result)

        print("🔁 End of run_turn")
        print(f"next_turn offense: {self.game.game_state['offense_team']}")
        print(f"{self.game.game_state['score']}")
        print(f"{self.game.game_state['clock']}")
        return result


    def set_playcalls(self):    
        off_team = self.game.game_state["offense_team"]
        def_team = self.game.game_state["defense_team"]

        # OFFENSIVE PLAYCALL
        off_weights = self.game.game_state["playcall_weights"][off_team]
        chosen_playcall = weighted_random_from_dict(off_weights)

        # DEFENSIVE PLAYCALL
        def_setting = self.game.game_state["strategy_settings"][def_team]["defense"]
        defense_options = STRATEGY_CALL_DICTS["defense"].get(def_setting, ["Man"])
        chosen_defense = random.choice(defense_options)

        # Track usage
        self.game.game_state["playcall_tracker"][off_team][chosen_playcall] += 1
        self.game.game_state["defense_playcall_tracker"][def_team][chosen_defense] += 1

        return {
            "offense": chosen_playcall,
            "defense": chosen_defense
        }

    # Inside TurnManager class
    def set_strategy_calls(self):
        game_state = self.game.game_state
        off_team = game_state["offense_team"]
        def_team = game_state["defense_team"]

        tempo_setting = game_state["strategy_settings"][off_team]["tempo"]
        aggression_setting = game_state["strategy_settings"][def_team]["aggression"]

        game_state["strategy_calls"][off_team]["tempo_call"] = random.choice(STRATEGY_CALL_DICTS["tempo"][tempo_setting])
        game_state["strategy_calls"][def_team]["aggression_call"] = random.choice(STRATEGY_CALL_DICTS["aggression"][aggression_setting])

    
    def resolve_half_court_offense(self):
        from BackEnd.engine.phase_resolution import resolve_half_court_offense_logic
        return resolve_half_court_offense_logic(self.game)


    def resolve_fast_break(self):
        return resolve_fast_break_logic(self.game) 

    def resolve_free_throw(self):
        return resolve_free_throw_logic(self.game.game_state)
    
    def resolve_turnover(self):
        return resolve_turnover_logic(self.game.game_state)

    def update_clock_and_possession(self, result):
        # 🕒 Reduce clock by time_elapsed
        time_elapsed = result.get("time_elapsed", 0)
        self.game.game_state["time_remaining"] -= time_elapsed

        # Clamp to 0
        if self.game.game_state["time_remaining"] < 0:
            self.game.game_state["time_remaining"] = 0

        # Convert to clock display (e.g., 400 → "6:40")
        minutes = self.game.game_state["time_remaining"] // 60
        seconds = self.game.game_state["time_remaining"] % 60
        self.game.game_state["clock"] = f"{minutes}:{seconds:02d}"

        # 🔁 Flip possession if flagged
        if result.get("possession_flips"):
            self.game._switch_possession()

    def assign_roles(self, playcall):
        
        off_team = self.game.game_state["offense_team"]
        def_team = self.game.game_state["defense_team"]
        players = self.game.game_state["players"][off_team]

        # Compute shot weights using attributes embedded in each player object
        print(f"inside assign_roles playcall: {playcall}")
        weights_dict = PLAYCALL_ATTRIBUTE_WEIGHTS.get("Attack" if playcall == "Set" else playcall, {})
        print(f"inside assign_roles weights_dict: {weights_dict}")

        shot_weights = {
            pos: sum(
                players[pos].attributes[attr] * weight
                for attr, weight in weights_dict.items()
            )
            for pos in players
        }
        print(f"inside assign_roles shot_weights: {shot_weights}")

        shooter_pos = weighted_random_from_dict(shot_weights)
        print(f"inside assign_roles shooter_pos: {shooter_pos}")

        # Compute screener weights (excluding the shooter)
        screen_weights = {
            pos: (
                players[pos].attributes["ST"] * 6 +
                players[pos].attributes["AG"] * 2 +
                players[pos].attributes["IQ"] * 1 +
                players[pos].attributes["CH"] * 1
            )
            for pos in players if pos != shooter_pos
        }

        screener_pos = max(screen_weights, key=screen_weights.get)
        if screener_pos == shooter_pos:
            screener_pos = ""

        # Pass chain and passer
        pass_chain = generate_pass_chain(self.game.game_state, shooter_pos)
        passer_pos = pass_chain[-2] if len(pass_chain) >= 2 else ""
        if passer_pos == shooter_pos or passer_pos == screener_pos:
            passer_pos = ""

        if self.game.game_state["defense_playcall"] == "Zone":
            defender_pos = random.choice(POSITION_LIST)
        else:
            defender_pos = shooter_pos

        shooter = self.game.game_state["players"][off_team][shooter_pos]
        screener = self.game.game_state["players"][off_team][screener_pos]
        passer = self.game.game_state["players"][off_team][passer_pos] if passer_pos else None
        defender = self.game.game_state["players"][def_team][defender_pos]

        print("end of assign_roles")
        print(f"shooter: {get_name_safe(shooter)}")
        print(f"screener: {get_name_safe(screener)}")
        print(f"passer: {get_name_safe(passer)}")
        print(f"defender: {get_name_safe(defender)}")

        
        return {
            "shooter": shooter,
            "screener": screener,
            "ball_handler": shooter,
            "passer": passer,
            "pass_chain": pass_chain,
            "defender": defender
        }
    
    def determine_event_type(self, roles):
        game_state = self.game.game_state
        # Base weights (can be tuned later)
        off_team = game_state["offense_team"]
        def_team = game_state["defense_team"]
        thresholds = get_team_thresholds(game_state)
        tempo_call = game_state["strategy_calls"][off_team]["tempo_call"]
        pass_count = TEMPO_PASS_DICT[tempo_call]
        positions = get_random_positions(pass_count)
        event_type = calculate_foul_turnover(game_state, positions, thresholds, roles)
    
        #determine number of turnover RNGs based on defense team'saggression
        for pos, player_obj in game_state["players"][off_team].items():
            attr = player_obj.attributes
            ng = attr["NG"]
            for key in MALLEABLE_ATTRS:
                anchor_val = attr[f"anchor_{key}"]
                attr[key] = int(anchor_val * ng)

        return event_type
