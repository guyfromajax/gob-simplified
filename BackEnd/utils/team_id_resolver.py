"""
Unified Team ID Resolver

This module provides a single source of truth for resolving team identifiers
to the canonical team_id format (all caps with underscores, e.g., "MORRISTOWN").

The canonical format is:
- All caps string with underscores (e.g., "MORRISTOWN", "OCEAN_CITY", "SOUTH_LANCASTER")
- Used for internal logic, game documents, and lookups
- NOT ObjectId strings (those are only for specific database document keys)

This resolver handles:
- Team names (e.g., "Morristown") → canonical team_id (e.g., "MORRISTOWN")
- ObjectId strings (e.g., "507f1f77bcf86cd799439011") → canonical team_id
- Canonical team_id (e.g., "MORRISTOWN") → returns as-is
"""

import logging
from typing import Optional
from bson import ObjectId

logger = logging.getLogger(__name__)

# Try to import database collections (optional, for database lookups)
try:
    from BackEnd.db import teams_collection
    HAS_DB = True
except ImportError:
    HAS_DB = False
    teams_collection = None


def resolve_team_id_to_canonical(
    team_identifier: str,
    mode: str = "single",
    doc: Optional[dict] = None,
    teams_collection_override = None
) -> str:
    """
    Resolves any team identifier to canonical team_id format.
    
    Canonical format: All caps string with underscores (e.g., "MORRISTOWN", "OCEAN_CITY")
    
    This is the single source of truth for team ID resolution across the codebase.
    
    Args:
        team_identifier: Team identifier in any format:
            - Team name (e.g., "Morristown")
            - ObjectId string (e.g., "507f1f77bcf86cd799439011")
            - Canonical team_id (e.g., "MORRISTOWN")
        mode: Game mode ("single", "franchise", "tournament")
        doc: Optional document (game/franchise/tournament) for context
        teams_collection_override: Optional teams collection override for testing
    
    Returns:
        Canonical team_id string (e.g., "MORRISTOWN")
    
    Raises:
        ValueError: If team_identifier cannot be resolved to canonical format
    """
    if not team_identifier:
        raise ValueError("team_identifier is required")
    
    team_identifier = str(team_identifier).strip()
    
    # Use override if provided, otherwise use module-level collection
    collection = teams_collection_override or teams_collection
    
    # Step 1: For single mode, ALWAYS resolve from game document first (don't trust input format)
    # This ensures we get the actual canonical team_id from the document, not just assume input is correct
    if mode == "single" and doc:
        canonical_id = _resolve_from_game_document(team_identifier, doc)
        if canonical_id:
            return canonical_id
    
    # Step 2: For franchise/tournament mode, resolve from document's user_team_object_id
    if mode in ("franchise", "tournament") and doc:
        canonical_id = _resolve_from_franchise_tournament_document(team_identifier, mode, doc, collection)
        if canonical_id:
            return canonical_id
    
    # Step 3: Check if already in canonical format (only if we don't have document context)
    # Canonical format: all caps, contains underscore or is single word in caps
    if _is_canonical_format(team_identifier):
        return team_identifier
    
    # Step 4: Try to resolve from database (if available)
    if HAS_DB and collection is not None:
        canonical_id = _resolve_from_database(team_identifier, collection)
        if canonical_id:
            return canonical_id
    
    # Step 5: Try ObjectId lookup (if it's an ObjectId string)
    if _is_objectid_string(team_identifier):
        if HAS_DB and collection is not None:
            canonical_id = _resolve_objectid_to_canonical(team_identifier, collection)
            if canonical_id:
                return canonical_id
    
    # Step 6: Try name-based resolution (case-insensitive, with underscore normalization)
    if HAS_DB and collection is not None:
        canonical_id = _resolve_name_to_canonical(team_identifier, collection)
        if canonical_id:
            return canonical_id
    
    # Step 7: Fail loudly if cannot resolve
    raise ValueError(
        f"Cannot resolve team identifier '{team_identifier}' to canonical team_id format. "
        f"Mode: {mode}, Has DB: {HAS_DB}"
    )


def _is_canonical_format(team_id: str) -> bool:
    """Check if team_id is already in canonical format (all caps with underscores)."""
    if not team_id:
        return False
    
    # Canonical format: all uppercase, and either:
    # - Contains underscore (e.g., "OCEAN_CITY", "SOUTH_LANCASTER")
    # - Or is a single word in all caps (e.g., "MORRISTOWN", "XAVIEN")
    is_uppercase = team_id.isupper()
    has_underscore = "_" in team_id
    is_single_word_caps = is_uppercase and not has_underscore and len(team_id) > 0
    
    return is_uppercase and (has_underscore or is_single_word_caps)


def _is_objectid_string(team_id: str) -> bool:
    """Check if team_id is a valid ObjectId string."""
    try:
        ObjectId(team_id)
        return len(team_id) == 24  # ObjectId strings are 24 characters
    except:
        return False


def _resolve_from_franchise_tournament_document(
    team_identifier: str,
    mode: str,
    doc: dict,
    collection
) -> Optional[str]:
    """
    Resolve team identifier from franchise/tournament document.
    
    For franchise/tournament mode, we get the user_team_object_id from the document
    and resolve it to canonical team_id via database lookup.
    """
    try:
        # Import here to avoid circular dependencies
        if mode == "franchise":
            from BackEnd.api.franchise_routes import get_user_team_from_franchise
            user_team_id, user_team_object_id = get_user_team_from_franchise(doc)
        elif mode == "tournament":
            from BackEnd.api.tournament_routes import get_user_team_from_tournament
            user_team_id, user_team_object_id = get_user_team_from_tournament(doc)
        else:
            return None
        
        if not user_team_object_id:
            return None
        
        # Resolve ObjectId to canonical team_id
        if HAS_DB and collection is not None:
            canonical_id = _resolve_objectid_to_canonical(user_team_object_id, collection)
            if canonical_id:
                return canonical_id
        
        # Fallback: if user_team_id is a team name, try to resolve it
        if user_team_id and HAS_DB and collection:
            canonical_id = _resolve_name_to_canonical(user_team_id, collection)
            if canonical_id:
                return canonical_id
        
    except Exception as e:
        logger.debug(f"Error resolving from franchise/tournament document: {e}")
    
    return None


def _resolve_from_game_document(team_identifier: str, doc: dict) -> Optional[str]:
    """
    Resolve team identifier from game document (single mode).
    
    Game documents store teams with canonical team_id as keys (e.g., "MORRISTOWN").
    """
    teams = doc.get("teams", {})
    
    # Direct key match
    if team_identifier in teams:
        return team_identifier
    
    # Name match (case-insensitive)
    for canonical_id, team_obj in teams.items():
        team_name = team_obj.get("name", "")
        if team_name.lower() == team_identifier.lower():
            return canonical_id
    
    return None


def _resolve_from_database(team_identifier: str, collection) -> Optional[str]:
    """
    Resolve team identifier from teams collection.
    
    Looks up team document and extracts canonical team_id from team_id field.
    """
    try:
        # Try as ObjectId first
        if _is_objectid_string(team_identifier):
            team_doc = collection.find_one({"_id": ObjectId(team_identifier)}, {"team_id": 1, "name": 1})
            if team_doc:
                # Team documents have a "team_id" field with canonical format
                canonical_id = team_doc.get("team_id")
                if canonical_id and _is_canonical_format(canonical_id):
                    return canonical_id
        
        # Try as team name (case-insensitive)
        team_doc = collection.find_one(
            {"name": {"$regex": f"^{team_identifier}$", "$options": "i"}},
            {"team_id": 1, "name": 1}
        )
        if team_doc:
            canonical_id = team_doc.get("team_id")
            if canonical_id and _is_canonical_format(canonical_id):
                return canonical_id
        
        # Try underscore normalization (e.g., "Ocean City" -> "OCEAN_CITY")
        if "_" in team_identifier:
            normalized_name = team_identifier.replace("_", " ").title()
            team_doc = collection.find_one(
                {"name": {"$regex": f"^{normalized_name}$", "$options": "i"}},
                {"team_id": 1, "name": 1}
            )
            if team_doc:
                canonical_id = team_doc.get("team_id")
                if canonical_id and _is_canonical_format(canonical_id):
                    return canonical_id
        
    except Exception as e:
        logger.debug(f"Error resolving from database: {e}")
    
    return None


def _resolve_objectid_to_canonical(object_id_str: str, collection) -> Optional[str]:
    """Resolve ObjectId string to canonical team_id."""
    try:
        team_doc = collection.find_one({"_id": ObjectId(object_id_str)}, {"team_id": 1})
        if team_doc:
            canonical_id = team_doc.get("team_id")
            if canonical_id and _is_canonical_format(canonical_id):
                return canonical_id
    except Exception as e:
        logger.debug(f"Error resolving ObjectId to canonical: {e}")
    
    return None


def _resolve_name_to_canonical(team_name: str, collection) -> Optional[str]:
    """Resolve team name to canonical team_id."""
    try:
        # Case-insensitive name lookup
        team_doc = collection.find_one(
            {"name": {"$regex": f"^{team_name}$", "$options": "i"}},
            {"team_id": 1, "name": 1}
        )
        if team_doc:
            canonical_id = team_doc.get("team_id")
            if canonical_id and _is_canonical_format(canonical_id):
                return canonical_id
        
        # Try underscore normalization
        if "_" not in team_name:
            # Try converting "Ocean City" -> "OCEAN_CITY" format
            normalized_name = team_name.replace(" ", "_").upper()
            # This is a heuristic - we'd need to check if this matches a team_id field
            # For now, just try the database lookup with the normalized name
            pass
        
    except Exception as e:
        logger.debug(f"Error resolving name to canonical: {e}")
    
    return None


def resolve_team_id_to_object_id(
    team_identifier: str,
    mode: str = "single",
    doc: Optional[dict] = None,
    teams_collection_override = None
) -> str:
    """
    Resolves team identifier to ObjectId string (for database document keys).
    
    This is a convenience function for cases where you need ObjectId strings
    (e.g., for tournament.teams[ObjectId] or FTD team list keys).
    
    Args:
        team_identifier: Team identifier in any format
        mode: Game mode
        doc: Optional document for context
        teams_collection_override: Optional teams collection override
    
    Returns:
        ObjectId string (e.g., "507f1f77bcf86cd799439011")
    
    Raises:
        ValueError: If team_identifier cannot be resolved
    """
    # First resolve to canonical format
    canonical_id = resolve_team_id_to_canonical(
        team_identifier, mode, doc, teams_collection_override
    )
    
    # Then look up ObjectId from canonical team_id
    collection = teams_collection_override or teams_collection
    
    if HAS_DB and collection is not None:
        try:
            team_doc = collection.find_one({"team_id": canonical_id}, {"_id": 1})
            if team_doc:
                return str(team_doc["_id"])
        except Exception as e:
            logger.debug(f"Error resolving canonical to ObjectId: {e}")
    
    raise ValueError(
        f"Cannot resolve canonical team_id '{canonical_id}' to ObjectId string"
    )

