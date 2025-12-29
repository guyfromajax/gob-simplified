"""
Fast Break Trigger Logic

Determines when a fast break should be triggered from defensive rebounds or steals.
Extracted from shot_manager.py for better organization and extensibility.
"""

import random
from typing import List, Optional, Tuple


class FastBreakTrigger:
    """Handles fast break trigger determination logic."""
    
    # Defense release chances based on fast_breaks value (0-4)
    DEFENSE_RELEASE_CHANCES = {0: 0.0, 1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0}
    
    @staticmethod
    def can_trigger_from_dreb(
        defense_tempo_value: int,  # Note: parameter name kept for backward compatibility, but now uses fast_breaks setting
        shooter_pos: str,
        def_team_lineup: dict
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Determine if a fast break can be triggered from a defensive rebound.
        
        Args:
            defense_tempo_value: Defense fast_breaks value (0-4) - parameter name kept for backward compatibility
            shooter_pos: Position of the shooter (to avoid releasing same position)
            def_team_lineup: Dictionary of defensive team lineup positions
        
        Returns:
            Tuple of:
            - can_trigger: Whether fast break should trigger
            - defense_release_list: List of positions releasing for fast break
            - defense_rebounders: List of positions staying for rebound
        """
        # Get release chance based on fast_breaks setting
        release_chance = FastBreakTrigger.DEFENSE_RELEASE_CHANCES.get(
            defense_tempo_value, 
            0.0
        )
        defense_releases = random.random() < release_chance
        
        # Determine release position (PG or SG, avoiding shooter's position)
        release_pos = "PG" if shooter_pos != "PG" else "SG"
        
        # Build lists based on whether release happens
        if defense_releases:
            # One player releases, others stay for rebound
            defense_release_list = [release_pos]
            defense_rebounders = [
                pos for pos in def_team_lineup.keys() 
                if pos != release_pos
            ]
        else:
            # No release, all players stay for rebound
            defense_release_list = []
            defense_rebounders = list(def_team_lineup.keys())
        
        can_trigger = len(defense_release_list) > 0
        
        return can_trigger, defense_release_list, defense_rebounders
    
    @staticmethod
    def can_trigger_from_steal(
        steal_chance: float,
        def_team_lineup: dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if a fast break can be triggered from a steal.
        
        Args:
            steal_chance: Probability of fast break after steal (0.0-1.0)
            def_team_lineup: Dictionary of defensive team lineup positions
        
        Returns:
            Tuple of:
            - can_trigger: Whether fast break should trigger
            - ball_handler_pos: Position of ball handler for fast break (usually PG)
        """
        can_trigger = random.random() < steal_chance
        
        if can_trigger:
            # Ball handler is typically the PG for fast breaks after steals
            ball_handler_pos = "PG" if "PG" in def_team_lineup else None
            return True, ball_handler_pos
        
        return False, None

