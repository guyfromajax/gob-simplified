"""Center-band trap gate: no HCT trap while BH y is in [20, 30]."""

from BackEnd.engine.dynamic_hct import _detect_moment
from BackEnd.engine.hct_trap_plays import (
    StandardDiamond,
    StandardTrap,
    StraightPressure,
)


def _two_ahead_defenders(bh_xy):
    """Two defenders within TRAP_MOMENT_RANGE and ahead of the BH (home)."""
    x = int(bh_xy["x"]) + 2
    y = int(bh_xy["y"])
    return {
        "PG": {"x": x, "y": y},
        "SG": {"x": x, "y": y + 1},
        "SF": {"x": 40, "y": 10},
        "PF": {"x": 70, "y": 25},
        "C": {"x": 80, "y": 25},
    }


def test_detect_moment_center_band_downgrades_trap_to_pressure():
    bh = {"x": 55, "y": 25}  # center band
    kind, in_range = _detect_moment(bh, _two_ahead_defenders(bh), False)
    assert kind == "pressure"
    assert len(in_range) >= 2


def test_detect_moment_upper_band_allows_trap():
    bh = {"x": 55, "y": 35}  # upper
    kind, _ = _detect_moment(bh, _two_ahead_defenders(bh), False)
    assert kind == "trap"


def test_detect_moment_lower_band_allows_trap():
    bh = {"x": 55, "y": 15}  # lower
    kind, _ = _detect_moment(bh, _two_ahead_defenders(bh), False)
    assert kind == "trap"


def test_all_hct_plays_respect_center_band_gate():
    bh = {"x": 55, "y": 25}
    defs = _two_ahead_defenders(bh)
    for play in (StandardTrap(), StraightPressure(), StandardDiamond()):
        # Straight Pressure needs begin_possession state for rover logic; even
        # without it, center-band must never surface as trap.
        kind, _ = play.detect_moment(bh, defs, False)
        assert kind == "pressure", play.key
