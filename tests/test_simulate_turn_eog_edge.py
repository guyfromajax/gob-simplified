from fastapi.testclient import TestClient

from BackEnd.api import api


client = TestClient(api.app)


class _DummyTeam:
    def __init__(self, name: str):
        self.name = name
        self.team_fouls = 0
        self.timeouts = 4

    def get_team_game_stats(self):
        return {}

    def get_all_players(self):
        return []


class _DummyGamesCollection:
    def update_one(self, *_args, **_kwargs):
        return None


def test_simulate_turn_zero_clock_no_pending_ft_returns_quarter_complete(monkeypatch):
    class DummyGM:
        def __init__(self):
            self.home_team = _DummyTeam("Home")
            self.away_team = _DummyTeam("Away")
            self.offense_team = self.home_team
            self.defense_team = self.away_team
            self.score = {"Home": 10, "Away": 8}
            self.quarter = 4
            self.turns = []
            self.game_state = {
                "time_remaining": 0,
                "clock": "0:00",
                "offensive_state": "HCO",
                "free_throws_remaining": 0,
            }
            self.sim_calls = 0

        def simulate_macro_turn(self):
            self.sim_calls += 1

        def get_box_score(self):
            return {}

    gm = DummyGM()
    monkeypatch.setattr(api, "ongoing_games", {"gid-zero-no-ft": gm})

    res = client.post("/api/simulate-turn", json={"game_id": "gid-zero-no-ft"})
    assert res.status_code == 200
    data = res.json()
    assert data["quarter_complete"] is True
    assert data["turn"] is None
    assert gm.sim_calls == 0


def test_simulate_turn_zero_clock_with_pending_ft_executes_turn(monkeypatch):
    class DummyGM:
        def __init__(self):
            self.home_team = _DummyTeam("Home")
            self.away_team = _DummyTeam("Away")
            self.offense_team = self.home_team
            self.defense_team = self.away_team
            self.score = {"Home": 10, "Away": 8}
            self.quarter = 4
            self.turns = []
            self.game_state = {
                "time_remaining": 0,
                "clock": "0:00",
                "offensive_state": "FREE_THROW",
                "free_throws_remaining": 1,
            }
            self.sim_calls = 0

        def simulate_macro_turn(self):
            self.sim_calls += 1
            # Simulate resolving the pending FT at 0:00
            self.game_state["free_throws_remaining"] = 0
            self.game_state["offensive_state"] = "HCO"
            self.turns.append(
                {
                    "result_type": "FREE_THROW",
                    "current_turn": "FREE_THROW",
                    "text": "FT made",
                    "time_elapsed": 0,
                }
            )

        def get_box_score(self):
            return {}

    gm = DummyGM()
    monkeypatch.setattr(api, "ongoing_games", {"gid-zero-with-ft": gm})
    monkeypatch.setattr(api, "games_collection", _DummyGamesCollection())

    res = client.post("/api/simulate-turn", json={"game_id": "gid-zero-with-ft"})
    assert res.status_code == 200
    data = res.json()
    assert gm.sim_calls == 1
    assert data["turn"] is not None
    assert data["turn"]["result_type"] == "FREE_THROW"
    # FT resolved; now quarter can complete.
    assert data["quarter_complete"] is True
