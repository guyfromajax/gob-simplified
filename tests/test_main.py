from tests.test_utils import build_mock_game

def test_box_score_includes_named_players():
    game = build_mock_game()
    box_score = game.get_box_score()
    team_key = game.home_team.team_id or game.home_team.name

    assert team_key in box_score
    assert "PG" in box_score[team_key]
    assert "name" in box_score[team_key]["PG"]
    assert isinstance(box_score[team_key]["PG"], dict)

def test_box_score_stats_match_recorded_stats():
    game = build_mock_game()
    player = game.home_team.lineup["PG"]
    
    player.record_stat("AST", 3)
    player.record_stat("FGM", 2)
    player.record_stat("3PTM", 1)
    player.record_stat("FTM", 2)

    box_score = game.get_box_score()
    team_key = game.home_team.team_id or game.home_team.name
    stats = box_score[team_key]["PG"]

    assert stats["AST"] == 3
    assert stats["FGM"] == 2
    assert stats["3PTM"] == 1
    assert stats["FTM"] == 2
    assert stats["PTS"] == (2 * 2) + 1 + 2
