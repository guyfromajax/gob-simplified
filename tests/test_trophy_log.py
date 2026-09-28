"""Trophy log: append-only itemised career history on the coach (mongomock + sqlite)."""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

import BackEnd.utils.franchise_championships as fc
import BackEnd.utils.franchise_team_display as ftdisp
import BackEnd.utils.local_coach as lc
import BackEnd.utils.trophy_log as tl
from BackEnd.api import franchise_routes
from BackEnd.api.api import app
from BackEnd.local_identity import LOCAL_PRINCIPAL, LOCAL_USER_ID
from BackEnd.persistence import create_store
from BackEnd.utils.auth import get_current_user
from BackEnd.utils.team_builder_leak_detector import scan_json_for_replaced_name
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
CORE_NAME = "Providence"
DISPLAY_NAME = "Lancaster"


@pytest.fixture(params=["mongo", "sqlite"])
def store(request, tmp_path, monkeypatch):
    env = _mongomock_env(tmp_path) if request.param == "mongo" else _sqlite_env(tmp_path)
    s = create_store(env)
    monkeypatch.setattr(tl, "users_collection", s.users_collection)
    monkeypatch.setattr(tl, "franchises_collection", s.franchises_collection)
    monkeypatch.setattr(ftdisp, "teams_collection", s.teams_collection)
    monkeypatch.setattr(lc, "coach_collection", lambda: s.db["save_meta"])
    monkeypatch.setattr(fc, "users_collection", s.users_collection)
    monkeypatch.setattr(fc, "geek_points_team_key_for_franchise_user", lambda _t: "PROVIDENCE")
    monkeypatch.setattr(fc, "_inc_player_titles", lambda **_k: None)
    return s


def _seed(store, owner, *, season=2, **extra):
    """A Team Builder franchise: user team core 'Providence' shown as 'Lancaster'."""
    user_tid, cpu_tid, fid = ObjectId(), ObjectId(), ObjectId()
    store.teams_collection.insert_many([
        {"_id": user_tid, "name": CORE_NAME, "team_id": "PROVIDENCE"},
        {"_id": cpu_tid, "name": "Concord", "team_id": "CONCORD"},
    ])
    doc = {
        "_id": fid,
        "user_id": owner,
        "current_season": season,
        "week": 36,
        "user_team_id": DISPLAY_NAME,
        "user_team_object_id": str(user_tid),
        "team_builder": {
            "replaced_object_id": str(user_tid),
            "replaced_name": CORE_NAME,
            "name": DISPLAY_NAME,
            "abbreviation": "LAN",
            "asset_strategy": "generated",
        },
        **extra,
    }
    store.franchises_collection.insert_one(doc)
    return doc, str(user_tid), str(cpu_tid)


def _coach_doc(store, owner):
    if owner == LOCAL_USER_ID:
        return store.db["save_meta"].find_one({"_id": lc.LOCAL_COACH_ID}) or {}
    return store.users_collection.find_one({"_id": ObjectId(owner)}) or {}


@pytest.fixture(params=["local", "online"])
def owner(request, store):
    if request.param == "local":
        return LOCAL_USER_ID
    oid = ObjectId()
    store.users_collection.insert_one({"_id": oid, "username": "online-coach"})
    return str(oid)


# --- titles ---------------------------------------------------------------------------------


def test_each_title_kind_appends_once_with_display_name(store, owner):
    doc, user_tid, _ = _seed(store, owner)
    fid = str(doc["_id"])
    for kind in fc.TITLE_KINDS:
        for _ in range(2):  # retry / idempotent replay
            fc._inc_championship(owner_user_id=owner, user_team_id_str=user_tid, kind=kind, franchise_id=fid)

    coach = _coach_doc(store, owner)
    trophies = coach["trophies"]
    assert [t["kind"] for t in trophies] == list(fc.TITLE_KINDS)
    for t in trophies:
        assert t["key"] == f"{fid}:2:{t['kind']}:{user_tid}"
        assert (t["season"], t["team_id"], t["franchise_id"]) == (2, user_tid, fid)
        assert t["team_name"] == DISPLAY_NAME
        assert "detail" not in t
        assert set(t) == {"key", "season", "kind", "team_id", "team_name", "franchise_id", "at"}
    # Counts are untouched by the log (no existing guard on the $inc).
    assert coach["championships_total"] == {k: 2 for k in fc.TITLE_KINDS}
    assert CORE_NAME not in json.dumps(trophies, default=str)


def test_offline_writes_local_coach_online_writes_users_never_both(store):
    online = ObjectId()
    store.users_collection.insert_one({"_id": online})
    local_doc, local_tid, _ = _seed(store, LOCAL_USER_ID)
    online_doc, online_tid, _ = _seed(store, str(online))

    fc._inc_championship(owner_user_id=LOCAL_USER_ID, user_team_id_str=local_tid, kind="national",
                         franchise_id=str(local_doc["_id"]))
    fc._inc_championship(owner_user_id=str(online), user_team_id_str=online_tid, kind="region",
                         franchise_id=str(online_doc["_id"]))

    local = store.db["save_meta"].find_one({"_id": lc.LOCAL_COACH_ID})
    remote = store.users_collection.find_one({"_id": online})
    assert [t["kind"] for t in local["trophies"]] == ["national"]
    assert [t["kind"] for t in remote["trophies"]] == ["region"]
    assert store.users_collection.find_one({"_id": LOCAL_USER_ID}) is None


def test_online_owner_without_users_doc_is_not_created(store):
    ghost = ObjectId()
    doc, tid, _ = _seed(store, str(ghost))
    entry = tl.build_trophy_entry(doc, kind="national", team_id=tid)
    assert tl.append_trophy(str(ghost), entry) is False
    assert store.users_collection.find_one({"_id": ghost}) is None


def test_keys_with_dots_still_guard(store, owner):
    doc, tid, _ = _seed(store, owner)
    entry = tl.build_trophy_entry(doc, kind="all_american_1", team_id=tid, player_id="p.1",
                                  detail={"player_id": "p.1", "player_name": "Dot"})
    assert tl.append_trophy(owner, entry) is True
    assert tl.append_trophy(owner, dict(entry)) is False
    assert len(_coach_doc(store, owner)["trophies"]) == 1


# --- All-Americans --------------------------------------------------------------------------


def _pick(pid, name, team_id):
    return {"player_id": pid, "name": name, "team_id": team_id, "team_name": "x", "score": 1.0}


def test_all_americans_user_team_only_and_replay_safe(store, owner):
    doc, user_tid, cpu_tid = _seed(store, owner)
    doc["awards"] = {
        "all_american_teams": {
            "first_team": [_pick("p1", "Ada Guard", user_tid), _pick("c1", "Cpu One", cpu_tid)],
            "second_team": [_pick("c2", "Cpu Two", cpu_tid)],
            "third_team": [_pick("p3", "Bo Wing", user_tid)],
        }
    }
    for _ in range(3):  # week-35 persist, command-center reads, awards route
        franchise_routes._persist_week_35_awards_if_needed(doc)

    trophies = _coach_doc(store, owner)["trophies"]
    by_kind = {t["kind"]: t for t in trophies}
    assert len(trophies) == 2
    assert set(by_kind) == {"all_american_1", "all_american_3"}
    assert by_kind["all_american_1"]["detail"] == {"player_id": "p1", "player_name": "Ada Guard"}
    assert by_kind["all_american_3"]["detail"] == {"player_id": "p3", "player_name": "Bo Wing"}
    assert by_kind["all_american_1"]["key"] == f"{doc['_id']}:2:all_american_1:{user_tid}:p1"
    assert all(t["team_name"] == DISPLAY_NAME for t in trophies)


# --- season_record --------------------------------------------------------------------------


def _m(away, home, winner=None):
    return {"away_team": away, "home_team": home, "winner": winner}


def _season_brackets(user_tid, cpu_tid):
    return {
        "results": {
            "1": [{"home_id": user_tid, "away_id": cpu_tid, "home_score": 80, "away_score": 70}],
            "2": [{"home_id": cpu_tid, "away_id": user_tid, "home_score": 75, "away_score": 60}],
            "30": [{"home_id": user_tid, "away_id": cpu_tid, "home_score": 90, "away_score": 50}],
        },
        "conference_tournaments": {
            "3": {"seeds": {user_tid: 2, cpu_tid: 1},
                  "bracket": {"round1": [_m(cpu_tid, user_tid)], "round2": [_m(user_tid, "x")],
                              "final": [_m(user_tid, cpu_tid, user_tid)]}}
        },
        "region_tournaments": {"B": {"round1": [_m(user_tid, "y")], "final": [_m(user_tid, "z")]}},
        "national_tournament": {"bracket": {"round1": [_m(user_tid, "q")], "round2": [_m("s", user_tid)],
                                            "final": []}},
    }


def test_season_record_detail_from_stored_doc(store, owner):
    doc, user_tid, cpu_tid = _seed(store, owner)
    doc.update(_season_brackets(user_tid, cpu_tid))
    for _ in range(2):
        tl.record_season_record_trophy(doc)
    trophies = _coach_doc(store, owner)["trophies"]
    assert len(trophies) == 1
    t = trophies[0]
    assert t["kind"] == "season_record" and t["team_name"] == DISPLAY_NAME
    assert t["key"] == f"{doc['_id']}:2:season_record:{user_tid}"
    assert t["detail"] == {"wins": 2, "losses": 1, "conf_finish": 2, "furthest_round": "national_semis"}


def test_furthest_round_labels():
    tid = "T"
    assert tl.furthest_round_reached({}, tid) is None
    assert tl.furthest_round_reached(
        {"national_tournament": {"bracket": {"final": [_m("T", "U")]}}}, tid) == "national_final"
    assert tl.furthest_round_reached(
        {"region_tournaments": {"A": {"round1": [_m("T", "U")], "final": [_m("V", "W")]}}}, tid) == "region_semis"
    assert tl.furthest_round_reached(
        {"conference_tournaments": {"1": {"bracket": {"round1": [_m("T", "U")]}}}}, tid) == "conference_quarters"
    assert tl.furthest_round_reached(
        {"conference_tournaments": {"1": {"bracket": {"round1": [_m("X", "U")]}}}}, tid) == "missed"


def test_season_record_omits_fields_it_cannot_read(store, owner):
    doc, user_tid, _ = _seed(store, owner)
    tl.record_season_record_trophy(doc)
    assert _coach_doc(store, owner)["trophies"][0]["detail"] == {"wins": 0, "losses": 0}


def test_finish_season_writes_season_record_before_the_reset():
    src = inspect.getsource(franchise_routes.finish_season)
    write = src.index("record_season_record_trophy(franchise_doc)")
    assert write < src.index('"conference_tournaments": {}')
    assert write < src.index('"results": {}')
    assert write < src.index("AWARDS_FIELD: awards_reset")
    # After the single-use transition token is consumed, so double calls 409 first.
    assert src.index("consume_result.modified_count == 0") < write


# --- coach-career ---------------------------------------------------------------------------


@pytest.fixture
def as_user():
    def _set(user):
        app.dependency_overrides[get_current_user] = lambda: dict(user)
    yield _set
    app.dependency_overrides.pop(get_current_user, None)


def _entry(fid, season, kind, at):
    return {"key": f"{fid}:{season}:{kind}:t", "season": season, "kind": kind, "team_id": "t",
            "team_name": DISPLAY_NAME, "franchise_id": fid, "at": at}


def test_coach_career_returns_trophies_newest_first_local(store, monkeypatch, as_user):
    monkeypatch.setattr(franchise_routes, "local_coach_doc", lc.local_coach_doc)
    fid = str(ObjectId())
    early, late = datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 2, tzinfo=timezone.utc)
    for e in (_entry(fid, 1, "national", late), _entry(fid, 2, "conf_rs", early),
              _entry(fid, 2, "season_record", late)):
        tl.append_trophy(LOCAL_USER_ID, e)
    # The franchise is gone; the career keeps its trophies.
    store.franchises_collection.delete_many({})
    as_user(LOCAL_PRINCIPAL)
    body = TestClient(app).get("/franchise/coach-career").json()
    assert [(t["season"], t["kind"]) for t in body["trophies"]] == [
        (2, "season_record"), (2, "conf_rs"), (1, "national")]
    assert body["trophies"][0]["at"] == "2026-09-02T00:00:00Z"


def test_coach_career_returns_trophies_online(as_user, monkeypatch):
    users = franchise_routes._store.users_collection
    user_oid, fid = ObjectId(), str(ObjectId())
    users.insert_one({"_id": user_oid, "username": "online-coach", "trophies": [
        _entry(fid, 1, "region", datetime(2026, 9, 1)),
        _entry(fid, 3, "national", datetime(2026, 9, 3)),
    ]})
    as_user({"user_id": str(user_oid), "email": "o@example.com"})
    try:
        body = TestClient(app).get("/franchise/coach-career").json()
        assert [t["season"] for t in body["trophies"]] == [3, 1]
        assert not scan_json_for_replaced_name(body, CORE_NAME)
    finally:
        users.delete_one({"_id": user_oid})


# --- guard ----------------------------------------------------------------------------------


def test_sim_modules_never_mention_trophies():
    for rel in SIM_MODULES:
        text = (ROOT / rel).read_text()
        assert "trophies" not in text, rel
        assert "trophy_log" not in text, rel
    for fn in (franchise_routes._complete_week_finish_cpu_and_persist,):
        src = inspect.getsource(fn)
        assert "trophies" not in src and "trophy" not in src
