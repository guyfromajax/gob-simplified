"""consume_moment pulls a pending championship item; a second Office load has none.

Runs on mongomock and SQLite (desktop path). Does not touch enqueue.
"""

from bson import ObjectId
import pytest

from BackEnd.api import franchise_routes as fr
from BackEnd.persistence import create_store
from BackEnd.utils import franchise_championship_moments as fcm
from tests.test_persistence_adapter import _mongomock_env

USER = "aaaaaaaaaaaaaaaaaaaaaaaa"


def _store_env(kind, tmp_path):
    if kind == "mongo":
        return _mongomock_env(tmp_path)
    return _mongomock_env(
        tmp_path,
        GOB_PERSISTENCE="sqlite",
        GOB_SQLITE_PATH=str(tmp_path / "champ-consume.sqlite"),
    )


@pytest.fixture(params=["mongo", "sqlite"])
def store(request, tmp_path, monkeypatch):
    built = create_store(_store_env(request.param, tmp_path))
    monkeypatch.setattr(fcm, "db", built.db)
    monkeypatch.setattr(fr, "db", built.db)
    return built


def _moment(mid="cm-spot-1", typ="trophy_spotlight"):
    return {
        "id": mid,
        "type": typ,
        "season": 3,
        "conference": 3,
        "winner_team_name": "Lancaster",
        "winner_primary_color": "#27408E",
        "user_is_winner": True,
    }


def _seed(store, moments):
    fid = ObjectId()
    store.franchises_collection.insert_one(
        {
            "_id": fid,
            "user_id": "coach-1",
            "current_season": 3,
            "week": 27,
            "pending_championship_moments": moments,
            "user_team_object_id": ObjectId(USER),
        }
    )
    return store.franchises_collection.find_one({"_id": fid})


def _office_kinds(store, doc):
    pending = fcm.list_moments(doc)
    response = {
        "pending_championship_moments": pending,
        "office_digest": {},
        "team_name_map": {},
    }
    queue = fr._build_moment_queue_for_command_center(
        response,
        doc,
        USER,
        {"conference": 3, "region": "B"},
        27,
        {
            "archetype_evolution_pending": "",
            "lead_archetype": "",
            "archetype_reveal_seen": True,
        },
        is_local=False,
    )
    return [m["kind"] for m in queue["moments_for_this_visit"]]


@pytest.mark.parametrize("is_local", [False, True])
def test_consume_moment_removes_and_second_office_has_no_championship(store, is_local):
    moment = _moment()
    doc = _seed(store, [moment])
    fid = doc["_id"]
    assert [m["id"] for m in fcm.list_moments(doc)] == ["cm-spot-1"]
    assert "championship" in _office_kinds(store, doc)

    assert fcm.consume_moment(fid, "cm-spot-1") is True

    after = store.franchises_collection.find_one({"_id": fid})
    assert fcm.list_moments(after) == []

    pending = fcm.list_moments(after)
    response = {
        "pending_championship_moments": pending,
        "office_digest": {},
        "team_name_map": {},
    }
    queue = fr._build_moment_queue_for_command_center(
        response,
        after,
        USER,
        {"conference": 3, "region": "B"},
        27,
        {
            "archetype_evolution_pending": "",
            "lead_archetype": "",
            "archetype_reveal_seen": True,
        },
        is_local=is_local,
    )
    kinds = [m["kind"] for m in queue["moments_for_this_visit"]]
    assert "championship" not in kinds
    fcm.consume_moment(fid, "cm-spot-1")
    still = store.franchises_collection.find_one({"_id": fid})
    assert fcm.list_moments(still) == []


def test_sqlite_pull_matches_subdocument_query():
    from BackEnd.persistence.sqlite_query import apply_update

    doc = {
        "pending_championship_moments": [
            {"id": "cm-spot-1", "type": "trophy_spotlight", "season": 3},
            {"id": "cm-conf-1", "type": "conference_championship", "season": 3},
        ]
    }
    apply_update(doc, {"$pull": {"pending_championship_moments": {"id": "cm-spot-1"}}})
    assert [m["id"] for m in doc["pending_championship_moments"]] == ["cm-conf-1"]


def test_consume_one_leaves_the_other_championship(store):
    doc = _seed(
        store,
        [
            _moment("cm-spot-1", "trophy_spotlight"),
            _moment("cm-conf-1", "conference_championship"),
        ],
    )
    fid = doc["_id"]
    assert fcm.consume_moment(fid, "cm-spot-1") is True
    after = store.franchises_collection.find_one({"_id": fid})
    left = fcm.list_moments(after)
    assert [m["id"] for m in left] == ["cm-conf-1"]
    assert "championship" in _office_kinds(store, after)
