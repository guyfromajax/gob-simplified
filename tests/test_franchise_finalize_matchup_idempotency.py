from types import SimpleNamespace
from unittest.mock import MagicMock

from bson import ObjectId

from BackEnd.utils import stat_updater
from BackEnd.utils.game_id_utils import franchise_matchup_claim_key


def test_franchise_matchup_claim_key_uses_team_ids_and_week():
    game = {
        "week": 3,
        "home_team_id": "MORRISTOWN",
        "away_team_id": "IDA_GROVE",
    }
    assert franchise_matchup_claim_key(game) == "3:IDA_GROVE:MORRISTOWN"


def test_finalize_game_franchise_skips_when_matchup_already_applied(monkeypatch):
    franchise_id = str(ObjectId())
    game_oid = ObjectId()
    game_id = str(game_oid)
    game_doc = {
        "_id": game_oid,
        "quarter": 4,
        "is_final": True,
        "week": 1,
        "home_team_id": "HOME",
        "away_team_id": "AWAY",
        "teams": {
            "HOME": {
                "box_score": {
                    "PG": {"playerId": "p1", "FGA": 10, "FGM": 4, "PTS": 8},
                }
            },
            "AWAY": {"box_score": {}},
        },
    }
    matchup_key = franchise_matchup_claim_key(game_doc)

    mock_games = MagicMock()
    mock_games.find_one.return_value = game_doc

    mock_franchises = MagicMock()
    mock_franchises.find_one.return_value = {
        "applied_games": [],
        "applied_matchups": [matchup_key],
    }

    mock_fpd = MagicMock()
    mock_franchises_update = MagicMock()
    mock_franchises.update_one = mock_franchises_update

    monkeypatch.setattr(stat_updater, "games_collection", mock_games)
    monkeypatch.setattr(stat_updater, "franchise_players_data_collection", mock_fpd)
    monkeypatch.setattr(
        stat_updater,
        "db",
        SimpleNamespace(franchises=mock_franchises),
    )
    monkeypatch.setattr(stat_updater, "_build_franchise_team_maps_from_ftd", lambda _fid: ({}, {}))
    monkeypatch.setattr(stat_updater, "commit_user_game_record", lambda *args, **kwargs: None)
    monkeypatch.setattr(stat_updater, "_update_defensive_playcall_season_stats", lambda *args, **kwargs: None)
    monkeypatch.setattr(stat_updater, "_update_offensive_play_season_stats", lambda *args, **kwargs: None)

    stat_updater.finalize_game(
        game_id,
        mode="franchise",
        franchise_id=franchise_id,
    )

    mock_franchises_update.assert_not_called()
    mock_fpd.update_one.assert_not_called()


def test_finalize_game_franchise_records_applied_matchups_on_claim(monkeypatch):
    franchise_id = str(ObjectId())
    game_oid = ObjectId()
    game_id = str(game_oid)
    game_doc = {
        "_id": game_oid,
        "quarter": 4,
        "is_final": True,
        "week": 2,
        "home_team_id": "HOME",
        "away_team_id": "AWAY",
        "teams": {
            "HOME": {
                "box_score": {
                    "PG": {"playerId": "p1", "FGA": 5, "FGM": 2, "PTS": 4},
                }
            },
            "AWAY": {"box_score": {}},
        },
    }
    matchup_key = franchise_matchup_claim_key(game_doc)

    mock_games = MagicMock()
    mock_games.find_one.return_value = game_doc

    mock_franchises = MagicMock()
    mock_franchises.find_one.return_value = {"applied_games": [], "applied_matchups": []}

    claim_result = SimpleNamespace(modified_count=1)
    mock_franchises.update_one = MagicMock(return_value=claim_result)

    mock_fpd_find = MagicMock(return_value=[])
    mock_fpd = MagicMock()
    mock_fpd.find.return_value = mock_fpd_find

    monkeypatch.setattr(stat_updater, "games_collection", mock_games)
    monkeypatch.setattr(stat_updater, "franchise_players_data_collection", mock_fpd)
    monkeypatch.setattr(
        stat_updater,
        "db",
        SimpleNamespace(franchises=mock_franchises),
    )
    monkeypatch.setattr(stat_updater, "_build_franchise_team_maps_from_ftd", lambda _fid: ({}, {}))
    monkeypatch.setattr(stat_updater, "commit_user_game_record", lambda *args, **kwargs: None)
    monkeypatch.setattr(stat_updater, "_update_defensive_playcall_season_stats", lambda *args, **kwargs: None)
    monkeypatch.setattr(stat_updater, "_update_offensive_play_season_stats", lambda *args, **kwargs: None)

    stat_updater.finalize_game(
        game_id,
        mode="franchise",
        franchise_id=franchise_id,
    )

    claim_call = mock_franchises.update_one.call_args_list[0]
    assert claim_call.args[0]["_id"] == ObjectId(franchise_id)
    assert claim_call.args[1]["$addToSet"]["applied_matchups"] == matchup_key
