"""Shot-clock enforcement policy for the late-game window.

At or below 30 seconds, a reset shot clock is capped to the game clock and no
longer creates a separate expiration. A shorter clock carried by the same
possession remains shorter and enforceable.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from BackEnd.utils.eoq_clock_progression import LATE_CLOCK_THRESHOLD


def is_shot_clock_enforced(game_state: Optional[Dict[str, Any]]) -> bool:
    """True when the shot clock can expire before the period clock."""
    if not isinstance(game_state, dict):
        return True
    game_remaining = max(0, int(game_state.get("time_remaining") or 0))
    if game_remaining <= 0:
        return False
    if game_remaining > LATE_CLOCK_THRESHOLD:
        return True

    raw_shot_remaining = game_state.get("shot_clock_remaining")
    if raw_shot_remaining is None:
        return False
    shot_remaining = max(0, int(raw_shot_remaining))
    return shot_remaining < game_remaining


def can_commit_shot_clock_violation(game_state: Optional[Dict[str, Any]]) -> bool:
    """True when a shot-clock violation turnover is legal."""
    return is_shot_clock_enforced(game_state)


def sync_late_game_shot_clock(game_state: Optional[Dict[str, Any]]) -> None:
    """Cap the late-game shot clock without increasing a carried clock."""
    if not isinstance(game_state, dict):
        return
    tr = max(0, int(game_state.get("time_remaining") or 0))
    if tr > LATE_CLOCK_THRESHOLD:
        return
    raw_shot_remaining = game_state.get("shot_clock_remaining")
    if raw_shot_remaining is None:
        game_state["shot_clock_remaining"] = tr
        return
    game_state["shot_clock_remaining"] = min(
        max(0, int(raw_shot_remaining)),
        tr,
    )
