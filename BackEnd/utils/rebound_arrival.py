"""Where a crasher actually gets to before the ball is rebounded.

A crash destination says where a player *aimed*. This says where he *got*: he travels
along the line from his shot-moment position toward that destination at his own
movement rate, for as long as the ball is live, and stops wherever that leaves him. A
player who guessed the right area and has the legs to get there arrives; one who
guessed wrong, or is slow, stops short and is scored from there.

WHY THIS MAY READ THE OUTCOME, WHEN ``crash_destination`` MAY NOT.
    ``crash_destination`` is forbidden from seeing the bounce because a crasher who
    knows where the ball will land is clairvoyant - he would aim at a spot nobody could
    know. That guard is about **where he aims**.

    This module is about **how far along that line he gets**, and the time available is
    legitimately outcome-dependent: a ball that rattles on the rim really does give
    crashers longer than one that drops straight through. ``sim_post_shot_window_seconds``
    carries exactly that - flight, rattle hops, the bounce step. Using it moves players
    further along a line they had already chosen; it never changes the line. So the
    clairvoyance guard does not apply here, and deliberately is not applied.

    Selection is the same case: ``select_rebounder_by_score`` is the *resolution* of the
    rebound and must know where the ball is. That is not clairvoyance either.

``GOB_REBOUND_FROM_ARRIVAL`` gates the whole thing, default OFF.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, Optional

#: Movement archetype rebounders travel under. They are running to a spot, not
#: sprinting a fast break, so the standard rate applies.
REBOUND_TRAVEL_ARCHETYPE = "standard"

#: Used when the post-shot window cannot be derived at the authoring point. See
#: ``reports/rebound-arrival-2026-09-19.md`` - the window needs ``uses_shot_arc``,
#: which is not set until after selection.
FALLBACK_WINDOW_SECONDS = 1.8


def enabled() -> bool:
    """``GOB_REBOUND_FROM_ARRIVAL`` - default OFF."""
    return os.environ.get("GOB_REBOUND_FROM_ARRIVAL", "0") == "1"


def race_enabled() -> bool:
    """``GOB_REBOUND_RACE`` - default OFF, and only meaningful with the arrival flag on.

    Scores the distance term on TIME to the ball rather than distance to it: two
    players equidistant from the bounce are not equally likely to get there, and this
    is the quantity that separates them. Selection may read the bounce - it is the
    resolution of the rebound. ``crash_destination`` still may not, and its guard is
    untouched.
    """
    return (os.environ.get("GOB_REBOUND_RACE", "0") == "1") and enabled()


def travel_rate(player: Any) -> float:
    """Grid units per game-second for this player, at the rebound archetype."""
    from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec

    try:
        return float(_ag_grid_per_game_sec(player, archetype=REBOUND_TRAVEL_ARCHETYPE))
    except Exception:  # noqa: BLE001
        # Same shape as the helper's own default for a missing AG.
        return float(_ag_grid_per_game_sec(None, archetype=REBOUND_TRAVEL_ARCHETYPE))


def arrival_point(start: Dict[str, float], dest: Dict[str, float], player: Any,
                  seconds: float) -> Dict[str, float]:
    """How far along ``start -> dest`` this player gets in ``seconds``.

    Returns ``dest`` when he can cover the distance, otherwise the point he reaches.
    Never overshoots.
    """
    try:
        sx, sy = float(start["x"]), float(start["y"])
        dx, dy = float(dest["x"]), float(dest["y"])
    except (TypeError, KeyError, ValueError):
        return dict(dest) if isinstance(dest, dict) else dict(start)

    span = math.hypot(dx - sx, dy - sy)
    if span <= 1e-9:
        return {"x": dx, "y": dy}

    reach = max(0.0, float(seconds)) * travel_rate(player)
    if reach >= span:
        return {"x": dx, "y": dy}
    f = reach / span
    return {"x": sx + (dx - sx) * f, "y": sy + (dy - sy) * f}


def arrival_coords(crash_map: Dict[Any, Dict[str, float]],
                   players_by_id: Dict[Any, Any],
                   seconds: Optional[float]) -> Dict[str, Dict[str, float]]:
    """``{player_id: arrival coords}`` for every crasher with a destination.

    ``seconds`` None falls back to ``FALLBACK_WINDOW_SECONDS``.
    """
    secs = FALLBACK_WINDOW_SECONDS if seconds is None else float(seconds)
    out: Dict[str, Dict[str, float]] = {}
    for pid, dest in (crash_map or {}).items():
        player = (players_by_id or {}).get(pid)
        start = getattr(player, "coords", None)
        if not isinstance(start, dict) or start.get("x") is None:
            out[str(pid)] = dict(dest)
            continue
        out[str(pid)] = arrival_point(start, dest, player, secs)
    return out


def travel_fraction(start: Dict[str, float], dest: Dict[str, float], player: Any,
                    seconds: float) -> float:
    """Share of the way to his destination this player covers. 1.0 = arrived."""
    try:
        span = math.hypot(float(dest["x"]) - float(start["x"]),
                          float(dest["y"]) - float(start["y"]))
    except (TypeError, KeyError, ValueError):
        return 1.0
    if span <= 1e-9:
        return 1.0
    return min(1.0, (max(0.0, float(seconds)) * travel_rate(player)) / span)
