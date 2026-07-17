"""Steal → FAST_BREAK vs HCO routing (potential cutoffs × aggression)."""

from types import SimpleNamespace

import pytest

from BackEnd.engine.steal_fast_break_routing import (
    count_potential_steal_cutoff_defenders,
    steal_fast_break_probability,
)


def test_steal_fb_probability_table():
    assert steal_fast_break_probability(0, 0) == pytest.approx(0.50)
    assert steal_fast_break_probability(4, 0) == pytest.approx(0.99)
    assert steal_fast_break_probability(2, 1) == pytest.approx(0.40)
    assert steal_fast_break_probability(4, 1) == pytest.approx(0.80)
    assert steal_fast_break_probability(0, 2) == pytest.approx(0.00)
    assert steal_fast_break_probability(4, 5) == pytest.approx(0.40)
    assert steal_fast_break_probability(3, 3) == pytest.approx(0.30)


def _player(pid, x, y, ag=50):
    return SimpleNamespace(
        player_id=pid,
        coords={"x": float(x), "y": float(y)},
        attributes={"AG": ag},
    )


def test_count_potential_cutoffs_x_ahead_in_time():
    bh = _player("bh", 50, 25, ag=50)
    # Ahead on the drive path — should count.
    ahead = _player("d1", 70, 25, ag=80)
    # Behind the stealer — cannot produce x-ahead meet.
    behind = _player("d2", 40, 25, ag=99)
    # Far off the path and slow — typically not in time.
    sideline = _player("d3", 55, 2, ag=20)
    lineup = {
        "PG": ahead,
        "SG": behind,
        "SF": sideline,
        "PF": None,
        "C": None,
    }
    n = count_potential_steal_cutoff_defenders(
        bh_start={"x": 50.0, "y": 25.0},
        shot_spot={"x": 88.0, "y": 25.0},
        bh=bh,
        new_def_lineup=lineup,
        is_away_offense=False,
    )
    assert n >= 1
    assert n <= 2


def test_choose_steal_uses_victim_lineup_as_new_defense(monkeypatch):
    from BackEnd.engine import steal_fast_break_routing as sfr

    stealer = _player("stl", 55, 25)
    victim_pg = _player("vic-pg", 70, 25)
    stealing = SimpleNamespace(
        team_id="away",
        strategy_settings={"aggression": 4},
        lineup={"PG": stealer},
    )
    victim = SimpleNamespace(
        team_id="home",
        lineup={"PG": victim_pg, "SG": None, "SF": None, "PF": None, "C": None},
    )
    game = SimpleNamespace(
        game_state={"last_stealer_coords": {"x": 55.0, "y": 25.0}},
        defense_team=stealing,
        offense_team=victim,
        away_team=SimpleNamespace(team_id="away"),
        home_team=SimpleNamespace(team_id="home"),
    )

    monkeypatch.setattr(sfr, "sample_after_steal_shot_spot", lambda *_a, **_k: {"x": 88.0, "y": 25.0})
    monkeypatch.setattr(sfr, "count_potential_steal_cutoff_defenders", lambda **_k: 0)
    monkeypatch.setattr(sfr.random, "random", lambda: 0.0)  # always FB if p > 0

    assert sfr.choose_steal_next_offensive_state(game, stealer) == "FAST_BREAK"

    monkeypatch.setattr(sfr, "count_potential_steal_cutoff_defenders", lambda **_k: 3)
    monkeypatch.setattr(sfr.random, "random", lambda: 0.99)  # 40% table → HCO
    assert sfr.choose_steal_next_offensive_state(game, stealer) == "HCO"
