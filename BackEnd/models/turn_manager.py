from models.logger import Logger
from models.rebound_manager import ReboundManager
from models.playbook_manager import PlaybookManager
from models.animation_manager import AnimationManager
from constants import POSITION_LIST
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

        # You can expand this with timeout logic, foul tracking, etc.