"""FCP off-ball attack routing (press-break destinations)."""

from BackEnd.engine.fcp_offball_attack import (
    FcpOffballAttackState,
    FCP_BACKCOURT_X_MAX,
    FCP_BACKCOURT_X_MIN,
    FCP_TIER1_MAX,
    FCP_TIER2_MAX,
    _ball_progress_x,
    _random_near_deep_key,
)

OFF = {
    "PG": {"x": 15, "y": 22},
    "SG": {"x": 28, "y": 18},
    "SF": {"x": 3, "y": 25},
    "PF": {"x": 48, "y": 25},
    "C": {"x": 65, "y": 25},
}


def test_backcourt_release_target_in_lane():
    state = FcpOffballAttackState(is_away_offense=False)
    state.refresh_incremental({"x": 20, "y": 22}, OFF, "PG", force=True)
    sg_dest = state._dest["SG"]
    assert FCP_BACKCOURT_X_MIN <= sg_dest["x"] <= FCP_BACKCOURT_X_MAX
    assert 12 <= sg_dest["y"] <= 24


def test_pf_holds_then_deep_key_band():
    state = FcpOffballAttackState(is_away_offense=False)
    state.refresh_incremental({"x": 30, "y": 25}, OFF, "PG", force=True)
    assert state._dest["PF"] == OFF["PF"]
    state.refresh_incremental({"x": 40, "y": 25}, OFF, "PG", force=False)
    deep = state._dest["PF"]
    assert FCP_TIER1_MAX < _ball_progress_x(deep, False) <= FCP_TIER2_MAX


def test_tier1_boundary_pf_and_c_hold_at_34():
    state = FcpOffballAttackState(is_away_offense=False)
    state.refresh_incremental({"x": FCP_TIER1_MAX, "y": 25}, OFF, "PG", force=True)
    assert state._phase["PF"] == "hold"
    assert state._phase["C"] == "hold"
    assert state._dest["PF"] == OFF["PF"]
    assert state._dest["C"] == OFF["C"]


def test_tier2_boundary_pf_and_c_mid_band_at_50():
    state = FcpOffballAttackState(is_away_offense=False)
    state.refresh_incremental({"x": FCP_TIER2_MAX, "y": 25}, OFF, "PG", force=True)
    assert state._phase["PF"] == "deep"
    assert state._phase["C"] == "mid"


def test_tier3_starts_at_51():
    state = FcpOffballAttackState(is_away_offense=False)
    state.refresh_incremental({"x": FCP_TIER2_MAX + 1, "y": 25}, OFF, "PG", force=True)
    assert state._phase["PF"] == "wing"
    assert state._phase["C"] == "front"


def test_c_respects_bh_vertical_half():
    state = FcpOffballAttackState(is_away_offense=False)
    state.refresh_incremental({"x": 45, "y": 30}, OFF, "PG", force=True)
    spot_y = state._dest["C"]["y"]
    assert spot_y >= 25


def test_deep_key_anchor_backcourt_side():
    pt = _random_near_deep_key(is_away_offense=False)
    assert pt["x"] < 50
