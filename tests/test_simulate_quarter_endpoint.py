from fastapi.testclient import TestClient
import pytest
import json

from BackEnd.api import api

client = TestClient(api.app)


def test_bulk_sim_metadata_sets_sticky_flag_for_sim_full_game():
    request = api.QuarterSimulationRequest(
        home_team="Home",
        away_team="Away",
        full_sim=True,
        advance_method="sim_full_game",
    )
    summary = {}

    bulk_sim_used = api._apply_bulk_sim_metadata(summary, request)

    assert bulk_sim_used is True
    assert summary["advance_method"] == "sim_full_game"
    assert summary["bulk_sim_used"] is True


def test_bulk_sim_metadata_sets_sticky_flag_for_sim_rest_of_game():
    request = api.QuarterSimulationRequest(
        home_team="Home",
        away_team="Away",
        full_sim=True,
        advance_method="sim_rest_of_game",
    )
    summary = {}

    bulk_sim_used = api._apply_bulk_sim_metadata(summary, request)

    assert bulk_sim_used is True
    assert summary["advance_method"] == "sim_rest_of_game"
    assert summary["bulk_sim_used"] is True


def test_bulk_sim_metadata_stays_true_after_later_non_bulk_save():
    request = api.QuarterSimulationRequest(
        home_team="Home",
        away_team="Away",
        full_sim=False,
        advance_method="play_quarter",
    )
    summary = {}

    bulk_sim_used = api._apply_bulk_sim_metadata(
        summary,
        request,
        previous_doc={"bulk_sim_used": True},
    )

    assert bulk_sim_used is True
    assert summary["advance_method"] == "play_quarter"
    assert summary["bulk_sim_used"] is True


def test_bulk_sim_metadata_does_not_set_flag_for_play_quarter_or_sim_quarter():
    for method, full_sim in (("play_quarter", False), ("sim_quarter", True)):
        request = api.QuarterSimulationRequest(
            home_team="Home",
            away_team="Away",
            full_sim=full_sim,
            advance_method=method,
        )
        summary = {}

        bulk_sim_used = api._apply_bulk_sim_metadata(summary, request)

        assert bulk_sim_used is False
        assert summary["advance_method"] == method
        assert "bulk_sim_used" not in summary


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


def test_simulate_quarter_unknown_id_quarter1(monkeypatch):
    class DummyTeam:
        def __init__(self, name: str):
            self.name = name
            self.points_by_quarter = [0, 0, 0, 0]

    class DummyGM:
        def __init__(self, home, away):
            self.home_team = DummyTeam(home)
            self.away_team = DummyTeam(away)
            self.quarter = 1
            self.game_state = {"start_box_score": {}, "score": {home: 0, away: 0}}
            self.score = self.game_state["score"]

    def fake_simulate_quarter(gm, home_lineup, away_lineup, game_id):
        gm.quarter += 1

    def fake_summarize_game_state(gm):
        return {"score": gm.score}

    monkeypatch.setattr(api, "GameManager", DummyGM)
    monkeypatch.setattr(api, "simulate_quarter", fake_simulate_quarter)
    monkeypatch.setattr(api, "summarize_game_state", fake_summarize_game_state)

    api.ongoing_games.clear()

    request = api.QuarterSimulationRequest(
        game_id="unknown",
        home_team="Home",
        away_team="Away",
        quarter=1,
    )

    summary = api.simulate_quarter_endpoint(request)
    assert summary["game_id"] != "unknown"
    assert summary["quarter"] == 1


def test_simulate_quarter_sequential_game_id(monkeypatch):
    class DummyTeam:
        def __init__(self, name: str):
            self.name = name
            self.points_by_quarter = [0, 0, 0, 0]

    class DummyGM:
        def __init__(self, home: str, away: str):
            self.home_team = DummyTeam(home)
            self.away_team = DummyTeam(away)
            self.quarter = 1
            self.game_state = {"start_box_score": {}, "score": {home: 0, away: 0}}
            self.score = self.game_state["score"]

    def fake_simulate_quarter(gm, home_lineup, away_lineup, game_id):
        gm.quarter += 1

    def fake_summarize_game_state(gm):
        return {"score": gm.score}

    monkeypatch.setattr(api, "GameManager", DummyGM)
    monkeypatch.setattr(api, "simulate_quarter", fake_simulate_quarter)
    monkeypatch.setattr(api, "summarize_game_state", fake_summarize_game_state)

    api.ongoing_games.clear()

    res1 = client.post(
        "/api/simulate-quarter", json={"home_team": "Home", "away_team": "Away"}
    )
    assert res1.status_code == 200
    gid = res1.json()["game_id"]

    res2 = client.post(
        "/api/simulate-quarter",
        json={"home_team": "Home", "away_team": "Away", "quarter": 2, "game_id": gid},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["game_id"] == gid


def test_simulate_quarter_mismatched_game_id(monkeypatch):
    class DummyTeam:
        def __init__(self, name: str):
            self.name = name
            self.points_by_quarter = [0, 0, 0, 0]

    class DummyGM:
        def __init__(self, home: str, away: str):
            self.home_team = DummyTeam(home)
            self.away_team = DummyTeam(away)
            self.quarter = 1
            self.game_state = {"start_box_score": {}, "score": {home: 0, away: 0}}
            self.score = self.game_state["score"]

    def fake_simulate_quarter(gm, home_lineup, away_lineup, game_id):
        gm.quarter += 1

    def fake_summarize_game_state(gm):
        return {"score": gm.score}

    monkeypatch.setattr(api, "GameManager", DummyGM)
    monkeypatch.setattr(api, "simulate_quarter", fake_simulate_quarter)
    monkeypatch.setattr(api, "summarize_game_state", fake_summarize_game_state)

    api.ongoing_games.clear()

    res1 = client.post(
        "/api/simulate-quarter", json={"home_team": "Home", "away_team": "Away"}
    )
    assert res1.status_code == 200
    gid = res1.json()["game_id"]

    res2 = client.post(
        "/api/simulate-quarter",
        json={"home_team": "Different", "away_team": "Away", "quarter": 2, "game_id": gid},
    )
    assert res2.status_code == 400
    assert res2.json()["detail"] == "game_id belongs to a different matchup"


def test_simulate_quarter_restores_team_stats_from_unified_teams(monkeypatch):
    class DummyCollection:
        def __init__(self, doc):
            self.doc = doc

        def find_one(self, query, *_args, **_kwargs):
            return self.doc if query.get("_id") == self.doc.get("_id") else None

        def update_one(self, *_args, **_kwargs):
            return None

    class DummyTeam:
        def __init__(self, name: str, team_id: str):
            self.name = name
            self.team_id = team_id
            self.team_fouls = 0
            self.timeouts = 4
            self.strategy_settings = {}
            self.playbook_settings = {}
            self.lineup = {"PG": object()}  # keep truthy to avoid lineup rebuild path

        def get_player_by_id(self, _player_id):
            return None

    class DummyGM:
        def __init__(self, home: str, away: str, **_kwargs):
            self.home_team = DummyTeam(home, "home-id")
            self.away_team = DummyTeam(away, "away-id")
            self.quarter = 1
            self.score = {home: 0, away: 0}
            self.team_totals = {home: {}, away: {}}
            self.game_state = {
                "score": self.score,
                "start_box_score": {},
                "points_by_quarter": {home: [0, 0, 0, 0], away: [0, 0, 0, 0]},
            }
            self.turns = []

    def fake_simulate_quarter(_gm, _home_lineup, _away_lineup, _game_id, *_args, **_kwargs):
        return None

    def fake_summarize_game_state(gm, **_kwargs):
        return {
            "score": dict(gm.score),
            "teams": {
                gm.home_team.team_id: {
                    "name": gm.home_team.name,
                    "totals": gm.team_totals[gm.home_team.name],
                    "points_by_quarter": gm.game_state["points_by_quarter"][gm.home_team.name],
                },
                gm.away_team.team_id: {
                    "name": gm.away_team.name,
                    "totals": gm.team_totals[gm.away_team.name],
                    "points_by_quarter": gm.game_state["points_by_quarter"][gm.away_team.name],
                },
            },
        }

    saved_doc = {
        "_id": "gid-unified",
        "quarter": 3,
        "home_team_id": "home-id",
        "away_team_id": "away-id",
        "teams": {
            "home-id": {
                "name": "Home",
                "score": 61,
                "team_fouls": 3,
                "timeouts": 2,
                "totals": {"PTS": 61, "REB": 28},
                "points_by_quarter": [20, 18, 23, 0],
            },
            "away-id": {
                "name": "Away",
                "score": 55,
                "team_fouls": 4,
                "timeouts": 1,
                "totals": {"PTS": 55, "REB": 24},
                "points_by_quarter": [17, 16, 22, 0],
            },
        },
        "players": [],
        "game_stats_initialized": True,
    }

    monkeypatch.setattr(api, "GameManager", DummyGM)
    monkeypatch.setattr(api, "simulate_quarter", fake_simulate_quarter)
    monkeypatch.setattr(api, "summarize_game_state", fake_summarize_game_state)
    monkeypatch.setattr(api, "games_collection", DummyCollection(saved_doc))
    monkeypatch.setattr(
        "BackEnd.utils.team_settings_manager.load_and_apply_team_settings_to_gamemanager",
        lambda **_kwargs: ({}, {}, {}, {}),
    )
    monkeypatch.setattr(api, "ongoing_games", {})

    request = api.QuarterSimulationRequest(
        game_id="gid-unified",
        home_team="Home",
        away_team="Away",
        quarter=4,
        mode="single",
    )

    response = api.simulate_quarter_endpoint(None, request)
    payload = json.loads(response.body)
    gm = api.ongoing_games["gid-unified"]

    assert payload["score"]["Home"] == 61
    assert payload["score"]["Away"] == 55
    assert gm.team_totals["Home"]["PTS"] == 61
    assert gm.team_totals["Away"]["PTS"] == 55
    assert gm.game_state["points_by_quarter"]["Home"] == [20, 18, 23, 0]
    assert gm.game_state["points_by_quarter"]["Away"] == [17, 16, 22, 0]


def test_simulate_quarter_restores_team_stats_from_legacy_team_fields(monkeypatch):
    class DummyCollection:
        def __init__(self, doc):
            self.doc = doc

        def find_one(self, query, *_args, **_kwargs):
            return self.doc if query.get("_id") == self.doc.get("_id") else None

        def update_one(self, *_args, **_kwargs):
            return None

    class DummyTeam:
        def __init__(self, name: str, team_id: str):
            self.name = name
            self.team_id = team_id
            self.team_fouls = 0
            self.timeouts = 4
            self.strategy_settings = {}
            self.playbook_settings = {}
            self.lineup = {"PG": object()}

        def get_player_by_id(self, _player_id):
            return None

    class DummyGM:
        def __init__(self, home: str, away: str, **_kwargs):
            self.home_team = DummyTeam(home, "home-id")
            self.away_team = DummyTeam(away, "away-id")
            self.quarter = 1
            self.score = {home: 0, away: 0}
            self.team_totals = {home: {}, away: {}}
            self.game_state = {
                "score": self.score,
                "start_box_score": {},
                "points_by_quarter": {home: [0, 0, 0, 0], away: [0, 0, 0, 0]},
            }
            self.turns = []

    def fake_simulate_quarter(_gm, _home_lineup, _away_lineup, _game_id, *_args, **_kwargs):
        return None

    def fake_summarize_game_state(gm, **_kwargs):
        return {
            "score": dict(gm.score),
            "teams": {
                gm.home_team.team_id: {
                    "name": gm.home_team.name,
                    "totals": gm.team_totals[gm.home_team.name],
                    "points_by_quarter": gm.game_state["points_by_quarter"][gm.home_team.name],
                },
                gm.away_team.team_id: {
                    "name": gm.away_team.name,
                    "totals": gm.team_totals[gm.away_team.name],
                    "points_by_quarter": gm.game_state["points_by_quarter"][gm.away_team.name],
                },
            },
        }

    saved_doc = {
        "_id": "gid-legacy",
        "quarter": 3,
        "home_team_id": "home-id",
        "away_team_id": "away-id",
        "teams": {},
        "home_team": {
            "name": "Home",
            "score": 48,
            "team_fouls": 6,
            "timeouts": 1,
            "totals": {"PTS": 48, "REB": 19},
            "points_by_quarter": [14, 17, 17, 0],
        },
        "away_team": {
            "name": "Away",
            "score": 52,
            "team_fouls": 5,
            "timeouts": 2,
            "totals": {"PTS": 52, "REB": 21},
            "points_by_quarter": [13, 18, 21, 0],
        },
        "players": [],
        "game_stats_initialized": True,
    }

    monkeypatch.setattr(api, "GameManager", DummyGM)
    monkeypatch.setattr(api, "simulate_quarter", fake_simulate_quarter)
    monkeypatch.setattr(api, "summarize_game_state", fake_summarize_game_state)
    monkeypatch.setattr(api, "games_collection", DummyCollection(saved_doc))
    monkeypatch.setattr(
        "BackEnd.utils.team_settings_manager.load_and_apply_team_settings_to_gamemanager",
        lambda **_kwargs: ({}, {}, {}, {}),
    )
    monkeypatch.setattr(api, "ongoing_games", {})

    request = api.QuarterSimulationRequest(
        game_id="gid-legacy",
        home_team="Home",
        away_team="Away",
        quarter=4,
        mode="single",
    )

    response = api.simulate_quarter_endpoint(None, request)
    payload = json.loads(response.body)
    gm = api.ongoing_games["gid-legacy"]

    assert payload["score"]["Home"] == 48
    assert payload["score"]["Away"] == 52
    assert gm.team_totals["Home"]["PTS"] == 48
    assert gm.team_totals["Away"]["PTS"] == 52
    assert gm.game_state["points_by_quarter"]["Home"] == [14, 17, 17, 0]
    assert gm.game_state["points_by_quarter"]["Away"] == [13, 18, 21, 0]
