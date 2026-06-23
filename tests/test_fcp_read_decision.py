"""FCP-specific §4 read gates (strong-handler sum + low-tier mix)."""

from types import SimpleNamespace
from unittest.mock import patch

from BackEnd.engine.dynamic_hct import (
    FCP_READ_LOW_TIER_CHOICES,
    FCP_READ_STRONG_HANDLER_SUM,
    _read_decision,
)


def _bh(attrs):
    return SimpleNamespace(attributes=attrs)


def test_fcp_high_read_passes_for_moderate_dribbler():
    """BH+AG between HCT (80) and FCP (140): HCT attacks, FCP passes on strong read."""
    player = _bh({"BH": 70, "AG": 50})  # sum 120 — strong in HCT, weak in FCP
    with patch("BackEnd.engine.dynamic_hct._player_read", return_value=250):
        assert _read_decision(player, fcp=False) == "attack"
        assert _read_decision(player, fcp=True) == "pass"


def test_fcp_high_read_attacks_for_elite_dribbler():
    """BH+AG > 140 may attack on a strong read under FCP."""
    player = _bh({"BH": 80, "AG": 65})  # sum 145
    with patch("BackEnd.engine.dynamic_hct._player_read", return_value=250):
        assert _read_decision(player, fcp=True) == "attack"


def test_fcp_low_tier_mix_weights():
    assert FCP_READ_STRONG_HANDLER_SUM == 140
    assert len(FCP_READ_LOW_TIER_CHOICES) == 20
    assert FCP_READ_LOW_TIER_CHOICES.count("hold") == 10
    assert FCP_READ_LOW_TIER_CHOICES.count("pass") == 7
    assert FCP_READ_LOW_TIER_CHOICES.count("attack") == 3
