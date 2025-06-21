from BackEnd.models.logger import Logger
from BackEnd.models.rebound_manager import ReboundManager
from BackEnd.models.playbook_manager import PlaybookManager
from BackEnd.models.animation_manager import AnimationManager
from BackEnd.constants import POSITION_LIST, PLAYCALL_ATTRIBUTE_WEIGHTS
import random

class TurnManager:
    def __init__(self, game_manager):
        self.game = game_manager
        self.logger = Logger()
        self.rebound_manager = ReboundManager()
        self.playbook_manager = PlaybookManager()
        self.animator = AnimationManager()

    def run_turn(self):
        state = self.game.offensive_state

        if state == "FREE_THROW":
            result = self.resolve_free_throw()
        elif state == "FAST_BREAK":
            result = self.resolve_fast_break()
        else:
            result = self.resolve_half_court_offense()

        self.update_clock_and_possession(result)
        self.logger.log_turn(result)
        self.animator.capture(result)

        return result

    def resolve_half_court_offense(self):
        # Determine shooter, screener, passer
        roles = self.playbook_manager.assign_roles(self.game)
        defense_result = self.game.assess_defense(roles)
        shot_result = self.game.resolve_shot(roles, defense_result)

        if shot_result.get("missed"):
            rebound_result = self.rebound_manager.handle_rebound(self.game, roles)
            return rebound_result

        return shot_result

    def resolve_fast_break(self):
        return self.game.resolve_fast_break_logic()

    def resolve_free_throw(self):
        return self.game.resolve_free_throw_logic()

    def update_clock_and_possession(self, result):
        # Basic example: reduce time and switch possession if needed
        if result.get("possession_flips"):
            self.game.flip_possession()

    def assign_roles(self, game_state, playcall):
        off_team = game_state["offense_team"]
        def_team = game_state["defense_team"]
        players = game_state["players"][off_team]

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

        # Pass chain and passer
        pass_chain = generate_pass_chain(game_state, shooter_pos)
        passer_pos = pass_chain[-2] if len(pass_chain) >= 2 else ""
        if passer_pos == shooter_pos:
            passer_pos = ""

        if game_state["defense_playcall"] == "Zone":
            defender_pos = random.choice(POSITION_LIST)
        else:
            defender_pos = shooter_pos

        passer = game_state["players"][off_team][passer_pos] if passer_pos else None
        return {
            "shooter": game_state["players"][off_team][shooter_pos],
            "screener": game_state["players"][off_team][screener_pos],
            "ball_handler": game_state["players"][off_team][shooter_pos],
            "passer": passer,
            "pass_chain": pass_chain,
            "defender": game_state["players"][def_team][defender_pos]
        }


        # You can expand this with timeout logic, foul tracking, etc.