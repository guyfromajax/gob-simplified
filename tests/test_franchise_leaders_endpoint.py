from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.api.franchise_routes import get_leaders
from BackEnd.db import db, franchise_players_data_collection

client = TestClient(app)


def setup_function(_fn):
    db.franchises.delete_many({})
    franchise_players_data_collection.delete_many({})


def seed_franchise():
    fid = db.franchises.insert_one({}).inserted_id
    franchise_players_data_collection.insert_many(
        [
            {
                "franchise_id": str(fid),
                "player_id": "p1",
                "meta": {"first_name": "Ann", "last_name": "Alpha", "team": "A"},
                "season": {"GP": 4, "PTS": 20},
            },
            {
                "franchise_id": str(fid),
                "player_id": "p2",
                "meta": {"first_name": "Bob", "last_name": "Beta", "team": "B"},
                "season": {"GP": 2, "PTS": 15},
            },
            {
                "franchise_id": str(fid),
                "player_id": "p3",
                "meta": {"first_name": "Cara", "last_name": "Gamma", "team": "C"},
                "season": {"GP": 1, "PTS": 5},
            },
        ]
    )
    return str(fid)


def test_missed_games_drop_a_player_who_cleared_the_old_player_gp_floor():
    """Team played 10. A player with 4 GP and 40 FGA cleared 5*GP and misses 5*team games."""
    fid = db.franchises.insert_one({}).inserted_id
    team = "69a6fcb68d2c56aa82e48a54"
    other = "69a6fcb68d2c56aa82e48a61"
    db.franchises.update_one(
        {"_id": fid},
        {
            "$set": {
                "results": {
                    str(week): [
                        {
                            "away_id": team,
                            "home_id": other,
                            "away_score": 70,
                            "home_score": 60,
                        }
                    ]
                    for week in range(1, 11)
                }
            }
        },
    )
    franchise_players_data_collection.insert_many(
        [
            {
                "franchise_id": str(fid),
                "player_id": "missed",
                "meta": {"first_name": "Mia", "last_name": "Miss", "team": "Lancaster", "team_id": team},
                "season": {"GP": 4, "FGM": 20, "FGA": 40, "DEF_S": 20, "DEF_A": 40},
                "career": {"GP": 4, "FGM": 20, "FGA": 40, "DEF_S": 20, "DEF_A": 40},
            },
            {
                "franchise_id": str(fid),
                "player_id": "full",
                "meta": {"first_name": "Finn", "last_name": "Full", "team": "Lancaster", "team_id": team},
                "season": {"GP": 10, "FGM": 20, "FGA": 50, "DEF_S": 40, "DEF_A": 80},
                "career": {"GP": 10, "FGM": 20, "FGA": 50, "DEF_S": 40, "DEF_A": 80},
            },
        ]
    )

    season = get_leaders(str(fid), scope="season", stat="FG%", limit=10)
    assert [p["player_id"] for p in season] == ["full"]

    defense = get_leaders(str(fid), scope="season", stat="DEF%", limit=10)
    assert [p["player_id"] for p in defense] == ["full"]

    career = get_leaders(str(fid), scope="career", stat="FG%", limit=10)
    assert {p["player_id"] for p in career} == {"missed", "full"}

    resp = client.get(f"/franchise/leaders?franchise_id={fid}&scope=season")
    assert resp.status_code == 200
    names = [row["name"] for row in resp.json()["FG%"]]
    assert names == ["Finn Full"]


def test_get_leaders_and_endpoint():
    fid = seed_franchise()

    top = get_leaders(fid, stat="PTS", limit=2)
    assert [p["player_id"] for p in top] == ["p2", "p1"]
    assert [p["value"] for p in top] == [7.5, 5.0]

    resp = client.get(f"/franchise/leaders?franchise_id={fid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["PTS"][0]["name"] == "Bob Beta"
    assert data["PTS"][0]["value"] == 7.5
    assert data["PTS"][1]["name"] == "Ann Alpha"
    assert data["PTS"][1]["value"] == 5.0
    assert data["PTS"][0]["team_id"] == ""
    assert data["PTS"][0]["position"] == ""
    assert data["PTS"][0]["year"] == ""


def test_basis_totals_and_per_game_and_qualification_caption():
    fid = seed_franchise()
    omitted = get_leaders(fid, stat="PTS", limit=2)
    per_game = get_leaders(fid, stat="PTS", limit=2, basis="per_game")
    assert [row["value"] for row in omitted] == [row["value"] for row in per_game] == [7.5, 5.0]

    totals = get_leaders(fid, stat="PTS", limit=2, basis="totals")
    assert [row["player_id"] for row in totals] == ["p1", "p2"]
    assert [row["value"] for row in totals] == [20, 15]

    franchise_players_data_collection.update_one(
        {"player_id": "p1"},
        {"$set": {"meta.position": "PG", "meta.year": "SR", "meta.team_id": "team-a", "season.STL": 8}},
    )
    steals = get_leaders(fid, stat="STL", limit=1)
    assert steals[0]["value"] == 8
    assert steals[0]["position"] == "PG"
    assert steals[0]["year"] == "SR"
    assert steals[0]["team_id"] == "team-a"
    per_steal = get_leaders(fid, stat="STL", limit=1, basis="per_game")
    assert per_steal[0]["value"] == 2.0

    qualified = db.franchises.insert_one({}).inserted_id
    team = "69a6fcb68d2c56aa82e48a54"
    other = "69a6fcb68d2c56aa82e48a61"
    db.franchises.update_one(
        {"_id": qualified},
        {"$set": {"results": {str(week): [{
            "away_id": team, "home_id": other, "away_score": 70, "home_score": 60,
        }] for week in range(1, 3)}}},
    )
    franchise_players_data_collection.insert_one({
        "franchise_id": str(qualified),
        "player_id": "shooter",
        "meta": {"first_name": "Sue", "last_name": "Shot", "team": "Lancaster", "team_id": team, "position": "SG"},
        "season": {"GP": 2, "FGM": 10, "FGA": 20, "DEF_S": 8, "DEF_A": 12},
        "career": {"GP": 2, "FGM": 10, "FGA": 20, "DEF_S": 8, "DEF_A": 12},
    })
    season = get_leaders(str(qualified), scope="season", stat="FG%", limit=5)
    assert season[0]["qualification_caption"] == "min 5 FGA per team game"
    defense = get_leaders(str(qualified), scope="season", stat="DEF%", limit=5)
    assert defense[0]["qualification_caption"] == "min 6 DEF_A per team game"
    career = get_leaders(str(qualified), scope="career", stat="FG%", limit=5)
    assert all("qualification_caption" not in row for row in career)

    resp = client.get(f"/franchise/leaders?franchise_id={fid}&basis=totals")
    assert resp.status_code == 200
    assert resp.json()["PTS"][0]["name"] == "Ann Alpha"
    assert resp.json()["PTS"][0]["value"] == 20
