import BackEnd.main as main
from BackEnd.models.game_manager import GameManager
from BackEnd.models.player import Player
from BackEnd.utils.roster_loader import load_roster


def fake_simulate_macro_turn(self):
    # End the quarter immediately
    self.game_state["time_remaining"] = 0


def fake_build_lineup(team_name):
    _, players = load_roster(team_name)
    positions = ["PG", "SG", "SF", "PF", "C"]
    return {pos: Player(p) for pos, p in zip(positions, players[:5])}


def test_simulate_quarter_advances_game(monkeypatch):
    monkeypatch.setattr(GameManager, "simulate_macro_turn", fake_simulate_macro_turn)
    monkeypatch.setattr(main, "build_lineup_from_mongo", fake_build_lineup)

    gm = GameManager("Lancaster", "Bentley-Truman")

    main.simulate_quarter(gm)
    assert gm.quarter == 2
    assert gm.game_state["time_remaining"] == 0

    # add fouls to ensure reset
    gm.home_team.team_fouls = 3
    gm.away_team.team_fouls = 4

    main.simulate_quarter(gm)
    assert gm.quarter == 3
    assert gm.game_state["team_fouls"][gm.home_team.name] == 0
    assert gm.game_state["team_fouls"][gm.away_team.name] == 0

