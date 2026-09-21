"""Development Focus, phase 3: the focus actually reaches training execution.

Phase 1 made the multiplier focus-aware. That is worthless if the player dicts the
builders hand to execution do not CARRY the field — the projection trap this codebase has
been bitten by before, where a cherry-picked dict silently drops a field and the read-side
resolver masks it by defaulting. These tests pin the wiring, not just the arithmetic.
"""
from __future__ import annotations

import pytest

import BackEnd.constants.training_shape as training_shape
import BackEnd.models.training_execution_v2 as training
from BackEnd.constants.training_shape import (
    training_attr_gain_multiplier,
    training_position_projection,
)
from BackEnd.models.training_execution_v2 import positional_focus_attrs_for_player


def _fpd(**over):
    doc = {
        "player_id": "p1",
        "position_intent": "PG",
        "position_ratings": {"PG": 90, "SG": 70, "SF": 60, "PF": 55, "C": 50},
        "attributes": {"anchor_RB": 50, "RB": 50},
        "training_focus": "standard",
    }
    doc.update(over)
    return doc


def _player(**over):
    p = {
        "_id": "p1",
        "year": "senior",   # class multiplier 1.0, so the profile is the only discount
        "attributes": {"anchor_RB": 50, "RB": 50, "anchor_SC": 50, "SC": 50},
    }
    p.update(over)
    return p


# ── the projection carries it ────────────────────────────────────────────────

def test_projection_carries_focus_into_the_training_dict():
    """Both training-player builders (user + CPU autotrain) use this projection."""
    projected = training_position_projection(_fpd(training_focus="rebounding"))
    assert projected["training_focus"] == "rebounding"
    assert projected["resolved_training_focus"] == "rebounding"


def test_projection_resolves_a_legacy_player_to_standard():
    doc = _fpd()
    doc.pop("training_focus")
    projected = training_position_projection(doc)
    assert projected["training_focus"] is None          # nothing invented on the raw field
    assert projected["resolved_training_focus"] == "standard"


def test_projection_keeps_position_and_focus_together():
    projected = training_position_projection(_fpd(training_position="PF", training_focus="athletic"))
    assert projected["resolved_training_position"] == "PF"
    assert projected["resolved_training_focus"] == "athletic"


# ── execution applies it ─────────────────────────────────────────────────────

def test_rebounding_focus_beats_standard_for_a_guard(monkeypatch):
    """The headline case: a PG on Rebounding keeps 75% of a rebounding point, not 25%."""
    monkeypatch.setattr(training.random, "randint", lambda a, b: 4)
    monkeypatch.setattr(training.random, "choice", lambda seq: seq[0])

    standard = _player(training_position="PG", training_focus="standard")
    focused = _player(training_position="PG", training_focus="rebounding")
    training._apply_player_training_points(standard, "RB", 3)
    training._apply_player_training_points(focused, "RB", 3)

    banked_standard = standard["training_gain_remainders"]["RB"]
    banked_focused = focused["training_gain_remainders"]["RB"]
    assert banked_focused == pytest.approx(banked_standard * 3), "0.75 vs 0.25 of the same roll"


def test_execution_uses_the_exact_profile_percentage(monkeypatch):
    """Pin the arithmetic to the matrix rather than to a hand-copied number."""
    monkeypatch.setattr(training.random, "randint", lambda a, b: 4)
    monkeypatch.setattr(training.random, "choice", lambda seq: seq[0])

    player = _player(training_position="C", training_focus="offensive")
    training._apply_player_training_points(player, "SC", 3)

    expected = 4 * training.IN_SEASON_GAIN_SCALE * training_attr_gain_multiplier("C", "SC", "offensive")
    whole = int(expected)
    banked = player["training_gain_remainders"]["SC"]
    assert player["attributes"]["anchor_SC"] - 50 == whole
    assert banked == pytest.approx(expected - whole)


def test_legacy_player_without_focus_trains_as_standard(monkeypatch):
    monkeypatch.setattr(training.random, "randint", lambda a, b: 4)
    monkeypatch.setattr(training.random, "choice", lambda seq: seq[0])

    legacy = _player(training_position="PG")            # no training_focus at all
    explicit = _player(training_position="PG", training_focus="standard")
    training._apply_player_training_points(legacy, "RB", 3)
    training._apply_player_training_points(explicit, "RB", 3)

    assert legacy["training_gain_remainders"]["RB"] == explicit["training_gain_remainders"]["RB"]


def test_camp_scale_and_focus_compose(monkeypatch):
    """Focus multiplies the camp scale; it does not replace or double-apply it."""
    monkeypatch.setattr(training.random, "randint", lambda a, b: 4)
    monkeypatch.setattr(training.random, "choice", lambda seq: seq[0])

    player = _player(training_position="PG", training_focus="rebounding")
    training._apply_player_training_points(player, "RB", 3, gain_scale=training_shape.CAMP_GAIN_SCALE)

    expected = 4 * training_shape.CAMP_GAIN_SCALE * training_attr_gain_multiplier("PG", "RB", "rebounding")
    whole = int(expected)
    assert player["attributes"]["anchor_RB"] - 50 == whole
    assert player["training_gain_remainders"]["RB"] == pytest.approx(expected - whole)


# ── Player Maximizer and Development Focus agree on the position ────────────

def test_maximizer_follows_a_converted_players_training_position():
    converted = {"position_ratings": {"PG": 95, "PF": 40}, "training_position": "PF"}
    assert positional_focus_attrs_for_player(converted) == ("RB", "ID", "ST")


def test_maximizer_falls_back_to_ratings_without_a_training_position():
    assert positional_focus_attrs_for_player({"position_ratings": {"PG": 95, "PF": 40}}) == ("PS", "BH", "IQ")


def test_maximizer_prefers_intent_over_ratings():
    """A natural PG rated highest at C is still coached as a PG until converted."""
    doc = {"position_ratings": {"C": 95, "PG": 40}, "position_intent": "PG"}
    assert positional_focus_attrs_for_player(doc) == ("PS", "BH", "IQ")
