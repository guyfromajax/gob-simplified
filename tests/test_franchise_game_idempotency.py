from types import SimpleNamespace
from unittest.mock import MagicMock

from bson import ObjectId

from BackEnd.utils import stat_updater


def test_finalize_game_franchise_duplicate_exits_before_player_updates(monkeypatch):
    franchise_id = str(ObjectId())
    game_id = str(ObjectId())
    game_doc = {
        "_id": ObjectId(game_id),
        "quarter": 4,
        "is_final": True,
        "week": 12,
    }

    mock_games = MagicMock()
    mock_games.find_one.return_value = game_doc

    mock_franchises = MagicMock()
    mock_franchises.find_one.return_value = {"applied_games": [game_id]}

    mock_fpd = MagicMock()

    monkeypatch.setattr(stat_updater, "games_collection", mock_games)
    monkeypatch.setattr(stat_updater, "franchise_players_data_collection", mock_fpd)
    monkeypatch.setattr(
        stat_updater,
        "db",
        SimpleNamespace(franchises=mock_franchises),
    )

    stat_updater.finalize_game(
        game_id,
        mode="franchise",
        franchise_id=franchise_id,
    )

    mock_franchises.update_one.assert_not_called()
    mock_fpd.update_one.assert_not_called()
