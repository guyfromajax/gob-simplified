from tests.test_utils import build_mock_game
from BackEnd.models.turn_manager import TurnManager


def test_team_orientation_switches_at_halftime():
    game = build_mock_game()
    game.home_team.team_id = "H"
    game.away_team.team_id = "A"
    tm = TurnManager(game)
    inbound_first = tm.setup_side_inbound()
    assert inbound_first["ball_spot"]["x"] < 51

    # simulate halftime by swapping team roles
    home, away = game.home_team, game.away_team
    game.home_team, game.away_team = away, home
    game.offense_team = game.away_team  # former home team now attacks opposite basket
    game.defense_team = game.home_team
    game.turn_manager = TurnManager(game)
    inbound_second = game.turn_manager.setup_side_inbound()
    assert inbound_second["ball_spot"]["x"] > 51
