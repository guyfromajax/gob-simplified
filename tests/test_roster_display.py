"""Roster view fields stamped onto GET /roster rows."""

from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.db import players_collection, teams_collection
from BackEnd.utils.db_utils import projected_starting_five_from_payload
from BackEnd.utils.roster_display import apply_lineup_roles, stamp_roster_player

client = TestClient(app)

POSITIONS = ("PG", "SG", "SF", "PF", "C")


def test_stamp_uses_roster_position_and_max_rating():
    row = {
        "_id": "p1",
        "position_ratings": {"PG": 40, "SG": 82, "SF": 60, "PF": 50, "C": 44},
        "training_position": "PF",
        "resolved_training_position": "C",
    }
    stamp_roster_player(row, on_user_team=False, stored_position="")
    assert row["position"] == "SG"
    assert row["rt"] == 82
    assert row["starter"] is False
    assert row["lineup_order"] is None


def test_user_team_training_position_wins_when_stored_position_is_empty():
    row = {
        "position_ratings": {"PG": 90, "SG": 40},
        "resolved_training_position": "PF",
        "training_position": "C",
    }
    stamp_roster_player(row, on_user_team=True, stored_position="--")
    assert row["position"] == "PF"


def test_lineup_order_follows_projected_starting_five():
    players = [
        {"_id": "bench", "name": "Bench"},
        {"_id": "two", "name": "Two"},
        {"_id": "one", "name": "One"},
    ]
    for player in players:
        stamp_roster_player(player, on_user_team=True, stored_position="PG")
    apply_lineup_roles(players, [
        {"player_id": "one"},
        {"player_id": "two"},
    ])
    by_id = {player["_id"]: player for player in players}
    assert by_id["one"]["starter"] is True
    assert by_id["one"]["lineup_order"] == 0
    assert by_id["two"]["lineup_order"] == 1
    assert by_id["bench"]["starter"] is False
    assert by_id["bench"]["lineup_order"] is None


def test_no_projected_lineup_marks_nobody():
    players = [{"_id": "a"}, {"player_id": "b"}]
    apply_lineup_roles(players, [])
    assert [player["starter"] for player in players] == [False, False]
    assert [player["lineup_order"] for player in players] == [None, None]


def test_roster_route_marks_the_same_five_the_sim_would_seat():
    """CPU starting fives come from the autoset selector, not a stored document.

    ``projected_starting_five_from_payload`` is the display path of
    ``build_lineup_from_mongo``. The route stamps ``starter`` from that five.
    Payload order is roster order, so the first row need not be a starter.
    """
    team = "Starter Route FC"
    players_collection.delete_many({"team": team})
    teams_collection.delete_many({"name": team})
    docs = []
    for index in range(12):
        ratings = {pos: 20 for pos in POSITIONS}
        if index < 5:
            ratings[POSITIONS[index]] = 90
        pid = f"uuid-{index:02d}-starter-route"
        attrs = {key: 50 for key in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]}
        attrs["NG"] = 1.0
        docs.append({
            "_id": pid,
            "player_id": pid,
            "first_name": "Start" if index < 5 else "Bench",
            "last_name": str(index),
            "team": team,
            "year": "Junior",
            "attributes": attrs,
            "position_ratings": ratings,
        })
    ordered = list(reversed(docs))
    players_collection.insert_many(ordered)
    teams_collection.insert_one({
        "name": team,
        "team_id": team,
        "player_ids": [player["_id"] for player in ordered],
    })

    response = client.get(f"/roster/{team}?team_id={team}")
    assert response.status_code == 200, response.text
    body = response.json()
    seated = projected_starting_five_from_payload(body["players"])
    marked = [player["_id"] for player in body["players"] if player["starter"]]
    assert len(seated) == 5
    assert set(marked) == set(seated.values())
    assert len(marked) == 5
    orders = {
        player["_id"]: player["lineup_order"]
        for player in body["players"]
        if player["starter"]
    }
    assert sorted(orders.values()) == [0, 1, 2, 3, 4]
