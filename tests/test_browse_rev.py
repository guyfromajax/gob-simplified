"""browse_rev bumps and browse ETag / 304. A writer missing from the table fails."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from BackEnd.api import franchise_routes, gameplan_routes
from BackEnd.api.api import app
from BackEnd.db import (
    db,
    franchise_players_data_collection,
    franchise_recruits_data_collection,
    franchise_team_data_collection,
)
from BackEnd.persistence import create_store
from BackEnd.utils.auth import get_current_user
from BackEnd.utils.browse_cache import (
    attach_browse_etag_header,
    browse_cached,
    bump_browse_rev,
)
from tests.test_persistence_adapter import _mongomock_env, _sqlite_env

USER_ID = "browse-rev-user"
client = TestClient(app)

# Every franchise-scoped writer in the store brief. Press conference, lineup,
# simulate-quarter, and /api/game/{id} are intentionally absent.
REQUIRED_WRITERS = frozenset(
    {
        "complete-week",
        "complete-week-phase-a",
        "complete-week-phase-b",
        "start-cpu-sims",
        "run-training-user",
        "run-training-cpu",
        "recruiting-orders",
        "recruiting-orders-week-35",
        "recruiting-watchlist",
        "run-week-35-recruiting",
        "recruit-visits",
        "cut-players",
        "cut-players-final",
        "development-focus",
        "put-gameplan",
        "post-playbooks",
        "finish-season",
        "sim-rest-of-tournament",
        "sim-championship",
        "seen-region-bye",
        "seen-conference-rs-region",
        "seen-bracket-reveal",
        "seen-recruiting-results",
        "seen-recruit-visit",
        "seen-invite-seed",
        "seen-week-35-reveal",
        "seen-week-36-results",
        "seen-recruiting-wire",
        "seen-walk-on-welcome",
    }
)

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


def _fake_cpu_sim(*_args, **_kwargs):
    return (54, 58, {})


def _etag(fid: str, **params) -> str:
    query = {"franchise_id": fid, **params}
    res = client.get("/franchise/news", params=query)
    assert res.status_code == 200, res.text
    tag = res.headers.get("etag")
    assert tag, res.headers
    return tag


def _cycle(fid: str, perform: Callable[[], None]) -> None:
    before = _etag(fid)
    perform()
    stale = client.get(
        "/franchise/news",
        params={"franchise_id": fid},
        headers={"If-None-Match": before},
    )
    assert stale.status_code == 200, stale.text
    after = stale.headers.get("etag")
    assert after and after != before
    fresh = client.get(
        "/franchise/news",
        params={"franchise_id": fid},
        headers={"If-None-Match": after},
    )
    assert fresh.status_code == 304
    assert fresh.content == b""
    assert fresh.headers.get("etag") == after
    assert "no-cache" in (fresh.headers.get("cache-control") or "")


def _insert_franchise(**fields) -> tuple[str, ObjectId]:
    team_id = fields.pop("team_id", None) or ObjectId()
    if not db.teams.find_one({"_id": team_id}):
        db.teams.insert_one(
            {
                "_id": team_id,
                "name": fields.get("user_team_id") or "A",
                "record": {"W": 0, "L": 0},
                "PF": 0,
                "PA": 0,
            }
        )
    doc = {
        "week": 1,
        "current_season": 1,
        "user_id": USER_ID,
        "user_team_id": "A",
        "user_team_object_id": str(team_id),
        "schedule": [],
        "browse_rev": 0,
    }
    doc.update(fields)
    doc["user_team_object_id"] = str(team_id)
    fid = db.franchises.insert_one(doc).inserted_id
    return str(fid), team_id


def _league() -> tuple[str, list[ObjectId]]:
    ids = [ObjectId() for _ in range(4)]
    db.teams.insert_many(
        [
            {"_id": oid, "name": name, "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0}
            for oid, name in zip(ids, ("A", "B", "C", "D"))
        ]
    )
    fid = db.franchises.insert_one(
        {
            "schedule": [[(ids[0], ids[1]), (ids[2], ids[3])]],
            "week": 1,
            "current_season": 1,
            "user_id": USER_ID,
            "user_team_id": "A",
            "user_team_object_id": str(ids[0]),
            "browse_rev": 0,
        }
    ).inserted_id
    return str(fid), ids


def _cleanup(fid: str, team_ids: list | None = None) -> None:
    oid = ObjectId(fid)
    db.franchises.delete_one({"_id": oid})
    franchise_team_data_collection.delete_many({"franchise_id": oid})
    franchise_team_data_collection.delete_many({"franchise_id": fid})
    franchise_players_data_collection.delete_many({"franchise_id": fid})
    franchise_recruits_data_collection.delete_many({"franchise_id": fid})
    if team_ids:
        db.teams.delete_many({"_id": {"$in": list(team_ids)}})
    db.games.delete_many({"franchise_id": fid})


def _post(path: str, payload: dict) -> None:
    res = client.post(path, json=payload)
    assert res.status_code == 200, res.text


def _patch(path: str, payload: dict) -> None:
    res = client.patch(path, json=payload)
    assert res.status_code == 200, res.text


def _cpu_patch():
    return patch.object(
        franchise_routes,
        "_run_franchise_cpu_full_simulation_core",
        side_effect=_fake_cpu_sim,
    )


@dataclass
class Writer:
    id: str
    setup: Callable[[], tuple[str, dict]]
    perform: Callable[[str, dict], None]


def _setup_league() -> tuple[str, dict]:
    fid, ids = _league()
    return fid, {"teams": ids}


def _setup_phase_b() -> tuple[str, dict]:
    fid, ctx = _setup_league()
    with _cpu_patch():
        _post(
            "/franchise/complete-week/phase-a",
            {
                "franchise_id": fid,
                "week": 1,
                "result": {"team1_id": "A", "team2_id": "B", "team1_score": 70, "team2_score": 60},
            },
        )
    return fid, ctx


def _setup_recruit(week: int) -> tuple[str, dict]:
    fid, team = _insert_franchise(week=week)
    franchise_recruits_data_collection.insert_one(
        {"franchise_id": fid, "recruit_id": "r1", "name": "Recruit"}
    )
    return fid, {"teams": [team], "recruit_id": "r1"}


def _setup_week35_orders() -> tuple[str, dict]:
    fid, ctx = _setup_recruit(35)
    franchise_team_data_collection.insert_one(
        {
            "franchise_id": ObjectId(fid),
            "team_id": ctx["teams"][0],
            franchise_routes.RECRUITING_ORDERS_WEEK_35_FIELD: [{"id": "r1", "points": 1}],
        }
    )
    return fid, ctx


def _setup_player() -> tuple[str, dict]:
    fid, team = _insert_franchise()
    player_id = "p1"
    franchise_players_data_collection.insert_one(
        {
            "franchise_id": fid,
            "player_id": player_id,
            "meta": {"team_id": str(team), "team": "A", "first_name": "Pat", "last_name": "Lee", "height": 78},
            "attributes": {"SC": 50},
        }
    )
    return fid, {"teams": [team], "player_id": player_id}


def _setup_training_user() -> tuple[str, dict]:
    fid, ctx = _setup_player()
    team = ctx["teams"][0]
    franchise_team_data_collection.insert_one(
        {
            "franchise_id": ObjectId(fid),
            "team_id": team,
            "players": [ctx["player_id"]],
            "plays": {"kept": True},
            "scouting_data": {"defense": {}},
            "team_attributes": {},
        }
    )
    db.franchises.update_one({"_id": ObjectId(fid)}, {"$set": {"week": 2}})
    return fid, ctx


def _setup_training_cpu() -> tuple[str, dict]:
    fid, team = _insert_franchise(
        week=3,
        training_status={"user_training_applied_week": 3, "cpu_training_camp_cuts_applied": True},
        practice_squad={"initialized": True},
    )
    return fid, {"teams": [team]}


def _setup_cut() -> tuple[str, dict]:
    fid, team = _insert_franchise(week=2)
    players = [f"c{i}" for i in range(13)]
    franchise_team_data_collection.insert_one(
        {"franchise_id": ObjectId(fid), "team_id": team, "players": players}
    )
    return fid, {"teams": [team], "cut": players[0]}


def _perform_complete(fid: str, _ctx: dict) -> None:
    with _cpu_patch():
        _post(
            "/franchise/complete-week",
            {
                "franchise_id": fid,
                "week": 1,
                "result": {"team1_id": "A", "team2_id": "B", "team1_score": 70, "team2_score": 60},
            },
        )


def _perform_phase_a(fid: str, _ctx: dict) -> None:
    with _cpu_patch():
        _post(
            "/franchise/complete-week/phase-a",
            {
                "franchise_id": fid,
                "week": 1,
                "result": {"team1_id": "A", "team2_id": "B", "team1_score": 70, "team2_score": 60},
            },
        )


def _perform_phase_b(fid: str, _ctx: dict) -> None:
    with _cpu_patch():
        _post("/franchise/complete-week/phase-b", {"franchise_id": fid, "week": 1})


def _perform_start_cpu(fid: str, _ctx: dict) -> None:
    with _cpu_patch():
        _post("/franchise/complete-week/start-cpu-sims", {"franchise_id": fid, "week": 1})


def _perform_training_user(fid: str, ctx: dict) -> None:
    def _execute(players, team, allocations, coaching_focus, **kw):
        return players, team or {}, kw.get("plays_data"), kw.get("scouting_data"), {
            "player_logs": {},
            "team_log": {},
            "coaching_focus": {},
        }

    with patch(
        "BackEnd.models.training_execution_v2.execute_training",
        side_effect=_execute,
    ), patch(
        "BackEnd.constants.training_shape.training_points_spent",
        return_value=24,
    ), patch.object(franchise_routes, "compute_position_ratings", return_value={}):
        _post(
            "/franchise/run-training/user",
            {
                "franchise_id": fid,
                "team_id": str(ctx["teams"][0]),
                "training_data": {"player_drills": {}, "team_drills": {}, "general": {}},
            },
        )


def _perform_training_cpu(fid: str, _ctx: dict) -> None:
    with patch.object(franchise_routes, "_apply_franchise_cpu_training"), patch(
        "BackEnd.practice_squad.manager.run_practice_squad_week",
        return_value={"initialized": True, "training_job": {"status": "complete"}},
    ), patch.object(franchise_routes, "_build_ps_game_results_news_story", return_value=None):
        _post("/franchise/run-training/cpu-train", {"franchise_id": fid})


def _perform_orders(fid: str, _ctx: dict) -> None:
    _post("/franchise/recruiting-orders", {"franchise_id": fid, "recruit_ids": ["r1"]})


def _perform_orders_35(fid: str, _ctx: dict) -> None:
    _post(
        "/franchise/recruiting-orders",
        {"franchise_id": fid, "order_entries": [{"id": "r1", "points": 1, "playing_time": False}]},
    )


def _perform_watchlist(fid: str, _ctx: dict) -> None:
    _patch("/franchise/recruiting-watchlist", {"franchise_id": fid, "recruit_id": "r1", "watching": True})


def _perform_week35(fid: str, _ctx: dict) -> None:
    with patch.object(franchise_routes, "_apply_cpu_week_35_cuts"), patch.object(
        franchise_routes, "_run_week_35_signings", return_value={"signed_players": []}
    ), patch.object(franchise_routes, "_build_season_recruiting_results_story", return_value=None):
        _post("/franchise/run-week-35-recruiting", {"franchise_id": fid})


def _perform_visits(fid: str, _ctx: dict) -> None:
    doc = db.franchises.find_one({"_id": ObjectId(fid)})
    franchise_routes._apply_complete_week_recruiting_lean_updates(doc, 20, [])


def _perform_cut(fid: str, ctx: dict) -> None:
    with patch.object(
        franchise_routes,
        "_week_1_cut_requirement",
        return_value={"cut_required": True, "cut_count": 1},
    ):
        _post("/franchise/cut-players", {"franchise_id": fid, "player_ids": [ctx["cut"]]})


def _perform_cut_final(fid: str, _ctx: dict) -> None:
    _post("/franchise/cut-players-final", {"franchise_id": fid, "player_ids": []})


def _perform_focus(fid: str, ctx: dict) -> None:
    _post(
        "/franchise/player/development-focus",
        {"franchise_id": fid, "player_id": ctx["player_id"], "training_focus": "standard"},
    )


def _perform_gameplan(fid: str, ctx: dict) -> None:
    with patch(
        "BackEnd.utils.team_settings_manager.save_team_settings",
        return_value=(True, str(ctx["teams"][0]), "ftd"),
    ):
        res = client.put(
            "/api/gameplan",
            json={
                "mode": "franchise",
                "team_id": str(ctx["teams"][0]),
                "franchise_id": fid,
                "strategy_settings": {"offense": 2, "inside": 2, "outside": 2, "attack": 2},
            },
        )
    assert res.status_code == 200, res.text


def _perform_playbooks(fid: str, ctx: dict) -> None:
    with patch.object(
        gameplan_routes,
        "_normalize_playbook_settings_payload",
        side_effect=lambda incoming, *_a, **_k: {**(incoming or {}), "_meta": {}},
    ), patch.object(
        gameplan_routes,
        "_load_current_team_plays_for_save",
        return_value=({}, str(ctx["teams"][0])),
    ), patch.object(
        gameplan_routes, "compute_position_shot_weights", return_value={}
    ), patch(
        "BackEnd.utils.team_settings_manager.save_team_settings",
        return_value=(True, str(ctx["teams"][0]), "ftd"),
    ):
        res = client.post(
            "/api/playbooks",
            json={
                "mode": "franchise",
                "team_id": str(ctx["teams"][0]),
                "franchise_id": fid,
                "playbook_settings": {},
            },
        )
    assert res.status_code == 200, res.text


def _perform_finish(fid: str, _ctx: dict) -> None:
    from BackEnd.models.franchise_manager import FranchiseManager as RealManager

    class _Manager(RealManager):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.schedule_manager.generate_schedule = lambda: []
            self._build_region_team_map = lambda: {"E": []}
            self._build_recruit_lean = lambda *_a, **_k: {}

    with patch("BackEnd.models.franchise_manager.FranchiseManager", _Manager), patch(
        "BackEnd.models.recruit_sets.load_unused_set_or_generate",
        return_value=([], None),
    ):
        _post("/franchise/finish-season", {"franchise_id": fid})


def _perform_sim_rest(fid: str, _ctx: dict) -> None:
    with patch.object(franchise_routes.ft, "get_eos_week_games", return_value=[]), patch.object(
        franchise_routes,
        "_eos_calendar_advance_update_fields",
        return_value={"week": 31},
    ):
        _post("/franchise/sim-rest-of-tournament", {"franchise_id": fid})


def _perform_championship(fid: str, _ctx: dict) -> None:
    class _Game:
        def __init__(self, home, away):
            self.score = {home: 70, away: 60}

    with patch.object(franchise_routes, "run_simulation", side_effect=lambda h, a: _Game(h, a)), patch.object(
        franchise_routes, "summarize_game_state", return_value={"quarter": 4}
    ), patch.object(franchise_routes.stat_updater, "finalize_game"), patch.object(
        franchise_routes.ftp, "record_tournament_game_result"
    ), patch.object(franchise_routes.ftp, "advance_national_bracket"), patch.object(
        franchise_routes, "_persist_week_35_awards_if_needed"
    ), patch.object(franchise_routes, "maybe_award_franchise_win_geek_points"), patch.object(
        franchise_routes, "maybe_award_franchise_loss_geek_points"
    ), patch.object(franchise_routes, "maybe_award_franchise_eos_title_championship"):
        _post("/franchise/sim-championship", {"franchise_id": fid})


def _seen(path: str, extra: dict | None = None):
    def perform(fid: str, _ctx: dict) -> None:
        body = {"franchise_id": fid}
        if extra:
            body.update(extra)
        _patch(path, body)

    return perform


def _setup_seen() -> tuple[str, dict]:
    fid, team = _insert_franchise()
    return fid, {"teams": [team]}


def _setup_visits() -> tuple[str, dict]:
    fid, team = _insert_franchise(week=20)
    return fid, {"teams": [team]}


def _setup_finish() -> tuple[str, dict]:
    fid, team = _insert_franchise(week=36, season_transition_token="tok-browse")
    return fid, {"teams": [team]}


def _setup_sim_rest() -> tuple[str, dict]:
    fid, team = _insert_franchise(
        week=30,
        eos_tournament_active=True,
        region_tournaments={"E": {"round1": []}},
    )
    return fid, {"teams": [team]}


def _setup_championship() -> tuple[str, dict]:
    home, away = ObjectId(), ObjectId()
    db.teams.insert_many(
        [
            {"_id": home, "name": "Home", "record": {"W": 0, "L": 0}},
            {"_id": away, "name": "Away", "record": {"W": 0, "L": 0}},
        ]
    )
    fid, _team = _insert_franchise(
        team_id=home,
        user_team_id="Home",
        national_tournament={
            "bracket": {"final": [{"home_team": str(home), "away_team": str(away)}]}
        },
    )
    return fid, {"teams": [home, away]}


WRITERS: tuple[Writer, ...] = (
    Writer("complete-week", _setup_league, _perform_complete),
    Writer("complete-week-phase-a", _setup_league, _perform_phase_a),
    Writer("complete-week-phase-b", _setup_phase_b, _perform_phase_b),
    Writer("start-cpu-sims", _setup_league, _perform_start_cpu),
    Writer("run-training-user", _setup_training_user, _perform_training_user),
    Writer("run-training-cpu", _setup_training_cpu, _perform_training_cpu),
    Writer("recruiting-orders", lambda: _setup_recruit(20), _perform_orders),
    Writer("recruiting-orders-week-35", lambda: _setup_recruit(35), _perform_orders_35),
    Writer("recruiting-watchlist", lambda: _setup_recruit(3), _perform_watchlist),
    Writer("run-week-35-recruiting", _setup_week35_orders, _perform_week35),
    Writer("recruit-visits", _setup_visits, _perform_visits),
    Writer("cut-players", _setup_cut, _perform_cut),
    Writer("cut-players-final", lambda: _insert_pair(35), _perform_cut_final),
    Writer("development-focus", _setup_player, _perform_focus),
    Writer("put-gameplan", _setup_seen, _perform_gameplan),
    Writer("post-playbooks", _setup_seen, _perform_playbooks),
    Writer("finish-season", _setup_finish, _perform_finish),
    Writer("sim-rest-of-tournament", _setup_sim_rest, _perform_sim_rest),
    Writer("sim-championship", _setup_championship, _perform_championship),
    Writer("seen-region-bye", _setup_seen, _seen("/franchise/region-bye-modal-seen")),
    Writer("seen-conference-rs-region", _setup_seen, _seen("/franchise/conference-rs-region-modal-seen")),
    Writer("seen-bracket-reveal", _setup_seen, _seen("/franchise/bracket-reveal-modal-seen", {"reveal_key": "region"})),
    Writer("seen-recruiting-results", _setup_seen, _seen("/franchise/recruiting-results-modal-seen")),
    Writer("seen-recruit-visit", _setup_seen, _seen("/franchise/recruit-visit-modal-seen")),
    Writer("seen-invite-seed", _setup_seen, _seen("/franchise/invite-seed-modal-seen")),
    Writer("seen-week-35-reveal", _setup_seen, _seen("/franchise/week-35-reveal-seen")),
    Writer("seen-week-36-results", _setup_seen, _seen("/franchise/week-36-results-seen")),
    Writer("seen-recruiting-wire", _setup_seen, _seen("/franchise/recruiting-wire-seen")),
    Writer("seen-walk-on-welcome", _setup_seen, _seen("/franchise/walk-on-welcome-modal-seen")),
)


def _insert_pair(week: int) -> tuple[str, dict]:
    fid, team = _insert_franchise(week=week)
    return fid, {"teams": [team]}


def _doc_hash(fid: str) -> str:
    doc = db.franchises.find_one({"_id": ObjectId(fid)})
    return json.dumps(doc, sort_keys=True, default=str)


@pytest.fixture
def as_owner():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": USER_ID}
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_writer_table_lists_every_required_writer():
    assert {writer.id for writer in WRITERS} == REQUIRED_WRITERS


@pytest.mark.parametrize("writer", WRITERS, ids=lambda writer: writer.id)
def test_writer_bumps_browse_etag(as_owner, writer: Writer):
    fid, ctx = writer.setup()
    try:
        _cycle(fid, lambda: writer.perform(fid, ctx))
    finally:
        _cleanup(fid, ctx.get("teams"))


def test_press_conference_does_not_use_browse_rev():
    text = Path("BackEnd/api/press_conference_routes.py").read_text()
    assert "browse_cache" not in text
    assert "bump_browse_rev" not in text
    assert "fold_browse_rev" not in text


def test_sim_modules_do_not_import_browse_cache():
    root = Path(__file__).resolve().parents[1]
    for rel in SIM_MODULES:
        text = (root / rel).read_text()
        assert "browse_cache" not in text, rel
        assert "bump_browse_rev" not in text, rel


def test_get_gameplan_franchise_does_not_write_the_franchise(as_owner):
    fid, team = _insert_franchise()
    try:
        before = _doc_hash(fid)
        tag = _etag(fid)
        res = client.get(
            "/api/gameplan",
            params={"mode": "franchise", "team_id": str(team), "franchise_id": fid},
        )
        assert res.status_code == 200, res.text
        assert _doc_hash(fid) == before
        assert _etag(fid) == tag
    finally:
        _cleanup(fid, [team])


def test_writing_gets_change_the_tag_when_the_franchise_changes(as_owner):
    """Playbooks init and practice-squad backfill still write. The tag must move."""
    fid, team = _insert_franchise(practice_squad={"initialized": True, "teams": {}})
    try:
        before_hash = _doc_hash(fid)
        before_tag = _etag(fid)
        playbooks = client.get(
            "/api/playbooks",
            params={"mode": "franchise", "team_id": str(team), "franchise_id": fid},
        )
        assert playbooks.status_code == 200, playbooks.text
        after_playbooks = _etag(fid)
        assert _doc_hash(fid) != before_hash
        assert after_playbooks != before_tag
        assert playbooks.headers.get("etag") != before_tag

        mid_hash = _doc_hash(fid)
        mid_tag = after_playbooks
        ps = client.get(
            "/franchise/practice-squad/team",
            params={"franchise_id": fid, "ps_team_id": "missing"},
        )
        assert ps.status_code == 404
        assert _doc_hash(fid) != mid_hash
        assert _etag(fid) != mid_tag
        assert ps.headers.get("etag")
        assert ps.headers.get("etag") != mid_tag
    finally:
        _cleanup(fid, [team])


def test_command_center_region_reconcile_bumps_when_it_writes(as_owner, monkeypatch):
    fid, team = _insert_franchise(
        week=30,
        eos_tournament_active=True,
        region_tournaments={"E": {"round1": [{"placeholder": True}]}},
    )
    franchise_team_data_collection.insert_one({"franchise_id": ObjectId(fid), "team_id": team})
    monkeypatch.setattr(
        franchise_routes.ft,
        "reconcile_region_tournaments_with_canonical",
        lambda *_args, **_kwargs: {"E": {"round1": [], "reconciled": True}},
    )
    try:
        before = _doc_hash(fid)
        tag = _etag(fid)
        res = client.get("/franchise/command-center/data", params={"franchise_id": fid})
        assert res.status_code == 200, res.text
        assert _doc_hash(fid) != before
        assert _etag(fid) != tag
        written = res.headers.get("etag") or ""
        assert ":30:1:" in written
    finally:
        _cleanup(fid, [team])


def test_304_does_not_run_the_handler_and_reads_once(as_owner, monkeypatch):
    fid, team = _insert_franchise()
    try:
        tag = _etag(fid)
        calls = {"verify": 0, "projected": 0}
        real_verify = franchise_routes.verify_franchise_owned_by_user
        real_find = db.franchises.find_one

        def _verify(*args, **kwargs):
            calls["verify"] += 1
            return real_verify(*args, **kwargs)

        def _find(*args, **kwargs):
            proj = kwargs.get("projection")
            if proj is None and len(args) > 1:
                proj = args[1]
            if isinstance(proj, dict) and "browse_rev" in proj:
                calls["projected"] += 1
            return real_find(*args, **kwargs)

        monkeypatch.setattr(franchise_routes, "verify_franchise_owned_by_user", _verify)
        monkeypatch.setattr(db.franchises, "find_one", _find)
        res = client.get(
            "/franchise/news",
            params={"franchise_id": fid},
            headers={"If-None-Match": tag},
        )
        assert res.status_code == 304
        assert res.content == b""
        assert calls["verify"] == 0
        assert calls["projected"] == 1
    finally:
        _cleanup(fid, [team])


def test_profile_bypasses_304(as_owner):
    fid, team = _insert_franchise()
    try:
        first = client.get("/franchise/news", params={"franchise_id": fid, "profile": "1"})
        assert first.status_code == 200, first.text
        tag = first.headers.get("etag")
        assert tag
        second = client.get(
            "/franchise/news",
            params={"franchise_id": fid, "profile": "1"},
            headers={"If-None-Match": tag},
        )
        assert second.status_code == 200
        assert second.content
        assert second.json()["news"] == []
    finally:
        _cleanup(fid, [team])


class _Counting:
    def __init__(self, inner):
        self.inner = inner
        self.projected = 0

    def find_one(self, *args, **kwargs):
        proj = kwargs.get("projection")
        if proj is None and len(args) > 1:
            proj = args[1]
        if isinstance(proj, dict) and "browse_rev" in proj:
            self.projected += 1
        return self.inner.find_one(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def _mini_app():
    mini = FastAPI()
    ran: list[str] = []

    @mini.middleware("http")
    async def _stamp(request, call_next):
        response = await call_next(request)
        return attach_browse_etag_header(request, response)

    @mini.get("/browse")
    @browse_cached
    def browse(franchise_id: str):
        ran.append("browse")
        return {"ok": True}

    return mini, ran


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_etag_cycle_on_mongo_and_sqlite(kind, tmp_path, monkeypatch):
    if kind == "mongo":
        store = create_store(_mongomock_env(tmp_path))
    else:
        store = create_store(_sqlite_env(tmp_path))
    counting = _Counting(store.franchises_collection)
    monkeypatch.setattr(
        "BackEnd.utils.browse_cache.franchise_collection",
        lambda: counting,
    )
    oid = ObjectId()
    store.franchises_collection.insert_one(
        {"_id": oid, "current_season": 2, "week": 4, "browse_rev": 0}
    )
    mini, ran = _mini_app()
    http = TestClient(mini)
    fid = str(oid)
    first = http.get("/browse", params={"franchise_id": fid})
    assert first.status_code == 200, first.text
    tag = first.headers.get("etag")
    assert tag and tag.startswith('W/"')
    assert f"{fid}:2:4:0:" in tag
    assert ran == ["browse"]

    store.franchises_collection.update_one({"_id": oid}, {"$inc": {"browse_rev": 1}})
    counting.projected = 0
    ran.clear()
    stale = http.get("/browse", params={"franchise_id": fid}, headers={"If-None-Match": tag})
    assert stale.status_code == 200, stale.text
    new_tag = stale.headers.get("etag")
    assert new_tag and new_tag != tag
    assert f"{fid}:2:4:1:" in new_tag
    assert ran == ["browse"]

    counting.projected = 0
    ran.clear()
    fresh = http.get("/browse", params={"franchise_id": fid}, headers={"If-None-Match": new_tag})
    assert fresh.status_code == 304
    assert fresh.content == b""
    assert ran == []
    assert counting.projected == 1

    # A handler that bumps must return the post-write tag.
    @mini.get("/writing")
    @browse_cached
    def writing(franchise_id: str):
        ran.append("writing")
        bump_browse_rev(franchise_id)
        return {"wrote": True}

    ran.clear()
    wrote = http.get("/writing", params={"franchise_id": fid})
    assert wrote.status_code == 200, wrote.text
    wrote_tag = wrote.headers.get("etag")
    assert wrote_tag and ":2:" in wrote_tag
    assert f"{fid}:2:4:2:" in wrote_tag
    again = http.get("/writing", params={"franchise_id": fid}, headers={"If-None-Match": wrote_tag})
    assert again.status_code == 304
    assert ran == ["writing"]
