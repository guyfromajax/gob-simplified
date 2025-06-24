
def test_game_state_structure(mock_game_manager):
    assert "players" in mock_game_manager.game_state
    assert mock_game_manager.game_state["offense_team"] in ["Team A", "Team B"]