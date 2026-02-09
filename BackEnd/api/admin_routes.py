"""
Admin API (Step 12.2).

All endpoints require role=admin (get_admin_user).
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from BackEnd.db import (
    db,
    tournaments_collection,
    franchises_collection,
    franchise_team_data_collection,
    franchise_players_data_collection,
    franchise_recruits_data_collection,
)
from BackEnd.utils.auth import get_admin_user

router = APIRouter(prefix="/api/admin", tags=["admin"])

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"


class ResetUserStateRequest(BaseModel):
    """Target user by ID (string, same as user_id in JWT)."""
    user_id: str


@router.post("/reset-user-state")
def reset_user_state(
    body: ResetUserStateRequest,
    admin: dict = Depends(get_admin_user),
):
    """
    Admin only. Deletes the target user's tournament and franchise(s) plus related data
    (FTD, FPD, FRD, and games for each franchise) so they can start fresh. Use to unstick broken state.
    """
    user_id = body.user_id.strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    # Delete tournaments for this user
    tr = tournaments_collection.delete_many({"user_id": user_id})
    tournaments_deleted = tr.deleted_count

    # Find and delete franchises and related data
    franchise_docs = list(franchises_collection.find({"user_id": user_id}, {"_id": 1}))
    franchises_deleted = 0
    for doc in franchise_docs:
        fid = doc["_id"]
        # FTD uses ObjectId; FPD/FRD use string franchise_id
        franchise_team_data_collection.delete_many({"franchise_id": fid})
        franchise_players_data_collection.delete_many({"franchise_id": str(fid)})
        franchise_recruits_data_collection.delete_many({"franchise_id": str(fid)})
        db.games.delete_many({"franchise_id": str(fid)})
        franchises_collection.delete_one({"_id": fid})
        franchises_deleted += 1

    return {
        "ok": True,
        "tournaments_deleted": tournaments_deleted,
        "franchises_deleted": franchises_deleted,
    }


