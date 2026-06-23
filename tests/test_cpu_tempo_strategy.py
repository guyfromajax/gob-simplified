"""CPU tempo (Q4 situational) and alterations autoset behavior."""

from types import SimpleNamespace

import pytest

from BackEnd.models.team_manager import TeamManager


def _cpu_team(name="CPU"):
    return SimpleNamespace(name=name)


@pytest.mark.parametrize(
    "quarter,time_remaining,score,expected",
    [
        (3, 120, {"CPU": 80, "OPP": 70}, "roll"),
        (4, 300, {"CPU": 91, "OPP": 80}, 0),  # winning: 11 > 300/30 (10)
        (4, 300, {"CPU": 85, "OPP": 80}, "roll"),  # winning: 5 <= 10
        (4, 200, {"CPU": 70, "OPP": 90}, 4),  # losing, >90s: 20 > 200/30
        (4, 200, {"CPU": 75, "OPP": 80}, "roll"),  # losing, >90s: 5 <= 200/30
        (4, 80, {"CPU": 70, "OPP": 100}, 0),  # losing, <=90s: 30 > 80/4 (20)
        (4, 80, {"CPU": 85, "OPP": 95}, 4),  # losing, <=90s: 10 > 80/30, 10 <= 20
        (4, 80, {"CPU": 93, "OPP": 95}, "roll"),  # losing, <=90s: 2 <= 80/30 (2.67)
        (4, 80, {"CPU": 90, "OPP": 90}, "roll"),  # tied
        (5, 60, {"CPU": 100, "OPP": 95}, 0),  # OT winning: 5 > 60/30
    ],
)
def test_compute_cpu_tempo_q4_branches(monkeypatch, quarter, time_remaining, score, expected):
    team = _cpu_team()
    monkeypatch.setattr(TeamManager, "init_tempo_random", staticmethod(lambda: 2))

    game_state = {
        "quarter": quarter,
        "time_remaining": time_remaining,
        "score": score,
    }
    result = TeamManager._compute_cpu_tempo(team, game_state)

    if expected == "roll":
        assert result == 2
    else:
        assert result == expected


def test_compute_cpu_tempo_without_game_state_uses_weighted_roll(monkeypatch):
    team = _cpu_team()
    monkeypatch.setattr(TeamManager, "init_tempo_random", staticmethod(lambda: 3))

    assert TeamManager._compute_cpu_tempo(team, None) == 3


def test_autoset_passes_game_state_for_q4_tempo(monkeypatch):
    from BackEnd.utils import db_utils

    captured = {}

    def fake_compute(self, game_state=None):
        captured["game_state"] = game_state
        return {"tempo": 0, "alterations": 2}

    team = SimpleNamespace(
        name="CPU",
        is_user_team=False,
        strategy_settings={},
        _compute_strategic_strategy_settings=lambda game_state=None: fake_compute(team, game_state),
    )
    gs = {"quarter": 4, "time_remaining": 60, "score": {"CPU": 90, "OPP": 80}}

    db_utils.autoset_strategy_settings(team, gs)

    assert captured["game_state"] is gs
    assert team.strategy_settings["tempo"] == 0
