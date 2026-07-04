"""Phase 2 unit tests: After-Steal coordinated OFFENSE positioning."""

import random

from BackEnd.constants.fast_break_constants import (
    FB_AS_LEAD_REBOUND_X_OFFSET,
    FB_AS_TIER_Y_JITTER,
    FB_AS_TIER_LOWER_Y,
    FB_AS_TIER_UPPER_Y,
)
from BackEnd.constants.fast_break_constants import (
    FB_AS_HELP_SPOTS_LOWER,
    FB_AS_HELP_SPOTS_UPPER,
    FB_AS_LEAD_DEF_X_OFFSET,
    FB_AS_NO_MEET_CHASE_X_BEHIND,
)
from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.engine.after_steal_transition_positioning import (
    author_defense_end_coords,
    author_offense_end_coords,
    classify_offense_roles,
)


def _home_offense():
    # BH at x=55; two teammates farther downcourt (leads), two behind (trailers).
    return {
        "bh": {"x": 55.0, "y": 25.0},
        "lead_hi": {"x": 70.0, "y": 40.0},
        "lead_lo": {"x": 68.0, "y": 12.0},
        "trail_hi": {"x": 45.0, "y": 33.0},
        "trail_lo": {"x": 42.0, "y": 15.0},
    }


def test_classify_leads_are_two_closest_to_basket_home():
    coords = _home_offense()
    leads, trailers = classify_offense_roles(
        stealer_id="bh", off_start_coords=coords, is_away_offense=False
    )
    assert set(leads) == {"lead_hi", "lead_lo"}
    assert set(trailers) == {"trail_hi", "trail_lo"}


def test_classify_leads_are_two_closest_to_basket_away():
    # Away attacks low x → closest = lowest x.
    coords = {
        "bh": {"x": 45.0, "y": 25.0},
        "lead_hi": {"x": 30.0, "y": 40.0},
        "lead_lo": {"x": 32.0, "y": 12.0},
        "trail_hi": {"x": 55.0, "y": 33.0},
        "trail_lo": {"x": 58.0, "y": 15.0},
    }
    leads, trailers = classify_offense_roles(
        stealer_id="bh", off_start_coords=coords, is_away_offense=True
    )
    assert set(leads) == {"lead_hi", "lead_lo"}
    assert set(trailers) == {"trail_hi", "trail_lo"}


def test_rim_finish_leads_crash_basket_x_distinct_tiers():
    coords = _home_offense()
    bh_end = {"x": 88.0, "y": 25.0}
    ends = author_offense_end_coords(
        stealer_id="bh",
        bh_end=bh_end,
        off_start_coords=coords,
        outcome_kind="rim_finish",
        is_away_offense=False,
        rng=random.Random(0),
    )
    assert ends["bh"] == {"x": 88.0, "y": 25.0}
    rebound_x = 91.0 - FB_AS_LEAD_REBOUND_X_OFFSET
    for lead in ("lead_hi", "lead_lo"):
        assert ends[lead]["x"] == rebound_x
    # Leads occupy distinct fanned tiers (one low, one high), geometry-true:
    # lead_lo started lower → lower tier.
    assert ends["lead_lo"]["y"] <= FB_AS_TIER_LOWER_Y + FB_AS_TIER_Y_JITTER
    assert ends["lead_hi"]["y"] >= FB_AS_TIER_UPPER_Y - FB_AS_TIER_Y_JITTER
    assert ends["lead_lo"]["y"] != ends["lead_hi"]["y"]


def test_rim_finish_trailers_get_distinct_arc_spots():
    coords = _home_offense()
    ends = author_offense_end_coords(
        stealer_id="bh",
        bh_end={"x": 88.0, "y": 25.0},
        off_start_coords=coords,
        outcome_kind="rim_finish",
        is_away_offense=False,
        rng=random.Random(3),
    )
    t_hi = (ends["trail_hi"]["x"], ends["trail_hi"]["y"])
    t_lo = (ends["trail_lo"]["x"], ends["trail_lo"]["y"])
    assert t_hi != t_lo, "trailers must not share an arc spot"
    # Arc spots sit downcourt on the 3-point line (x >= 64 for home).
    assert ends["trail_hi"]["x"] >= 64
    assert ends["trail_lo"]["x"] >= 64
    # Upper-half trailer takes an upper spot, lower-half takes a lower spot
    # (unless bumped to the key at y=25).
    assert ends["trail_hi"]["y"] >= 25
    assert ends["trail_lo"]["y"] <= 25


def test_hco_leads_to_low_post_trailers_hold():
    coords = _home_offense()
    ends = author_offense_end_coords(
        stealer_id="bh",
        bh_end={"x": 74.0, "y": 25.0},
        off_start_coords=coords,
        outcome_kind="hco",
        is_away_offense=False,
        rng=random.Random(0),
    )
    # Leads on the low blocks (lowPost x=86).
    assert ends["lead_hi"]["x"] == 86
    assert ends["lead_lo"]["x"] == 86
    assert {ends["lead_hi"]["y"], ends["lead_lo"]["y"]} == {32, 19}
    # Trailers hold their starting spots.
    assert ends["trail_hi"] == {"x": 45.0, "y": 33.0}
    assert ends["trail_lo"] == {"x": 42.0, "y": 15.0}


def test_terminal_everyone_holds_except_bh():
    coords = _home_offense()
    bh_end = {"x": 75.0, "y": 25.0}
    ends = author_offense_end_coords(
        stealer_id="bh",
        bh_end=bh_end,
        off_start_coords=coords,
        outcome_kind="terminal",
        is_away_offense=False,
        rng=random.Random(0),
    )
    assert ends["bh"] == {"x": 75.0, "y": 25.0}
    for pid in ("lead_hi", "lead_lo", "trail_hi", "trail_lo"):
        assert ends[pid] == coords[pid]


def test_away_offense_mirrors_arc_spots():
    coords = {
        "bh": {"x": 45.0, "y": 25.0},
        "lead_hi": {"x": 30.0, "y": 40.0},
        "lead_lo": {"x": 32.0, "y": 12.0},
        "trail_hi": {"x": 55.0, "y": 33.0},
        "trail_lo": {"x": 58.0, "y": 15.0},
    }
    ends = author_offense_end_coords(
        stealer_id="bh",
        bh_end={"x": 12.0, "y": 25.0},
        off_start_coords=coords,
        outcome_kind="rim_finish",
        is_away_offense=True,
        rng=random.Random(1),
    )
    # Away attacks low x → lead rebound x mirrored to ~15, arc spots at low x.
    assert ends["lead_hi"]["x"] == 9.0 + FB_AS_LEAD_REBOUND_X_OFFSET
    assert ends["trail_hi"]["x"] <= 36
    assert ends["trail_lo"]["x"] <= 36


# --- Defense planner -------------------------------------------------------


def _defense_start():
    # Two defenders back near the basket (lead defenders), two at midcourt
    # (help), one closest to the ball handler (BH defender).
    return {
        "d_bh": {"x": 58.0, "y": 24.0},   # nearest the BH at x~55
        "d_lead_hi": {"x": 78.0, "y": 38.0},
        "d_lead_lo": {"x": 76.0, "y": 14.0},
        "d_help_hi": {"x": 40.0, "y": 34.0},
        "d_help_lo": {"x": 38.0, "y": 16.0},
    }


def _offense_shot_ends():
    # Result of author_offense_end_coords for the home shot case (approx).
    return {
        "bh": {"x": 88.0, "y": 25.0},
        "lead_hi": {"x": 85.0, "y": 32.0},
        "lead_lo": {"x": 85.0, "y": 18.0},
        "trail_hi": {"x": 68.0, "y": 36.0},
        "trail_lo": {"x": 68.0, "y": 14.0},
    }


def test_defense_no_meet_bh_defender_trails_three_behind():
    off_ends = _offense_shot_ends()
    ends = author_defense_end_coords(
        def_start_coords=_defense_start(),
        bh_defender_id=None,  # NO_MEET → closest to BH chases
        bh_start={"x": 55.0, "y": 25.0},
        bh_end=off_ends["bh"],
        meet=None,
        bh_reaches_rim=True,
        lead_ids=["lead_hi", "lead_lo"],
        offense_end_coords=off_ends,
        is_away_offense=False,
        rng=random.Random(0),
    )
    # d_bh is closest to the ball handler → he chases to 3 behind the finish.
    assert ends["d_bh"]["x"] == off_ends["bh"]["x"] - FB_AS_NO_MEET_CHASE_X_BEHIND
    assert ends["d_bh"]["y"] == off_ends["bh"]["y"]


def test_defense_lead_defenders_pick_up_leads():
    off_ends = _offense_shot_ends()
    ends = author_defense_end_coords(
        def_start_coords=_defense_start(),
        bh_defender_id="d_bh",
        bh_start={"x": 55.0, "y": 25.0},
        bh_end=off_ends["bh"],
        meet=None,
        bh_reaches_rim=True,
        lead_ids=["lead_hi", "lead_lo"],
        offense_end_coords=off_ends,
        is_away_offense=False,
        rng=random.Random(0),
    )
    # The two defenders closest to the basket guard the two leads, ball-side.
    assert ends["d_lead_hi"]["x"] == off_ends["lead_hi"]["x"] - FB_AS_LEAD_DEF_X_OFFSET
    assert ends["d_lead_hi"]["y"] == off_ends["lead_hi"]["y"]
    assert ends["d_lead_lo"]["x"] == off_ends["lead_lo"]["x"] - FB_AS_LEAD_DEF_X_OFFSET


def test_defense_help_defenders_get_distinct_side_biased_spots():
    off_ends = _offense_shot_ends()
    ends = author_defense_end_coords(
        def_start_coords=_defense_start(),
        bh_defender_id="d_bh",
        bh_start={"x": 55.0, "y": 25.0},
        bh_end=off_ends["bh"],
        meet=None,
        bh_reaches_rim=True,
        lead_ids=["lead_hi", "lead_lo"],
        offense_end_coords=off_ends,
        is_away_offense=False,
        rng=random.Random(2),
    )
    help_hi = (ends["d_help_hi"]["x"], ends["d_help_hi"]["y"])
    help_lo = (ends["d_help_lo"]["x"], ends["d_help_lo"]["y"])
    assert help_hi != help_lo, "help defenders must not share a spot"
    help_coords = {
        name: HCO_STRING_SPOTS[name]
        for name in set(FB_AS_HELP_SPOTS_UPPER) | set(FB_AS_HELP_SPOTS_LOWER)
    }
    valid = {(c["x"], c["y"]) for c in help_coords.values()}
    assert help_hi in valid
    assert help_lo in valid


def test_defense_stopped_bh_defender_sits_on_meet():
    off_ends = _offense_shot_ends()
    meet = {"x": 72.0, "y": 25.0}
    ends = author_defense_end_coords(
        def_start_coords=_defense_start(),
        bh_defender_id="d_bh",
        bh_start={"x": 55.0, "y": 25.0},
        bh_end=meet,
        meet=meet,
        bh_reaches_rim=False,  # NEUTRAL stop → BH defender on the meet
        lead_ids=["lead_hi", "lead_lo"],
        offense_end_coords=off_ends,
        is_away_offense=False,
        rng=random.Random(0),
    )
    assert ends["d_bh"] == {"x": 72.0, "y": 25.0}
