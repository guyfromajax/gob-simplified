"""Player Potential Rating — Phase 4 projection formula (single source, already ratcheted)."""
import logging

from BackEnd.utils.rt_projection import (
    ratcheted_potential_rt,
    potential_rt_for_player,
    rt_current_potential,
    POTENTIAL_PROJECTION_MULTIPLE,
    POTENTIAL_RT_FIELD,
)
from BackEnd.utils.player_generation import JH_ANCHOR_BY_TIER


def test_projection_is_senior_anchor_times_factor():
    # Average anchor 30 × 2.0 × 1.0 = 60 (the senior ladder anchor)
    assert ratcheted_potential_rt("Average", 1.0, current_rt=40) == 60.0
    # Elite 50 × 2.0 × 1.15 = 115
    assert abs(ratcheted_potential_rt("Elite", 1.15, current_rt=50) - 115.0) < 1e-9
    assert POTENTIAL_PROJECTION_MULTIPLE == 2.0
    for tier, anchor in JH_ANCHOR_BY_TIER.items():
        assert ratcheted_potential_rt(tier, 1.0, current_rt=0) == anchor * 2.0


def test_value_is_already_ratcheted():
    # current far above raw projection → the EMITTED value ratchets up to current
    assert ratcheted_potential_rt("Average", 1.0, current_rt=105) == 105.0
    # current below projection → projection stands
    assert ratcheted_potential_rt("Average", 1.0, current_rt=50) == 60.0
    # a consumer re-applying max() would be a no-op (proof the ratchet is here, not there)
    v = ratcheted_potential_rt("Average", 1.0, current_rt=105)
    assert max(v, 105) == v


def test_missing_basis_returns_none():
    # no tier / no factor → None so the caller shows the current rating ALONE
    assert ratcheted_potential_rt(None, 1.0, current_rt=55) is None
    assert ratcheted_potential_rt("Average", None, current_rt=55) is None
    assert ratcheted_potential_rt("Average", 0, current_rt=55) is None
    assert ratcheted_potential_rt(None, None, current_rt=None) is None


def test_letter_pair_format():
    assert rt_current_potential(45, "Average", 1.0) == "C/B"          # C(45)/B(60)
    assert rt_current_potential(105, "Average", 1.0) == "A++/A++"     # met ceiling → pair, not single
    assert rt_current_potential(90, "Elite", 1.15) == "A+/A++"        # A+(90)/A++(115)
    assert "/" not in rt_current_potential(55, None, None)            # no basis → current alone


def test_field_name_is_unmistakable():
    # the payload key advertises that the value is already ratcheted
    assert POTENTIAL_RT_FIELD == "potential_rt_ratcheted"
    assert "ratchet" in POTENTIAL_RT_FIELD


# --- potential_rt_for_player: the payload-builder convenience -----------------

def test_for_player_uses_best_position_and_stored_pf():
    # best of position_ratings is the current; stored pf → projection; returns int
    v = potential_rt_for_player("p1", "Average", 1.0, {"PG": 55, "SF": 58})
    assert v == 60  # 30×2×1.0, above current 58


def test_for_player_ratchets_to_current():
    assert potential_rt_for_player("p2", "Average", 1.0, {"C": 105}) == 105


def test_for_player_fallback_is_stable_and_quiet(caplog):
    # pool player, no stored pf → deterministic hash, and NO warning on the read path
    with caplog.at_level(logging.WARNING):
        a = potential_rt_for_player("pool-xyz", "Good", None, {"SF": 64})
        b = potential_rt_for_player("pool-xyz", "Good", None, {"SF": 64})
    assert a == b and a is not None
    assert not any("potential_factor missing" in r.message for r in caplog.records), \
        "read path must not warn on the expected pool fallback"


def test_for_player_no_tier_returns_none_but_valid_basis_stands():
    assert potential_rt_for_player("p3", None, None, {"PG": 50}) is None    # no tier → None
    # valid tier+pf but empty ratings → raw projection stands (no current to ratchet against)
    assert potential_rt_for_player("p4", "Average", 1.0, {}) == 60
