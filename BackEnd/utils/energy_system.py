"""Energy system utilities for quarter breaks."""

import random
from typing import List
from BackEnd.models.game_manager import GameManager

def recharge_lineups(game: GameManager, amount_options: List[float]) -> None:
    """Recharge energy for all players in both lineups.
    
    Each player gets a random amount from the provided list.

    Args:
        game: GameManager instance containing home and away teams.
        amount_options: List of possible energy amounts to restore. Each player
                       gets a random choice from this list.
    """
    for team in [game.home_team, game.away_team]:
        for player in team.lineup.values():
            if player:  # Skip None players
                amount = random.choice(amount_options)
                player.recharge_energy(amount)
