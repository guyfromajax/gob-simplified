import BackEnd.main as main
from BackEnd.models.game_manager import GameManager


def fake_turn_add_points(self):
    pg = self.home_team.lineup["PG"]
    pg.stats["game"]["PTS"] += 2
    self.game_state["time_remaining"] = 0


def fake_load_roster(team_name):
    players = []
    for i, pos in enumerate(["PG", "SG", "SF", "PF", "C"]):
        players.append({
            "_id": f"{team_name}_{i}",
            "first_name": f"{team_name}{i}",
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


def test_player_stats_persist_across_quarters(monkeypatch):
    monkeypatch.setattr("BackEnd.models.team_manager.load_roster", fake_load_roster)
    monkeypatch.setattr(main, "build_lineup_from_mongo", fake_build_lineup)
    monkeypatch.setattr(GameManager, "simulate_macro_turn", fake_turn_add_points)

    gm = GameManager("Lancaster", "Bentley-Truman")

    main.simulate_quarter(gm)
    pg = gm.home_team.lineup["PG"]
    assert pg.stats["game"]["PTS"] == 2

    gm.home_team.lineup = {}

    main.simulate_quarter(gm)
    same_player = gm.home_team.players[pg.player_id]
    assert same_player is pg
    assert same_player.stats["game"]["PTS"] == 4

