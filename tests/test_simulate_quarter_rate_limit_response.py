from starlette.requests import Request
from starlette.responses import Response

from BackEnd.api import api


def _make_request() -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/simulate-quarter",
        "raw_path": b"/api/simulate-quarter",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_simulate_quarter_early_return_is_response(monkeypatch):
    class DummyTeam:
        def __init__(self, name: str):
            self.name = name

    class DummyGM:
        def __init__(self):
            self.home_team = DummyTeam("Home")
            self.away_team = DummyTeam("Away")
            self.quarter = 3
            self.game_state = {"start_box_score": {}, "score": {"Home": 10, "Away": 8}}
            self.score = self.game_state["score"]

    def fake_summary(gm):
        return {"score": gm.score}

    monkeypatch.setattr(api, "summarize_game_state", fake_summary)
    monkeypatch.setattr(api, "load_team_settings_from_doc", lambda *args, **kwargs: None)
    monkeypatch.setattr(api, "ongoing_games", {"gid": DummyGM()})

    body = api.QuarterSimulationRequest(
        game_id="gid",
        home_team="Home",
        away_team="Away",
        quarter=2,  # Already simulated (gm is at quarter 3)
    )
    response = api.simulate_quarter_endpoint(_make_request(), body)

    assert isinstance(response, Response)
    assert response.status_code == 200
