from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from BackEnd.api.api import app
from BackEnd.api import franchise_routes
from BackEnd.db import db
from bson import ObjectId

client = TestClient(app)

def setup_franchise():
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    ids = [ObjectId() for _ in range(4)]
    teams = [
        {"_id": ids[0], "name": "A", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": ids[1], "name": "B", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": ids[2], "name": "C", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": ids[3], "name": "D", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
    ]
    db.teams.insert_many(teams)
    schedule = [[(ids[0], ids[1]), (ids[2], ids[3])]]
    fid = db.franchises.insert_one({"schedule": schedule, "week": 1}).inserted_id
    return str(fid), ids

def test_complete_week_saves_and_simulates():
    franchise_id, ids = setup_franchise()
    payload = {
        "franchise_id": franchise_id,
        "week": 1,
        "result": {"team1_id": "A", "team2_id": "B", "team1_score": 70, "team2_score": 60},
    }
    res = client.post("/franchise/complete-week", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) == 2

    team_a = db.teams.find_one({"_id": ids[0]})
    team_b = db.teams.find_one({"_id": ids[1]})
    assert team_a["record"]["W"] == 1
    assert team_b["record"]["L"] == 1
    assert team_a["PF"] == 70
    assert team_b["PF"] == 60

    # Idempotent second call
    res2 = client.post("/franchise/complete-week", json=payload)
    assert res2.status_code == 200
    team_a2 = db.teams.find_one({"_id": ids[0]})
    assert team_a2["record"]["W"] == 1
    games = list(db.games.find({"week": 1, "$or": [{"team1_id": ids[0], "team2_id": ids[1]}, {"team1_id": ids[1], "team2_id": ids[0]}]}))
    assert len(games) == 1

    franchise_doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
    assert franchise_doc["week"] == 2
    assert "1" in franchise_doc.get("results", {})
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})


def test_complete_week_accepts_canonical_team_ids_single_word():
    """Regression: Play Quarter sends LANCASTER / SOUTH_LANCASTER; backend must resolve via name."""
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    id_l = ObjectId()
    id_sl = ObjectId()
    db.teams.insert_many([
        {"_id": id_l, "name": "Lancaster", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": id_sl, "name": "South Lancaster", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
    ])
    fid = db.franchises.insert_one({
        "schedule": [[(id_l, id_sl)]],
        "week": 1,
    }).inserted_id
    payload = {
        "franchise_id": str(fid),
        "week": 1,
        "result": {
            "team1_id": "LANCASTER",
            "team2_id": "SOUTH_LANCASTER",
            "team1_score": 76,
            "team2_score": 59,
        },
    }
    res = client.post("/franchise/complete-week", json=payload)
    assert res.status_code == 200, res.json()
    data = res.json()
    assert len(data["results"]) >= 1
    lancaster = db.teams.find_one({"_id": id_l})
    south_lancaster = db.teams.find_one({"_id": id_sl})
    assert lancaster["record"]["W"] == 1
    assert south_lancaster["record"]["L"] == 1
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})


def test_complete_week_accepts_canonical_team_ids_multi_word():
    """Regression: canonical keys with underscores (FOUR_CORNERS, LITTLE_YORK) resolve to team name."""
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    id_fc = ObjectId()
    id_ly = ObjectId()
    db.teams.insert_many([
        {"_id": id_fc, "name": "Four Corners", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
        {"_id": id_ly, "name": "Little York", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0},
    ])
    fid = db.franchises.insert_one({
        "schedule": [[(id_fc, id_ly)]],
        "week": 1,
    }).inserted_id
    payload = {
        "franchise_id": str(fid),
        "week": 1,
        "result": {
            "team1_id": "FOUR_CORNERS",
            "team2_id": "LITTLE_YORK",
            "team1_score": 80,
            "team2_score": 72,
        },
    }
    res = client.post("/franchise/complete-week", json=payload)
    assert res.status_code == 200, res.json()
    data = res.json()
    assert len(data["results"]) >= 1
    fc = db.teams.find_one({"_id": id_fc})
    ly = db.teams.find_one({"_id": id_ly})
    assert fc["record"]["W"] == 1
    assert ly["record"]["L"] == 1
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})


def test_normalize_team_id_canonical_single_word_no_mongo():
    """Unit test: LANCASTER (no underscore) resolves via canonical->name without needing MongoDB."""
    id_lancaster = ObjectId()
    id_south_lancaster = ObjectId()
    call_count = [0]

    def fake_find_one(query):
        call_count[0] += 1
        # First call: by _id/name/code -> miss for "LANCASTER" / "SOUTH_LANCASTER"
        if "$or" in query:
            return None
        # Second call: by name after .replace("_", " ").title()
        if query.get("name") == "Lancaster":
            return {"_id": id_lancaster}
        if query.get("name") == "South Lancaster":
            return {"_id": id_south_lancaster}
        return None

    with patch.object(franchise_routes.db, "teams") as mock_teams:
        mock_teams.find_one.side_effect = fake_find_one
        out1 = franchise_routes._normalize_team_id("LANCASTER")
        out2 = franchise_routes._normalize_team_id("SOUTH_LANCASTER")
    assert out1 == id_lancaster
    assert out2 == id_south_lancaster


def test_normalize_team_id_canonical_multi_word_no_mongo():
    """Unit test: FOUR_CORNERS, LITTLE_YORK resolve via canonical->name without needing MongoDB."""
    id_fc = ObjectId()
    id_ly = ObjectId()

    def fake_find_one(query):
        if "$or" in query:
            return None
        if query.get("name") == "Four Corners":
            return {"_id": id_fc}
        if query.get("name") == "Little York":
            return {"_id": id_ly}
        return None

    with patch.object(franchise_routes.db, "teams") as mock_teams:
        mock_teams.find_one.side_effect = fake_find_one
        out1 = franchise_routes._normalize_team_id("FOUR_CORNERS")
        out2 = franchise_routes._normalize_team_id("LITTLE_YORK")
    assert out1 == id_fc
    assert out2 == id_ly


def test_merge_phase_a_user_row_replaces_same_matchup():
    """User row merge overwrites the same away/home pairing (order-insensitive keys)."""
    existing = [
        {"away_id": "a", "home_id": "b", "away_score": 1, "home_score": 2},
        {"away_id": "c", "home_id": "d", "away_score": 3, "home_score": 4},
    ]
    user_row = {"away_id": "b", "home_id": "a", "away_score": 70, "home_score": 60}
    merged = franchise_routes._merge_phase_a_user_row_into_week_results(existing, user_row)
    assert len(merged) == 2
    ab = next(x for x in merged if set(map(str, [x["away_id"], x["home_id"]])) == {"a", "b"})
    assert ab["away_score"] == 70
    assert ab["home_score"] == 60

