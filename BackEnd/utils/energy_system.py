"""Energy system utilities for quarter breaks."""

import random
from typing import List
from BackEnd.models.game_manager import GameManager

def recharge_lineups(game: GameManager, amount_options: List[float]) -> None:
    """Recharge energy for all players in both lineups.
    
    Each player gets a random amount from the provided list.
    
    NOTE: This function is deprecated. Use recharge_all_players() instead.
    This function only affects lineup players, not bench players.

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

def recharge_all_players(game: GameManager, amount_options: List[float]) -> None:
    """Recharge energy for ALL players (lineup + bench) on both teams.
    
    Each player gets a random amount from the provided list.
    This is used for quarter breaks and timeouts to ensure all players
    receive energy recharge, not just those in the active lineup.

    Args:
        game: GameManager instance containing home and away teams.
        amount_options: List of possible energy amounts to restore. Each player
                       gets a random choice from this list.
    """
    for team in [game.home_team, game.away_team]:
        for player in team.get_all_players():
            if player and hasattr(player, "recharge_energy"):
                amount = random.choice(amount_options)
                player.recharge_energy(amount)
