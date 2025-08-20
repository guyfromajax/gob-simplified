from fastapi.testclient import TestClient
import pytest

from BackEnd.api import api

client = TestClient(api.app)


def make_fake_load_roster(short_team_name: str):
    def fake_load_roster(team_name):
        num_players = 4 if team_name == short_team_name else 5
        players = []
        for i in range(num_players):
            players.append({
                "_id": f"{team_name}_{i}",
                "first_name": team_name,
                "last_name": str(i),
                "team": team_name,
                "attributes": {
                    "SC": 50,
                    "SH": 50,
                    "ID": 50,
                    "OD": 50,
                    "PS": 50,
                    "BH": 50,
                    "RB": 50,
                    "AG": 50,
                    "ST": 50,
                    "ND": 50,
                    "IQ": 50,
                    "FT": 50,
                    "NG": 1.0,
                },
            })
        team_doc = {"name": team_name}
        return team_doc, players
    return fake_load_roster


@pytest.mark.parametrize("short_side", ["home", "away"])
def test_simulate_quarter_short_roster(monkeypatch, short_side):
    home_team = "ShortTeam" if short_side == "home" else "FullTeam"
    away_team = "ShortTeam" if short_side == "away" else "FullTeam"
    short_team_name = home_team if short_side == "home" else away_team

    monkeypatch.setattr("BackEnd.models.team_manager.load_roster", make_fake_load_roster(short_team_name))

    api.ongoing_games.clear()

    response = client.post(
        "/api/simulate-quarter",
        json={"home_team": home_team, "away_team": away_team},
    )
    assert response.status_code == 400
    assert "fewer than 5 players" in response.json()["detail"]
    assert short_team_name in response.json()["detail"]


def test_simulate_quarter_endpoint_handles_none_games_collection(monkeypatch):
    class DummyTeam:
        def __init__(self, name: str):
            self.name = name
            self.points_by_quarter = [0, 0, 0, 0]

    class DummyGM:
        def __init__(self):
            self.quarter = 1
            self.home_team = DummyTeam("Home")
            self.away_team = DummyTeam("Away")
            self.game_state = {"start_box_score": {}, "score": {"Home": 0, "Away": 0}}
            self.score = self.game_state["score"]

    dummy_gm = DummyGM()
    monkeypatch.setattr(api, "ongoing_games", {"gid": dummy_gm})
    monkeypatch.setattr(api, "games_collection", None)

    def fake_simulate_quarter(gm, home_lineup, away_lineup, game_id):
        gm.quarter += 1

    def fake_summarize_game_state(gm):
        return {"score": gm.score}

    monkeypatch.setattr(api, "simulate_quarter", fake_simulate_quarter)
    monkeypatch.setattr(api, "summarize_game_state", fake_summarize_game_state)

    request = api.QuarterSimulationRequest(
        game_id="gid",
        home_team="Home",
        away_team="Away",
        quarter=1,
        home_lineup={},
        away_lineup={},
    )

    summary = api.simulate_quarter_endpoint(request)
    assert summary["game_id"] == "gid"
