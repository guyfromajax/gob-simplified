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


def test_week_advance_shows_the_new_box_score_without_clearing_the_cache():
    """A new result must invalidate the game-id map. Do not clear it by hand."""
    from BackEnd.utils import schedule_browse as browse

    fid = seed()
    before = client.get(
        "/franchise/team-detail",
        params={"franchise_id": str(fid), "team_id": str(USER)},
    )
    assert before.status_code == 200, before.text
    assert all(row["week"] != 9 for row in before.json()["results"])
    assert str(fid) in browse._GAME_IDS

    doc = db.franchises.find_one({"_id": fid})
    schedule = list(doc["schedule"])
    while len(schedule) < 9:
        schedule.append([])
    schedule[8] = [[str(OTHER), str(USER)]]
    results = dict(doc["results"])
    results["9"] = [{
        "away_id": str(OTHER),
        "home_id": str(USER),
        "away_score": 55,
        "home_score": 77,
    }]
    db.franchises.update_one(
        {"_id": fid},
        {"$set": {"schedule": schedule, "results": results, "week": 9}},
    )
    inserted = db.games.insert_one({
        "franchise_id": str(fid),
        "week": 9,
        "away_team_id": "YORK",
        "home_team_id": "LANCASTER",
    }).inserted_id

    after = client.get(
        "/franchise/team-detail",
        params={"franchise_id": str(fid), "team_id": str(USER)},
    )
    assert after.status_code == 200, after.text
    week9 = [row for row in after.json()["results"] if row["week"] == 9]
    assert len(week9) == 1
    assert week9[0]["game_id"] == str(inserted)

    week = client.get("/franchise/schedule/week", params={"franchise_id": str(fid), "week": 9})
    assert week.status_code == 200, week.text
    match = [game for game in week.json()["games"] if game["is_user"]]
    assert len(match) == 1
    assert match[0]["game_id"] == str(inserted)
    assert match[0]["status"] == "complete"

    assert list(browse._GAME_IDS) == [str(fid)]
    assert list(browse._BUNDLES) == [str(fid)]
    assert isinstance(browse._GAME_IDS[str(fid)][0], tuple)
    assert browse._GAME_IDS[str(fid)][0][0] == 9
    assert browse._GAME_IDS[str(fid)][0][3] == 2
