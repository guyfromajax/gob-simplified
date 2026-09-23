"""The defender AG spread ships behind ``GOB_DEFENDER_AG_SPREAD``, **default OFF** (2026-09-24).

The shipped AG curve is nearly flat — across the real league a p90-AG defender is only 1.103×
a p10-AG one — so defenders all move alike. This widens the player multiplier for **defenders
only**, at the **endpoint only**, keeping AG=50 fixed:

    scale(AG) = (1 - s) + (AG / 100) * 2s,   s = DEFENDER_AG_SPREAD = 0.50

This is a shipped-defaults guard. It also pins the properties the build rests on:

  * at ``s = 0.10`` the wrapper is **byte-identical** to the shipped formula, so the kill
    switch is exact rather than merely equivalent;
  * **AG=50 is unchanged at every s** — the midpoint is preserved, so the average player never
    moves and the flag cannot be a stealth global speed change;
  * **offence is untouched** at any s;
  * **step duration T is untouched** at any s — this is the whole reason the spread lives at
    the endpoint and not in ``_ag_grid_per_game_sec``. Widening the shared function costs
    +11.2% game length at s=0.50 (reports/ag-spread-sweep-2026-09-24.md §5);
  * **the endpoint and the tween read the SAME wrapper.** If one is changed and not the other,
    the rendered motion stops matching the distance covered — so both call sites are pinned.
"""

import inspect
import os

import pytest

from BackEnd.utils import animation_step_helpers as ASH
from BackEnd.utils import transition_bridge as TB


class _P:
    def __init__(self, ag, pid="p"):
        self.player_id = pid
        self.attributes = {"AG": ag}


ARCHES = ("standard", "sprint", "cruise", "drift", "burst", "shot_motion", "compressed_hco")


@pytest.fixture
def clean_env(monkeypatch):
    """No flag set - so the helper returns its shipped default (OFF)."""
    monkeypatch.delenv(ASH.DEFENDER_AG_SPREAD_FLAG, raising=False)


@pytest.fixture
def spread_on(monkeypatch):
    monkeypatch.setenv(ASH.DEFENDER_AG_SPREAD_FLAG, "1")


def test_spread_defaults_off(clean_env):
    assert ASH.defender_ag_spread_enabled() is False, (
        "GOB_DEFENDER_AG_SPREAD must default OFF. This is built and measured, not flipped."
    )


def test_spread_kill_switch(clean_env, monkeypatch):
    monkeypatch.setenv(ASH.DEFENDER_AG_SPREAD_FLAG, "0")
    assert ASH.defender_ag_spread_enabled() is False
    monkeypatch.setenv(ASH.DEFENDER_AG_SPREAD_FLAG, "1")
    assert ASH.defender_ag_spread_enabled() is True


def test_flag_off_is_the_shipped_function_itself(clean_env):
    """OFF must return `_ag_grid_per_game_sec`'s own value for defenders too."""
    for arch in ARCHES:
        for ag in (0, 24, 39, 50, 73, 100, 144):
            assert ASH.defender_movement_rate(_P(ag), arch, True) == \
                ASH._ag_grid_per_game_sec(_P(ag), arch)


def test_s_010_is_byte_identical_to_the_shipped_formula(spread_on, monkeypatch):
    """The kill switch is exact, not approximate: (1-0.10) + (AG/100)*0.20 IS the shipped
    0.90 + (AG/100)*0.2. Checked across every archetype and the full AG range in play."""
    monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", 0.10)
    for arch in ARCHES:
        for ag in range(0, 145):
            assert ASH.defender_movement_rate(_P(ag), arch, True) == \
                ASH._ag_grid_per_game_sec(_P(ag), arch), (arch, ag)


def test_midpoint_is_preserved_at_every_s(spread_on, monkeypatch):
    """AG=50 must never move, or the flag is a global speed change in disguise."""
    for s in (0.10, 0.25, 0.50, 0.75, 1.00):
        monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", s)
        for arch in ARCHES:
            assert ASH.defender_movement_rate(_P(50), arch, True) == \
                ASH._ag_grid_per_game_sec(_P(50), arch), (s, arch)


def test_spread_constant_is_reused_not_copied(spread_on, monkeypatch):
    """Doubling DEFENDER_AG_SPREAD must double the deviation from the midpoint."""
    mid = ASH._ag_grid_per_game_sec(_P(50), "standard")
    monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", 0.25)
    d1 = ASH.defender_movement_rate(_P(100), "standard", True) - mid
    monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", 0.50)
    d2 = ASH.defender_movement_rate(_P(100), "standard", True) - mid
    assert d1 > 0
    assert d2 == pytest.approx(2 * d1)


def test_it_actually_widens(spread_on):
    """The point of the build: the p10->p90 league rate ratio must grow."""
    lo, hi = _P(24), _P(73)          # real-league p10 / p90
    today = ASH._ag_grid_per_game_sec(hi, "standard") / ASH._ag_grid_per_game_sec(lo, "standard")
    wide = (ASH.defender_movement_rate(hi, "standard", True)
            / ASH.defender_movement_rate(lo, "standard", True))
    assert today == pytest.approx(1.1034, abs=1e-3)
    assert wide > 1.6


def test_offence_is_untouched_at_any_s(spread_on, monkeypatch):
    for s in (0.10, 0.25, 0.50, 0.75, 1.00):
        monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", s)
        for arch in ARCHES:
            for ag in (0, 24, 50, 73, 144):
                assert ASH.defender_movement_rate(_P(ag), arch, False) == \
                    ASH._ag_grid_per_game_sec(_P(ag), arch), (s, arch, ag)


def test_the_shared_rate_function_is_not_touched():
    """The spread must NOT live in `_ag_grid_per_game_sec` or `ag_to_grid_per_game_sec`:
    those feed natural_t -> the gate -> step duration T, which is the +11.2% pacing trap."""
    from BackEnd.utils import shared as SH
    for fn in (ASH._ag_grid_per_game_sec, SH.ag_to_grid_per_game_sec):
        src = inspect.getsource(fn)
        assert "DEFENDER_AG_SPREAD" not in src
        assert "defender_ag_spread_enabled" not in src


def test_step_duration_is_computed_before_the_spread_is_applied():
    """The ordering constraint, pinned in source: in `build_walk_up_step`, `t` is frozen and
    `natural_t` consumed by the gate BEFORE `defender_movement_rate` is ever called. If someone
    moves the call earlier, a slow defender would start stretching T and the offence would wait
    for him instead of beating him."""
    src = inspect.getsource(TB.build_walk_up_step)
    i_rates = src.index("rate = _ag_grid_per_game_sec(player, arch)")
    i_t = src.index("t = max(float(min_t_game_sec), slowest_t)")
    i_spread = src.index("defender_movement_rate(")
    assert i_rates < i_t < i_spread, "the spread must be applied after T is frozen"


def test_natural_t_is_built_from_the_unwidened_rate():
    """natural_t feeds the gate. It must use `_ag_grid_per_game_sec`, never the wrapper."""
    src = inspect.getsource(TB.build_walk_up_step)
    head = src[:src.index("t = max(float(min_t_game_sec), slowest_t)")]
    assert "defender_movement_rate" not in head
    assert "natural_t[pid] = dist / rate" in head


def test_the_endpoint_and_the_tween_read_the_same_wrapper():
    """THE central invariant. If either call site stops using `defender_movement_rate`, the
    rendered motion and the simulated endpoint diverge — the animation stops matching the game.
    Both are pinned here so that change cannot pass silently."""
    endpoint_src = inspect.getsource(TB.build_walk_up_step)
    tween_src = inspect.getsource(ASH.stamp_tween_durations)
    assert "defender_movement_rate(" in endpoint_src, "endpoint stopped using the wrapper"
    assert "defender_movement_rate(" in tween_src, "tween stopped using the wrapper"
    # and the tween must not have reverted to the raw function
    assert "_ag_grid_per_game_sec(" not in tween_src, (
        "stamp_tween_durations must go through defender_movement_rate, not the raw rate"
    )


def test_the_tween_matches_the_endpoint_for_a_slow_defender(spread_on, monkeypatch):
    """End to end on the two functions that must agree: at the same rate, the duration the
    stamper writes covers exactly the distance the endpoint helper says was travelled."""
    monkeypatch.setattr(ASH, "DEFENDER_AG_SPREAD", 0.50)
    slow = _P(10, "D")
    rate = ASH.defender_movement_rate(slow, "standard", True)
    T = 1.0
    start = {"x": 0.0, "y": 0.0}
    target = {"x": 40.0, "y": 0.0}                    # far beyond rate*T
    end = TB._interrupted_coord(start, target, rate, T)
    covered = ((end["x"] - start["x"]) ** 2 + (end["y"] - start["y"]) ** 2) ** 0.5
    assert covered == pytest.approx(rate * T)
    start_blk = {"coords": {"D": start}, "archetype": {"D": "standard"}}
    ASH.stamp_tween_durations(start_blk, {"D": end}, T, {}, {"PG": slow})
    dur = start_blk["tween_durations"]["D"]
    assert dur * rate == pytest.approx(covered, abs=1e-6)


def test_no_new_rng(spread_on):
    """A spread is arithmetic. The wrapper must not draw."""
    from BackEnd.utils import sim_random
    st = sim_random.sim_rng.getstate()
    for ag in range(0, 101, 5):
        ASH.defender_movement_rate(_P(ag), "standard", True)
    assert sim_random.sim_rng.getstate() == st


def test_constants_unchanged():
    """Nothing retuned to build this."""
    from BackEnd.constants import (STANDARD_GRID_PER_GAME_SEC, SPRINT_GRID_PER_GAME_SEC,
                                   CRUISE_GRID_PER_GAME_SEC, DRIFT_GRID_PER_GAME_SEC,
                                   BURST_GRID_PER_GAME_SEC, SHOT_MOTION_GRID_PER_GAME_SEC)
    assert (STANDARD_GRID_PER_GAME_SEC, SPRINT_GRID_PER_GAME_SEC, CRUISE_GRID_PER_GAME_SEC,
            DRIFT_GRID_PER_GAME_SEC, BURST_GRID_PER_GAME_SEC,
            SHOT_MOTION_GRID_PER_GAME_SEC) == (14, 18, 13, 8, 32, 14)
    assert ASH.DEFENDER_AG_SPREAD == 0.50
    from BackEnd.utils.shared import ag_to_grid_per_game_sec
    assert ag_to_grid_per_game_sec(50) == 14.0
    assert ag_to_grid_per_game_sec(0) == pytest.approx(12.6)
    assert ag_to_grid_per_game_sec(100) == pytest.approx(15.4)
