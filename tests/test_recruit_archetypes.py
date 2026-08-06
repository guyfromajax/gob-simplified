"""Tests for position-intent-first recruit generation (design §11.2).

The former 20-archetype attribute machinery was replaced; recruits are now
generated at the class-year ladder target for a drawn position intent + tier via
BackEnd.utils.player_generation. Archetype survives only as a cosmetic label.
"""
import random
from collections import Counter

import pytest
from unittest.mock import Mock

from BackEnd.models.franchise_manager import RecruitManager
from BackEnd.utils.position_ratings import POSITION_WEIGHTS


@pytest.fixture
def mock_db():
    db = Mock()
    db.recruits = Mock()
    return db


@pytest.fixture
def recruit_manager(mock_db):
    return RecruitManager(mock_db)


def test_generate_recruits_creates_correct_count(recruit_manager):
    assert len(recruit_manager.generate_recruits_list(count=25)) == 25


def test_recruit_structure_includes_all_fields(recruit_manager):
    for recruit in recruit_manager.generate_recruits_list(count=20):
        for field in ("name", "attributes", "position_ratings", "height", "weight", "archetype", "year"):
            assert field in recruit


def test_recruit_attributes_include_all_stats(recruit_manager):
    recruit = recruit_manager.generate_recruits_list(count=5)[0]
    attrs = recruit["attributes"]
    for stat in ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT", "CH", "EM", "MO", "NG"):
        assert stat in attrs
    # Anchors are written for every attribute (development/fatigue baseline).
    assert attrs["anchor_SC"] == attrs["SC"]
    assert attrs["NG"] == 1.0


def test_position_ratings_are_five_positions(recruit_manager):
    pr = recruit_manager.generate_recruits_list(count=5)[0]["position_ratings"]
    assert set(pr) == {"PG", "SG", "SF", "PF", "C"}


def test_argmax_mostly_follows_intended_position(recruit_manager):
    """Corrected §3.6.4 gauge (was a mature-height JH-argmax-follows-intent threshold, superseded
    by grow-into-frame). Recruits span class years and are mostly pre-growth; a young frontcourt
    player sits below his adult frame and reads one slot toward the perimeter, so RT-argmax at his
    CURRENT height is NOT the gauge. INTENT supply is; the SR-only argmax check is expressed here
    as a DIRECTION (growing into frame moves argmax toward intent), not a fitted match-rate a
    future height shift would invalidate."""
    random.seed(3)
    recruits = recruit_manager.generate_recruits_list(count=400)

    # Primary — intent supply: position-intent-first generation represents every position, centre
    # included, none collapsed. (The old check measured argmax-C, the grow-into-frame-skewed
    # quantity; intent is the right one — §3.6.4, and the audit script's gauge note.)
    intents = Counter(r["position_intent"] for r in recruits)
    for pos in ("PG", "SG", "SF", "PF", "C"):
        assert intents[pos] / len(recruits) > 0.12, f"{pos} intent supply collapsed: {intents[pos]}"

    # Secondary — SR-only argmax as a direction: project each recruit to his adult frame (current
    # height + the remaining career HT gain for his class year) and confirm growing-in moves argmax
    # TOWARD intent. More recruits argmax at intent grown-in than at their current pre-growth height
    # — the grow-into-frame mechanism itself, asserted without a magic threshold.
    from BackEnd.utils.position_ratings import compute_position_ratings
    from BackEnd.utils.player_generation import (
        HT_TOTAL_MEAN, HT_REMAINING_SHARE_BY_YEAR, normalize_year,
    )
    raw_hits = sum(max(r["position_ratings"], key=r["position_ratings"].get) == r["position_intent"]
                   for r in recruits)
    grown_hits = 0
    for r in recruits:
        remaining = HT_REMAINING_SHARE_BY_YEAR.get(normalize_year(r["year"]), 0.0)
        adult_h = r["height"] + remaining * HT_TOTAL_MEAN
        pr = compute_position_ratings({"attributes": r["attributes"], "height": adult_h})
        grown_hits += max(pr, key=pr.get) == r["position_intent"]
    assert grown_hits > raw_hits, f"grow-into-frame should move argmax toward intent: {raw_hits} → {grown_hits}"


def test_ch_is_flat_uniform(recruit_manager):
    """CH is flat randint(1,100) for every recruit now (§8) — no Intangibles floor."""
    random.seed(1)
    chs = [r["attributes"]["CH"] for r in recruit_manager.generate_recruits_list(count=300)]
    assert min(chs) < 25 and max(chs) > 75  # spans the full range


def test_removed_archetype_internals_are_gone(recruit_manager):
    for gone in ("_select_archetype", "_generate_recruit_profile", "_generate_weight", "_roll_recruit_character"):
        assert not hasattr(recruit_manager, gone), gone
