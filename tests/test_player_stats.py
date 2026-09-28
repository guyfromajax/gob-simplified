"""GET /franchise/player-stats. Rates come from stat_line. Runs on mongomock and SQLite."""

import logging

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.db import db, franchise_players_data_collection, franchise_team_data_collection
from BackEnd.persistence import get_store

client = TestClient(app)

TEAM = ObjectId()


def setup_function(_fn):
    db.franchises.delete_many({})
    db.teams.delete_many({})
    franchise_players_data_collection.delete_many({})
    franchise_team_data_collection.delete_many({})


def seed():
    fid = db.franchises.insert_one({
        "user_team_id": "Lancaster",
        "user_team_object_id": str(TEAM),
        "week": 4,
        "browse_rev": 1,
    }).inserted_id
    db.teams.insert_one({"_id": TEAM, "name": "Lancaster", "conference": 1, "region": "A"})
    franchise_team_data_collection.insert_one({
        "franchise_id": fid,
        "team_id": TEAM,
        "players": ["ada", "zero"],
    })
    franchise_players_data_collection.insert_one({
        "franchise_id": str(fid),
        "player_id": "ada",
        "meta": {
            "first_name": "Ada",
            "last_name": "Ace",
            "position": "SG",
            "year": "Junior",
            "jersey": 23,
            "team_id": str(TEAM),
            "team": "Lancaster",
        },
        "attributes": {"blob": "x" * 4000},
        "season": {
            "GP": 2, "MIN": 31, "PTS": 22,
            "FGM": 8, "FGA": 20,
            "3PTM": 0, "3PTA": 0,
            "FTM": 0, "FTA": 4,
            "OREB": 1, "DREB": 5, "REB": 6,
            "AST": 4, "TO": 3, "STL": 2, "BLK": 1, "F": 4,
            "DEF_S": 0, "DEF_A": 0,
        },
    })
    franchise_players_data_collection.insert_one({
        "franchise_id": str(fid),
        "player_id": "zero",
        "meta": {"first_name": "Cy", "last_name": "Zero", "position": "C", "year": "Freshman", "jersey": 0},
        "season": {"GP": 0, "PTS": 0, "FGA": 0, "3PTA": 0, "FTA": 0, "DEF_A": 0},
    })
    franchise_players_data_collection.insert_one({
        "franchise_id": str(fid),
        "player_id": "bench",
        "meta": {"first_name": "Not", "last_name": "Roster", "position": "PF"},
        "season": {"GP": 5, "PTS": 40, "FGA": 10, "FGM": 5},
    })
    return fid


def test_player_stats_bases_zero_attempts_and_zero_games(caplog, monkeypatch):
    monkeypatch.setenv("GOB_SQLITE_QUERY_LOG", "1")
    fid = seed()
    with caplog.at_level(logging.WARNING, logger="BackEnd.persistence.sqlite_collection"):
        response = client.get("/franchise/player-stats", params={"franchise_id": str(fid), "team_id": str(TEAM)})
    assert response.status_code == 200
    body = response.json()
    ids = [row["player_id"] for row in body["players"]]
    assert ids == ["ada", "zero"]
    ada = body["players"][0]
    assert ada["name"] == "Ada Ace"
    assert ada["position"] == "SG"
    assert ada["year"] == "JR"
    assert ada["jersey"] == 23
    assert ada["totals"]["PTS"] == 22
    assert ada["totals"]["GP"] == 2
    assert ada["totals"]["MIN"] == 31
    assert ada["per_game"]["GP"] == 2
    assert ada["per_game"]["PTS"] == 11
    assert ada["per_game"]["MIN"] == 15.5
    assert ada["rates"]["fg_pct"] == 40
    assert ada["rates"]["tp_pct"] is None
    assert ada["rates"]["ft_pct"] == 0
    assert ada["rates"]["def_pct"] is None
    zero = body["players"][1]
    assert zero["totals"]["PTS"] == 0
    assert zero["totals"]["GP"] == 0
    assert zero["per_game"]["GP"] == 0
    assert zero["per_game"]["PTS"] is None
    assert zero["per_game"]["FGA"] is None
    assert zero["rates"]["fg_pct"] is None
    assert zero["rates"]["tp_pct"] is None
    assert zero["rates"]["ft_pct"] is None
    assert zero["rates"]["def_pct"] is None
    # The store is chosen once per process; another test can leave GOB_PERSISTENCE
    # set while this process still runs on mongomock.
    if type(get_store()).__name__ == "SqliteStore":
        player_lines = [
            record.getMessage()
            for record in caplog.records
            if "franchise_players_data" in record.getMessage()
        ]
        assert player_lines
        assert any("decoded=False" in line for line in player_lines)


def test_player_stats_missing_franchise_and_bad_team():
    fid = seed()
    missing = client.get("/franchise/player-stats", params={
        "franchise_id": str(ObjectId()),
        "team_id": str(TEAM),
    })
    assert missing.status_code == 404
    bad = client.get("/franchise/player-stats", params={"franchise_id": str(fid), "team_id": "nope"})
    assert bad.status_code == 400
