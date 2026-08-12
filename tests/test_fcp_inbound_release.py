"""FCP SF inbound release target + pass-clear gating."""

import BackEnd.engine.fcp_inbound_release as inbound_release

from BackEnd.engine.fcp_inbound_release import (
    FCP_SF_RELEASE_X_HOME,
    FCP_SF_TIER_Y,
    compute_sf_inbound_release_target,
    pick_open_sf_tier,
    sf_at_fcp_inbound_baseline,
    sf_cleared_for_fcp_pass,
)


def test_sf_at_baseline_home():
    assert sf_at_fcp_inbound_baseline({"SF": {"x": 3, "y": 25}}, False) is True
    assert sf_at_fcp_inbound_baseline({"SF": {"x": 12, "y": 25}}, False) is False


def test_sf_at_baseline_away():
    assert sf_at_fcp_inbound_baseline({"SF": {"x": 97, "y": 25}}, True) is True
    assert sf_at_fcp_inbound_baseline({"SF": {"x": 88, "y": 25}}, True) is False


def test_pick_open_tier_always_has_choice():
    off = {
        "PG": {"x": 15, "y": 22},  # center
        "SG": {"x": 28, "y": 18},  # lower
        "SF": {"x": 3, "y": 25},
    }
    tier = pick_open_sf_tier(off, "PG")
    assert tier == "upper"


def test_pick_open_tier_random_when_two_open(monkeypatch):
    off = {
        "PG": {"x": 15, "y": 22},  # center
        "SG": {"x": 28, "y": 32},  # upper
        "SF": {"x": 3, "y": 25},
    }
    captured = {}

    def choose_first(options):
        captured["options"] = list(options)
        return options[0]

    monkeypatch.setattr(inbound_release.random, "choice", choose_first)
    tier = pick_open_sf_tier(off, "PG")
    # PG is the ball handler and therefore does not occupy a release tier;
    # SG occupies upper, leaving center and lower open.
    assert set(captured["options"]) == {"center", "lower"}
    assert tier == captured["options"][0]


def test_release_target_x34_home(monkeypatch):
    off = {
        "PG": {"x": 15, "y": 22},
        "SG": {"x": 28, "y": 32},
        "SF": {"x": 3, "y": 25},
    }
    monkeypatch.setattr(inbound_release.random, "choice", lambda options: "lower")
    dest = compute_sf_inbound_release_target(off, "PG", is_away_offense=False)
    assert dest["x"] == FCP_SF_RELEASE_X_HOME
    assert dest["y"] == FCP_SF_TIER_Y["lower"]


def test_release_target_flipped_away(monkeypatch):
    off = {
        "PG": {"x": 85, "y": 22},
        "SG": {"x": 72, "y": 32},
        "SF": {"x": 97, "y": 25},
    }
    monkeypatch.setattr(inbound_release.random, "choice", lambda options: "lower")
    dest = compute_sf_inbound_release_target(off, "PG", is_away_offense=True)
    assert dest["x"] == 100 - FCP_SF_RELEASE_X_HOME
    # Away orientation mirrors x around half court; vertical tiers do not flip.
    assert dest["y"] == FCP_SF_TIER_Y["lower"]


def test_pass_clear_threshold_home():
    assert not sf_cleared_for_fcp_pass({"x": 10, "y": 25}, False, 14)
    assert sf_cleared_for_fcp_pass({"x": 14, "y": 25}, False, 14)
    assert sf_cleared_for_fcp_pass({"x": 20, "y": 25}, False, 14)


def test_pass_clear_threshold_away():
    assert not sf_cleared_for_fcp_pass({"x": 90, "y": 25}, True, 14)
    assert sf_cleared_for_fcp_pass({"x": 86, "y": 25}, True, 14)


def test_offball_sf_keeps_inbound_release_until_arrival():
    from BackEnd.engine.fcp_offball_attack import FcpOffballAttackState

    off = {
        "PG": {"x": 15, "y": 22},
        "SG": {"x": 28, "y": 18},
        "SF": {"x": 3, "y": 25},
        "PF": {"x": 48, "y": 25},
        "C": {"x": 65, "y": 25},
    }
    state = FcpOffballAttackState(is_away_offense=False)
    release = {"x": 34, "y": 35}
    state.set_sf_inbound_release(release)
    state.refresh_incremental({"x": 20, "y": 22}, off, "PG", force=True)
    assert state._dest["SF"] == release
    assert state._phase["SF"] == "inbound_release"

    off["SF"] = dict(release)
    state.refresh_incremental({"x": 20, "y": 22}, off, "PG", force=True)
    assert state._phase["SF"] == "release"
    assert 46 <= state._dest["SF"]["x"] <= 53
