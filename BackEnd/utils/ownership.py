"""
Ownership verification for user-specific resources.

Verifies that franchise, tournament, and game documents belong to the current user.
Used to prevent cross-user data access (IDOR).

Usage:
    from BackEnd.utils.ownership import (
        verify_franchise_owned_by_user,
        verify_tournament_owned_by_user,
        verify_game_owned_by_user,
    )

    franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
    tournament_doc = verify_tournament_owned_by_user(tournament_id, user["user_id"])
    game_doc = verify_game_owned_by_user(game_id, user["user_id"])
"""

from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status

from BackEnd.db import (
    franchises_collection,
    tournaments_collection,
    games_collection,
)


def verify_franchise_owned_by_user(franchise_id: str, user_id: str) -> dict:
    """
    Verify the franchise exists and belongs to the user.
    Returns the franchise document if owned; raises 403 or 404 otherwise.

    Documents without user_id (pre-migration) are denied - run migration to add user_id.
    """
    try:
        oid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise_id")
    doc = franchises_collection.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    doc_user_id = doc.get("user_id")
    if doc_user_id is None:
        raise HTTPException(status_code=403, detail="Access denied to this franchise")
    if str(doc_user_id) != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied to this franchise")
    return doc


def verify_tournament_owned_by_user(tournament_id: str, user_id: str) -> dict:
    """
    Verify the tournament exists and belongs to the user.
    Returns the tournament document if owned; raises 403 or 404 otherwise.

    Documents without user_id (pre-migration) are denied - run migration to add user_id.
    """
    try:
        oid = ObjectId(tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament_id")
    doc = tournaments_collection.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Tournament not found")
    doc_user_id = doc.get("user_id")
    if doc_user_id is None:
        raise HTTPException(status_code=403, detail="Access denied to this tournament")
    if str(doc_user_id) != str(user_id):
        raise HTTPException(status_code=403, detail="Access denied to this tournament")
    return doc


def verify_game_owned_by_user(game_id: str, user_id: str) -> dict:
    """
    Verify the game exists and belongs to the user (via franchise or tournament).
    Returns the game document if owned; raises 403 or 404 otherwise.

    Ownership is inferred from:
    - franchise_id -> verify franchise belongs to user
    - tournament_id -> verify tournament belongs to user
    - single game mode -> no parent; for now we allow if no franchise/tournament
    """
    # Try ObjectId first, then string (games may use composite keys)
    doc = None
    try:
        oid = ObjectId(game_id)
        doc = games_collection.find_one({"_id": oid})
    except Exception:
        pass
    if not doc:
        doc = games_collection.find_one({"_id": game_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Game not found")
    franchise_id = doc.get("franchise_id")
    tournament_id = doc.get("tournament_id")
    if franchise_id:
        verify_franchise_owned_by_user(str(franchise_id), user_id)
    elif tournament_id:
        verify_tournament_owned_by_user(str(tournament_id), user_id)
    # Single-game mode: no parent, allow (or could restrict to user_id on game if added later)
    return doc


def get_franchise_for_user(franchise_id: str, user_id: str) -> Optional[dict]:
    """
    Get franchise doc if owned by user; return None if not found.
    Use when you need to check ownership without raising.
    """
    try:
        return verify_franchise_owned_by_user(franchise_id, user_id)
    except HTTPException:
        return None


def get_tournament_for_user(tournament_id: str, user_id: str) -> Optional[dict]:
    """
    Get tournament doc if owned by user; return None if not found.
    Use when you need to check ownership without raising.
    """
    try:
        return verify_tournament_owned_by_user(tournament_id, user_id)
    except HTTPException:
        return None
