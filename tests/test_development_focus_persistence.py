"""Development Focus, phase 2: derivation, creation-path defaults, and the write path.

The runtime creation paths and the backfill script must agree about what training position
a doc should get — they share ``derive_training_position`` precisely so they cannot drift.
"""
from __future__ import annotations

import pytest

from BackEnd.constants.training_shape import (
    DEFAULT_TRAINING_FOCUS,
    POSITIONS,
    TRAINING_FOCUSES,
    derive_training_position,
    resolve_training_focus,
    resolve_training_position,
)
from BackEnd.models.franchise_manager import PLAYER_DEV_CARRY_FIELDS, carry_dev_fields


# ── derivation ───────────────────────────────────────────────────────────────

def test_position_intent_wins_over_ratings():
    doc = {"position_intent": "SG", "position_ratings": {"C": 99, "SG": 10}}
    assert derive_training_position(doc) == "SG"


def test_falls_back_to_the_highest_rating():
    assert derive_training_position({"position_ratings": {"PG": 10, "C": 40, "SF": 20}}) == "C"


def test_unknown_position_is_left_unknown():
    """Rule 26: no position source means no position, not a substituted one."""
    assert derive_training_position({}) is None
    assert derive_training_position({"position_ratings": {}}) is None
    assert derive_training_position({"position_intent": "ZZ"}) is None


def test_garbage_ratings_are_ignored_not_ranked():
    assert derive_training_position({"position_ratings": {"PG": "high", "ZZ": 99}}) is None


def test_tie_is_deterministic_for_the_same_document():
    doc = {"_id": "abc123", "position_ratings": {"PG": 50, "C": 50}}
    picks = {derive_training_position(doc) for _ in range(25)}
    assert len(picks) == 1
    assert picks.pop() in ("PG", "C")


def test_tie_break_varies_across_documents():
    """Deterministic per doc, but not the same answer for every doc."""
    picks = {
        derive_training_position({"_id": f"doc-{i}", "position_ratings": {"PG": 50, "C": 50}})
        for i in range(40)
    }
    assert picks == {"PG", "C"}


# ── creation-path defaults (every hop goes through carry_dev_fields) ─────────

def test_carry_set_declares_both_development_fields():
    assert "training_position" in PLAYER_DEV_CARRY_FIELDS
    assert "training_focus" in PLAYER_DEV_CARRY_FIELDS


def test_new_player_gets_both_fields():
    carried = carry_dev_fields({"position_intent": "SG", "entry_tier": "blue"})
    assert carried["training_position"] == "SG"
    assert carried["training_focus"] == DEFAULT_TRAINING_FOCUS


def test_a_coachs_choice_survives_the_hop():
    """The whole point of the carry set: signing or rollover must not reset a conversion."""
    carried = carry_dev_fields({
        "position_intent": "SG",       # natural fit
        "training_position": "PF",     # coach converted him
        "training_focus": "rebounding",
    })
    assert carried["training_position"] == "PF"
    assert carried["training_focus"] == "rebounding"
    assert carried["position_intent"] == "SG", "natural fit must be preserved alongside"


def test_position_is_omitted_when_it_cannot_be_derived():
    carried = carry_dev_fields({"entry_tier": "green"})
    assert "training_position" not in carried
    assert carried["training_focus"] == DEFAULT_TRAINING_FOCUS


def test_carry_does_not_invent_other_absent_fields():
    carried = carry_dev_fields({"position_intent": "PG"})
    for field in ("development", "coaching_quality", "potential_factor", "entry_tier"):
        assert field not in carried


# ── the backfill script shares the runtime rule ─────────────────────────────

def test_backfill_uses_the_same_derivation_as_the_runtime():
    from scripts.backfill_development_focus import resolve_position

    cases = [
        {"position_intent": "SF"},
        {"position_ratings": {"PG": 12, "PF": 30}},
        {"_id": "x1", "position_ratings": {"SG": 40, "SF": 40}},
        {},
    ]
    for doc in cases:
        assert resolve_position(doc)[0] == derive_training_position(doc)


@pytest.mark.parametrize("doc,expected_source", [
    ({"position_intent": "SF"}, "intent"),
    ({"position_ratings": {"PG": 12, "PF": 30}}, "ratings"),
    ({"_id": "x1", "position_ratings": {"SG": 40, "SF": 40}}, "ratings-tie"),
    ({}, "none"),
])
def test_backfill_reports_where_the_position_came_from(doc, expected_source):
    from scripts.backfill_development_focus import resolve_position

    assert resolve_position(doc)[1] == expected_source


# ── read-side resolution stays forgiving ────────────────────────────────────

def test_stored_garbage_never_blocks_training():
    """A bad stored value degrades to standard rather than raising mid-week."""
    assert resolve_training_focus({"training_focus": "sabotage"}) == DEFAULT_TRAINING_FOCUS
    assert resolve_training_position({"training_position": "ZZ", "position_intent": "PG"}) == "PG"


def test_every_stored_focus_value_is_resolvable():
    for focus in TRAINING_FOCUSES:
        assert resolve_training_focus({"training_focus": focus}) == focus


def test_every_position_is_a_valid_training_position():
    for pos in POSITIONS:
        assert resolve_training_position({"training_position": pos}) == pos
