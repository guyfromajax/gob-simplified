from BackEnd.models.game_manager import GameManager
from BackEnd.models.player import Player
import pytest  # for exception testing or parameterized testing
from copy import deepcopy  # for cloning mock input states


def test_game_manager_initializes_teams_correctly():
    gm = GameManager("Team A", "Team B", {}, {})
    assert gm.home_team == "Team A"
    assert gm.away_team == "Team B"

def test_game_manager_creates_player_objects():
    mock_player_data = {"first_name": "John", "last_name": "Doe"}
    home_players = {"PG": mock_player_data}
    gm = GameManager("Team A", "Team B", home_players, {})
    assert isinstance(gm.players["Team A"]["PG"], Player)
    assert gm.players["Team A"]["PG"].get_name() == "John Doe"

def test_game_manager_box_score_structure():
    mock_player_data = {"first_name": "John", "last_name": "Doe"}
    home_players = {"PG": mock_player_data}
    gm = GameManager("Team A", "Team B", home_players, {})
    box_score = gm.get_box_score()
    assert "Team A" in box_score
    assert "PG" in box_score["Team A"]
    assert isinstance(box_score["Team A"]["PG"], dict)
    assert "PTS" in box_score["Team A"]["PG"]

def test_game_manager_simulate_turn_runs():
    mock_player_data = {"first_name": "John", "last_name": "Doe"}
    players = {pos: mock_player_data for pos in ["PG", "SG", "SF", "PF", "C"]}
    gm = GameManager("Team A", "Team B", players, players)
    gm.simulate_turn()  # Should not raise

