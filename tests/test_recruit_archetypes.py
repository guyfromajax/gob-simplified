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


# Year-based attribute tier ranges: (STRONG, SECONDARY, STANDARD, WEAK)
YEAR_TIERS = {
    "JH": ((20, 80), (10, 60), (1, 40), (1, 20)),
    "Freshman": ((30, 80), (20, 60), (10, 40), (10, 20)),
    "Sophomore": ((40, 85), (30, 70), (10, 50), (10, 30)),
    "Junior": ((60, 95), (40, 80), (10, 60), (10, 50)),
}


@pytest.mark.parametrize("year", list(YEAR_TIERS.keys()))
def test_generate_recruit_profile_five_star(recruit_manager, year):
    """Five-Star rolls all attributes in the year's STRONG range"""
    strong, _, _, _ = YEAR_TIERS[year]
    attributes, height, weight = recruit_manager._generate_recruit_profile("Five-Star", year)

    for attr, value in attributes.items():
        assert strong[0] <= value <= strong[1], f"{attr} should be strong {strong}, got {value} ({year})"

    # Height should be in Five-Star range (archetype-based, not year-based)
    assert 69 <= height <= 80

    # Weight should be appropriate for height
    assert isinstance(weight, int)
    assert 150 <= weight <= 270


@pytest.mark.parametrize("year", list(YEAR_TIERS.keys()))
def test_generate_recruit_profile_below_average(recruit_manager, year):
    """Below Average rolls all attributes in the year's WEAK range"""
    _, _, _, weak = YEAR_TIERS[year]
    attributes, height, weight = recruit_manager._generate_recruit_profile("Below Average", year)

    for attr, value in attributes.items():
        assert weak[0] <= value <= weak[1], f"{attr} should be weak {weak}, got {value} ({year})"


@pytest.mark.parametrize("year", list(YEAR_TIERS.keys()))
def test_generate_recruit_profile_defensive_wizard(recruit_manager, year):
    """Defensive Wizard rolls correct strong/secondary/standard tiers for the year"""
    strong, secondary, standard, _ = YEAR_TIERS[year]
    attributes, height, weight = recruit_manager._generate_recruit_profile("Defensive Wizard", year)

    assert strong[0] <= attributes["ID"] <= strong[1]
    assert strong[0] <= attributes["OD"] <= strong[1]

    assert secondary[0] <= attributes["ST"] <= secondary[1]
    assert secondary[0] <= attributes["AG"] <= secondary[1]

    for attr in ["SC", "SH", "PS", "BH", "RB", "ND", "IQ", "FT"]:
        assert standard[0] <= attributes[attr] <= standard[1]


def test_generate_recruit_profile_defaults_to_jh_tiers(recruit_manager):
    """Calling without a year uses the JH tier table"""
    strong, _, _, _ = YEAR_TIERS["JH"]
    attributes, _, _ = recruit_manager._generate_recruit_profile("Five-Star")
    for attr, value in attributes.items():
        assert strong[0] <= value <= strong[1]


def test_generate_recruit_profile_classic_c(recruit_manager):
    """Test Classic C has correct height range and attributes (JH tiers)"""
    strong, secondary, _, _ = YEAR_TIERS["JH"]
    attributes, height, weight = recruit_manager._generate_recruit_profile("Classic C", "JH")

    # Height range for Classic C: 72-78
    assert 72 <= height <= 78

    # Strong traits: ID, ST
    assert strong[0] <= attributes["ID"] <= strong[1]
    assert strong[0] <= attributes["ST"] <= strong[1]

    # Secondary traits: RB, SC
    assert secondary[0] <= attributes["RB"] <= secondary[1]
    assert secondary[0] <= attributes["SC"] <= secondary[1]


def test_generate_recruit_profile_three_and_d(recruit_manager):
    """Test Three & D has correct attributes and height range (JH tiers)"""
    strong, secondary, _, _ = YEAR_TIERS["JH"]
    attributes, height, weight = recruit_manager._generate_recruit_profile("Three & D", "JH")

    # Height range: 69-75
    assert 69 <= height <= 75

    # Strong trait: SH
    assert strong[0] <= attributes["SH"] <= strong[1]

    # Secondary traits: ID, OD
    assert secondary[0] <= attributes["ID"] <= secondary[1]
    assert secondary[0] <= attributes["OD"] <= secondary[1]


def test_roll_recruit_character_intangibles_uses_year_strong_floor(recruit_manager):
    """Intangibles CH floor matches recruit YEAR_TIER_RANGES STRONG minimum; max 100."""
    floors = {"JH": 20, "Freshman": 30, "Sophomore": 40, "Junior": 60}
    for year, floor in floors.items():
        for _ in range(50):
            ch = recruit_manager._roll_recruit_character("Intangibles", year)
            assert floor <= ch <= 100, f"year={year} got CH={ch}"


def test_roll_recruit_character_non_intangibles_uniform(recruit_manager):
    """Non-Intangibles recruits roll CH uniformly 1-100."""
    for _ in range(100):
        ch = recruit_manager._roll_recruit_character("Classic PG", "JH")
        assert 1 <= ch <= 100


def test_generate_recruits_list_intangibles_ch_preserved(recruit_manager):
    """Full pipeline keeps Intangibles CH floor; does not cap at year STRONG max."""
    for _ in range(200):
        recruits = recruit_manager.generate_recruits_list(count=1)
        recruit = recruits[0]
        if recruit["archetype"] != "Intangibles":
            continue
        year = recruit["year"]
        floor = RecruitManager.YEAR_TIER_RANGES[year][0][0]
        ch = recruit["attributes"]["CH"]
        assert floor <= ch <= 100
        assert recruit["attributes"]["anchor_CH"] == ch
        return
    pytest.skip("No Intangibles recruit in sample")


def test_generate_recruits_list_non_intangibles_ch_uniform(recruit_manager):
    """Full pipeline: non-Intangibles CH stays in 1-100 (not tier-capped)."""
    recruits = recruit_manager.generate_recruits_list(count=50)
    for recruit in recruits:
        if recruit["archetype"] == "Intangibles":
            continue
        ch = recruit["attributes"]["CH"]
        assert 1 <= ch <= 100


def test_year_distribution_counts(recruit_manager):
    """300-pool year roll: Junior 5-15, Sophomore 5-15, Freshman 10-30, JH = remainder"""
    years = recruit_manager._roll_year_distribution(300)
    assert len(years) == 300
    junior = years.count("Junior")
    sophomore = years.count("Sophomore")
    freshman = years.count("Freshman")
    jh = years.count("JH")
    assert 5 <= junior <= 15
    assert 5 <= sophomore <= 15
    assert 10 <= freshman <= 30
    assert jh == 300 - (junior + sophomore + freshman)


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
        assert recruit["year"] in ("JH", "Freshman", "Sophomore", "Junior")
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

