from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.api.franchise_routes import get_team_player_stats
from BackEnd.db import db, franchise_players_data_collection
# Note: franchise_state_collection removed - using franchise document instead


client = TestClient(app)


def setup_function(_fn):
    db.franchises.delete_many({})
    db.teams.delete_many({})
    franchise_players_data_collection.delete_many({})
    # Note: franchise_state_collection cleanup removed - no longer used


def seed_franchise():
    fid = db.franchises.insert_one(
        {
            "user_team_id": "Team1",  # Use new approach instead of franchise_state
            "user_team_object_id": "t1",
        }
    ).inserted_id
    franchise_players_data_collection.insert_many(
        [
            {
                "franchise_id": str(fid),
                "player_id": "p1",
                "meta": {"team_id": "t1", "first_name": "A", "last_name": "One"},
                "season": {"PTS": 5},
            },
            {
                "franchise_id": str(fid),
                "player_id": "p2",
                "meta": {"team_id": "t1", "first_name": "B", "last_name": "Two"},
                "season": {"PTS": 10},
            },
            {
                "franchise_id": str(fid),
                "player_id": "p3",
                "meta": {"team_id": "t2", "first_name": "C", "last_name": "Three"},
                "season": {"PTS": 7},
            },
        ]
    )
    return str(fid)


def test_get_team_player_stats_and_endpoints():
    fid = seed_franchise()

    # ensure teams exist for endpoint normalization
    db.teams.insert_many([
        {"_id": "t1", "name": "Team1"},
        {"_id": "t2", "name": "Team2"},
    ])

    players = get_team_player_stats(fid, "t1")
    assert [p["player_id"] for p in players] == ["p2", "p1"]

    resp = client.get(f"/franchise/team-player-stats/t1?franchise_id={fid}&limit=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["players"]) == 1
    assert data["players"][0]["player_id"] == "p2"

    # Test with franchise_id (new approach - franchise document has user_team_id)
    resp = client.get(f"/franchise/team-player-stats?franchise_id={fid}")
    assert resp.status_code == 200
    data2 = resp.json()
    assert [p["player_id"] for p in data2["players"]] == ["p2", "p1"]
