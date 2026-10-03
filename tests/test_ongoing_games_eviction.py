"""ongoing_games must not leak finished or abandoned GameManagers.

- final game: evicted after the final save (simulate-turn / simulate-quarter)
- post-final readers (GET /api/game/{id}, resume-state) fall back to the doc
- in-progress game: not evicted by the finish logic
- abandoned game: evicted by the idle TTL / LRU cap
"""

import logging

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api import api
from BackEnd.db import games_collection as mock_games
from BackEnd.utils.live_game_cache import LiveGameCache, evict_game

client = TestClient(api.app)


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


# --- LiveGameCache bounds ------------------------------------------------------


def test_cache_keeps_plain_dict_interface():
    cache = LiveGameCache()
    gm = object()
    cache["g1"] = gm
    assert cache.get("g1") is gm and cache["g1"] is gm
    assert "g1" in cache and len(cache) == 1 and list(cache.keys()) == ["g1"]
    assert cache.get("missing") is None
    del cache["g1"]
    assert "g1" not in cache
    cache["g2"] = gm
    assert cache.pop("g2") is gm
    cache["g3"] = gm
    cache.clear()
    assert len(cache) == 0


def test_idle_entry_evicted_by_ttl_on_next_store(caplog):
    clock = _Clock()
    cache = LiveGameCache(idle_ttl_seconds=100, max_games=10, clock=clock)
    abandoned, active = object(), object()
    cache["abandoned"] = abandoned
    cache["active"] = active
    clock.now += 60
    cache.get("active")  # a read counts as activity
    clock.now += 60      # abandoned idle 120s, active idle 60s
    with caplog.at_level(logging.INFO, logger="BackEnd.utils.live_game_cache"):
        cache["new"] = object()
    assert "abandoned" not in cache
    assert cache.get("active") is active and "new" in cache
    lines = [r for r in caplog.records if "[ONGOING-GAMES-EVICT]" in r.getMessage()]
    assert len(lines) == 1 and lines[0].levelno == logging.INFO
    assert "game_id=abandoned reason=idle_ttl remaining=2" in lines[0].getMessage()


def test_lru_cap_evicts_least_recently_touched_game():
    clock = _Clock()
    cache = LiveGameCache(idle_ttl_seconds=10_000, max_games=2, clock=clock)
    cache["a"] = object()
    clock.now += 1
    cache["b"] = object()
    clock.now += 1
    cache.get("a")  # b is now the least recently used
    clock.now += 1
    cache["c"] = object()
    assert set(cache.keys()) == {"a", "c"}


def test_aliases_of_one_game_age_and_evict_together():
    clock = _Clock()
    cache = LiveGameCache(idle_ttl_seconds=100, max_games=10, clock=clock)
    gm = object()
    cache["raw-id"] = gm
    cache["normalized-id"] = gm
    clock.now += 90
    cache.get("normalized-id")  # only one alias touched: game stays live
    clock.now += 50
    cache["other"] = object()
    assert cache.get("raw-id") is gm and cache.get("normalized-id") is gm
    clock.now += 200
    cache["another"] = object()
    assert "raw-id" not in cache and "normalized-id" not in cache


def test_evict_game_removes_every_alias_and_works_on_plain_dict():
    gm, other = object(), object()
    cache = {"raw": gm, "norm": gm, "x": other}
    assert sorted(evict_game(cache, "final", "raw")) == ["norm", "raw"]
    assert cache == {"x": other}
    assert evict_game(cache, "final", "missing") == []


# --- final eviction through the endpoints ---------------------------------------


class _DummyTeam:
    def __init__(self, name):
        self.name = name
        self.team_fouls = 0
        self.timeouts = 4

    def get_team_game_stats(self):
        return {}

    def get_all_players(self):
        return []


class _EogGM:
    """simulate-turn early-return path: clock at 0, no pending FT."""

    def __init__(self, quarter, home, away):
        self.home_team = _DummyTeam("Home")
        self.away_team = _DummyTeam("Away")
        self.offense_team = self.home_team
        self.defense_team = self.away_team
        self.score = {"Home": home, "Away": away}
        self.quarter = quarter
        self.turns = []
        self.game_state = {
            "time_remaining": 0,
            "clock": "0:00",
            "offensive_state": "HCO",
            "free_throws_remaining": 0,
            "quarter": quarter,
        }

    def simulate_macro_turn(self):
        raise AssertionError("no turn should run at 0:00 without a pending FT")

    def get_box_score(self):
        return {}


def _patch_turn_save(monkeypatch):
    monkeypatch.setattr(
        api,
        "summarize_game_state",
        lambda gm, **_kw: {"quarter": gm.quarter, "is_final": True, "game_state": {}},
    )
    monkeypatch.setattr(api, "_build_resume_anchor", lambda *a, **k: {"anchor_type": "quarter_break"})


def test_simulate_turn_final_evicts_game(monkeypatch):
    _patch_turn_save(monkeypatch)
    gid = str(ObjectId())
    gm = _EogGM(quarter=4, home=70, away=64)
    cache = LiveGameCache()
    cache[gid] = gm
    monkeypatch.setattr(api, "ongoing_games", cache)

    res = client.post("/api/simulate-turn", json={"game_id": gid})
    assert res.status_code == 200
    assert res.json()["is_final"] is True
    assert gid not in api.ongoing_games


def test_simulate_turn_in_progress_quarter_break_is_not_evicted(monkeypatch):
    _patch_turn_save(monkeypatch)
    gid = str(ObjectId())
    gm = _EogGM(quarter=2, home=30, away=28)
    cache = LiveGameCache()
    cache[gid] = gm
    monkeypatch.setattr(api, "ongoing_games", cache)

    res = client.post("/api/simulate-turn", json={"game_id": gid})
    assert res.status_code == 200
    assert res.json()["is_final"] is False
    assert api.ongoing_games.get(gid) is gm


def test_simulate_turn_tied_end_of_regulation_is_not_evicted(monkeypatch):
    _patch_turn_save(monkeypatch)
    gid = str(ObjectId())
    gm = _EogGM(quarter=4, home=60, away=60)  # overtime next
    monkeypatch.setattr(api, "ongoing_games", {gid: gm})

    res = client.post("/api/simulate-turn", json={"game_id": gid})
    assert res.status_code == 200
    assert res.json()["is_final"] is False
    assert api.ongoing_games.get(gid) is gm


def test_simulate_turn_final_kept_when_final_save_fails(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(api, "summarize_game_state", _boom)
    gid = str(ObjectId())
    gm = _EogGM(quarter=4, home=70, away=64)
    monkeypatch.setattr(api, "ongoing_games", {gid: gm})

    res = client.post("/api/simulate-turn", json={"game_id": gid})
    assert res.status_code == 200
    assert api.ongoing_games.get(gid) is gm  # TTL cleans it up later


class _QTeam:
    def __init__(self, name):
        self.name = name
        self.points_by_quarter = [0, 0, 0, 0]


class _QGM:
    def __init__(self, quarter):
        self.quarter = quarter
        self.home_team = _QTeam("Home")
        self.away_team = _QTeam("Away")
        self.game_state = {"start_box_score": {}, "score": {"Home": 0, "Away": 0}}
        self.score = self.game_state["score"]
        self.stats_printed = False

    def print_game_statistics(self):
        self.stats_printed = True


def _run_simulate_quarter(monkeypatch, gm, final):
    gid = str(ObjectId())
    cache = LiveGameCache()
    cache[gid] = gm
    monkeypatch.setattr(api, "ongoing_games", cache)
    monkeypatch.setattr(api, "simulate_quarter", lambda gm, *a, **k: None)
    monkeypatch.setattr(
        api,
        "summarize_game_state",
        lambda gm, **_kw: {"score": gm.score, "quarter": gm.quarter, "is_final": final},
    )
    res = client.post("/api/simulate-quarter", json={
        "game_id": gid, "home_team": "Home", "away_team": "Away",
        "quarter": gm.quarter, "home_lineup": {}, "away_lineup": {},
    })
    assert res.status_code == 200, res.text
    return gid


def test_simulate_quarter_final_evicts_game_after_save(monkeypatch):
    gm = _QGM(quarter=4)
    gid = _run_simulate_quarter(monkeypatch, gm, final=True)
    assert gid not in api.ongoing_games
    saved = mock_games.find_one({"_id": ObjectId(gid)})
    assert saved and saved["is_final"] is True
    assert gm.stats_printed  # post-final work in the same request still ran


def test_simulate_quarter_in_progress_is_not_evicted(monkeypatch):
    gm = _QGM(quarter=2)
    gid = _run_simulate_quarter(monkeypatch, gm, final=False)
    assert api.ongoing_games.get(gid) is gm


# --- post-final readers fall back to the saved doc -------------------------------


def _final_doc():
    gid = ObjectId()
    mock_games.insert_one({
        "_id": gid,
        "mode": "single",
        "is_final": True,
        "quarter": 4,
        "time_remaining": 0,
        "clock": "0:00",
        "home_team_id": "HOME",
        "away_team_id": "AWAY",
        "teams": {
            "HOME": {"name": "Home", "score": 70, "box_score": {}},
            "AWAY": {"name": "Away", "score": 64, "box_score": {}},
        },
    })
    return str(gid)


def test_resume_state_reports_final_from_doc_after_eviction(monkeypatch):
    monkeypatch.setattr(api, "ongoing_games", LiveGameCache())
    gid = _final_doc()
    res = client.get(f"/api/game/{gid}/resume-state")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "final"
    assert body["has_cached_game"] is False


def test_get_game_reads_doc_after_eviction(monkeypatch):
    monkeypatch.setattr(api, "ongoing_games", LiveGameCache())
    gid = _final_doc()
    res = client.get(f"/api/game/{gid}")
    assert res.status_code == 200
    body = res.json()
    assert body["clock"] == "0:00"
    assert body["home_team_id"] == "HOME" and body["away_team_id"] == "AWAY"
