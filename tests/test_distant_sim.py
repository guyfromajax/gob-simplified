"""Unit tests for distant franchise game sim win-probability inputs (Phase 1+)."""

from BackEnd.constants.distant_sim import DISTANT_MO_MULT_BANDS
from BackEnd.distant_sim_engine import (
    clamp_distant_momentum_score,
    compute_distant_momentum_score_updates,
    distant_sim_momentum_multiplier,
    distant_sim_record_momentum,
    distant_sim_season_momentum,
    distant_sim_talent_signal,
    distant_sim_team_attr_composite,
    distant_sim_team_combined,
)


def _ftd(*, prestige: int = 500, attrs: int = 1000, chemistry: int = 9) -> dict:
    return {
        "prestige": prestige,
        "total_player_attrs": attrs,
        "team_attributes": {"team_chemistry": chemistry},
    }


def test_franchise_init_chemistry_uses_floor_band():
    assert distant_sim_momentum_multiplier(7) == 3
    assert distant_sim_momentum_multiplier(10) == 3


def test_mid_and_top_chemistry_bands():
    assert distant_sim_momentum_multiplier(15) == 4
    assert distant_sim_momentum_multiplier(20) == 5
    assert distant_sim_momentum_multiplier(24) == 6
    assert distant_sim_momentum_multiplier(25) == 8


def test_clamp_out_of_range_chemistry():
    assert distant_sim_momentum_multiplier(3) == 3
    assert distant_sim_momentum_multiplier(99) == 8


def test_invalid_chemistry_defaults_to_min_band():
    assert distant_sim_momentum_multiplier(None) == 3
    assert distant_sim_momentum_multiplier("bad") == 3


def test_even_record_zero_momentum():
    assert distant_sim_record_momentum(9, season_wins=0, season_losses=0) == 0
    assert distant_sim_record_momentum(9, season_wins=10, season_losses=10) == 0


def test_winning_record_positive_momentum():
    assert distant_sim_record_momentum(9, season_wins=15, season_losses=5) == 30


def test_losing_record_negative_momentum():
    assert distant_sim_record_momentum(9, season_wins=5, season_losses=15) == -30


def test_undefeated_mid_season_momentum():
    assert distant_sim_record_momentum(10, season_wins=12, season_losses=0) == 36


def test_winless_mid_season_momentum():
    assert distant_sim_record_momentum(10, season_wins=0, season_losses=12) == -36


def test_negative_wl_inputs_clamped_to_zero():
    assert distant_sim_record_momentum(9, season_wins=-2, season_losses=-3) == 0


def test_base_only_at_kickoff():
    ftd = _ftd(prestige=600, attrs=1400, chemistry=8)
    assert distant_sim_team_combined(ftd, season_wins=0, season_losses=0, is_home=False) == 740


def test_home_chemistry_bonus():
    ftd = _ftd(prestige=600, attrs=1400, chemistry=10)
    away = distant_sim_team_combined(ftd, season_wins=0, season_losses=0, is_home=False)
    home = distant_sim_team_combined(ftd, season_wins=0, season_losses=0, is_home=True)
    assert home - away == 20


def test_winning_team_higher_combined_than_losing_peer():
    hot = _ftd(prestige=600, attrs=1400, chemistry=9)
    cold = _ftd(prestige=600, attrs=1400, chemistry=9)
    hot_score = distant_sim_team_combined(hot, season_wins=18, season_losses=4, is_home=False)
    cold_score = distant_sim_team_combined(cold, season_wins=6, season_losses=16, is_home=False)
    assert hot_score > cold_score
    assert hot_score - cold_score == 72


def test_multiplier_bands_count():
    assert len(DISTANT_MO_MULT_BANDS) == 5


def test_season_momentum_from_score():
    assert distant_sim_season_momentum(0) == 0
    assert distant_sim_season_momentum(5) == 40
    assert distant_sim_season_momentum(10) == 80


def test_momentum_score_clamp():
    assert clamp_distant_momentum_score(15) == 10
    assert clamp_distant_momentum_score(-15) == -10


def test_win_updates_momentum_and_streak():
    winner_attrs = {"team_chemistry": 10, "momentum_score": 0, "distant_win_streak": 0}
    loser_attrs = {"team_chemistry": 10, "momentum_score": 0, "distant_win_streak": 2}
    w_up, l_up = compute_distant_momentum_score_updates(winner_attrs, loser_attrs)
    assert w_up["distant_win_streak"] == 1
    assert l_up["distant_win_streak"] == 0
    assert l_up["distant_loss_streak"] == 1
    assert float(w_up["momentum_score"]) > 0


def test_loss_after_win_streak_applies_reset_penalty():
    winner_attrs = {"team_chemistry": 10, "momentum_score": 0, "distant_win_streak": 0}
    loser_attrs = {"team_chemistry": 10, "momentum_score": 5, "distant_win_streak": 4}
    _, l_up = compute_distant_momentum_score_updates(winner_attrs, loser_attrs)
    assert abs(float(l_up["momentum_score"]) - 2.2) < 0.01


def test_team_combined_includes_season_momentum():
    ftd = _ftd(prestige=600, attrs=1400, chemistry=9)
    ftd["team_attributes"]["momentum_score"] = 5
    base = distant_sim_team_combined(ftd, season_wins=0, season_losses=0, is_home=False)
    assert base == 740 + 40


def test_talent_signal_live_from_fpd():
    ftd = {
        "total_player_attrs": 1000,
        "players": ["p1", "p2"],
        "team_attributes": {},
    }
    fpd = {
        "p1": {"attributes": {"SC": 100, "SH": 100, "ID": 100, "OD": 100, "PS": 100, "BH": 100,
                               "RB": 100, "ST": 100, "AG": 100, "ND": 100, "IQ": 100, "FT": 100}},
        "p2": {"attributes": {"SC": 50, "SH": 50, "ID": 50, "OD": 50, "PS": 50, "BH": 50,
                              "RB": 50, "ST": 50, "AG": 50, "ND": 50, "IQ": 50, "FT": 50}},
    }
    assert distant_sim_talent_signal(ftd, fpd) == 1800


def test_talent_signal_fallback_adds_team_attr_composite():
    ftd = {
        "total_player_attrs": 1000,
        "team_attributes": {
            "offensive_efficiency": 8,
            "defensive_efficiency": 6,
            "shot_threshold": 100,
        },
    }
    assert distant_sim_team_attr_composite(ftd["team_attributes"]) == 9
    assert distant_sim_talent_signal(ftd, None) == 1009


def test_team_combined_uses_live_fpd_for_base():
    ftd = _ftd(prestige=600, attrs=1000, chemistry=9)
    ftd["players"] = ["p1"]
    fpd = {
        "p1": {"attributes": {"SC": 150, "SH": 150, "ID": 150, "OD": 150, "PS": 150, "BH": 150,
                               "RB": 150, "ST": 150, "AG": 150, "ND": 150, "IQ": 150, "FT": 150}},
    }
    # live attrs 1800 → base 600 + 180 = 780 (not frozen 700)
    assert distant_sim_team_combined(
        ftd, season_wins=0, season_losses=0, is_home=False, fpd_by_player_id=fpd
    ) == 780
