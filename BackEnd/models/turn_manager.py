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
    get_foul_and_turnover_positions,
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
        self.rebound_manager = ReboundManager(self.game)
        self.playbook_manager = PlaybookManager(self.game.offense_team)
        self.animator = AnimationManager()

    def run_micro_turn(self):
        # Increment micro turn counter
        self.game.micro_turn_count += 1
        
        # STEP 1: Set strategy calls (tempo + aggression)
        self.set_strategy_calls()

        print("*****RUN TURN*****")
        print(f"offensive state: {self.game.game_state['offensive_state']}")
        if self.game.game_state["offensive_state"] in ["HCO", "HALF_COURT"]:
            print(f"{self.game.offense_team.name}: {self.game.game_state['current_playcall']}")
            print(f"{self.game.defense_team.name}: {self.game.game_state['defense_playcall']}")

        # STEP 3: Route based on offensive state
        state = self.game.game_state["offensive_state"]
        if state == "FREE_THROW":
            result = self.resolve_free_throw()
        elif state == "FAST_BREAK":
            result = self.resolve_fast_break()
        else:
            calls = self.set_playcalls()
            self.game.game_state["current_playcall"] = calls["offense"]
            self.game.game_state["defense_playcall"] = calls["defense"]
            result = self.resolve_half_court_offense()

        print("Inside run_micro_turn // coming out of resolve offensive state functions")
        print(f"result: {result}")

        # STEP 4: Final updates (clock, logs, animation)
        self.update_clock_and_possession(result)
        self.logger.log_turn_result(result)
        self.animator.capture(result)
        animations = self.animator.get_latest_animation_packet()  # see below
        result["animations"] = animations


        print("🔁 End of run_micro_turn after housekeeping functions")
        print(f"{result['text']}")
        print(f"{self.game.game_state['score']}")
        print(f"{self.game.game_state['clock']}")
        print(f"animations: {animations}")
        # print(f"game state: {self.game.game_state}")
        
        result["turn_count"] = self.game.micro_turn_count
        result["possession_team_id"] = self.game.offense_team.team_id
        print(f"possesion team id: {self.game.offense_team.team_id}")

        return result


    def set_playcalls(self):

        chosen_playcall = weighted_random_from_dict(self.game.offense_team.playcall_weights)
        defense_setting = self.game.defense_team.strategy_settings["defense"]
        chosen_defense = random.choice(STRATEGY_CALL_DICTS["defense"][defense_setting])

        # Track usage
        self.game.offense_team.playcall_tracker[chosen_playcall] += 1
        self.game.defense_team.defense_playcall_tracker[chosen_defense] += 1

        return {
            "offense": chosen_playcall,
            "defense": chosen_defense
        }


    def set_strategy_calls(self):

        tempo_setting = self.game.offense_team.strategy_settings["tempo"]
        aggression_setting = self.game.defense_team.strategy_settings["aggression"]

        self.game.offense_team.strategy_calls["tempo_call"] = random.choice(STRATEGY_CALL_DICTS["tempo"][tempo_setting])
        self.game.defense_team.strategy_calls["aggression_call"] = random.choice(STRATEGY_CALL_DICTS["aggression"][aggression_setting])


    
    def resolve_half_court_offense(self):
        from BackEnd.engine.phase_resolution import resolve_half_court_offense_logic
        return resolve_half_court_offense_logic(self.game)


    def resolve_fast_break(self):
        return resolve_fast_break_logic(self.game) 

    def resolve_free_throw(self):
        return resolve_free_throw_logic(self.game)
    
    def resolve_turnover(self):
        return resolve_turnover_logic(self.game)

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
            self.game.switch_possession()

    def assign_roles(self):
        
        off_team = self.game.offense_team
        def_team = self.game.defense_team
        off_lineup = self.game.offense_team.lineup
        def_lineup = self.game.defense_team.lineup
        playcall = self.game.game_state["current_playcall"]
        print(f"playcall: {playcall}")

        # Compute shot weights using attributes embedded in each player object
        weights_dict = PLAYCALL_ATTRIBUTE_WEIGHTS.get("Attack" if playcall == "Set" else playcall, {})
        print(f"weights_dict: {weights_dict}")

        for pos, player in off_lineup.items():
            print(f"{pos}: {player.attributes}")
        
        shot_weights = {
            pos: sum(
                off_lineup[pos].attributes[attr] * weight
                for attr, weight in weights_dict.items()
            )
            for pos in off_lineup
        }
        print(f"shot_weights: {shot_weights}")
        shooter_pos = weighted_random_from_dict(shot_weights)

        # Compute screener weights (excluding the shooter)
        screen_weights = {
            pos: (
                off_lineup[pos].attributes["ST"] * 6 +
                off_lineup[pos].attributes["AG"] * 2 +
                off_lineup[pos].attributes["IQ"] * 1 +
                off_lineup[pos].attributes["CH"] * 1
            )
            for pos in off_lineup if pos != shooter_pos
        }

        screener_pos = max(screen_weights, key=screen_weights.get)
        if screener_pos == shooter_pos:
            screener_pos = ""

        # Pass chain and passer
        pass_chain = generate_pass_chain(self.game, shooter_pos)

        passer_pos = pass_chain[-2] if len(pass_chain) >= 2 else ""
        if passer_pos == shooter_pos or passer_pos == screener_pos:
            passer_pos = ""

        if self.game.game_state["defense_playcall"] == "Zone":
            defender_pos = random.choice(POSITION_LIST)
        else:
            defender_pos = shooter_pos

        shooter = self.game.offense_team.lineup[shooter_pos]
        screener = self.game.offense_team.lineup[screener_pos]
        passer = self.game.offense_team.lineup[passer_pos] if passer_pos else None
        defender = self.game.defense_team.lineup[defender_pos]

        # print("end of assign_roles")
        # print(f"shooter: {get_name_safe(shooter)}")
        # print(f"screener: {get_name_safe(screener)}")
        # print(f"passer: {get_name_safe(passer)}")
        # print(f"defender: {get_name_safe(defender)}")

        
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
        off_team = self.game.offense_team
        def_team = self.game.defense_team
        tempo_call = self.game.offense_team.strategy_calls["tempo_call"]
        pass_count = TEMPO_PASS_DICT[tempo_call]
        positions = get_foul_and_turnover_positions(pass_count)
        event_type = calculate_foul_turnover(self.game, positions, roles)
    
        #determine number of turnover RNGs based on defense team'saggression
        
        for pos, player_obj in self.game.offense_team.lineup.items():
            attr = player_obj.attributes
            ng = attr["NG"]
            for key in MALLEABLE_ATTRS:
                anchor_val = attr[f"anchor_{key}"]
                attr[key] = int(anchor_val * ng)

        return event_type
