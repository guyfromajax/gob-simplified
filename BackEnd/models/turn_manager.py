from BackEnd.models.logger import Logger
from BackEnd.models.rebound_manager import ReboundManager
from BackEnd.models.playbook_manager import PlaybookManager
from BackEnd.models.animation_manager import AnimationManager
import random
import json
from BackEnd.db import players_collection, teams_collection
from BackEnd.models.player import Player
# from BackEnd.models.game_manager import GameManager
from BackEnd.constants import PLAYCALL_ATTRIBUTE_WEIGHTS, POSITION_LIST
from BackEnd.utils.shared import weighted_random_from_dict, generate_pass_chain
from BackEnd.engine.phase_resolution import resolve_fast_break_logic, resolve_free_throw_logic, resolve_turnover_logic
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
        # STEP 1: Read offensive state
        state = self.game.game_state["offensive_state"]

        # STEP 2: Inject playcalls into game_state
        self.game.game_state["current_playcall"] = self.playbook_manager.get_offensive_playcall()
        self.game.game_state["defense_playcall"] = self.playbook_manager.get_defensive_playcall()

        # STEP 3: Route based on state
        if state == "FREE_THROW":
            result = self.resolve_free_throw()
        elif state == "FAST_BREAK":
            result = self.resolve_fast_break()
        else:
            result = self.resolve_half_court_offense()

        self.update_clock_and_possession(result)
        self.logger.log_turn_result(result)
        self.animator.capture(result)

        return result


    def resolve_half_court_offense(self):
        
        #need to check for a foul or turnover here
        # Determine shooter, screener, passer
        roles = self.assign_roles(self.game)
        shot_result = self.game.shot_manager.resolve_shot(roles)

        if shot_result.get("missed"):
            rebound_result = self.rebound_manager.handle_rebound(self.game, roles)
            return rebound_result

        return shot_result

    def resolve_fast_break(self):
        return resolve_fast_break_logic(self.game.game_state) 

    def resolve_free_throw(self):
        return resolve_free_throw_logic(self.game.game_state)
    
    def resolve_turnover(self):
        return resolve_turnover_logic(self.game.game_state)

    def update_clock_and_possession(self, result):
        # Basic example: reduce time and switch possession if needed
        if result.get("possession_flips"):
            self.game._switch_possession()

    def assign_roles(self, playcall):
        print("inside assign_roles")
        print(self.game.game_state.keys())
        off_team = self.game.game_state["offense_team"]
        def_team = self.game.game_state["defense_team"]
        players = self.game.game_state["players"][off_team]

        # Compute shot weights using attributes embedded in each player object
        weights_dict = PLAYCALL_ATTRIBUTE_WEIGHTS.get("Attack" if playcall == "Set" else playcall, {})

        shot_weights = {
            pos: sum(
                players[pos].attributes[attr] * weight
                for attr, weight in weights_dict.items()
            )
            for pos in players
        }

        shooter_pos = weighted_random_from_dict(shot_weights)

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

        print("assign_roles game_state keys:", self.game.game_state.keys())

        if self.game.game_state["defense_playcall"] == "Zone":
            defender_pos = random.choice(POSITION_LIST)
        else:
            defender_pos = shooter_pos

        passer = self.game.game_state["players"][off_team][passer_pos] if passer_pos else None
        return {
            "shooter": self.game.game_state["players"][off_team][shooter_pos],
            "screener": self.game.game_state["players"][off_team][screener_pos],
            "ball_handler": self.game.game_state["players"][off_team][shooter_pos],
            "passer": passer,
            "pass_chain": pass_chain,
            "defender": self.game.game_state["players"][def_team][defender_pos]
        }


        # You can expand this with timeout logic, foul tracking, etc.