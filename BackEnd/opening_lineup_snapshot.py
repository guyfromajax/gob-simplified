"""
Immutable Q1 opening-five snapshot for PGPC and related features.

See _documentation_master/03_Data_Persistence/Data_Persistence_System.md ("Special Gameplay-Tracking Fields")
"""

from __future__ import annotations

import logging
from typing import Any

from BackEnd.constants import POSITION_LIST

_logger = logging.getLogger(__name__)


def snapshot_opening_lineups_to_game_state(game: Any) -> None:
    """
    Record each team's starting five (player_id strings keyed by team_id) once at the Q1 opening tip.

    Immutable for the rest of the game: if ``opening_lineup`` is already set (e.g. restored from DB),
    this is a no-op. OT opening tips (quarter != 1) do not snapshot.
    """
    gs = getattr(game, "game_state", None)
    if not isinstance(gs, dict):
        return
    if gs.get("opening_lineup"):
        return
    try:
        q = int(getattr(game, "quarter", 0) or 0)
    except (TypeError, ValueError):
        q = 0
    if q != 1:
        return

    def _five_ids(lineup_dict) -> list[str]:
        if not isinstance(lineup_dict, dict):
            return []
        out: list[str] = []
        for pos in POSITION_LIST:
            pl = lineup_dict.get(pos)
            if pl is None:
                return []
            pid = getattr(pl, "player_id", None)
            if pid is None:
                return []
            out.append(str(pid))
        return out

    home_ids = _five_ids(getattr(game.home_team, "lineup", None))
    away_ids = _five_ids(getattr(game.away_team, "lineup", None))
    if len(home_ids) != 5 or len(away_ids) != 5:
        _logger.warning(
            "opening_lineup snapshot skipped: need 5 starters per team (home=%s away=%s)",
            len(home_ids),
            len(away_ids),
        )
        return

    gs["opening_lineup"] = {
        str(game.home_team.team_id): list(home_ids),
        str(game.away_team.team_id): list(away_ids),
    }


__all__ = ["snapshot_opening_lineups_to_game_state"]
