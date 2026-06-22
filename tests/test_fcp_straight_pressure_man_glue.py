"""FCP Straight Pressure — backcourt defenders stay on man, no rover trap."""

from BackEnd.engine.dynamic_hct import (
    _converge_xy,
    _straight_pressure_begin,
    _straight_pressure_targets,
)


def _sample_coords():
    off = {
        "PG": {"x": 18, "y": 22},
        "SG": {"x": 28, "y": 26},
        "SF": {"x": 3, "y": 24},
        "PF": {"x": 52, "y": 25},
        "C": {"x": 65, "y": 25},
    }
    defc = {
        "PG": {"x": 22, "y": 24},
        "SG": {"x": 28, "y": 32},
        "SF": {"x": 28, "y": 18},
        "PF": {"x": 52, "y": 25},
        "C": {"x": 73, "y": 25},
    }
    bh = off["PG"]
    return bh, off, defc


def test_fcp_begin_has_no_rover_or_key():
    bh, off, defc = _sample_coords()
    state = _straight_pressure_begin(bh, defc, off, False, fcp=True)
    assert state.get("fcp_man_glue") is True
    assert state["rover"] is None
    assert state["key"] is None
    assert "SG" in state["assignment"]
    assert "SF" in state["assignment"]


def test_fcp_targets_sg_sf_not_on_ball():
    bh, off, defc = _sample_coords()
    state = _straight_pressure_begin(bh, defc, off, False, fcp=True)
    targets = _straight_pressure_targets(state, bh, defc, False, off)
    on_ball = _converge_xy(bh, False)
    assert targets["PG"] == on_ball
    assert targets["SG"] != on_ball
    assert targets["SF"] != on_ball
