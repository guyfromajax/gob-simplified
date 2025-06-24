import pytest
from BackEnd.models.game_manager import GameManager
from BackEnd.constants import POSITION_LIST

@pytest.fixture
def mock_game_manager():
    mock_player_data = {
        "first_name": "John",
        "last_name": "Doe"
    }
    players = {pos: mock_player_data.copy() for pos in POSITION_LIST}
    gm = GameManager("Team A", "Team B", players, players)
    return gm  # <== return the full GameManager, not just gm.game_state
