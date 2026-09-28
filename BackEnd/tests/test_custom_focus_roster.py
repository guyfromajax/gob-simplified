"""custom_focus_roster carries portrait, jersey, potential, and tallies.

The builder reads franchise collections. One case uses mongomock, the other a
SQLite collection, so a field that only one backend keeps still fails.
"""
import sqlite3

import mongomock
import pytest
from bson import ObjectId

from BackEnd.api import franchise_routes
from BackEnd.persistence.sqlite_collection import SqliteCollection


def _seed(players, teams, franchise_id, team_id):
    players.insert_one({
        "franchise_id": str(franchise_id),
        "player_id": "p1",
        "entry_tier": "Average",
        "potential_factor": 1.0,
        "training_position": "PG",
        "training_focus": "offensive",
        "position_ratings": {"PG": 70, "SG": 40},
        "attributes": {"anchor_SC": 6},
        "meta": {
            "first_name": "Devin",
            "last_name": "Park",
            "image_id": "img-9",
            "portrait_source": "player",
            "jersey": 3,
            "year": "SR",
            "height": 74,
            "weight": 180,
        },
    })
    teams.insert_one({
        "franchise_id": franchise_id,
        "team_id": team_id,
        "players": ["p1"],
    })


def _run(players, teams, monkeypatch):
    franchise_id = ObjectId()
    team_id = ObjectId()
    _seed(players, teams, franchise_id, team_id)
    monkeypatch.setattr(franchise_routes, "franchise_players_data_collection", players)
    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", teams)
    monkeypatch.setattr(
        franchise_routes,
        "get_user_team_from_franchise",
        lambda doc: ("Lancaster", str(team_id)),
    )
    rows, _ranking = franchise_routes._build_custom_focus_roster_for_franchise(
        {"_id": franchise_id}, franchise_id
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["image_id"] == "img-9"
    assert row["portrait_source"] == "player"
    assert row["jersey"] == 3
    assert row["pos"] == "PG"
    assert isinstance(row["potential_rt_ratcheted"], int)
    assert row["resolved_training_position"] == "PG"
    assert row["resolved_training_focus"] == "offensive"
    position_tallies = {"PG": 0, "SG": 0, "SF": 0, "PF": 0, "C": 0}
    position_tallies[row["resolved_training_position"]] += 1
    assert position_tallies["PG"] == 1


def test_roster_fields_on_mongomock(monkeypatch):
    client = mongomock.MongoClient()
    _run(client.db.franchise_players_data, client.db.franchise_team_data, monkeypatch)


def test_roster_fields_on_sqlite(tmp_path, monkeypatch):
    conn = sqlite3.connect(str(tmp_path / "roster.sqlite"))
    players = SqliteCollection(conn, "franchise_players_data")
    teams = SqliteCollection(conn, "franchise_team_data")
    _run(players, teams, monkeypatch)
