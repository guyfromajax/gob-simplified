from BackEnd.utils.shared import (
    collect_near_bounce_rebound_attemptors,
    filter_rebound_candidate_lineups_near_bounce,
)
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


def test_collect_near_bounce_rebound_attemptors_uses_20_grid_radius():
    game = build_mock_game()
    _sync_lineup_to_roster(game)
    bounce = {"x": 89, "y": 25}

    off_pg = game.offense_team.lineup["PG"]
    off_sg = game.offense_team.lineup["SG"]
    def_pg = game.defense_team.lineup["PG"]
    def_sg = game.defense_team.lineup["SG"]

    off_pg.coords = {"x": 80, "y": 25}   # 9 away: included
    off_sg.coords = {"x": 68, "y": 25}   # 21 away: excluded
    def_pg.coords = {"x": 89, "y": 45}   # 20 away: included
    def_sg.coords = {"x": 89, "y": 46}   # 21 away: excluded

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


def test_filter_rebound_candidate_lineups_near_bounce_preserves_position_keys():
    game = build_mock_game()
    _sync_lineup_to_roster(game)
    bounce = {"x": 89, "y": 25}

    off_pg = game.offense_team.lineup["PG"]
    off_sg = game.offense_team.lineup["SG"]
    def_pg = game.defense_team.lineup["PG"]
    def_sg = game.defense_team.lineup["SG"]

    off_pg.coords = {"x": 80, "y": 25}   # 9 away: included
    off_sg.coords = {"x": 68, "y": 25}   # 21 away: excluded
    def_pg.coords = {"x": 89, "y": 45}   # 20 away: included
    def_sg.coords = {"x": 89, "y": 46}   # 21 away: excluded

    off_filtered, def_filtered = filter_rebound_candidate_lineups_near_bounce(
        game.offense_team.lineup,
        game.defense_team.lineup,
        bounce,
    )

    assert off_filtered == {"PG": off_pg}
    assert def_filtered == {"PG": def_pg}


def test_filter_rebound_candidate_lineups_near_bounce_falls_back_when_both_empty():
    game = build_mock_game()
    _sync_lineup_to_roster(game)
    bounce = {"x": 89, "y": 25}

    for team in (game.offense_team, game.defense_team):
        for player in team.lineup.values():
            player.coords = {"x": 50, "y": 25}

    off_filtered, def_filtered = filter_rebound_candidate_lineups_near_bounce(
        game.offense_team.lineup,
        game.defense_team.lineup,
        bounce,
    )

    assert off_filtered is game.offense_team.lineup
    assert def_filtered is game.defense_team.lineup
