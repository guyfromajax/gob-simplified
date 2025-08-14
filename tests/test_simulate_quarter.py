import BackEnd.main as main
from BackEnd.models.game_manager import GameManager
from BackEnd.models.player import Player


def fake_simulate_macro_turn(self):
    # End the quarter immediately
    self.game_state["time_remaining"] = 0


def fake_build_lineup(team):
    """Return a simple deterministic lineup for tests.

    Constructs new :class:`Player` objects each call without relying on any
    database state, allowing the simulation to proceed with minimal data.
    """
    name = team.name if hasattr(team, "name") else str(team)
    positions = ["PG", "SG", "SF", "PF", "C"]
    lineup = {}
    for i, pos in enumerate(positions):
        pdata = {
            "_id": f"{name}_{i}",
            "first_name": f"{name}{i}",
            "last_name": pos,
            "team": name,
            "attributes": {},
        }
        lineup[pos] = Player(pdata)
    return lineup


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

