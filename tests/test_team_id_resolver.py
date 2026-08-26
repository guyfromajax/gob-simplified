"""
Unit tests for team_id_resolver.py

Tests the unified team ID resolution system.
"""

import pytest
from unittest.mock import Mock, MagicMock
from BackEnd.utils.team_id_resolver import (
    resolve_team_id_to_canonical,
    resolve_team_id_to_object_id,
    _is_canonical_format,
    _is_objectid_string,
    find_team_row,
)


class TestCanonicalFormatDetection:
    """Test canonical format detection."""
    
    def test_is_canonical_format_uppercase_with_underscore(self):
        """Test: "OCEAN_CITY" is canonical format."""
        assert _is_canonical_format("OCEAN_CITY") is True
        assert _is_canonical_format("SOUTH_LANCASTER") is True
    
    def test_is_canonical_format_uppercase_single_word(self):
        """Test: "MORRISTOWN" is canonical format."""
        assert _is_canonical_format("MORRISTOWN") is True
        assert _is_canonical_format("XAVIEN") is True
    
    def test_is_not_canonical_format_lowercase(self):
        """Test: Lowercase strings are not canonical."""
        assert _is_canonical_format("morristown") is False
        assert _is_canonical_format("ocean_city") is False
    
    def test_is_not_canonical_format_mixed_case(self):
        """Test: Mixed case strings are not canonical."""
        assert _is_canonical_format("Morristown") is False
        assert _is_canonical_format("Ocean_City") is False
    
    def test_is_not_canonical_format_objectid(self):
        """Test: ObjectId strings are not canonical format."""
        assert _is_canonical_format("507f1f77bcf86cd799439011") is False


class TestObjectIdDetection:
    """Test ObjectId string detection."""
    
    def test_is_objectid_string_valid(self):
        """Test: Valid ObjectId strings are detected."""
        assert _is_objectid_string("507f1f77bcf86cd799439011") is True
        assert _is_objectid_string("68c98b09674d3f9b04546b32") is True
    
    def test_is_objectid_string_invalid(self):
        """Test: Invalid ObjectId strings are not detected."""
        assert _is_objectid_string("MORRISTOWN") is False
        assert _is_objectid_string("Morristown") is False
        assert _is_objectid_string("123") is False
        assert _is_objectid_string("") is False


class TestResolveFromGameDocument:
    """Test resolution from game document (single mode)."""
    
    def test_resolve_canonical_from_game_document(self):
        """Test: Canonical team_id in game document returns as-is."""
        doc = {
            "teams": {
                "MORRISTOWN": {"name": "Morristown"},
                "OCEAN_CITY": {"name": "Ocean City"}
            }
        }
        result = resolve_team_id_to_canonical("MORRISTOWN", mode="single", doc=doc)
        assert result == "MORRISTOWN"
    
    def test_resolve_name_from_game_document(self):
        """Test: Team name resolves to canonical team_id from game document."""
        doc = {
            "teams": {
                "MORRISTOWN": {"name": "Morristown"},
                "OCEAN_CITY": {"name": "Ocean City"}
            }
        }
        result = resolve_team_id_to_canonical("Morristown", mode="single", doc=doc)
        assert result == "MORRISTOWN"
    
    def test_resolve_name_case_insensitive(self):
        """Test: Team name resolution is case-insensitive."""
        doc = {
            "teams": {
                "MORRISTOWN": {"name": "Morristown"},
                "OCEAN_CITY": {"name": "Ocean City"}
            }
        }
        result = resolve_team_id_to_canonical("morristown", mode="single", doc=doc)
        assert result == "MORRISTOWN"
    
    def test_resolve_fails_if_not_in_document(self):
        """Test: Resolution fails if team not in game document."""
        doc = {
            "teams": {
                "MORRISTOWN": {"name": "Morristown"}
            }
        }
        with pytest.raises(ValueError, match="Cannot resolve"):
            resolve_team_id_to_canonical("XAVIEN", mode="single", doc=doc)


class TestResolveFromDatabase:
    """Test resolution from database."""
    
    def test_resolve_objectid_from_database(self):
        """Test: ObjectId string resolves to canonical team_id from database."""
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            "_id": "507f1f77bcf86cd799439011",
            "team_id": "MORRISTOWN",
            "name": "Morristown"
        }
        
        result = resolve_team_id_to_canonical(
            "507f1f77bcf86cd799439011",
            teams_collection_override=mock_collection
        )
        assert result == "MORRISTOWN"
        mock_collection.find_one.assert_called()
    
    def test_resolve_name_from_database(self):
        """Test: Team name resolves to canonical team_id from database."""
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            "team_id": "MORRISTOWN",
            "name": "Morristown"
        }
        
        result = resolve_team_id_to_canonical(
            "Morristown",
            teams_collection_override=mock_collection
        )
        assert result == "MORRISTOWN"
    
    def test_resolve_name_case_insensitive_from_database(self):
        """Test: Team name resolution is case-insensitive from database."""
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            "team_id": "MORRISTOWN",
            "name": "Morristown"
        }
        
        result = resolve_team_id_to_canonical(
            "morristown",
            teams_collection_override=mock_collection
        )
        assert result == "MORRISTOWN"
    
    def test_resolve_fails_if_not_in_database(self):
        """Test: Resolution fails if team not in database."""
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        
        with pytest.raises(ValueError, match="Cannot resolve"):
            resolve_team_id_to_canonical(
                "UNKNOWN_TEAM",
                teams_collection_override=mock_collection
            )


class TestResolveToObjectId:
    """Test resolution to ObjectId string."""
    
    def test_resolve_canonical_to_object_id(self):
        """Test: Canonical team_id resolves to ObjectId string."""
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            "_id": "507f1f77bcf86cd799439011",
            "team_id": "MORRISTOWN"
        }
        
        result = resolve_team_id_to_object_id(
            "MORRISTOWN",
            teams_collection_override=mock_collection
        )
        assert result == "507f1f77bcf86cd799439011"
    
    def test_resolve_name_to_object_id(self):
        """Test: Team name resolves to ObjectId string."""
        # First lookup: name -> canonical
        # Second lookup: canonical -> ObjectId
        mock_collection = MagicMock()
        mock_collection.find_one.side_effect = [
            {"team_id": "MORRISTOWN", "name": "Morristown"},  # Name lookup
            {"_id": "507f1f77bcf86cd799439011", "team_id": "MORRISTOWN"}  # ObjectId lookup
        ]
        
        result = resolve_team_id_to_object_id(
            "Morristown",
            teams_collection_override=mock_collection
        )
        assert result == "507f1f77bcf86cd799439011"


class TestErrorHandling:
    """Test error handling."""
    
    def test_empty_team_identifier_raises_error(self):
        """Test: Empty team_identifier raises ValueError."""
        with pytest.raises(ValueError, match="team_identifier is required"):
            resolve_team_id_to_canonical("")
    
    def test_none_team_identifier_raises_error(self):
        """Test: None team_identifier raises ValueError."""
        with pytest.raises(ValueError, match="team_identifier is required"):
            resolve_team_id_to_canonical(None)
    
    def test_unresolvable_team_identifier_raises_error(self):
        """Test: Unresolvable team_identifier raises ValueError."""
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        
        with pytest.raises(ValueError, match="Cannot resolve"):
            resolve_team_id_to_canonical(
                "NONEXISTENT_TEAM",
                teams_collection_override=mock_collection
            )


class TestFindTeamRow:
    """Fuzzy teams-slot lookup used by simulate-quarter score restore."""

    def test_finds_row_when_id_is_objectid_and_slot_is_slug(self):
        teams = {
            "CHAPEL_HILL": {
                "name": "Chapel Hill",
                "team_id": "CHAPEL_HILL",
                "score": 58,
            },
            "BENTLEY_TRUMAN": {
                "name": "Bentley-Truman",
                "team_id": "BENTLEY_TRUMAN",
                "score": 51,
            },
        }
        home = find_team_row(
            teams,
            "69a6fcb68d2c56aa82e48a5d",
            "Chapel Hill",
        )
        away = find_team_row(
            teams,
            "69a6fcb68d2c56aa82e48a52",
            "Bentley-Truman",
        )
        assert home["score"] == 58
        assert away["score"] == 51

    def test_returns_empty_when_no_candidates_match(self):
        assert find_team_row({"CHAPEL_HILL": {"name": "Chapel Hill"}}, "nope") == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

