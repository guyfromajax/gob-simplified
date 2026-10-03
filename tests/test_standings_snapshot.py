"""Standings snapshot matches the live rows, including scope filters."""

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.api.franchise_routes import _standings_rows_from_doc
from BackEnd.db import franchise_team_data_collection, franchises_collection, teams_collection
from BackEnd.persistence import get_store
from BackEnd.utils.standings_snapshot import fresh_rows, note_standings_stale

client = TestClient(app)


def _game(away, home, away_score, home_score):
    return {
        "away_id": str(away),
        "home_id": str(home),
        "away_score": away_score,
        "home_score": home_score,
    }


def _seed():
    franchises_collection.delete_many({})
    teams_collection.delete_many({"name": {"$in": ["Alpha", "Beta", "Gamma", "Delta"]}})
    get_store().standings_snapshots_collection.delete_many({})
    ids = {
        "Alpha": ObjectId(),
        "Beta": ObjectId(),
        "Gamma": ObjectId(),
        "Delta": ObjectId(),
    }
    specs = [
        ("Alpha", 1, "A", 4),
        ("Beta", 1, "A", 20),
        ("Gamma", 2, "A", 8),
        ("Delta", 3, "B", 40),
    ]
    for name, conference, region, rank in specs:
        teams_collection.insert_one({
            "_id": ids[name],
            "name": name,
            "team_id": name,
            "conference": conference,
            "region": region,
            "primary_color": "#112233",
        })
    franchise_id = franchises_collection.insert_one({
        "current_season": 1,
        "week": 3,
        "browse_rev": 1,
        "results": {
            "1": [_game(ids["Alpha"], ids["Beta"], 80, 70)],
            "2": [_game(ids["Gamma"], ids["Alpha"], 60, 70)],
        },
        "schedule": [
            [[str(ids["Alpha"]), str(ids["Beta"])]],
            [[str(ids["Gamma"]), str(ids["Alpha"])]],
            [[str(ids["Alpha"]), str(ids["Beta"])], [str(ids["Gamma"]), str(ids["Delta"])]],
        ],
    }).inserted_id
    franchise_team_data_collection.delete_many({"franchise_id": franchise_id})
    for name, _conference, _region, rank in specs:
        franchise_team_data_collection.insert_one({
            "franchise_id": franchise_id,
            "team_id": ids[name],
            "natl_rank": rank,
        })
    return franchise_id, ids


def _rows(body):
    return body["standings"]


def test_snapshot_matches_live_rows_for_every_scope():
    franchise_id, ids = _seed()
    doc = franchises_collection.find_one({"_id": franchise_id})
    live = _standings_rows_from_doc(doc)
    by_name = {row["name"]: row for row in live}
    assert by_name["Alpha"]["W"] == 2
    assert by_name["Alpha"]["L"] == 0
    assert by_name["Alpha"]["pct"] == 1.0
    assert by_name["Alpha"]["differential"] == 20
    assert by_name["Alpha"]["streak"] == "W2"
    assert by_name["Alpha"]["next_opponent_id"] == str(ids["Beta"])
    assert by_name["Beta"]["streak"] == "L1"
    assert by_name["Beta"]["pct"] == 0.0
    assert by_name["Gamma"]["differential"] == -10
    assert by_name["Gamma"]["streak"] == "L1"

    url = f"/franchise/standings?franchise_id={franchise_id}"
    first = client.get(url)
    assert first.status_code == 200, first.text
    assert _rows(first.json()) == live
    second = client.get(url)
    assert _rows(second.json()) == live
    assert fresh_rows(str(franchise_id), week=3, season=1) == live

    conference = client.get(url + f"&scope=conference&team_id={ids['Alpha']}")
    assert conference.status_code == 200
    assert [row["name"] for row in _rows(conference.json())] == [
        row["name"] for row in live if row["conference"] == 1
    ]
    region_scope = client.get(url + f"&scope=region&team_id={ids['Alpha']}")
    assert [row["name"] for row in _rows(region_scope.json())] == [
        row["name"] for row in live if row["region"] == "A"
    ]
    user_region = client.get(url + f"&scope=user_region&team_id={ids['Alpha']}")
    body = user_region.json()
    assert body["sister_conference"] == 2
    assert {row["name"] for row in _rows(body)} == {"Alpha", "Beta", "Gamma"}
    narrowed = client.get(url + "&region=B")
    assert [row["name"] for row in _rows(narrowed.json())] == ["Delta"]


def test_stale_mark_drops_the_snapshot_when_results_change():
    franchise_id, ids = _seed()
    url = f"/franchise/standings?franchise_id={franchise_id}"
    before = _rows(client.get(url).json())
    franchises_collection.update_one(
        {"_id": franchise_id},
        {"$set": {"results.1": [_game(ids["Alpha"], ids["Beta"], 60, 70)]}},
    )
    assert _rows(client.get(url).json()) == before
    note_standings_stale(str(franchise_id))
    after = _rows(client.get(url).json())
    assert after != before
    beta = next(row for row in after if row["name"] == "Beta")
    assert beta["W"] == 1
    assert beta["streak"] == "W1"
