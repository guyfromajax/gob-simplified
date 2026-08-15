from BackEnd.utils.shared import (
    _team_rebound_bonus,
    collect_near_bounce_rebound_attemptors,
    filter_rebound_candidate_lineups_near_bounce,
    select_rebounder_by_score,
)
from tests.test_utils import build_mock_game


POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def test_team_rebound_bonus_uses_half_chemistry_impact():
    game = build_mock_game()
    game.offense_team.team_attributes["team_chemistry"] = 25
    game.offense_team.team_attributes["rebound_modifier"] = 0.4

    assert _team_rebound_bonus(game.offense_team) == 5.0


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


def test_select_rebounder_by_score_checks_all_eligible_players_not_just_closest(monkeypatch):
    game = build_mock_game()
    _sync_lineup_to_roster(game)
    bounce = {"x": 89, "y": 25}

    low_close = game.offense_team.lineup["PG"]
    high_far = game.offense_team.lineup["SG"]
    defender = game.defense_team.lineup["PG"]

    low_close.coords = {"x": 89, "y": 25}
    low_close.attributes.update({"RB": 1, "ST": 1, "IQ": 1, "CH": 1})
    high_far.coords = {"x": 77, "y": 25}
    high_far.attributes.update({"RB": 100, "ST": 100, "IQ": 100, "CH": 100})
    defender.coords = {"x": 90, "y": 25}
    defender.attributes.update({"RB": 1, "ST": 1, "IQ": 1, "CH": 1})

    monkeypatch.setattr("BackEnd.utils.shared.random.randint", lambda a, b: 6)

    rebounder, team, stat = select_rebounder_by_score(
        game.offense_team,
        game.defense_team,
        {"PG": low_close, "SG": high_far},
        {"PG": defender},
        bounce,
    )

    assert rebounder is high_far
    assert team is game.offense_team
    assert stat == "OREB"


def test_select_rebounder_by_score_uses_rebound_modifier_tiebreaker(monkeypatch):
    game = build_mock_game()
    _sync_lineup_to_roster(game)
    bounce = {"x": 89, "y": 25}

    off_player = game.offense_team.lineup["PG"]
    def_player = game.defense_team.lineup["PG"]
    off_player.coords = {"x": 89, "y": 25}
    def_player.coords = {"x": 89, "y": 25}
    off_player.attributes.update({"RB": 50, "ST": 50, "IQ": 50, "CH": 50, "MO": 0})
    def_player.attributes.update({"RB": 50, "ST": 50, "IQ": 50, "CH": 50, "MO": 0})
    game.offense_team.team_attributes["team_chemistry"] = 0
    game.defense_team.team_attributes["team_chemistry"] = 0
    game.offense_team.team_attributes["rebound_modifier"] = 0.1
    game.defense_team.team_attributes["rebound_modifier"] = 0.2

    monkeypatch.setattr("BackEnd.utils.shared.random.randint", lambda a, b: 6)

    rebounder, team, stat = select_rebounder_by_score(
        game.offense_team,
        game.defense_team,
        {"PG": off_player},
        {"PG": def_player},
        bounce,
    )

    assert rebounder is def_player
    assert team is game.defense_team
    assert stat == "DREB"


def test_select_rebounder_by_score_prefers_closer_equal_attrs(monkeypatch):
    """Equal attributes: smooth distance discount awards the closer player."""
    game = build_mock_game()
    _sync_lineup_to_roster(game)
    bounce = {"x": 89, "y": 25}

    close = game.defense_team.lineup["PG"]
    far = game.defense_team.lineup["SG"]
    close.coords = {"x": 89, "y": 25}  # distance 0
    far.coords = {"x": 73, "y": 25}    # distance 16 → ×1/(1+16/8)=1/3
    close.attributes.update({"RB": 50, "ST": 50, "IQ": 50, "CH": 50, "MO": 0})
    far.attributes.update({"RB": 50, "ST": 50, "IQ": 50, "CH": 50, "MO": 0})
    game.offense_team.team_attributes["team_chemistry"] = 0
    game.defense_team.team_attributes["team_chemistry"] = 0
    game.offense_team.team_attributes["rebound_modifier"] = 0.0
    game.defense_team.team_attributes["rebound_modifier"] = 0.0

    monkeypatch.setattr("BackEnd.utils.shared.random.randint", lambda a, b: 6)

    rebounder, team, stat = select_rebounder_by_score(
        game.offense_team,
        game.defense_team,
        {},
        {"PG": close, "SG": far},
        bounce,
    )

    assert rebounder is close
    assert team is game.defense_team
    assert stat == "DREB"
