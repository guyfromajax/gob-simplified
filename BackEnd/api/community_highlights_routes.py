"""Universal community highlights feed (Mode Select)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from BackEnd.utils.auth import get_current_user
from BackEnd.utils.around_the_league import list_around_the_league_entries
from BackEnd.utils.community_highlights import (
    list_community_highlight_entries,
    push_debut_entry,
)

router = APIRouter(prefix="/api/community", tags=["community"])


@router.get("/highlights")
def get_community_highlights(_user: dict = Depends(get_current_user)):
    return {"entries": list_community_highlight_entries()}


@router.get("/around-the-league")
def get_around_the_league(_user: dict = Depends(get_current_user)):
    return {"slots": list_around_the_league_entries()}


class DebutEntryRequest(BaseModel):
    """Body for the tutorial-game debut publish."""
    user_team_name: str
    opponent_name: str
    user_won: bool
    user_score: int
    opponent_score: int


@router.post("/debut")
def post_debut_entry(body: DebutEntryRequest, user: dict = Depends(get_current_user)):
    """Publish a tutorial-game debut row to the community highlights feed.

    Called by the tutorial post-game modal after the user finishes their first
    game. Display username + team colors are resolved server-side; the client
    only needs to supply the matchup + score.
    """
    push_debut_entry(
        owner_user_id=user["user_id"],
        user_team_name=body.user_team_name,
        opponent_name=body.opponent_name,
        user_won=body.user_won,
        user_score=body.user_score,
        opponent_score=body.opponent_score,
    )
    return {"ok": True}
