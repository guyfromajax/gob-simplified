import BackEnd.main as main
from BackEnd.models.game_manager import GameManager
from BackEnd.models.player import Player
from BackEnd.utils.roster_loader import load_roster


def test_run_simulation_handles_overtime(monkeypatch):
    def fake_simulate_macro_turn(self):
        # end period immediately
        self.game_state["time_remaining"] = 0
        q = self.game_state["quarter"]
        home = self.home_team.name
        away = self.away_team.name
        if q == 4 and self.score[home] == 0:
            # force a tie at end of regulation
            self.score[home] = 90
            self.score[away] = 90
            self.home_team.points_by_quarter[3] = 90
            self.away_team.points_by_quarter[3] = 90
        elif q == 5 and self.score[home] == 90:
            # give home team the win in OT1
            self.score[home] = 92
            self.home_team.points_by_quarter[4] = 2

    def fake_build_lineup(team_name):
        _, players = load_roster(team_name)
        positions = ["PG", "SG", "SF", "PF", "C"]
        return {pos: Player(p) for pos, p in zip(positions, players[:5])}

    monkeypatch.setattr(GameManager, "simulate_macro_turn", fake_simulate_macro_turn)
    monkeypatch.setattr(main, "build_lineup_from_mongo", fake_build_lineup)

    gm = main.run_simulation("Lancaster", "Bentley-Truman")

    assert gm.quarter == 5
    home = gm.home_team.name
    away = gm.away_team.name
    assert gm.score[home] == 92
    assert gm.score[away] == 90
    assert len(gm.home_team.points_by_quarter) == 5
    assert gm.home_team.points_by_quarter[4] == 2
