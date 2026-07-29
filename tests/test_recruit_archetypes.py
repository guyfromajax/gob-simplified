"""Tests for position-intent-first recruit generation (design §11.2).

The former 20-archetype attribute machinery was replaced; recruits are now
generated at the class-year ladder target for a drawn position intent + tier via
BackEnd.utils.player_generation. Archetype survives only as a cosmetic label.
"""
import random

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
    """Position-intent-first: a recruit's top RT usually lands at his archetype's
    position, and centre supply now exists (was collapsing before)."""
    random.seed(3)
    recruits = recruit_manager.generate_recruits_list(count=400)
    # Classic-<POS> archetypes should mostly argmax at <POS>.
    classic = [r for r in recruits if r["archetype"].startswith("Classic ")]
    hits = 0
    for r in classic:
        pos = r["archetype"].split()[1]
        pr = r["position_ratings"]
        if max(pr, key=pr.get) == pos:
            hits += 1
    assert hits / max(1, len(classic)) > 0.8
    # Centre supply is materially above the old 10.9%.
    argmax_c = sum(max(r["position_ratings"], key=r["position_ratings"].get) == "C" for r in recruits)
    assert argmax_c / len(recruits) > 0.12


def test_ch_is_flat_uniform(recruit_manager):
    """CH is flat randint(1,100) for every recruit now (§8) — no Intangibles floor."""
    random.seed(1)
    chs = [r["attributes"]["CH"] for r in recruit_manager.generate_recruits_list(count=300)]
    assert min(chs) < 25 and max(chs) > 75  # spans the full range


def test_removed_archetype_internals_are_gone(recruit_manager):
    for gone in ("_select_archetype", "_generate_recruit_profile", "_generate_weight", "_roll_recruit_character"):
        assert not hasattr(recruit_manager, gone), gone
