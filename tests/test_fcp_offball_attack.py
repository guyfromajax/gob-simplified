"""FCP off-ball attack routing (press-break destinations)."""

from BackEnd.engine.fcp_offball_attack import (
    FcpOffballAttackState,
    FCP_BACKCOURT_X_MAX,
    FCP_BACKCOURT_X_MIN,
    _ball_progress_x,
    _random_near_deep_key,
)


def test_backcourt_release_target_in_lane():
    state = FcpOffballAttackState(is_away_offense=False)
    off = {
        "PG": {"x": 15, "y": 22},
        "SG": {"x": 28, "y": 18},
        "SF": {"x": 3, "y": 25},
        "PF": {"x": 50, "y": 25},
        "C": {"x": 65, "y": 25},
    }
    state.refresh_incremental({"x": 20, "y": 22}, off, "PG", force=True)
    sg_dest = state._dest["SG"]
    assert FCP_BACKCOURT_X_MIN <= sg_dest["x"] <= FCP_BACKCOURT_X_MAX
    assert 12 <= sg_dest["y"] <= 24


def test_pf_holds_then_deep_key_band():
    state = FcpOffballAttackState(is_away_offense=False)
    off = {
        "PG": {"x": 15, "y": 25},
        "SG": {"x": 28, "y": 25},
        "SF": {"x": 3, "y": 25},
        "PF": {"x": 48, "y": 25},
        "C": {"x": 65, "y": 25},
    }
    state.refresh_incremental({"x": 30, "y": 25}, off, "PG", force=True)
    assert state._dest["PF"] == off["PF"]
    state.refresh_incremental({"x": 40, "y": 25}, off, "PG", force=False)
    deep = state._dest["PF"]
    assert 34 <= _ball_progress_x(deep, False) < 50


def test_c_respects_bh_vertical_half():
    state = FcpOffballAttackState(is_away_offense=False)
    off = {
        "PG": {"x": 40, "y": 25},
        "SG": {"x": 28, "y": 25},
        "SF": {"x": 3, "y": 25},
        "PF": {"x": 48, "y": 25},
        "C": {"x": 65, "y": 25},
    }
    state.refresh_incremental({"x": 45, "y": 30}, off, "PG", force=True)
    spot_y = state._dest["C"]["y"]
    assert spot_y >= 25


def test_deep_key_anchor_backcourt_side():
    pt = _random_near_deep_key(is_away_offense=False)
    assert pt["x"] < 50
