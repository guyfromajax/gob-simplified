from fastapi.testclient import TestClient

from BackEnd.api import api


client = TestClient(api.app)


class _DummyTeam:
    def __init__(self, name: str):
        self.name = name
        self.team_fouls = 0
        self.timeouts = 4
        self.strategy_calls = {}

    def get_team_game_stats(self):
        return {}

    def get_all_players(self):
        return []


class _DummyGM:
    def __init__(self, turn_payload: dict | None = None, timeout_turn: dict | None = None):
        self.home_team = _DummyTeam("Home")
        self.away_team = _DummyTeam("Away")
        self.offense_team = self.home_team
        self.defense_team = self.away_team
        self.score = {"Home": 10, "Away": 8}
        self.quarter = 2
        self.game_state = {
            "time_remaining": 120,
            "clock": "2:00",
            "offensive_state": "HCO",
            "free_throws_remaining": 0,
            "shot_clock_remaining": 20,
        }
        self.turns = [timeout_turn] if timeout_turn else []
        self._turn_payload = turn_payload
        self.sim_calls = 0

    def simulate_macro_turn(self):
        self.sim_calls += 1
        if self._turn_payload:
            self.turns.append(self._turn_payload)
            # Keep game live after one turn for non-quarter-complete response.
            self.game_state["time_remaining"] = 114
            self.game_state["clock"] = "1:54"
            self.game_state["shot_clock_remaining"] = 16

    def get_box_score(self):
        return {}


def test_simulate_turn_smoke_clamps_standard_turn(monkeypatch):
    turn_payload = {
        "result_type": "MISS",
        "text": "Missed jumper",
        "oDestinations": {"PG": {"x": 120, "y": -5}},
        "dDestinations": {"PG": {"x": -10, "y": 70}},
        "ball_spot": {"x": 200, "y": -30},
        "animations": [
            {
                "playerId": "p1",
                "end": {"x": 99, "y": 0},
                "movement": [{"coords": {"x": -4, "y": 53}}],
            }
        ],
    }
    gm = _DummyGM(turn_payload=turn_payload)
    monkeypatch.setattr(api, "ongoing_games", {"gid-clamp-smoke": gm})

    res = client.post("/api/simulate-turn", json={"game_id": "gid-clamp-smoke"})
    assert res.status_code == 200
    turn = res.json()["turn"]
    assert turn["oDestinations"]["PG"] == {"x": 91.0, "y": 2.0}
    assert turn["dDestinations"]["PG"] == {"x": 9.0, "y": 49.0}
    assert turn["ball_spot"] == {"x": 91.0, "y": 2.0}
    assert turn["animations"][0]["end"] == {"x": 91.0, "y": 2.0}
    assert turn["animations"][0]["movement"][0]["coords"] == {"x": 9.0, "y": 49.0}


def test_simulate_turn_smoke_preserves_side_inbound_exemption(monkeypatch):
    turn_payload = {
        "result_type": "SIDE_INBOUND",
        "text": "Side inbound",
        "oDestinations": {"PG": {"x": 2, "y": 51}},
        "dDestinations": {"PG": {"x": 97, "y": 0}},
        "ball_spot": {"x": 1, "y": 52},
        "animations": [{"movement": [{"coords": {"x": 3, "y": 50}}]}],
    }
    gm = _DummyGM(turn_payload=turn_payload)
    monkeypatch.setattr(api, "ongoing_games", {"gid-side-inbound-smoke": gm})

    res = client.post("/api/simulate-turn", json={"game_id": "gid-side-inbound-smoke"})
    assert res.status_code == 200
    turn = res.json()["turn"]
    assert turn["oDestinations"]["PG"] == {"x": 2, "y": 51}
    assert turn["dDestinations"]["PG"] == {"x": 97, "y": 0}
    assert turn["ball_spot"] == {"x": 1, "y": 52}
    assert turn["animations"][0]["movement"][0]["coords"] == {"x": 3, "y": 50}


def test_simulate_turn_smoke_preserves_timeout_exemption(monkeypatch):
    timeout_turn = {
        "result_type": "TIMEOUT",
        "timeout_reason": "USER",
        "text": "Timeout",
        "oDestinations": {"PG": {"x": 0, "y": 52}},
        "ball_spot": {"x": 0, "y": 52},
        "animations": [{"movement": [{"coords": {"x": 1, "y": 50}}]}],
    }
    gm = _DummyGM(timeout_turn=timeout_turn)
    monkeypatch.setattr(api, "ongoing_games", {"gid-timeout-smoke": gm})

    res = client.post("/api/simulate-turn", json={"game_id": "gid-timeout-smoke"})
    assert res.status_code == 200
    turn = res.json()["turn"]
    assert turn["result_type"] == "TIMEOUT"
    assert turn["oDestinations"]["PG"] == {"x": 0, "y": 52}
    assert turn["ball_spot"] == {"x": 0, "y": 52}
    assert turn["animations"][0]["movement"][0]["coords"] == {"x": 1, "y": 50}
    # Existing timeout is returned immediately (no new simulation turn).
    assert gm.sim_calls == 0
