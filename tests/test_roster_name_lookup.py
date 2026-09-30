"""Strategy 3 /roster/{name} lookup on mongomock and SQLite.

The id path (Strategy 1, team_id) and the hyphen-normalized name path must
return the same team. mongomock has no $replaceAll; the helper falls back to a
Python-side match with the same hyphen/lower rules.
"""

from pathlib import Path

from fastapi.testclient import TestClient
from pymongo.errors import OperationFailure

from BackEnd.api.api import app, lookup_team_doc_by_normalized_name
from BackEnd.db import players_collection, teams_collection
from BackEnd.env_config import resolve_database_environment
from BackEnd.persistence.sqlite import SqliteStore

client = TestClient(app)

TEAM_NAME = "Four-Corners-NL"
TEAM_ID = "NAME_LOOKUP_FC"
OBJECTID_SHAPED_MISS = "aaaaaaaaaaaaaaaaaaaaaaaa"


def _sqlite_env(tmp_path: Path):
    return resolve_database_environment(
        pristine_env={
            "GOB_DB_MODE": "mongomock",
            "ENVIRONMENT": "test",
            "MONGO_DB_NAME": "gob-test",
            "GOB_PERSISTENCE": "sqlite",
            "GOB_SQLITE_PATH": str(tmp_path / "save.sqlite"),
        },
        repo_root=tmp_path,
        target_environ={},
    )


def _player(idx, team):
    return {
        "_id": f"nl-p{idx}",
        "first_name": f"N{idx}",
        "last_name": "Lookup",
        "team": team,
        "attributes": {
            k: 1
            for k in (
                "SC",
                "SH",
                "ID",
                "OD",
                "PS",
                "BH",
                "RB",
                "AG",
                "ST",
                "ND",
                "IQ",
                "FT",
                "NG",
            )
        },
    }


def _seed_http_team():
    players_collection.delete_many({"team": TEAM_NAME})
    teams_collection.delete_many({"team_id": TEAM_ID})
    teams_collection.delete_many({"name": TEAM_NAME})
    sample = [_player(i, TEAM_NAME) for i in range(2)]
    players_collection.insert_many(sample)
    teams_collection.insert_one(
        {
            "name": TEAM_NAME,
            "team_id": TEAM_ID,
            "player_ids": [p["_id"] for p in sample],
        }
    )


def test_roster_name_lookup_matches_id_path_mongomock():
    _seed_http_team()
    by_id = client.get(f"/roster/{TEAM_ID}")
    by_name = client.get(f"/roster/{TEAM_NAME}")
    by_spaces = client.get("/roster/four-corners-nl")
    assert by_id.status_code == 200
    assert by_name.status_code == 200
    assert by_spaces.status_code == 200
    assert by_id.json()["team_name"] == TEAM_NAME
    assert by_name.json()["team_name"] == by_id.json()["team_name"]
    assert by_spaces.json()["team_name"] == by_id.json()["team_name"]
    assert len(by_name.json()["players"]) == len(by_id.json()["players"])


def test_roster_unknown_objectid_shaped_identifier_is_404():
    """24-hex strings miss Strategy 2 then used to 500 on mongomock $replaceAll."""
    resp = client.get(f"/roster/{OBJECTID_SHAPED_MISS}")
    assert resp.status_code == 404


def test_name_lookup_matches_id_path_sqlite(tmp_path: Path):
    store = SqliteStore(_sqlite_env(tmp_path))
    store.teams_collection.insert_one(
        {"_id": "t-nl", "name": TEAM_NAME, "team_id": TEAM_ID}
    )
    by_id = store.teams_collection.find_one({"team_id": TEAM_ID})
    by_name = lookup_team_doc_by_normalized_name(store.teams_collection, TEAM_NAME)
    by_spaces = lookup_team_doc_by_normalized_name(
        store.teams_collection, "four corners nl"
    )
    assert by_id["team_id"] == TEAM_ID
    assert by_name["team_id"] == by_id["team_id"]
    assert by_spaces["team_id"] == by_id["team_id"]
    assert by_name["name"] == TEAM_NAME


def test_name_lookup_python_fallback_when_aggregate_rejects_replace_all():
    class _NoReplaceAll:
        def aggregate(self, pipeline):
            raise OperationFailure("Unrecognized expression '$replaceAll'")

        def find(self, query):
            return [
                {"name": "Lancaster", "team_id": "LANCASTER"},
                {"name": TEAM_NAME, "team_id": TEAM_ID},
            ]

    doc = lookup_team_doc_by_normalized_name(_NoReplaceAll(), "four corners nl")
    assert doc["team_id"] == TEAM_ID
    assert doc["name"] == TEAM_NAME
    miss = lookup_team_doc_by_normalized_name(_NoReplaceAll(), OBJECTID_SHAPED_MISS)
    assert miss is None
