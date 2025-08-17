from fastapi.testclient import TestClient
from bson import ObjectId

from BackEnd.api.api import app
from BackEnd.db import tournaments_collection


client = TestClient(app)


def setup_function(fn):
    tournaments_collection.delete_many({})


def test_tournament_state_casts_applied_games_to_strings():
    oid = ObjectId()
    tid = tournaments_collection.insert_one({"applied_games": [oid]}).inserted_id

    resp = client.get(f"/tournament/state/{tid}")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["applied_games"] == [str(oid)]
