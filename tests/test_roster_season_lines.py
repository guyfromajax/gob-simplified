"""Franchise roster carries the player's season line so the Office can skip /franchise/state."""

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.db import (
    franchise_players_data_collection,
    franchises_collection,
    players_collection,
    teams_collection,
)

client = TestClient(app)

ATTRS = {key: 5 for key in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]}


def test_franchise_roster_attaches_fpd_season_on_read():
    franchises_collection.delete_many({})
    franchise_players_data_collection.delete_many({})
    players_collection.delete_many({"team": "Season Lines FC"})
    teams_collection.delete_many({"name": "Season Lines FC"})

    team_id = teams_collection.insert_one(
        {"name": "Season Lines FC", "player_ids": ["sl-1"], "conference": 1, "region": "A"}
    ).inserted_id
    franchise_id = franchises_collection.insert_one(
        {
            "current_season": 1,
            "week": 3,
            "browse_rev": 0,
            "user_team_id": "Season Lines FC",
            "user_team_object_id": team_id,
        }
    ).inserted_id
    franchise_players_data_collection.insert_one(
        {
            "franchise_id": str(franchise_id),
            "player_id": "sl-1",
            "meta": {
                "first_name": "Ada",
                "last_name": "Keeper",
                "team": "Season Lines FC",
                "year": "Junior",
            },
            "attributes": ATTRS,
            "position_ratings": {"PG": 70},
            "season": {"GP": 4, "PTS": 80, "REB": 12},
        }
    )

    response = client.get(f"/roster/{team_id}?franchise_id={franchise_id}")
    assert response.status_code == 200, response.text
    players = response.json()["players"]
    assert len(players) == 1
    assert players[0]["stats"]["season"]["PTS"] == 80
    assert players[0]["stats"]["season"]["GP"] == 4
    assert players[0]["stats"]["season"]["REB"] == 12
    assert response.headers.get("etag")
