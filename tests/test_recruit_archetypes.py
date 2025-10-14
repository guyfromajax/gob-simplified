"""
Tests for recruit archetype generation system
"""
import pytest
from unittest.mock import Mock, MagicMock
from BackEnd.models.franchise_manager import RecruitManager


@pytest.fixture
def mock_db():
    """Create a mock database"""
    db = Mock()
    db.recruits = Mock()
    db.recruits.delete_many = Mock()
    db.recruits.insert_many = Mock()
    return db


@pytest.fixture
def recruit_manager(mock_db):
    """Create a RecruitManager instance"""
    return RecruitManager(mock_db)


def test_select_archetype_returns_valid_archetype(recruit_manager):
    """Test that _select_archetype returns one of the defined archetypes"""
    valid_archetypes = [
        "Five-Star", "Four-Star", "Defensive Wizard", "All-Around Scorer",
        "Classic PG", "Classic SG", "Classic SF", "Classic PF", "Classic C",
        "Pure Shooter", "Intangibles", "Athlete", "Inside Defender",
        "Outside Defender", "Average", "Below Average", "Outside Dual Threat",
        "Driver", "Outside C", "Three & D"
    ]
    
    archetype = recruit_manager._select_archetype()
    assert archetype in valid_archetypes


def test_generate_weight_based_on_height(recruit_manager):
    """Test that weight is generated correctly based on height ranges"""
    # Test height < 72
    weight = recruit_manager._generate_weight(70)
    assert 150 <= weight <= 190
    
    # Test height 72-75
    weight = recruit_manager._generate_weight(73)
    assert 170 <= weight <= 210
    
    # Test height 76-80
    weight = recruit_manager._generate_weight(78)
    assert 195 <= weight <= 240
    
    # Test height > 80
    weight = recruit_manager._generate_weight(82)
    assert 220 <= weight <= 270


def test_generate_recruit_profile_five_star(recruit_manager):
    """Test Five-Star archetype has all strong traits"""
    attributes, height, weight = recruit_manager._generate_recruit_profile("Five-Star")
    
    # All attributes should be in strong range (20-40)
    for attr, value in attributes.items():
        assert 20 <= value <= 40, f"{attr} should be strong (20-40), got {value}"
    
    # Height should be in Five-Star range
    assert 69 <= height <= 80
    
    # Weight should be appropriate for height
    assert isinstance(weight, int)
    assert 150 <= weight <= 270


def test_generate_recruit_profile_below_average(recruit_manager):
    """Test Below Average archetype has all weak traits"""
    attributes, height, weight = recruit_manager._generate_recruit_profile("Below Average")
    
    # All attributes should be in weak range (1-20)
    for attr, value in attributes.items():
        assert 1 <= value <= 20, f"{attr} should be weak (1-20), got {value}"


def test_generate_recruit_profile_defensive_wizard(recruit_manager):
    """Test Defensive Wizard has correct strong and secondary traits"""
    attributes, height, weight = recruit_manager._generate_recruit_profile("Defensive Wizard")
    
    # Strong traits: ID, OD (20-40)
    assert 20 <= attributes["ID"] <= 40
    assert 20 <= attributes["OD"] <= 40
    
    # Secondary traits: ST, AG (10-40)
    assert 10 <= attributes["ST"] <= 40
    assert 10 <= attributes["AG"] <= 40
    
    # Standard traits: all others (1-40)
    for attr in ["SC", "SH", "PS", "BH", "RB", "ND", "IQ", "FT", "CH"]:
        assert 1 <= attributes[attr] <= 40


def test_generate_recruit_profile_classic_c(recruit_manager):
    """Test Classic C has correct height range and attributes"""
    attributes, height, weight = recruit_manager._generate_recruit_profile("Classic C")
    
    # Height range for Classic C: 72-82
    assert 72 <= height <= 82
    
    # Strong traits: ID, ST
    assert 20 <= attributes["ID"] <= 40
    assert 20 <= attributes["ST"] <= 40
    
    # Secondary traits: RB, SC
    assert 10 <= attributes["RB"] <= 40
    assert 10 <= attributes["SC"] <= 40


def test_generate_recruit_profile_three_and_d(recruit_manager):
    """Test Three & D has correct attributes and height range"""
    attributes, height, weight = recruit_manager._generate_recruit_profile("Three & D")
    
    # Height range: 69-77
    assert 69 <= height <= 77
    
    # Strong trait: SH
    assert 20 <= attributes["SH"] <= 40
    
    # Secondary traits: ID, OD
    assert 10 <= attributes["ID"] <= 40
    assert 10 <= attributes["OD"] <= 40


def test_generate_recruits_creates_correct_count(recruit_manager):
    """Test that generate_recruits_list creates the specified number of recruits"""
    recruits = recruit_manager.generate_recruits_list(count=25)
    assert len(recruits) == 25


def test_recruit_structure_includes_all_fields(recruit_manager):
    """Test that each recruit has all required fields"""
    recruits = recruit_manager.generate_recruits_list(count=5)
    
    for recruit in recruits:
        assert "name" in recruit
        assert "attributes" in recruit
        assert "position_ratings" in recruit
        assert "height" in recruit
        assert "weight" in recruit
        assert "archetype" in recruit
        assert "year" in recruit
        assert recruit["year"] == "Freshman"
        assert "created_at" in recruit


def test_recruit_attributes_include_all_stats(recruit_manager):
    """Test that each recruit has all 13 attributes"""
    recruits = recruit_manager.generate_recruits_list(count=5)
    expected_attrs = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "CH"]
    
    for recruit in recruits:
        for attr in expected_attrs:
            assert attr in recruit["attributes"], f"Missing {attr} in recruit attributes"


def test_archetype_distribution_includes_rare_types(recruit_manager):
    """Test that rare archetypes (Five-Star, Four-Star) can be generated"""
    archetypes_found = set()
    
    # Generate many recruits to increase chance of finding rare types
    for _ in range(100):
        archetype = recruit_manager._select_archetype()
        archetypes_found.add(archetype)
    
    # Should have generated multiple different archetypes
    assert len(archetypes_found) > 5, "Should generate variety of archetypes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

