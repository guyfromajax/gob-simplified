"""Saved-quarter guard on POST /api/simulate-quarter.

Legitimate requests reach simulate_quarter. A request for a quarter the saved
game has already passed returns 409 and does not simulate.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from BackEnd.api import api


client = TestClient(api.app)
ROOT = Path(__file__).parents[1]


class _DummyTeam:
    def __init__(self, name: str, team_id: str):
        self.name = name
        self.team_id = team_id
        self.points_by_quarter = [0, 0, 0, 0]
        self.team_fouls = 0
        self.timeouts = 4
        self.strategy_settings = {}
        self.playbook_settings = {}
        self.lineup = {"PG": object()}

    def get_team_game_stats(self):
        return {}

    def get_all_players(self):
        return []


class _DummyGM:
    def __init__(self, quarter: int = 1):
        self.quarter = quarter
        self.home_team = _DummyTeam("Home", "home-id")
        self.away_team = _DummyTeam("Away", "away-id")
        self.offense_team = self.home_team
        self.defense_team = self.away_team
        self.score = {"Home": 0, "Away": 0}
        self.team_totals = {"Home": {}, "Away": {}}
        self.turns = []
        self.text_log = []
        self.game_state = {
            "start_box_score": {},
            "score": self.score,
            "clock": "8:00",
            "time_remaining": 480,
            "quarter": quarter,
            "team_fouls": {"Home": 0, "Away": 0},
            "points_by_quarter": {"Home": [0, 0, 0, 0], "Away": [0, 0, 0, 0]},
        }

    def get_box_score(self):
        return {}


def _patch_common(monkeypatch, called):
    monkeypatch.setattr("BackEnd.utils.game_id_utils.normalize_game_id", lambda v: v)
    monkeypatch.setattr("BackEnd.utils.game_id_utils.validate_game_id", lambda v: True)
    monkeypatch.setattr(
        "BackEnd.utils.team_settings_manager.load_and_apply_team_settings_to_gamemanager",
        lambda **_kwargs: ({}, {}, {}, {}),
    )
    monkeypatch.setattr(api, "load_team_settings_from_doc", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        api,
        "summarize_game_state",
        lambda gm, **_kwargs: {
            "score": dict(gm.score),
            "quarter": gm.quarter,
            "clock": gm.game_state.get("clock", "8:00"),
            "time_remaining": gm.game_state.get("time_remaining", 480),
            "game_id": "gid",
        },
    )
    monkeypatch.setattr(api, "restore_timeout_resume_state", lambda *_args, **_kwargs: None)

    def _fake_sim(gm_obj, *_args, **_kwargs):
        called["count"] += 1
        called["quarter"] = gm_obj.quarter
        return gm_obj

    monkeypatch.setattr(api, "simulate_quarter", _fake_sim)


GAME_ID = "0123456789abcdef01234567"


class _DummyCollection:
    def find_one(self, *_args, **_kwargs):
        return None

    def update_one(self, *_args, **_kwargs):
        class _R:
            matched_count = 1
            modified_count = 0
            upserted_id = None

        return _R()


def _saved_game(quarter, **extra):
    doc = {
        "_id": GAME_ID,
        "quarter": quarter,
        "home_team_id": "home-id",
        "away_team_id": "away-id",
        "home_team_name": "Home",
        "away_team_name": "Away",
        "mode": "single",
        "score": {"Home": 10, "Away": 8},
        "clock": "1:20",
        "time_remaining": 80,
        "shot_clock_remaining": 30,
        "players": [],
        "teams": {
            "home-id": {"name": "Home", "team_fouls": 0, "timeouts": 4},
            "away-id": {"name": "Away", "team_fouls": 0, "timeouts": 4},
        },
        "game_stats_initialized": True,
        "marker": "untouched",
    }
    doc.update(extra)
    return doc


def _install_saved_game(monkeypatch, saved):
    monkeypatch.setattr(api, "games_collection", _DummyCollection())
    monkeypatch.setattr(api, "find_game_doc", lambda *_args, **_kwargs: (saved, GAME_ID))
    monkeypatch.setattr(api, "GameManager", lambda *_args, **_kwargs: _DummyGM(quarter=saved.get("quarter", 1)))


def _post(quarter, **extra):
    body = {
        "game_id": GAME_ID,
        "home_team": "Home",
        "away_team": "Away",
        "quarter": quarter,
        "mode": "single",
    }
    body.update(extra)
    return client.post("/api/simulate-quarter", json=body)


def test_fresh_q1_play_is_allowed(monkeypatch):
    called = {"count": 0, "quarter": None}
    gm = _DummyGM(quarter=1)
    monkeypatch.setattr(api, "ongoing_games", {GAME_ID: gm})
    _patch_common(monkeypatch, called)
    res = _post(1, full_sim=False, advance_method="play_quarter")
    assert res.status_code == 200
    assert called["count"] == 1
    assert called["quarter"] == 1


def test_next_quarter_after_break_is_allowed(monkeypatch):
    called = {"count": 0, "quarter": None}
    gm = _DummyGM(quarter=3)
    monkeypatch.setattr(api, "ongoing_games", {GAME_ID: gm})
    _patch_common(monkeypatch, called)
    res = _post(3, advance_method="play_quarter")
    assert res.status_code == 200
    assert called["count"] == 1
    assert gm.quarter == 3


def test_timeout_and_foul_out_resume_are_allowed(monkeypatch):
    for next_play in ("SIDE_INBOUND", "FREE_THROW"):
        called = {"count": 0, "quarter": None}
        gm = _DummyGM(quarter=2)
        saved = _saved_game(2, timeout_next_play_type=next_play)
        monkeypatch.setattr(api, "ongoing_games", {GAME_ID: gm})
        _patch_common(monkeypatch, called)
        _install_saved_game(monkeypatch, saved)
        monkeypatch.setattr(
            api,
            "restore_timeout_resume_state",
            lambda *_args, next_play=next_play, **_kwargs: {
                "quarter": 2,
                "timeout_next_play_type": next_play,
                "timeout_offense_team_id": "home-id",
                "clock": "1:20",
                "time_remaining": 80,
            },
        )
        res = _post(2, resume_from_timeout=True)
        assert res.status_code == 200, (next_play, res.text)
        assert called["count"] == 1
        assert saved["marker"] == "untouched"


def test_anchor_resume_rewrites_stale_quarter_and_is_allowed(monkeypatch):
    called = {"count": 0, "quarter": None}
    snapshot = _saved_game(4, clock="2:10", time_remaining=130)
    saved = _saved_game(4, resume_anchor={"snapshot": snapshot, "resume_from_timeout": False})
    monkeypatch.setattr(api, "ongoing_games", {GAME_ID: _DummyGM(quarter=4)})
    _patch_common(monkeypatch, called)
    _install_saved_game(monkeypatch, saved)
    res = _post(1, resume_from_anchor=True)
    assert res.status_code == 200, res.text
    assert called["count"] == 1
    assert called["quarter"] == 4
    assert saved["marker"] == "untouched"


def test_refresh_at_quarter_break_and_mid_quarter_are_allowed(monkeypatch):
    for saved_quarter, clock, remaining in ((3, "8:00", 480), (2, "3:11", 191)):
        called = {"count": 0, "quarter": None}
        gm = _DummyGM(quarter=saved_quarter)
        gm.game_state["clock"] = clock
        gm.game_state["time_remaining"] = remaining
        monkeypatch.setattr(api, "ongoing_games", {GAME_ID: gm})
        _patch_common(monkeypatch, called)
        res = _post(saved_quarter)
        assert res.status_code == 200
        assert called["count"] == 1


def test_sim_game_and_sim_rest_of_game_are_allowed(monkeypatch):
    for method in ("sim_full_game", "sim_rest_of_game"):
        called = {"count": 0, "quarter": None}
        gm = _DummyGM(quarter=2)
        monkeypatch.setattr(api, "ongoing_games", {GAME_ID: gm})
        _patch_common(monkeypatch, called)
        res = _post(2, full_sim=True, advance_method=method)
        assert res.status_code == 200, method
        assert called["count"] == 1


def test_overtime_quarter_is_allowed(monkeypatch):
    called = {"count": 0, "quarter": None}
    gm = _DummyGM(quarter=5)
    monkeypatch.setattr(api, "ongoing_games", {GAME_ID: gm})
    _patch_common(monkeypatch, called)
    res = _post(5)
    assert res.status_code == 200
    assert called["count"] == 1
    assert called["quarter"] == 5


def test_tutorial_and_tournament_games_are_allowed(monkeypatch):
    for mode, extra in (
        ("tutorial", {"mode": "tutorial"}),
        ("tournament", {"mode": "tournament", "tournament_id": "eos-1"}),
    ):
        called = {"count": 0, "quarter": None}
        gm = _DummyGM(quarter=2)
        monkeypatch.setattr(api, "ongoing_games", {GAME_ID: gm})
        _patch_common(monkeypatch, called)
        res = _post(2, **extra)
        assert res.status_code == 200, mode
        assert called["count"] == 1


def test_saved_quarter_ahead_of_request_is_blocked(monkeypatch):
    called = {"count": 0, "quarter": None}
    gm = _DummyGM(quarter=3)
    monkeypatch.setattr(api, "ongoing_games", {GAME_ID: gm})
    _patch_common(monkeypatch, called)
    res = _post(2)
    assert res.status_code == 409
    body = res.json()
    assert body["error"] == "QUARTER_ALREADY_PLAYED"
    assert body["saved_quarter"] == 3
    assert body["requested_quarter"] == 2
    assert called["count"] == 0
    assert gm.quarter == 3


def test_q1_request_while_memory_is_past_q1_reloads_saved_and_blocks(monkeypatch):
    called = {"count": 0, "quarter": None}
    saved = _saved_game(3)
    monkeypatch.setattr(api, "ongoing_games", {GAME_ID: _DummyGM(quarter=3)})
    _patch_common(monkeypatch, called)
    _install_saved_game(monkeypatch, saved)
    res = _post(1)
    assert res.status_code == 409
    body = res.json()
    assert body["error"] == "QUARTER_ALREADY_PLAYED"
    assert body["saved_quarter"] == 3
    assert body["requested_quarter"] == 1
    assert called["count"] == 0
    assert saved["quarter"] == 3
    assert saved["marker"] == "untouched"


def test_q1_request_when_saved_game_is_past_q1_is_blocked(monkeypatch):
    called = {"count": 0, "quarter": None}
    saved = {"_id": GAME_ID, "quarter": 4, "marker": "untouched"}
    monkeypatch.setattr(api, "ongoing_games", {})
    monkeypatch.setattr(api, "games_collection", object())
    _patch_common(monkeypatch, called)
    monkeypatch.setattr(api, "find_game_doc", lambda *_args, **_kwargs: (saved, GAME_ID))
    res = _post(1)
    assert res.status_code == 409
    body = res.json()
    assert body["error"] == "QUARTER_ALREADY_PLAYED"
    assert body["saved_quarter"] == 4
    assert body["requested_quarter"] == 1
    assert called["count"] == 0
    assert saved["quarter"] == 4
    assert saved["marker"] == "untouched"


def test_cpu_week_and_practice_squad_do_not_use_this_endpoint():
    franchise = (ROOT / "BackEnd/api/franchise_routes.py").read_text()
    practice = (ROOT / "BackEnd/practice_squad/sim.py").read_text()
    assert "simulate_quarter(gm)" in franchise
    assert "simulate_quarter(gm)" in practice
    assert "/api/simulate-quarter" not in franchise
    assert "/api/simulate-quarter" not in practice
