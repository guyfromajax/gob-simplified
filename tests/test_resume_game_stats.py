import BackEnd.main as main
from BackEnd.models.game_manager import GameManager
from BackEnd.models.team_manager import TeamManager
from BackEnd.db import games_collection
from BackEnd.constants import BOX_SCORE_KEYS


def fake_load_roster(team_name):
    players = []
    for i, pos in enumerate(["PG", "SG", "SF", "PF", "C"]):
        players.append({
            "_id": f"{team_name}_{i}",
            "first_name": team_name,
            "last_name": pos,
            "team": team_name,
            "attributes": {"SC": 50, "SH": 50, "ID": 50, "OD": 50, "PS": 50, "BH": 50, "RB": 50, "AG": 50, "ST": 50, "ND": 50, "IQ": 50, "FT": 50, "NG": 1.0},
        })
    team_doc = {"name": team_name}
    return team_doc, players


def fake_build_lineup(team):
    roster = list(team.players.values())
    positions = ["PG", "SG", "SF", "PF", "C"]
    return {pos: roster[i] for i, pos in enumerate(positions)}


def no_turn(self):
    self.game_state["time_remaining"] = 0


def test_resume_game_skips_stat_reset(monkeypatch):
    monkeypatch.setattr("BackEnd.models.team_manager.load_roster", fake_load_roster)
    monkeypatch.setattr(main, "build_lineup_from_mongo", fake_build_lineup)
    monkeypatch.setattr(GameManager, "simulate_macro_turn", no_turn)

    game_id = "existing"
    games_collection.insert_one({
        "_id": game_id,
        "game_stats_initialized": True,
        "players": [
            {
                "playerId": "Lancaster_0",
                "team": "home",
                "team_id": None,
                "pos": "PG",
                "stats": {**{k: 0 for k in BOX_SCORE_KEYS}, "PTS": 5},
            }
        ],
    })

    gm = GameManager("Lancaster", "Bentley-Truman")

    main.simulate_quarter(gm, game_id=game_id)

    pg = gm.home_team.players["Lancaster_0"]
    assert pg.stats["game"]["PTS"] == 5
    assert gm.game_state.get("game_stats_initialized") is True
