"""Universal community highlights feed (Mode Select)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from BackEnd.utils.auth import get_current_user
from BackEnd.utils.community_highlights import list_community_highlight_entries

router = APIRouter(prefix="/api/community", tags=["community"])


@router.get("/highlights")
def get_community_highlights(_user: dict = Depends(get_current_user)):
    return {"entries": list_community_highlight_entries()}
