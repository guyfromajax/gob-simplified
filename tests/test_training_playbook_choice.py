"""The Training playbook choice is a saved setting on the franchise (Jamie, 2026-10-03).

Custom Playbook stays the default for every later training, training camp and the next
season included, until the user switches back to Current Playbooks, and the plays in the
custom playbook carry forward with it. It is a setting only: saving it never runs training.

The route is owner-gated. ``tests/conftest.py`` overrides auth for every test, so the
ownership tests here set the user explicitly and run the real
``verify_franchise_owned_by_user``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api import franchise_routes as fr
from BackEnd.api.api import app
from BackEnd.db import db
from BackEnd.persistence import create_store
from BackEnd.utils.auth import get_current_user
from tests.test_persistence_adapter import _mongomock_env, _sqlite_env

OWNER = "playbook-choice-owner"
FIELD = fr.TRAINING_PLAYBOOK_CHOICE_FIELD
FOCUS = {"offense": ["m-1", "s-4"], "defense": ["man", "zone-23"]}
CURRENT = {"mode": "current-playbooks", "focus": None}
client = TestClient(app)


@pytest.fixture
def as_user():
    def _as(user_id):
        app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id}

    yield _as
    app.dependency_overrides.pop(get_current_user, None)


def _franchise(**fields) -> str:
    oid = ObjectId()
    doc = {"_id": oid, "user_id": OWNER, "week": 5, "current_season": 1, "user_team_id": "A", "browse_rev": 3}
    doc.update(fields)
    db.franchises.insert_one(doc)
    return str(oid)


def _patch(fid: str, mode: str, focus=None):
    body = {"franchise_id": fid, "mode": mode}
    if focus is not None:
        body["focus"] = focus
    return client.patch("/franchise/training-playbook-choice", json=body)


def _stored(fid: str) -> dict:
    return db.franchises.find_one({"_id": ObjectId(fid)})


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def test_a_franchise_with_nothing_saved_trains_current_playbooks():
    assert fr._training_playbook_choice({}) == CURRENT
    assert fr._training_playbook_choice(None) == CURRENT


@pytest.mark.parametrize("saved", [
    {"mode": "custom"},
    {"mode": "custom", "focus": {"offense": ["m-1"], "defense": []}},
    {"mode": "custom", "focus": {"offense": [], "defense": ["man"]}},
    {"mode": "custom", "focus": "m-1"},
    {"mode": "all-plays-even", "focus": FOCUS},
    "custom",
])
def test_a_custom_choice_needs_an_offense_play_and_a_defense(saved):
    assert fr._training_playbook_choice({FIELD: saved}) == CURRENT


def test_play_ids_are_strings_in_order_without_repeats():
    saved = {"mode": "custom", "focus": {"offense": [7, "m-1", " m-1 ", "", None, "s-4"], "defense": ["man", "man"]}}
    assert fr._training_playbook_choice({FIELD: saved}) == {
        "mode": "custom",
        "focus": {"offense": ["7", "m-1", "s-4"], "defense": ["man"]},
    }


# ---------------------------------------------------------------------------
# The route
# ---------------------------------------------------------------------------

def test_saving_custom_writes_only_the_choice(as_user):
    as_user(OWNER)
    fid = _franchise()
    before = _stored(fid)
    res = _patch(fid, "custom", FOCUS)
    assert res.status_code == 200, res.text
    assert res.json() == {"mode": "custom", "focus": FOCUS}
    after = _stored(fid)
    assert after[FIELD] == {"mode": "custom", "focus": FOCUS}
    after.pop(FIELD)
    # Nothing else on the franchise moved: not the week, not training status, not browse_rev.
    assert after == before


def test_switching_back_to_current_playbooks_removes_the_field(as_user):
    as_user(OWNER)
    fid = _franchise(**{FIELD: {"mode": "custom", "focus": FOCUS}})
    res = _patch(fid, "current-playbooks")
    assert res.status_code == 200, res.text
    assert res.json() == CURRENT
    assert FIELD not in _stored(fid)


def test_the_choice_and_its_plays_carry_forward_through_weeks_camp_and_seasons(as_user):
    as_user(OWNER)
    fid = _franchise(week=9, current_season=1)
    assert _patch(fid, "custom", FOCUS).status_code == 200
    saved = {"mode": "custom", "focus": FOCUS}
    # Later weeks, then training camp (week 1) of the next two seasons: the franchise
    # document only ever takes $set updates, and none of them names this field.
    for week, season in ((10, 1), (26, 1), (36, 1), (1, 2), (14, 2), (1, 3)):
        db.franchises.update_one(
            {"_id": ObjectId(fid)},
            {"$set": {"week": week, "current_season": season, "training_status": {}}},
        )
        res = client.get("/franchise/training-points", params={"franchise_id": fid})
        assert res.status_code == 200, res.text
        assert res.json()["training_playbook_choice"] == saved, (week, season)
    # ...until the user switches back.
    assert _patch(fid, "current-playbooks").status_code == 200
    res = client.get("/franchise/training-points", params={"franchise_id": fid})
    assert res.json()["training_playbook_choice"] == CURRENT


def test_training_points_reports_current_playbooks_when_nothing_is_saved():
    fid = _franchise()
    res = client.get("/franchise/training-points", params={"franchise_id": fid})
    assert res.status_code == 200, res.text
    assert res.json()["training_playbook_choice"] == CURRENT


@pytest.mark.parametrize("focus", [None, {"offense": ["m-1"], "defense": []}, {"offense": [], "defense": ["man"]}])
def test_an_empty_custom_playbook_is_refused_and_changes_nothing(as_user, focus):
    as_user(OWNER)
    fid = _franchise(**{FIELD: {"mode": "custom", "focus": FOCUS}})
    res = _patch(fid, "custom", focus)
    assert res.status_code == 400, res.text
    assert _stored(fid)[FIELD] == {"mode": "custom", "focus": FOCUS}


def test_an_unknown_mode_is_refused(as_user):
    as_user(OWNER)
    fid = _franchise()
    assert _patch(fid, "all-plays-even", FOCUS).status_code == 400
    assert FIELD not in _stored(fid)


def test_only_the_owner_can_save_the_choice(as_user):
    """Real ownership check: another signed-in user is refused and nothing is written."""
    fid = _franchise()
    as_user("someone-else")
    assert fr.verify_franchise_owned_by_user.__module__ == "BackEnd.utils.ownership"
    res = _patch(fid, "custom", FOCUS)
    assert res.status_code == 403, res.text
    assert FIELD not in _stored(fid)
    as_user(OWNER)
    assert _patch(fid, "custom", FOCUS).status_code == 200


def test_the_route_requires_a_signed_in_user():
    """With the test override lifted, the real auth dependency refuses an anonymous call."""
    fid = _franchise()
    saved_override = app.dependency_overrides.pop(get_current_user, None)
    try:
        res = _patch(fid, "custom", FOCUS)
        assert res.status_code in (401, 403), res.text
        assert FIELD not in _stored(fid)
    finally:
        if saved_override is not None:
            app.dependency_overrides[get_current_user] = saved_override


# ---------------------------------------------------------------------------
# Online (Mongo) and offline (SQLite): the same update, the same read
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_the_choice_round_trips_on_mongo_and_sqlite(kind, tmp_path: Path):
    store = create_store(_mongomock_env(tmp_path) if kind == "mongo" else _sqlite_env(tmp_path))
    franchises = store.franchises_collection
    oid = ObjectId()
    franchises.insert_one({"_id": oid, "user_id": OWNER, "week": 3, "current_season": 1})

    franchises.update_one({"_id": oid}, fr._training_playbook_choice_update("custom", FOCUS))
    assert fr._training_playbook_choice(franchises.find_one({"_id": oid})) == {"mode": "custom", "focus": FOCUS}
    # The projected read the route answers with.
    assert fr._training_playbook_choice(franchises.find_one({"_id": oid}, {FIELD: 1})) == {
        "mode": "custom", "focus": FOCUS,
    }

    # A new selection replaces the old one whole (no merge of the two play lists).
    smaller = {"offense": ["s-4"], "defense": ["zone-23"]}
    franchises.update_one({"_id": oid}, fr._training_playbook_choice_update("custom", smaller))
    assert fr._training_playbook_choice(franchises.find_one({"_id": oid})) == {"mode": "custom", "focus": smaller}

    # The rollover-style update leaves it alone.
    franchises.update_one({"_id": oid}, {"$set": {"week": 1, "current_season": 2}})
    doc = franchises.find_one({"_id": oid})
    assert (doc["week"], doc["current_season"]) == (1, 2)
    assert fr._training_playbook_choice(doc) == {"mode": "custom", "focus": smaller}

    franchises.update_one({"_id": oid}, fr._training_playbook_choice_update("current-playbooks", None))
    doc = franchises.find_one({"_id": oid})
    assert FIELD not in doc
    assert fr._training_playbook_choice(doc) == CURRENT
    assert fr._training_playbook_choice(franchises.find_one({"_id": oid}, {FIELD: 1})) == CURRENT
