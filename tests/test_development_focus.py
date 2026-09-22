"""Development Focus — the position + focus training profile (Phase 1).

Two jobs:
  1. the 30 profiles are well-formed (30 exist, 12 attrs, 808, FT/IQ/ND locked at 100);
  2. `standard` behaves EXACTLY as the pre-feature position-only table, so shipping the
     matrix on its own cannot move a single existing gain.

The locked wall / ordering invariants stay strict for `standard` in
tests/test_training_shape_framework.py; the looser, deliberate rule for focus profiles
lives there too.
"""
from __future__ import annotations

import pytest

from BackEnd.constants.training_shape import (
    CORE_12,
    DEFAULT_TRAINING_FOCUS,
    POSITIONS,
    TRAINING_FOCUS_PERCENTAGES,
    TRAINING_FOCUSES,
    TRAINING_GAIN_PERCENTAGES,
    TRAINING_GAIN_UNIVERSALS,
    class_gain_multiplier,
    player_attr_gain_multiplier,
    resolve_training_focus,
    training_attr_gain_multiplier,
)


# ── shape of the matrix ──────────────────────────────────────────────────────

def test_all_thirty_profiles_exist():
    assert set(TRAINING_FOCUS_PERCENTAGES) == set(POSITIONS)
    for pos in POSITIONS:
        assert tuple(sorted(TRAINING_FOCUS_PERCENTAGES[pos])) == tuple(sorted(TRAINING_FOCUSES))
    assert sum(len(v) for v in TRAINING_FOCUS_PERCENTAGES.values()) == 30


@pytest.mark.parametrize("pos", POSITIONS)
@pytest.mark.parametrize("focus", TRAINING_FOCUSES)
def test_every_profile_has_twelve_attrs_and_totals_808(pos, focus):
    profile = TRAINING_FOCUS_PERCENTAGES[pos][focus]
    assert set(profile) == set(CORE_12)
    assert sum(profile.values()) == 808


@pytest.mark.parametrize("pos", POSITIONS)
@pytest.mark.parametrize("focus", TRAINING_FOCUSES)
def test_universals_stay_at_100_in_every_profile(pos, focus):
    for attr in TRAINING_GAIN_UNIVERSALS:
        assert TRAINING_FOCUS_PERCENTAGES[pos][focus][attr] == 100, f"{pos}/{focus}/{attr}"


# ── standard is the old behaviour, not a copy of it ──────────────────────────

def test_standard_is_the_live_position_table():
    for pos in POSITIONS:
        assert TRAINING_FOCUS_PERCENTAGES[pos]["standard"] == TRAINING_GAIN_PERCENTAGES[pos]


@pytest.mark.parametrize("pos", POSITIONS)
def test_focus_none_matches_legacy_lookup_for_every_attr(pos):
    """The pre-feature call signature must be untouched, attribute for attribute."""
    for attr in CORE_12:
        legacy = TRAINING_GAIN_PERCENTAGES[pos][attr] / 100
        assert training_attr_gain_multiplier(pos, attr) == legacy
        assert training_attr_gain_multiplier(pos, attr, "standard") == legacy


def test_unknown_position_still_falls_back_to_sf():
    for attr in ("SC", "RB"):
        assert training_attr_gain_multiplier("XX", attr) == training_attr_gain_multiplier("SF", attr)


# ── focus actually changes the profile ───────────────────────────────────────

def test_rebounding_focus_lifts_guard_rebounding_through_the_wall():
    """Deliberate: a coach may convert a guard into a rebounder."""
    for pos in ("PG", "SG"):
        assert training_attr_gain_multiplier(pos, "RB", "standard") == 0.25
        assert training_attr_gain_multiplier(pos, "RB", "rebounding") == 0.75


def test_offensive_focus_trades_defense_for_scoring():
    assert training_attr_gain_multiplier("PG", "SC", "offensive") > training_attr_gain_multiplier("PG", "SC", "standard")
    assert training_attr_gain_multiplier("PG", "OD", "offensive") < training_attr_gain_multiplier("PG", "OD", "standard")


# ── resolver ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw", [None, "", "  ", "nonsense", 7, {"a": 1}])
def test_missing_or_invalid_focus_resolves_to_standard(raw):
    assert resolve_training_focus({"training_focus": raw}) == DEFAULT_TRAINING_FOCUS


def test_legacy_player_with_no_field_resolves_to_standard():
    assert resolve_training_focus({}) == "standard"


@pytest.mark.parametrize("focus", TRAINING_FOCUSES)
def test_valid_focus_round_trips(focus):
    assert resolve_training_focus({"training_focus": focus}) == focus


def test_focus_is_case_and_whitespace_tolerant():
    assert resolve_training_focus({"training_focus": "  Rebounding "}) == "rebounding"


def test_focus_may_ride_on_meta():
    assert resolve_training_focus({"meta": {"training_focus": "athletic"}}) == "athletic"


# ── the one multiplier: profile x class, never profile x position x class ────

def test_player_multiplier_is_profile_times_class_only():
    player = {"training_position": "C", "training_focus": "athletic", "year": "sophomore"}
    expected = training_attr_gain_multiplier("C", "AG", "athletic") * class_gain_multiplier("sophomore")
    assert player_attr_gain_multiplier(player, "AG") == expected


def test_no_double_apply_of_the_old_position_multiplier():
    """If the position lookup were still stacked on top, this product would appear."""
    player = {"training_position": "PG", "training_focus": "rebounding", "year": "freshman"}
    got = player_attr_gain_multiplier(player, "RB")
    stacked = (
        training_attr_gain_multiplier("PG", "RB", "rebounding")
        * training_attr_gain_multiplier("PG", "RB", "standard")
        * class_gain_multiplier("freshman")
    )
    assert got == pytest.approx(0.75 * class_gain_multiplier("freshman"))
    assert got != pytest.approx(stacked)


def test_legacy_player_trains_exactly_as_before_the_feature():
    """A doc with no training_focus must be bit-for-bit unchanged."""
    player = {"training_position": "SF", "year": "junior"}
    for attr in CORE_12:
        expected = (TRAINING_GAIN_PERCENTAGES["SF"][attr] / 100) * class_gain_multiplier("junior")
        assert player_attr_gain_multiplier(player, attr) == expected


def test_focus_follows_the_training_position_not_the_natural_fit():
    """position_intent stays the natural fit; training_position is what the coach set."""
    converted = {"position_intent": "PG", "training_position": "PF", "training_focus": "standard"}
    assert player_attr_gain_multiplier(converted, "RB") == pytest.approx(
        training_attr_gain_multiplier("PF", "RB") * class_gain_multiplier(None)
    )
