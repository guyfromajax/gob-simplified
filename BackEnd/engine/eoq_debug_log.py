"""
Structured step tracing for Final Shot and FLSS (EOQ perfection debugging).

All messages use the prefix [EOQ-TRACE] for easy filtering in server logs.
On by default. Disable with game_state['eoq_trace'] = False (e.g. bulk sims).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from BackEnd.utils.shared import get_name_safe, get_player_position

logger = logging.getLogger(__name__)

_TRACE_PREFIX = "[EOQ-TRACE]"


def is_eoq_trace_enabled(game) -> bool:
    gs = getattr(game, "game_state", None) or {}
    return gs.get("eoq_trace") is not False


def snapshot_time(game) -> Dict[str, Any]:
    gs = getattr(game, "game_state", None) or {}
    return {
        "quarter": getattr(game, "quarter", None),
        "time_remaining": gs.get("time_remaining"),
        "shot_clock_remaining": gs.get("shot_clock_remaining"),
        "offensive_state": gs.get("offensive_state"),
        "final_shot_possession_active": gs.get("final_shot_possession_active"),
        "final_turn_shot_this_turn": gs.get("final_turn_shot_this_turn"),
    }


def _coords_for_player(player) -> Optional[Dict[str, float]]:
    if player is None:
        return None
    raw = getattr(player, "coords", None) or {}
    if not isinstance(raw, dict):
        return None
    try:
        return {"x": round(float(raw.get("x", 0)), 2), "y": round(float(raw.get("y", 0)), 2)}
    except (TypeError, ValueError):
        return None


def snapshot_all_players(game) -> Dict[str, Any]:
    """Live model coords for both lineups keyed by pos."""
    out: Dict[str, Any] = {"offense": {}, "defense": {}}
    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    if off_team and getattr(off_team, "lineup", None):
        for pos, player in off_team.lineup.items():
            if not player:
                continue
            out["offense"][pos] = {
                "player_id": getattr(player, "player_id", None),
                "name": get_name_safe(player),
                "coords": _coords_for_player(player),
            }
    if def_team and getattr(def_team, "lineup", None):
        for pos, player in def_team.lineup.items():
            if not player:
                continue
            out["defense"][pos] = {
                "player_id": getattr(player, "player_id", None),
                "name": get_name_safe(player),
                "coords": _coords_for_player(player),
            }
    return out


def snapshot_shooter(
    game,
    player,
    *,
    pos: Optional[str] = None,
    label: str = "shooter",
) -> Optional[Dict[str, Any]]:
    if player is None:
        return None
    if pos is None:
        lineup = getattr(game.offense_team, "lineup", None) or {}
        pos = get_player_position(lineup, player)
    coords = _coords_for_player(player)
    return {
        "label": label,
        "pos": pos,
        "player_id": getattr(player, "player_id", None),
        "name": get_name_safe(player),
        "coords": coords,
    }


def log_eoq_step(
    game,
    flow: str,
    step: str,
    phase: str,
    *,
    shooter=None,
    shooter_pos: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log one trace step.

    flow: FINAL_SHOT | FLSS | ROUTING
    step: logical step name (e.g. turn_trigger, alignment_build, resolve_shot)
    phase: START | END
    """
    if not is_eoq_trace_enabled(game):
        return
    payload: Dict[str, Any] = {
        "flow": flow,
        "step": step,
        "phase": phase,
        "clock": snapshot_time(game),
        "players": snapshot_all_players(game),
    }
    if shooter is not None or shooter_pos is not None:
        payload["shooter"] = snapshot_shooter(game, shooter, pos=shooter_pos)
    if extra:
        payload["extra"] = extra
    try:
        body = json.dumps(payload, default=str)
    except TypeError:
        body = str(payload)
    logger.info("%s %s", _TRACE_PREFIX, body)


def log_eoq_routing_decision(
    game,
    *,
    branch: str,
    game_clock_remaining,
    would_final_shot: bool,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    if not is_eoq_trace_enabled(game):
        return
    log_eoq_step(
        game,
        "ROUTING",
        branch,
        "DECISION",
        extra={
            "game_clock_remaining": game_clock_remaining,
            "would_take_final_shot": would_final_shot,
            **(extra or {}),
        },
    )
