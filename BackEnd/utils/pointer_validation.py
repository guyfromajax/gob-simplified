"""
Pointer Validation Utility
Phase 2: Validate that pointers (game_id, franchise_id, tournament_id) point to existing documents

This module provides utilities to validate that pointers in URLs actually point to
valid documents in the database, ensuring we fail loudly when pointers are invalid.
"""

from fastapi import HTTPException
from bson import ObjectId
from BackEnd.db import db
from BackEnd.utils.game_id_utils import normalize_game_id
import logging

logger = logging.getLogger(__name__)


def validate_game_id(game_id: str) -> bool:
    """
    Validate that game_id points to an existing game document.
    
    Args:
        game_id: Game ID to validate (will be normalized to ObjectId format)
    
    Returns:
        True if document exists, False otherwise
    
    Raises:
        HTTPException: If game_id is invalid format or document not found
    """
    if not game_id:
        raise HTTPException(status_code=400, detail="game_id is required")
    
    # Normalize to ObjectId format
    normalized_id = normalize_game_id(game_id)
    
    # Try to find document (try both formats for backward compatibility)
    doc = db.games.find_one({"_id": normalized_id}, {"_id": 1})
    if not doc:
        # Try as ObjectId if string lookup failed
        try:
            doc = db.games.find_one({"_id": ObjectId(normalized_id)}, {"_id": 1})
        except:
            pass
    
    if not doc:
        logger.warning(f"⚠️ [VALIDATE] game_id '{game_id}' (normalized: '{normalized_id}') does not point to existing document")
        raise HTTPException(
            status_code=404,
            detail=f"Game document not found for game_id: {game_id}. Please ensure the game exists or create a new game."
        )
    
    return True


def validate_franchise_id(franchise_id: str) -> bool:
    """
    Validate that franchise_id points to an existing franchise document.
    
    Args:
        franchise_id: Franchise ID to validate
    
    Returns:
        True if document exists, False otherwise
    
    Raises:
        HTTPException: If franchise_id is invalid format or document not found
    """
    if not franchise_id:
        raise HTTPException(status_code=400, detail="franchise_id is required")
    
    try:
        doc = db.franchises.find_one({"_id": ObjectId(franchise_id)}, {"_id": 1})
    except Exception as e:
        logger.warning(f"⚠️ [VALIDATE] Invalid franchise_id format '{franchise_id}': {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid franchise_id format: {franchise_id}"
        )
    
    if not doc:
        logger.warning(f"⚠️ [VALIDATE] franchise_id '{franchise_id}' does not point to existing document")
        raise HTTPException(
            status_code=404,
            detail=f"Franchise document not found for franchise_id: {franchise_id}. Please ensure the franchise exists."
        )
    
    return True


def validate_tournament_id(tournament_id: str) -> bool:
    """
    Validate that tournament_id points to an existing tournament document.
    
    Args:
        tournament_id: Tournament ID to validate
    
    Returns:
        True if document exists, False otherwise
    
    Raises:
        HTTPException: If tournament_id is invalid format or document not found
    """
    if not tournament_id:
        raise HTTPException(status_code=400, detail="tournament_id is required")
    
    try:
        doc = db.tournaments.find_one({"_id": ObjectId(tournament_id)}, {"_id": 1})
    except Exception as e:
        logger.warning(f"⚠️ [VALIDATE] Invalid tournament_id format '{tournament_id}': {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tournament_id format: {tournament_id}"
        )
    
    if not doc:
        logger.warning(f"⚠️ [VALIDATE] tournament_id '{tournament_id}' does not point to existing document")
        raise HTTPException(
            status_code=404,
            detail=f"Tournament document not found for tournament_id: {tournament_id}. Please ensure the tournament exists."
        )
    
    return True


def validate_pointer(pointer_type: str, pointer_value: str) -> bool:
    """
    Generic pointer validation function.
    
    Args:
        pointer_type: Type of pointer ('game_id', 'franchise_id', 'tournament_id')
        pointer_value: Value of the pointer
    
    Returns:
        True if document exists, False otherwise
    
    Raises:
        HTTPException: If pointer is invalid or document not found
    """
    if pointer_type == 'game_id':
        return validate_game_id(pointer_value)
    elif pointer_type == 'franchise_id':
        return validate_franchise_id(pointer_value)
    elif pointer_type == 'tournament_id':
        return validate_tournament_id(pointer_value)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown pointer type: {pointer_type}. Valid types: game_id, franchise_id, tournament_id"
        )

