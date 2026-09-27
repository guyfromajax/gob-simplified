"""GET /franchise/schedule/week. One week, server-sorted. Runs on mongomock and SQLite."""

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.db import db, franchise_team_data_collection
from BackEnd.utils.schedule_browse import clear_schedule_browse_cache

client = TestClient(app)

USER = ObjectId()
SISTER = ObjectId()
OTHER = ObjectId()


def setup_function(_fn):
    clear_schedule_browse_cache()
    db.franchises.delete_many({})
    db.teams.delete_many({})
    db.games.delete_many({})
    franchise_team_data_collection.delete_many({})


def _team(oid, name, conference, color, rank):
    db.teams.insert_one({
        "_id": oid,
        "name": name,
        "conference": conference,
        "primary_color": color,
        "team_id": name.upper().replace(" ", "_").replace("-", "_"),
    })


def seed():
    fid = db.franchises.insert_one({
        "user_team_id": "Lancaster",
        "user_team_object_id": str(USER),
        "week": 8,
        "current_season": 1,
        "browse_rev": 2,
        "schedule": [
            [[str(OTHER), str(SISTER)]],
            [],
            [],
            [],
            [],
            [],
            [],
            [
                [str(OTHER), str(SISTER)],
                [str(SISTER), str(OTHER)],
                [str(OTHER), str(USER)],
            ],
        ],
        "results": {
            "8": [{
                "away_id": str(OTHER),
                "home_id": str(USER),
                "away_score": 60,
                "home_score": 70,
            }],
        },
    }).inserted_id
    _team(USER, "Lancaster", 1, "#112233", 4)
    _team(SISTER, "Four-Corners", 2, "#445566", 21)
    _team(OTHER, "York", 8, "#778899", 80)
    for oid, rank in ((USER, 4), (SISTER, 21), (OTHER, 80)):
        franchise_team_data_collection.insert_one({
            "franchise_id": fid,
            "team_id": oid,
            "natl_rank": rank,
        })
    db.games.insert_one({
        "franchise_id": str(fid),
        "week": 8,
        "away_team_id": "YORK",
        "home_team_id": "LANCASTER",
    })
    return fid


def test_week_defaults_sorts_and_marks_the_user_game():
    fid = seed()
    response = client.get("/franchise/schedule/week", params={"franchise_id": str(fid)})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["week"] == 8
    assert body["current_week"] == 8
    assert body["label"] == "Week 8"
    assert body["user_team_id"] == str(USER)
    names = [(row["away"]["name"], row["home"]["name"]) for row in body["games"]]
    assert names == [
        ("York", "Lancaster"),
        ("Four-Corners", "York"),
        ("York", "Four-Corners"),
    ]
    user = body["games"][0]
    assert user["is_user"] is True
    assert user["status"] == "complete"
    assert user["away_score"] == 60
    assert user["home_score"] == 70
    assert user["game_id"]
    assert user["home"]["natl_rank"] == 4
    assert user["home"]["wins"] == 1
    assert user["home"]["losses"] == 0
    assert user["away"]["natl_rank"] == 80
    upcoming = body["games"][1]
    assert upcoming["status"] == "scheduled"
    assert upcoming["away_score"] is None
    assert upcoming["game_id"] is None
    catalog = {row["week"]: row["enabled"] for row in body["weeks"]}
    assert catalog[1] is True
    assert catalog[2] is False
    assert catalog[8] is True
    assert catalog[27] is False
    assert len(body["weeks"]) == 34

    asked = client.get("/franchise/schedule/week", params={"franchise_id": str(fid), "week": 1})
    assert asked.status_code == 200
    assert asked.json()["week"] == 1
    assert len(asked.json()["games"]) == 1

    bad = client.get("/franchise/schedule/week", params={"franchise_id": str(fid), "week": 40})
    assert bad.status_code == 422
