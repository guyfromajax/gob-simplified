"""Shot-clock enforcement policy (late-game universal off rule).

When the game clock is at or below the late-clock threshold (30s), the shot
clock is disabled for the rest of the quarter: it tracks the game clock and
shot-clock violations cannot occur.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from BackEnd.utils.eoq_clock_progression import LATE_CLOCK_THRESHOLD


def is_shot_clock_enforced(game_state: Optional[Dict[str, Any]]) -> bool:
    """True when the shot clock runs and violations are possible."""
    if not isinstance(game_state, dict):
        return True
    return int(game_state.get("time_remaining") or 0) > LATE_CLOCK_THRESHOLD


def can_commit_shot_clock_violation(game_state: Optional[Dict[str, Any]]) -> bool:
    """True when a shot-clock violation turnover is legal."""
    return is_shot_clock_enforced(game_state)


def sync_late_game_shot_clock(game_state: Optional[Dict[str, Any]]) -> None:
    """Pin shot clock to game clock when enforcement is off."""
    if not isinstance(game_state, dict):
        return
    if is_shot_clock_enforced(game_state):
        return
    tr = max(0, int(game_state.get("time_remaining") or 0))
    game_state["shot_clock_remaining"] = tr
