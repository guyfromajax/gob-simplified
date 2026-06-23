"""FCP PF/C compressed zone + Straight Pressure BH release at x≥64."""

from BackEnd.engine.dynamic_hct import (
    _straight_pressure_begin,
    _straight_pressure_targets,
)
from BackEnd.engine.fcp_pf_c_zone import (
    fcp_anchor_names,
    fcp_bh_past_press_break,
    fcp_zone_bounds,
    fcp_zone_bounds_home,
    offender_in_fcp_zone,
)


def test_zone_pre_compression_static():
    assert fcp_zone_bounds_home(30) == (50, 64, 1, 50)


def test_zone_sliding_at_40():
    assert fcp_zone_bounds_home(40) == (40, 54, 10, 40)


def test_zone_edge_at_36():
    assert fcp_zone_bounds_home(36) == (36, 50, 10, 40)


def test_zone_fixed_after_50():
    assert fcp_zone_bounds_home(55) == (50, 64, 10, 40)


def test_zone_broken_at_64():
    assert fcp_zone_bounds_home(64) is None


def test_zone_away_mirror():
    bounds = fcp_zone_bounds({"x": 60, "y": 25}, is_away_offense=True)
    assert bounds == (46, 60, 10, 40)


def test_anchor_ladder_progression():
    assert fcp_anchor_names(30) == ("midcourt", "key")
    assert fcp_anchor_names(45) == ("midcourt", "key")
    assert fcp_anchor_names(55) == ("key", "midLane")
    assert fcp_anchor_names(64) == ("midLane", "basketSpot")


def test_bh_past_press_break_at_64():
    assert fcp_bh_past_press_break({"x": 64, "y": 25}, False) is True
    assert fcp_bh_past_press_break({"x": 63, "y": 25}, False) is False


def test_offender_in_zone():
    bounds = (40, 54, 10, 40)
    assert offender_in_fcp_zone({"x": 45, "y": 20}, bounds)
    assert not offender_in_fcp_zone({"x": 39, "y": 20}, bounds)
    assert not offender_in_fcp_zone({"x": 45, "y": 5}, bounds)


def test_fcp_release_sg_sf_when_bh_crosses_64():
    off = {
        "PG": {"x": 65, "y": 25},
        "SG": {"x": 28, "y": 26},
        "SF": {"x": 3, "y": 24},
        "PF": {"x": 52, "y": 25},
        "C": {"x": 65, "y": 25},
    }
    defc = {
        "PG": {"x": 62, "y": 24},
        "SG": {"x": 28, "y": 32},
        "SF": {"x": 28, "y": 18},
        "PF": {"x": 52, "y": 25},
        "C": {"x": 73, "y": 25},
    }
    bh = off["PG"]
    state = _straight_pressure_begin(bh, defc, off, False, fcp=True)
    assert state["assignment"]["SG"] == "SG"
    assert state["assignment"]["SF"] == "SF"
    _straight_pressure_targets(state, bh, defc, False, off)
    assert "SG" not in state["assignment"]
    assert "SF" not in state["assignment"]
    assert state["assignment"]["PG"] == "PG"


def test_fcp_no_release_when_man_in_aba_but_bh_deep():
    """Off-ball man in ABA y-band does not release SG until BH crosses x≥64."""
    off = {
        "PG": {"x": 40, "y": 25},
        "SG": {"x": 70, "y": 20},
        "SF": {"x": 3, "y": 24},
        "PF": {"x": 52, "y": 25},
        "C": {"x": 65, "y": 25},
    }
    defc = {
        "PG": {"x": 42, "y": 24},
        "SG": {"x": 68, "y": 22},
        "SF": {"x": 28, "y": 18},
        "PF": {"x": 52, "y": 25},
        "C": {"x": 73, "y": 25},
    }
    bh = off["PG"]
    state = _straight_pressure_begin(bh, defc, off, False, fcp=True)
    guarded = state["assignment"]["SG"]
    _straight_pressure_targets(state, bh, defc, False, off)
    assert state["assignment"]["SG"] == guarded
