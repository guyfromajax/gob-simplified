from types import SimpleNamespace
from unittest.mock import MagicMock

from bson import ObjectId

from BackEnd.api import franchise_routes
from BackEnd.db import db, franchise_players_data_collection
from BackEnd.models import franchise_manager
from BackEnd.utils import stat_updater
from BackEnd.utils.game_id_utils import franchise_matchup_claim_key


def test_franchise_matchup_claim_key_uses_team_ids_and_week():
    game = {
        "week": 3,
        "home_team_id": "MORRISTOWN",
        "away_team_id": "IDA_GROVE",
    }
    assert franchise_matchup_claim_key(game) == "3:IDA_GROVE:MORRISTOWN"


def test_franchise_matchup_claim_key_is_season_scoped():
    game = {"week": 3, "home_team_id": "MORRISTOWN", "away_team_id": "IDA_GROVE"}
    s1 = franchise_matchup_claim_key(game, season=1)
    s2 = franchise_matchup_claim_key(game, season=2)
    assert s1 == "s1:3:IDA_GROVE:MORRISTOWN"
    assert s2 == "s2:3:IDA_GROVE:MORRISTOWN"
    assert s1 != s2


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
    matchup_key = franchise_matchup_claim_key(game_doc, season=1)

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
    monkeypatch.setattr(
        "BackEnd.utils.user_game_commit.commit_user_game_record",
        lambda *args, **kwargs: None,
    )
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
    matchup_key = franchise_matchup_claim_key(game_doc, season=1)

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
    monkeypatch.setattr(
        "BackEnd.utils.user_game_commit.commit_user_game_record",
        lambda *args, **kwargs: None,
    )
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


# --- mongomock end-to-end: season-scoped matchup claim -----------------------


def _reset_db():
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    franchise_players_data_collection.delete_many({})


def _franchise_setup(season=1):
    team_a, team_b = ObjectId(), ObjectId()
    db.teams.insert_many([
        {"_id": team_a, "name": "Lancaster", "team_id": "LANCASTER"},
        {"_id": team_b, "name": "Casino Row", "team_id": "CASINO_ROW"},
    ])
    fid = db.franchises.insert_one({
        "schedule": [[(team_a, team_b)], [(team_b, team_a)]],
        "week": 1,
        "current_season": season,
        "user_team_id": "Lancaster",
        "user_team_object_id": str(team_a),
        "results": {},
        "applied_games": [],
        "applied_matchups": [],
    }).inserted_id
    for pid, team in (("starter", team_a), ("cpu", team_b)):
        franchise_players_data_collection.insert_one({
            "franchise_id": str(fid),
            "player_id": pid,
            "meta": {"first_name": pid, "last_name": "X", "team_id": str(team)},
            "season": {"GP": 0, "MIN": 0, "PTS": 0, "FGA": 0},
            "career": {"GP": 0, "MIN": 0, "PTS": 0, "FGA": 0},
        })
    return fid


def _franchise_game(fid, week, _id):
    db.games.insert_one({
        "_id": _id,
        "week": week,
        "quarter": 4,
        "is_final": True,
        "franchise_id": str(fid),
        "home_team_id": "CASINO_ROW",
        "away_team_id": "LANCASTER",
        "teams": {
            "LANCASTER": {"name": "Lancaster", "box_score": {
                "PG": {"playerId": "starter", "name": "starter", "MIN": 600, "PTS": 10, "FGA": 8},
            }},
            "CASINO_ROW": {"name": "Casino Row", "box_score": {
                "PG": {"playerId": "cpu", "name": "cpu", "MIN": 600, "PTS": 6, "FGA": 5},
            }},
        },
    })
    return str(_id)


def _starter(fid):
    return franchise_players_data_collection.find_one(
        {"franchise_id": str(fid), "player_id": "starter"}, {"_id": 0}
    )


def test_same_season_week_pair_str_and_objectid_docs_counted_once():
    _reset_db()
    fid = _franchise_setup(season=1)
    # Two distinct docs for one played game: a string _id and an ObjectId _id.
    # applied_games can't link them (different ids); the matchup claim must.
    g_str = _franchise_game(fid, 4, str(ObjectId()))
    g_oid = _franchise_game(fid, 4, ObjectId())
    stat_updater.finalize_game(g_str, mode="franchise", franchise_id=str(fid))
    stat_updater.finalize_game(g_oid, mode="franchise", franchise_id=str(fid))

    starter = _starter(fid)
    assert starter["season"]["GP"] == 1
    assert starter["season"]["PTS"] == 10
    assert starter["career"]["PTS"] == 10
    assert db.franchises.find_one({"_id": fid})["applied_matchups"] == [
        "s1:4:CASINO_ROW:LANCASTER"
    ]


def test_same_week_pair_in_next_season_is_counted():
    _reset_db()
    fid = _franchise_setup(season=1)
    g1 = _franchise_game(fid, 4, ObjectId())
    stat_updater.finalize_game(g1, mode="franchise", franchise_id=str(fid))
    assert _starter(fid)["career"]["PTS"] == 10

    # Season rolls over without clearing claims (worst case: pre-fix franchise
    # doc still carrying last season's list); games dropped and season stats
    # zeroed like finish_season.
    db.franchises.update_one({"_id": fid}, {"$set": {"current_season": 2, "week": 1}})
    db.games.delete_many({"franchise_id": str(fid)})
    franchise_players_data_collection.update_many(
        {"franchise_id": str(fid)},
        # Per-field $set: a whole-dict $set via update_many makes mongomock share
        # one dict object across docs, so one player's $inc would leak to another.
        {"$set": {"season.GP": 0, "season.MIN": 0, "season.PTS": 0, "season.FGA": 0}},
    )
    g2 = _franchise_game(fid, 4, ObjectId())
    stat_updater.finalize_game(g2, mode="franchise", franchise_id=str(fid))

    starter = _starter(fid)
    assert starter["season"]["GP"] == 1
    assert starter["season"]["PTS"] == 10
    assert starter["career"]["PTS"] == 20


def test_legacy_unscoped_claim_from_prior_season_does_not_block():
    _reset_db()
    fid = _franchise_setup(season=2)
    # A franchise that played season 1 before the fix carries legacy keys.
    db.franchises.update_one(
        {"_id": fid}, {"$set": {"applied_matchups": ["4:CASINO_ROW:LANCASTER"]}}
    )
    g = _franchise_game(fid, 4, ObjectId())
    stat_updater.finalize_game(g, mode="franchise", franchise_id=str(fid))
    assert _starter(fid)["season"]["PTS"] == 10


def test_finish_season_clears_applied_matchups(monkeypatch):
    franchise_id = ObjectId()
    captured_update = {}

    mock_franchises = MagicMock()
    mock_franchises.find_one.return_value = {
        "_id": franchise_id,
        "week": 36,
        "current_season": 1,
        "results": {},
        "applied_matchups": ["s1:4:CASINO_ROW:LANCASTER", "4:A:B"],
    }

    def capture_update(query, update_doc):
        if "$unset" in update_doc:
            return SimpleNamespace(modified_count=1)
        captured_update.update(update_doc.get("$set", {}))
        return SimpleNamespace(modified_count=1)

    mock_franchises.update_one.side_effect = capture_update
    monkeypatch.setattr(
        franchise_routes,
        "db",
        SimpleNamespace(franchises=mock_franchises, games=MagicMock()),
    )
    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", MagicMock(find=MagicMock(return_value=[])))
    monkeypatch.setattr(franchise_routes, "franchise_players_data_collection", MagicMock(find=MagicMock(return_value=[]), delete_many=MagicMock()))
    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", MagicMock(delete_many=MagicMock()))
    dummy_manager = SimpleNamespace(
        schedule_manager=SimpleNamespace(generate_schedule=lambda: []),
        recruit_manager=SimpleNamespace(generate_recruits_list=lambda count=200: []),
        _build_region_team_map=lambda: {"A": []},
    )
    monkeypatch.setattr(franchise_manager, "FranchiseManager", lambda _db: dummy_manager)

    result = franchise_routes.finish_season(
        franchise_routes.FinishSeasonRequest(franchise_id=str(franchise_id))
    )

    assert result["status"] == "success"
    assert captured_update["applied_matchups"] == []
    assert captured_update["current_season"] == 2
