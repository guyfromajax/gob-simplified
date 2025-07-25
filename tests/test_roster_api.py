from fastapi.testclient import TestClient
from BackEnd.api.api import app
from BackEnd.db import tournaments_collection, players_collection, teams_collection
from bson import ObjectId

client = TestClient(app)

def make_player(idx, team):
    return {
        "_id": f"p{idx}",
        "first_name": f"T{idx}",
        "last_name": "Player",
        "team": team,
        "attributes": {k: 1 for k in ["SC","SH","ID","OD","PS","BH","RB","AG","ST","ND","IQ","FT","NG"]},
    }

def test_roster_single_game_mode():
    players_collection.delete_many({})
    teams_collection.delete_many({})
    sample_players = [make_player(i, "Lancaster") for i in range(3)]
    players_collection.insert_many(sample_players)
    teams_collection.insert_one({"name": "Lancaster", "player_ids": [p["_id"] for p in sample_players]})

    resp = client.get("/roster/Lancaster")
    assert resp.status_code == 200
    data = resp.json()
    assert data["team_name"] == "Lancaster"
    assert len(data["players"]) > 0


def test_roster_with_tournament_id():
    tournaments_collection.delete_many({})
    # create minimal tournament doc; roster data is no longer stored
    tid = tournaments_collection.insert_one({"user_team_id": "Lancaster"}).inserted_id

    # roster should load correctly even when tournament_id is provided
    players_collection.delete_many({})
    teams_collection.delete_many({})
    sample_players = [make_player(i, "Lancaster") for i in range(2)]
    players_collection.insert_many(sample_players)
    teams_collection.insert_one({"name": "Lancaster", "player_ids": [p["_id"] for p in sample_players]})

    resp = client.get(f"/roster/Lancaster?tournament_id={tid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["team_name"] == "Lancaster"
    assert len(data["players"]) == 2

    # invalid team even when tournament_id provided
    resp = client.get(f"/roster/UnknownTeam?tournament_id={tid}")
    assert resp.status_code == 404
