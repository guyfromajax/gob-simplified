from BackEnd.utils.shared import collect_near_bounce_rebound_attemptors
from tests.test_utils import build_mock_game


POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def _sync_lineup_to_roster(game):
    for team in (game.home_team, game.away_team):
        for pos, player in team.lineup.items():
            if player.player_id is None:
                player.player_id = f"{team.name}-{pos}"
        team.players = {
            player.player_id: player
            for pos, player in team.lineup.items()
        }


def test_collect_near_bounce_rebound_attemptors_uses_15_grid_radius():
    game = build_mock_game()
    _sync_lineup_to_roster(game)
    bounce = {"x": 89, "y": 25}

    off_pg = game.offense_team.lineup["PG"]
    off_sg = game.offense_team.lineup["SG"]
    def_pg = game.defense_team.lineup["PG"]
    def_sg = game.defense_team.lineup["SG"]

    off_pg.coords = {"x": 80, "y": 25}   # 9 away: included
    off_sg.coords = {"x": 70, "y": 25}   # 19 away: excluded
    def_pg.coords = {"x": 89, "y": 40}   # 15 away: included
    def_sg.coords = {"x": 89, "y": 41}   # 16 away: excluded

    actual_rebounder = game.defense_team.lineup["C"]
    actual_rebounder.coords = {"x": 89, "y": 24}

    result = collect_near_bounce_rebound_attemptors(
        game,
        bounce,
        actual_rebounder.player_id,
    )

    assert off_pg.player_id in result["offense_rebounders"]
    assert off_sg.player_id not in result["offense_rebounders"]
    assert def_pg.player_id in result["defense_rebounders"]
    assert def_sg.player_id not in result["defense_rebounders"]
    assert actual_rebounder.player_id not in result["defense_rebounders"]
