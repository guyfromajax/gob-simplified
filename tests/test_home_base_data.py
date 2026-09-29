"""Home Base data: franchise last_played_at and the local desktop coach career (mongomock + sqlite)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

import BackEnd.utils.franchise_championships as fc
import BackEnd.utils.franchise_last_played as flp
import BackEnd.utils.local_coach as lc
import BackEnd.utils.user_game_commit as ugc
from BackEnd.api import franchise_routes
from BackEnd.api.api import app
from BackEnd.api.auth_routes import UserResponse
from BackEnd.db import db
from BackEnd.local_identity import LOCAL_PRINCIPAL, LOCAL_USER_ID
from BackEnd.persistence import create_store
from BackEnd.utils.auth import get_current_user
from tests.test_persistence_adapter import _mongomock_env, _sqlite_env

ROOT = Path(__file__).resolve().parents[1]
SIM_MODULES = (
    "BackEnd/main.py",
    "BackEnd/utils/cpu_week_pool.py",
    "BackEnd/utils/sim_random.py",
    "BackEnd/utils/stat_updater.py",
    "BackEnd/utils/headless_simulation.py",
    "BackEnd/models/game_manager.py",
    "BackEnd/practice_squad/sim.py",
    "BackEnd/eog_attr_rules.py",
)
PLAY_ROUTES = (
    "save_result",
    "complete_week",
    "complete_week_phase_a",
    "complete_week_phase_b",
    "sim_rest_of_tournament",
    "sim_championship",
    "finish_season",
)


@pytest.fixture(params=["mongo", "sqlite"])
def store(request, tmp_path):
    env = _mongomock_env(tmp_path) if request.param == "mongo" else _sqlite_env(tmp_path)
    return create_store(env)


# --- last_played_at -------------------------------------------------------------------------


def test_stamp_round_trips_as_utc_iso(store, monkeypatch):
    monkeypatch.setattr(flp, "franchise_collection", lambda: store.franchises_collection)
    oid = ObjectId()
    store.franchises_collection.insert_one({"_id": oid, "user_id": "u", "week": 3})
    when = datetime(2026, 9, 28, 22, 15, 30, tzinfo=timezone.utc)
    flp.stamp_last_played(str(oid), now=when)
    doc = store.franchises_collection.find_one({"_id": oid})
    assert flp.last_played_iso(doc) == "2026-09-28T22:15:30Z"


def test_decorator_stamps_success_and_skips_idempotent_or_error(store, monkeypatch):
    monkeypatch.setattr(flp, "franchise_collection", lambda: store.franchises_collection)
    oid = ObjectId()
    store.franchises_collection.insert_one({"_id": oid, "user_id": "u"})
    req = SimpleNamespace(franchise_id=str(oid))

    @flp.marks_last_played
    def idempotent(req):
        return {"status": "ok", "idempotent": True}

    @flp.marks_last_played
    def fails(req):
        raise RuntimeError("boom")

    @flp.marks_last_played
    def played(req):
        return {"status": "ok", "idempotent": False}

    idempotent(req)
    with pytest.raises(RuntimeError):
        fails(req=req)
    assert flp.LAST_PLAYED_FIELD not in store.franchises_collection.find_one({"_id": oid})
    played(req=req)
    assert flp.last_played_iso(store.franchises_collection.find_one({"_id": oid}))


def test_most_recent_prefers_played_then_creation():
    old, new = ObjectId.from_datetime(datetime(2026, 1, 1)), ObjectId.from_datetime(datetime(2026, 6, 1))
    t = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert flp.most_recent_franchise_id([]) is None
    assert flp.most_recent_franchise_id([{"_id": old}, {"_id": new}]) == str(new)
    assert flp.most_recent_franchise_id([{"_id": old, "last_played_at": t}, {"_id": new}]) == str(old)
    # Mongo returns naive UTC; the sqlite save returns aware datetimes.
    assert flp.most_recent_franchise_id([
        {"_id": old, "last_played_at": t.replace(tzinfo=None)},
        {"_id": new, "last_played_at": t - timedelta(hours=1)},
    ]) == str(old)


def test_play_routes_are_stamped_at_route_level_only():
    for name in PLAY_ROUTES:
        assert getattr(getattr(franchise_routes, name), "__wrapped__", None), name
    assert not hasattr(franchise_routes.complete_week_start_cpu_sims, "__wrapped__")
    for rel in SIM_MODULES:
        text = (ROOT / rel).read_text()
        assert "franchise_last_played" not in text, rel
        assert "last_played_at" not in text, rel


@pytest.fixture
def as_user():
    def _set(user):
        app.dependency_overrides[get_current_user] = lambda: dict(user)
    yield _set
    app.dependency_overrides.pop(get_current_user, None)


def test_franchise_list_returns_last_played_and_most_recent(as_user):
    uid = "home-base-list-user"
    as_user({"user_id": uid})
    first, second = ObjectId(), ObjectId()
    db.franchises.insert_many([
        {"_id": first, "user_id": uid, "user_team_id": "Alpha", "week": 5, "home_slot": 1,
         "last_played_at": datetime(2026, 9, 28, 20, 0, 0)},
        {"_id": second, "user_id": uid, "user_team_id": "Beta", "week": 2, "home_slot": 2},
    ])
    try:
        body = TestClient(app).get("/franchise/list").json()
        cards = {c["franchise_id"]: c for c in body["franchises"]}
        assert cards[str(first)]["last_played_at"] == "2026-09-28T20:00:00Z"
        assert cards[str(second)]["last_played_at"] is None
        assert body["most_recent_franchise_id"] == str(first)
    finally:
        db.franchises.delete_many({"_id": {"$in": [first, second]}})


# --- local coach career ---------------------------------------------------------------------


def _game(home_score, away_score, periods=None):
    return {
        "_id": ObjectId(),
        "user_team_side": "home",
        "home_team_id": "H",
        "away_team_id": "A",
        "teams": {"H": {"name": "Home", "score": home_score}, "A": {"name": "Away", "score": away_score}},
        "archetype_periods": periods or {},
    }


def test_local_owner_record_persists_in_the_save(store, monkeypatch):
    monkeypatch.setattr(ugc, "db", store.db)
    monkeypatch.setattr(ugc, "users_collection", store.users_collection)
    monkeypatch.setattr(lc, "coach_collection", lambda: store.db["save_meta"])
    fid = ObjectId()
    store.franchises_collection.insert_one({"_id": fid, "user_id": LOCAL_USER_ID})

    ugc.commit_user_game_record(_game(80, 70, {"1": "pure_offense", "2": "pure_offense"}), fid, "Home", "Away")
    ugc.commit_user_game_record(_game(60, 70), fid, "Home", "Away")

    doc = store.db["save_meta"].find_one({"_id": lc.LOCAL_COACH_ID})
    rec = doc["record"]
    assert (rec["wins"], rec["losses"], rec["total_games"], rec["win_rate"]) == (1, 1, 2, 50)
    assert doc["archetypes"]["pure_offense"] == 2
    assert doc["lead_archetype"] == "pure_offense"
    assert store.users_collection.find_one({"_id": LOCAL_USER_ID}) is None


def test_online_owner_record_still_goes_to_users(store, monkeypatch):
    monkeypatch.setattr(ugc, "db", store.db)
    monkeypatch.setattr(ugc, "users_collection", store.users_collection)
    monkeypatch.setattr(lc, "coach_collection", lambda: store.db["save_meta"])
    user_oid, fid = ObjectId(), ObjectId()
    store.users_collection.insert_one({"_id": user_oid, "record": {"wins": 0, "losses": 0}})
    store.franchises_collection.insert_one({"_id": fid, "user_id": str(user_oid)})
    ugc.commit_user_game_record(_game(80, 70), fid, "Home", "Away")
    assert store.users_collection.find_one({"_id": user_oid})["record"]["wins"] == 1
    assert store.db["save_meta"].find_one({"_id": lc.LOCAL_COACH_ID}) is None


def test_local_owner_championships_persist_in_the_save(store, monkeypatch):
    monkeypatch.setattr(fc, "users_collection", store.users_collection)
    monkeypatch.setattr(fc, "geek_points_team_key_for_franchise_user", lambda _t: "LANCASTER")
    monkeypatch.setattr(lc, "coach_collection", lambda: store.db["save_meta"])
    team = str(ObjectId())
    fc._inc_championship(owner_user_id=LOCAL_USER_ID, user_team_id_str=team, kind="national")
    fc._inc_championship(owner_user_id=LOCAL_USER_ID, user_team_id_str=team, kind="conf_t")
    fc._inc_championship(owner_user_id=LOCAL_USER_ID, user_team_id_str=team, kind="conf_t")
    doc = store.db["save_meta"].find_one({"_id": lc.LOCAL_COACH_ID})
    assert doc["championships_total"] == {"national": 1, "conf_t": 2}
    assert doc["championships_by_team"]["LANCASTER"] == {"national": 1, "conf_t": 2}

    online = ObjectId()
    store.users_collection.insert_one({"_id": online})
    fc._inc_championship(owner_user_id=str(online), user_team_id_str=team, kind="region")
    assert store.users_collection.find_one({"_id": online})["championships_total"] == {"region": 1}
    assert "region" not in store.db["save_meta"].find_one({"_id": lc.LOCAL_COACH_ID})["championships_total"]


def test_coach_career_route_serves_the_local_coach_in_me_shape(store, monkeypatch, as_user):
    monkeypatch.setattr(lc, "coach_collection", lambda: store.db["save_meta"])
    monkeypatch.setattr(franchise_routes, "local_coach_doc", lc.local_coach_doc)
    as_user(LOCAL_PRINCIPAL)
    http = TestClient(app)

    empty = http.get("/franchise/coach-career").json()
    assert empty["user_id"] == LOCAL_USER_ID
    assert empty["record"]["wins"] == 0
    assert empty["championships_total"] == {"conf_rs": 0, "conf_t": 0, "region": 0, "national": 0}

    store.db["save_meta"].update_one(
        {"_id": lc.LOCAL_COACH_ID},
        {"$inc": {"record.wins": 12, "record.losses": 5, "championships_total.national": 3}},
        upsert=True,
    )
    body = http.get("/franchise/coach-career").json()
    assert (body["record"]["wins"], body["record"]["losses"]) == (12, 5)
    assert body["championships_total"]["national"] == 3
    assert body["trophies"] == []
    # The /api/auth/me shape, plus the trophy log and the server-computed career
    # numerals Home Base and the Trophy Case read (Chapter 7).
    career_extras = {
        "trophies", "win_pct_display", "geek_points", "seasons_completed",
        "programs", "top_seasons",
    }
    assert set(body) - career_extras <= set(UserResponse.model_fields)


def test_coach_career_route_reads_users_online(as_user):
    user_oid = ObjectId()
    users = franchise_routes._store.users_collection
    users.insert_one({"_id": user_oid, "username": "online-coach", "record": {"wins": 4, "losses": 1},
                      "championships_total": {"region": 2}})
    as_user({"user_id": str(user_oid), "email": "o@example.com"})
    try:
        body = TestClient(app).get("/franchise/coach-career").json()
        assert body["username"] == "online-coach"
        assert (body["record"]["wins"], body["record"]["losses"]) == (4, 1)
        assert body["championships_total"]["region"] == 2
    finally:
        users.delete_one({"_id": user_oid})
