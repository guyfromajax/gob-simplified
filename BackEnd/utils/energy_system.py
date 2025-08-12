"""Energy system utilities for quarter breaks."""

from BackEnd.models.game_manager import GameManager

def recharge_lineups(game: GameManager, amount: float) -> None:
    """Recharge energy for all players in both lineups.

    Args:
        game: GameManager instance containing home and away teams.
        amount: Fraction of energy to restore (0.0-1.0).
    """
    for team in [game.home_team, game.away_team]:
        for player in team.lineup.values():
            player.recharge_energy(amount)
