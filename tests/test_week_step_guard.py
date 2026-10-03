"""Week-step guard on franchise game start, read-only GET /franchise/next-game,
and the idempotent region reconcile behind POST /franchise/play-next-game."""
from __future__ import annotations

import logging
from contextlib import contextmanager

import mongomock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api import franchise_routes
from BackEnd.api.api import app
from BackEnd.db import db, franchise_team_data_collection
from BackEnd.tournament import franchise_tournament as ft

USER_ID = "test-user-123"  # tests/conftest.py fake user
client = TestClient(app)

WRITE_METHODS = (
    "insert_one", "insert_many", "update_one", "update_many", "replace_one",
    "delete_one", "delete_many", "find_one_and_update", "find_one_and_replace",
    "find_one_and_delete", "bulk_write",
)


@contextmanager
def count_writes():
    """Count every mongomock write, on any collection, while the block runs.

    Patches the class, and also the collections these routes write through: a
    monkeypatch.setattr(collection, "update_one", ...) elsewhere in the suite leaves
    the original bound method behind as an instance attribute on undo, which would
    shadow a class-level spy.
    """
    calls: list[str] = []
    originals = {name: getattr(mongomock.collection.Collection, name) for name in WRITE_METHODS}
    instances = [db.franchises, db.games, db.teams, franchise_team_data_collection]
    shadowed = [(inst, name, vars(inst)[name]) for inst in instances for name in WRITE_METHODS
                if name in vars(inst)]

    def spy(name, original):
        def wrapper(self, *args, **kwargs):
            calls.append(f"{self.name}.{name}")
            return original(self, *args, **kwargs)
        return wrapper

    try:
        for name, original in originals.items():
            setattr(mongomock.collection.Collection, name, spy(name, original))
        for inst, name, bound in shadowed:
            setattr(inst, name, spy(name, lambda _self, *a, _bound=bound, **k: _bound(*a, **k)).__get__(inst))
        yield calls
    finally:
        for name, original in originals.items():
            setattr(mongomock.collection.Collection, name, original)
        for inst, name, bound in shadowed:
            setattr(inst, name, bound)


def _done_training(week: int) -> dict:
    return {"training_completed": True, "week": week, "user_training_applied_week": week,
            "cpu_training_complete_week": week}


def _doc(week: int, **fields) -> dict:
    doc = {
        "_id": ObjectId(),
        "week": week,
        "user_team_id": "A",
        "user_team_object_id": str(ObjectId()),
        "training_status": _done_training(week),
        franchise_routes.RECRUITING_BOARD_SAVED_WEEK_FIELD: week,
    }
    doc.update(fields)
    return doc


# --------------------------------------------------------------------------
# pending_week_step: same ladder as GOBAdvance.updatePlayButton
# --------------------------------------------------------------------------

def test_invites_pending_in_invite_weeks():
    for week in (20, 21, 25, 26):
        doc = _doc(week, **{franchise_routes.RECRUITING_BOARD_SAVED_WEEK_FIELD: week - 1})
        assert franchise_routes.pending_week_step(doc) == "recruit-invites", week


def test_invites_not_required_outside_weeks_20_to_26():
    for week in (5, 19):
        doc = _doc(week, **{franchise_routes.RECRUITING_BOARD_SAVED_WEEK_FIELD: 0})
        assert franchise_routes.pending_week_step(doc) is None, week


def test_invites_come_before_training():
    doc = _doc(25, training_status={}, **{franchise_routes.RECRUITING_BOARD_SAVED_WEEK_FIELD: 24})
    assert franchise_routes.pending_week_step(doc) == "recruit-invites"


def test_training_pending_when_week_not_fully_trained():
    assert franchise_routes.pending_week_step(_doc(25, training_status={})) == "training"
    # User applied, CPU half still pending: not fully complete, same as the FCC.
    partial = {"training_completed": True, "week": 12, "user_training_applied_week": 12}
    assert franchise_routes.pending_week_step(_doc(12, training_status=partial)) == "training"
    # Last week's training does not count for this week.
    assert franchise_routes.pending_week_step(_doc(12, training_status=_done_training(11))) == "training"


def test_all_steps_done_is_none():
    assert franchise_routes.pending_week_step(_doc(25)) is None
    assert franchise_routes.pending_week_step(_doc(3)) is None


def test_eos_weeks_have_no_invite_or_training_step():
    for week in ft.EOS_WEEKS:
        doc = _doc(week, training_status={}, **{franchise_routes.RECRUITING_BOARD_SAVED_WEEK_FIELD: 0})
        assert franchise_routes.pending_week_step(doc) is None, week


def test_unfinished_computer_games_come_first():
    doc = _doc(25, training_status={}, post_game_status={"phase_a_user_week": 25})
    assert franchise_routes.pending_week_step(doc) == "finish-cpu-sims"
    finalized = _doc(25, post_game_status={"phase_a_user_week": 25},
                     cpu_sim_jobs={"25": {"status": "finalized"}})
    assert franchise_routes.pending_week_step(finalized) != "finish-cpu-sims"


def test_camp_cut_required_before_week_1_game():
    doc = _doc(1)
    team_oid = ObjectId(doc["user_team_object_id"])
    franchise_team_data_collection.insert_one(
        {"franchise_id": doc["_id"], "team_id": team_oid, "players": [str(ObjectId()) for _ in range(14)]}
    )
    try:
        assert franchise_routes.pending_week_step(doc) == "cut-players"
        franchise_team_data_collection.update_one(
            {"franchise_id": doc["_id"]}, {"$set": {"players": [str(ObjectId()) for _ in range(12)]}}
        )
        assert franchise_routes.pending_week_step(doc) is None
    finally:
        franchise_team_data_collection.delete_many({"franchise_id": doc["_id"]})


def test_mode_defaults_to_report():
    assert franchise_routes.week_steps_mode({}) == "report"
    assert franchise_routes.week_steps_mode({"GOB_ENFORCE_WEEK_STEPS": ""}) == "report"
    assert franchise_routes.week_steps_mode({"GOB_ENFORCE_WEEK_STEPS": "bogus"}) == "report"
    assert franchise_routes.week_steps_mode({"GOB_ENFORCE_WEEK_STEPS": "ENFORCE"}) == "enforce"
    assert franchise_routes.week_steps_mode({"GOB_ENFORCE_WEEK_STEPS": "off"}) == "off"
    # Desktop builds get no special case: loopback env alone is still report.
    assert franchise_routes.week_steps_mode({"GOB_LOOPBACK": "1"}) == "report"


# --------------------------------------------------------------------------
# init-game: the guard's entry point
# --------------------------------------------------------------------------

@pytest.fixture
def invite_week_franchise():
    """Week 25, training done, this week's invites NOT sent."""
    teams = list(db.teams.find({}, {"name": 1}).limit(2))
    assert len(teams) == 2, "canonical teams are seeded for mongomock"
    home, away = teams
    fid = db.franchises.insert_one({
        "user_id": USER_ID,
        "week": 25,
        "current_season": 1,
        "user_team_id": home["name"],
        "user_team_object_id": str(home["_id"]),
        "schedule": [],
        "training_status": _done_training(25),
        franchise_routes.RECRUITING_BOARD_SAVED_WEEK_FIELD: 24,
    }).inserted_id
    yield {"fid": fid, "home": home, "away": away}
    db.franchises.delete_one({"_id": fid})
    db.games.delete_many({"franchise_id": str(fid)})


def _init_game(ctx, mode="franchise"):
    return client.post("/api/init-game", json={
        "home_team": ctx["home"]["name"],
        "away_team": ctx["away"]["name"],
        "home_id": str(ctx["home"]["_id"]),
        "away_id": str(ctx["away"]["_id"]),
        "mode": mode,
        "franchise_id": str(ctx["fid"]),
        "user_team_side": "home",
    })


@pytest.fixture
def sentry_messages(monkeypatch):
    import sentry_sdk

    sent = []

    class _Scope:
        def __init__(self):
            self.tags = {}

        def set_tag(self, key, value):
            self.tags[key] = value

        def set_context(self, *_args, **_kwargs):
            pass

    @contextmanager
    def push_scope():
        scope = _Scope()
        yield scope
        if scope.tags:
            sent.append(scope.tags)

    monkeypatch.setattr(sentry_sdk, "push_scope", push_scope)
    monkeypatch.setattr(sentry_sdk, "capture_message", lambda *a, **k: None)
    return sent


def test_report_mode_logs_the_violation_and_still_starts_the_game(
    monkeypatch, caplog, invite_week_franchise, sentry_messages
):
    monkeypatch.delenv("GOB_ENFORCE_WEEK_STEPS", raising=False)
    with caplog.at_level(logging.WARNING, logger=franchise_routes.logger.name):
        res = _init_game(invite_week_franchise)
    assert res.status_code == 200, res.text
    game_id = res.json()["game_id"]
    assert game_id
    assert db.games.find_one({"_id": game_id}) is not None
    lines = [r.getMessage() for r in caplog.records if "[WEEK-STEP-GUARD]" in r.getMessage()]
    assert len(lines) == 1
    fid = str(invite_week_franchise["fid"])
    assert f"franchise_id={fid}" in lines[0]
    assert "week=25" in lines[0]
    assert "pending_step=recruit-invites" in lines[0]
    assert "mode=report" in lines[0]
    assert sentry_messages == [{
        "gob.area": "week_step_guard", "franchise_id": fid, "week": "25",
        "pending_step": "recruit-invites", "gob.week_step_mode": "report",
    }]
    db.games.delete_one({"_id": game_id})


def test_enforce_mode_returns_409_and_creates_nothing(monkeypatch, invite_week_franchise, sentry_messages):
    monkeypatch.setenv("GOB_ENFORCE_WEEK_STEPS", "enforce")
    consumed = []
    import BackEnd.utils.home_crowd as home_crowd

    monkeypatch.setattr(home_crowd, "consume_franchise_community_engagement_for_matchup",
                        lambda *a, **k: consumed.append(a) or "none")
    games_before = db.games.count_documents({})
    franchise_before = db.franchises.find_one({"_id": invite_week_franchise["fid"]})
    with count_writes() as writes:
        res = _init_game(invite_week_franchise)
    assert res.status_code == 409
    body = res.json()
    assert body["next_required_step"] == "recruit-invites"
    assert "detail" in body and "recruit-invites" in body["detail"]
    assert writes == []
    assert consumed == []
    assert db.games.count_documents({}) == games_before
    assert db.franchises.find_one({"_id": invite_week_franchise["fid"]}) == franchise_before


def test_enforce_mode_lets_a_ready_week_start(monkeypatch, invite_week_franchise, sentry_messages):
    monkeypatch.setenv("GOB_ENFORCE_WEEK_STEPS", "enforce")
    db.franchises.update_one(
        {"_id": invite_week_franchise["fid"]},
        {"$set": {franchise_routes.RECRUITING_BOARD_SAVED_WEEK_FIELD: 25}},
    )
    res = _init_game(invite_week_franchise)
    assert res.status_code == 200, res.text
    assert sentry_messages == []
    db.games.delete_one({"_id": res.json()["game_id"]})


def test_off_mode_skips_the_check(monkeypatch, caplog, invite_week_franchise, sentry_messages):
    monkeypatch.setenv("GOB_ENFORCE_WEEK_STEPS", "off")
    with caplog.at_level(logging.WARNING, logger=franchise_routes.logger.name):
        res = _init_game(invite_week_franchise)
    assert res.status_code == 200, res.text
    assert not [r for r in caplog.records if "[WEEK-STEP-GUARD]" in r.getMessage()]
    assert sentry_messages == []
    db.games.delete_one({"_id": res.json()["game_id"]})


def test_non_franchise_modes_are_never_checked(monkeypatch, invite_week_franchise, sentry_messages):
    monkeypatch.setenv("GOB_ENFORCE_WEEK_STEPS", "enforce")
    res = _init_game(invite_week_franchise, mode="single")
    assert res.status_code == 200, res.text
    assert sentry_messages == []
    db.games.delete_one({"_id": res.json()["game_id"]})


def test_guard_failure_never_blocks_a_game_start(monkeypatch, invite_week_franchise):
    monkeypatch.setenv("GOB_ENFORCE_WEEK_STEPS", "enforce")

    def boom(_doc):
        raise RuntimeError("guard bug")

    monkeypatch.setattr(franchise_routes, "pending_week_step", boom)
    res = _init_game(invite_week_franchise)
    assert res.status_code == 200, res.text
    db.games.delete_one({"_id": res.json()["game_id"]})


# --------------------------------------------------------------------------
# GET /franchise/next-game: read-only twin of the POST lookup
# --------------------------------------------------------------------------

def test_get_next_game_matches_post_and_writes_nothing():
    teams = list(db.teams.find({}, {"name": 1}).limit(2))
    home, away = teams
    fid = db.franchises.insert_one({
        "user_id": USER_ID, "week": 1, "current_season": 1,
        "user_team_id": home["name"], "user_team_object_id": str(home["_id"]),
        "schedule": [[(away["_id"], home["_id"])]],
    }).inserted_id
    try:
        before = db.franchises.find_one({"_id": fid})
        with count_writes() as writes:
            got = client.get("/franchise/next-game", params={"franchise_id": str(fid)})
        assert got.status_code == 200, got.text
        assert writes == []
        assert db.franchises.find_one({"_id": fid}) == before
        posted = client.post("/franchise/play-next-game", json={"franchise_id": str(fid)})
        assert posted.status_code == 200, posted.text
        assert got.json() == posted.json()
        assert got.json()["home_id"] == str(home["_id"]) and got.json()["week"] == 1
    finally:
        db.franchises.delete_one({"_id": fid})


def test_get_next_game_is_owner_only():
    fid = db.franchises.insert_one({"user_id": "someone-else", "week": 1, "schedule": []}).inserted_id
    try:
        res = client.get("/franchise/next-game", params={"franchise_id": str(fid)})
        assert res.status_code in (403, 404)
    finally:
        db.franchises.delete_one({"_id": fid})


# --------------------------------------------------------------------------
# Region reconcile (weeks 30-31): idempotent, and never run by the GET
# --------------------------------------------------------------------------

@pytest.fixture
def region_week_franchise():
    """Week 30 with a half-built region A bracket (the TBD-slot case the POST repairs)."""
    teams = [ObjectId() for _ in range(16)]
    c1, c2 = teams[:8], teams[8:]
    db.teams.insert_many(
        [{"_id": t, "name": f"RW{i}", "conference": 1, "region": "A"} for i, t in enumerate(c1)]
        + [{"_id": t, "name": f"RW{8 + i}", "conference": 2, "region": "A"} for i, t in enumerate(c2)]
    )
    fid = ObjectId()
    franchise_team_data_collection.insert_many([{"franchise_id": fid, "team_id": t} for t in teams])
    s1, s2 = [str(t) for t in c1], [str(t) for t in c2]
    db.franchises.insert_one({
        "_id": fid,
        "user_id": USER_ID,
        "week": 30,
        "current_season": 1,
        "browse_rev": 0,
        "user_team_id": "RW7",
        "user_team_object_id": s1[7],
        "schedule": [],
        "eos_tournament_active": True,
        "conference_tournaments": {
            "1": {"champion": s1[7], "seeds": {s1[i]: i + 1 for i in range(8)}},
            "2": {"champion": s2[7], "seeds": {s2[i]: i + 1 for i in range(8)}},
        },
        "region_tournaments": {
            "A": {
                "round1": [{"away_team": s1[0], "home_team": None, "winner": None, "game_id": None, "score": {}}],
                "final": [{"away_team": "R1_0", "home_team": "R1_1", "winner": None, "game_id": None, "score": {}}],
                "current_round": 1,
            },
        },
    })
    yield fid
    db.franchises.delete_one({"_id": fid})
    franchise_team_data_collection.delete_many({"franchise_id": fid})
    db.teams.delete_many({"_id": {"$in": teams}})


def test_region_reconcile_writes_once_then_nothing(region_week_franchise):
    fid = region_week_franchise
    with count_writes() as writes:
        first = franchise_routes._maybe_reconcile_region_for_eos(
            db.franchises.find_one({"_id": fid}), fid, week=30, context_label="test")
    assert first is True
    assert writes == ["franchises.update_one"]
    saved = db.franchises.find_one({"_id": fid})
    with count_writes() as writes:
        second = franchise_routes._maybe_reconcile_region_for_eos(saved, fid, week=30, context_label="test")
    assert second is False
    assert writes == []
    assert db.franchises.find_one({"_id": fid}) == saved


def test_play_next_game_twice_in_a_region_week_writes_once(region_week_franchise):
    fid = region_week_franchise
    with count_writes() as writes:
        client.post("/franchise/play-next-game", json={"franchise_id": str(fid)})
    assert writes.count("franchises.update_one") == 1
    rev = db.franchises.find_one({"_id": fid})["browse_rev"]
    with count_writes() as writes:
        client.post("/franchise/play-next-game", json={"franchise_id": str(fid)})
    assert writes == []
    assert db.franchises.find_one({"_id": fid})["browse_rev"] == rev


def test_get_next_game_never_reconciles(region_week_franchise):
    fid = region_week_franchise
    before = db.franchises.find_one({"_id": fid})
    with count_writes() as writes:
        res = client.get("/franchise/next-game", params={"franchise_id": str(fid)})
    assert res.status_code in (200, 404)
    assert writes == []
    assert db.franchises.find_one({"_id": fid}) == before


# --------------------------------------------------------------------------
# Dead routes removed (UX dead-code sweep, 2026-09-30)
# --------------------------------------------------------------------------

def test_dead_franchise_routes_are_gone():
    fid = str(ObjectId())
    assert client.post("/franchise/save-result", json={"franchise_id": fid, "game_id": fid, "winner": "A"}).status_code in (404, 405)
    assert client.post("/franchise/delete-current").status_code in (404, 405)
    assert client.get("/franchise/team-traits", params={"franchise_id": fid}).status_code in (404, 405)
    assert client.get("/franchise/latest-training", params={"franchise_id": fid}).status_code in (404, 405)
    paths = {(m, r.path) for r in franchise_routes.router.routes for m in getattr(r, "methods", ())}
    # Only the POST alias went; the DELETE on the same handler was not in scope.
    assert ("DELETE", "/franchise/current") in paths
