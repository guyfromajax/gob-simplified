from tests.test_utils import build_mock_game
from BackEnd.models.game_manager import GameManager


def test_game_manager_simulate_macro_turn_runs():
    gm = build_mock_game()
    print("DEBUG: type(gm) =", type(gm))
    gm.simulate_macro_turn()


def test_game_manager_initializes_teams_correctly():
    gm = GameManager("Lancaster", "Bentley-Truman")
    assert gm.home_team.name == "Lancaster"
    assert gm.away_team.name == "Bentley-Truman"


def test_game_manager_has_lineups():
    gm = build_mock_game()
    assert len(gm.home_team.lineup) == 5
    assert len(gm.away_team.lineup) == 5
    assert "PG" in gm.home_team.lineup
    assert gm.home_team.lineup["PG"].get_name().startswith("Lancaster")


def test_game_manager_box_score_structure():
    gm = build_mock_game()
    player = gm.home_team.lineup["PG"]
    player.record_stat("FGM", 1)
    player.record_stat("3PTM", 1)
    player.record_stat("FTM", 1)

    box_score = gm.get_box_score()
    stats = box_score["Lancaster"]["PG"]

    assert "PTS" in stats
    assert stats["PTS"] == 2 + 1 + 1



def test_game_manager_simulate_macro_turn_runs():
    gm = build_mock_game()
    gm.simulate_macro_turn()  # Should not raise
