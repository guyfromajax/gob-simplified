from fastapi.testclient import TestClient

from BackEnd.api import api


client = TestClient(api.app)


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
    def __init__(self, quarter: int = 2):
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
            "clock": "1:20",
            "time_remaining": 80,
            "quarter": quarter,
            "team_fouls": {"Home": 0, "Away": 0},
            "points_by_quarter": {"Home": [0, 0, 0, 0], "Away": [0, 0, 0, 0]},
        }

    def get_box_score(self):
        return {}


def _patch_common(monkeypatch):
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
            "home_team_id": gm.home_team.team_id,
            "away_team_id": gm.away_team.team_id,
            "teams": {
                gm.home_team.team_id: {"name": gm.home_team.name, "totals": {}},
                gm.away_team.team_id: {"name": gm.away_team.name, "totals": {}},
            },
        },
    )


def test_non_resume_request_ignores_timeout_state(monkeypatch):
    gm = _DummyGM(quarter=2)
    game_id = "0123456789abcdef01234567"
    monkeypatch.setattr(api, "ongoing_games", {game_id: gm})
    monkeypatch.setattr("BackEnd.utils.game_id_utils.normalize_game_id", lambda v: v)
    _patch_common(monkeypatch)

    applied = {"count": 0}
    monkeypatch.setattr(
        api,
        "apply_timeout_resume_state_to_gm",
        lambda *_args, **_kwargs: applied.__setitem__("count", applied["count"] + 1),
    )

    called = {"resume": None}

    def _fake_sim_quarter(gm_obj, *_args, **kwargs):
        called["resume"] = kwargs.get("resume_from_timeout")
        return gm_obj

    monkeypatch.setattr(api, "simulate_quarter", _fake_sim_quarter)
    monkeypatch.setattr(
        api,
        "restore_timeout_resume_state",
        lambda *_args, **_kwargs: {
            "quarter": 2,
            "timeout_next_play_type": "SIDE_INBOUND",
            "timeout_offense_team_id": "home-id",
            "clock": "1:20",
            "time_remaining": 80,
        },
    )

    res = client.post(
        "/api/simulate-quarter",
        json={
            "game_id": game_id,
            "home_team": "Home",
            "away_team": "Away",
            "quarter": 2,
            "mode": "single",
            "full_sim": False,
        },
    )

    assert res.status_code == 200
    assert called["resume"] is False
    assert applied["count"] == 0


def test_resume_request_applies_timeout_state_when_explicit(monkeypatch):
    gm = _DummyGM(quarter=3)
    game_id = "abcdef0123456789abcdef01"
    monkeypatch.setattr(api, "ongoing_games", {game_id: gm})
    monkeypatch.setattr("BackEnd.utils.game_id_utils.normalize_game_id", lambda v: v)
    _patch_common(monkeypatch)

    called = {"resume": None, "quarter_at_call": None}

    def _fake_sim_quarter(gm_obj, *_args, **kwargs):
        called["resume"] = kwargs.get("resume_from_timeout")
        called["quarter_at_call"] = gm_obj.quarter
        return gm_obj

    monkeypatch.setattr(api, "simulate_quarter", _fake_sim_quarter)
    monkeypatch.setattr(api, "GameManager", lambda *_args, **_kwargs: _DummyGM(quarter=3))
    monkeypatch.setattr(
        api,
        "restore_timeout_resume_state",
        lambda *_args, **_kwargs: {
            "quarter": 3,
            "timeout_next_play_type": "SIDE_INBOUND",
            "timeout_offense_team_id": "home-id",
            "clock": "1:20",
            "time_remaining": 80,
        },
    )
    monkeypatch.setattr(
        api,
        "find_game_doc",
        lambda *_args, **_kwargs: (
            {
                "_id": game_id,
                "quarter": 3,
                "home_team_id": "home-id",
                "away_team_id": "away-id",
                "score": {"Home": 0, "Away": 0},
                "clock": "1:20",
                "time_remaining": 80,
                "shot_clock_remaining": 30,
                "timeout_next_play_type": "SIDE_INBOUND",
                "timeout_offense_team_id": "home-id",
                "players": [],
                "teams": {
                    "home-id": {"name": "Home", "team_fouls": 0, "timeouts": 4},
                    "away-id": {"name": "Away", "team_fouls": 0, "timeouts": 4},
                },
                "game_stats_initialized": True,
            },
            game_id,
        ),
    )

    class _DummyCollection:
        def find_one(self, *_args, **_kwargs):
            return None

        def update_one(self, *_args, **_kwargs):
            class _R:
                matched_count = 1
                modified_count = 0
                upserted_id = None

            return _R()

    monkeypatch.setattr(api, "games_collection", _DummyCollection())

    res = client.post(
        "/api/simulate-quarter",
        json={
            "game_id": game_id,
            "home_team": "Home",
            "away_team": "Away",
            "quarter": 3,
            "resume_from_timeout": True,
            "mode": "single",
            "full_sim": False,
        },
    )

    assert res.status_code == 200
    assert called["resume"] is True
    assert called["quarter_at_call"] == 3


def test_resume_request_normalizes_quarter_mismatch(monkeypatch):
    gm = _DummyGM(quarter=3)
    game_id = "1234567890abcdef12345678"
    monkeypatch.setattr(api, "ongoing_games", {game_id: gm})
    monkeypatch.setattr("BackEnd.utils.game_id_utils.normalize_game_id", lambda v: v)
    _patch_common(monkeypatch)

    called = {"resume": None, "quarter_at_call": None}

    def _fake_sim_quarter(gm_obj, *_args, **kwargs):
        called["resume"] = kwargs.get("resume_from_timeout")
        called["quarter_at_call"] = gm_obj.quarter
        return gm_obj

    monkeypatch.setattr(api, "simulate_quarter", _fake_sim_quarter)
    monkeypatch.setattr(api, "GameManager", lambda *_args, **_kwargs: _DummyGM(quarter=3))
    monkeypatch.setattr(
        api,
        "restore_timeout_resume_state",
        lambda *_args, **_kwargs: {
            "quarter": 3,
            "timeout_next_play_type": "SIDE_INBOUND",
            "timeout_offense_team_id": "home-id",
            "clock": "1:20",
            "time_remaining": 80,
        },
    )
    monkeypatch.setattr(
        api,
        "find_game_doc",
        lambda *_args, **_kwargs: (
            {
                "_id": game_id,
                "quarter": 3,
                "home_team_id": "home-id",
                "away_team_id": "away-id",
                "score": {"Home": 0, "Away": 0},
                "clock": "1:20",
                "time_remaining": 80,
                "shot_clock_remaining": 30,
                "timeout_next_play_type": "SIDE_INBOUND",
                "timeout_offense_team_id": "home-id",
                "players": [],
                "teams": {
                    "home-id": {"name": "Home", "team_fouls": 0, "timeouts": 4},
                    "away-id": {"name": "Away", "team_fouls": 0, "timeouts": 4},
                },
                "game_stats_initialized": True,
            },
            game_id,
        ),
    )

    class _DummyCollection:
        def find_one(self, *_args, **_kwargs):
            return None

        def update_one(self, *_args, **_kwargs):
            class _R:
                matched_count = 1
                modified_count = 0
                upserted_id = None

            return _R()

    monkeypatch.setattr(api, "games_collection", _DummyCollection())

    res = client.post(
        "/api/simulate-quarter",
        json={
            "game_id": game_id,
            "home_team": "Home",
            "away_team": "Away",
            "quarter": 2,
            "resume_from_timeout": True,
            "mode": "single",
            "full_sim": False,
        },
    )

    assert res.status_code == 200
    assert called["resume"] is True
    assert called["quarter_at_call"] == 3
