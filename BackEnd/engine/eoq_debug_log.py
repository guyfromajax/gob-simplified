"""
Structured tracing for Final Shot / FLSS EOQ chains.

Filter server logs with: [EOQ-TRACE]

On by default. Disable with game_state['eoq_trace'] = False (e.g. bulk sims).

Once a Final Shot sequence starts, all related turns in the chain share
``eoq_trace_seq`` (also stamped on turn payloads for frontend correlation):

  FINAL_SHOT → optional BIP/SIP → FLSS → optional BIP → … until quarter end
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from BackEnd.utils.shared import get_name_safe, get_player_position

logger = logging.getLogger(__name__)

_TRACE_PREFIX = "[EOQ-TRACE]"


def is_eoq_trace_enabled(game) -> bool:
    gs = getattr(game, "game_state", None) or {}
    return gs.get("eoq_trace") is not False


def is_eoq_turn(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("eoq_trace_role"):
        return True
    return bool(
        result.get("final_turn")
        or result.get("flss")
        or result.get("final_shot_possession")
        or result.get("late_clock_eoq")
        or result.get("terminal_dreb_eoq")
        or result.get("result_type") in ("BASELINE_INBOUND", "SIDE_INBOUND")
        and (
            result.get("late_clock_eoq")
            or (result.get("eoq_trace_seq"))
        )
    )


def clear_eoq_trace_sequence(game) -> None:
    gs = getattr(game, "game_state", None)
    if not isinstance(gs, dict):
        return
    gs.pop("eoq_trace_seq", None)
    gs.pop("eoq_trace_turn_in_seq", None)


def begin_eoq_trace_sequence(game) -> str:
    """Start or continue an EOQ trace sequence; returns sequence id."""
    if not is_eoq_trace_enabled(game):
        return ""
    gs = getattr(game, "game_state", None) or {}
    seq = gs.get("eoq_trace_seq")
    if not seq:
        seq = uuid.uuid4().hex[:10]
        gs["eoq_trace_seq"] = seq
        gs["eoq_trace_turn_in_seq"] = 0
    return str(seq)


def bump_eoq_trace_turn(game) -> int:
    gs = getattr(game, "game_state", None) or {}
    n = int(gs.get("eoq_trace_turn_in_seq") or 0) + 1
    gs["eoq_trace_turn_in_seq"] = n
    return n


def stamp_eoq_trace_on_turn(game, result: Dict[str, Any], role: str) -> None:
    if not isinstance(result, dict) or not is_eoq_trace_enabled(game):
        return
    if result.get("eoq_trace_seq"):
        if role and not result.get("eoq_trace_role"):
            result["eoq_trace_role"] = role
        return
    seq = begin_eoq_trace_sequence(game)
    if not seq:
        return
    turn_in_seq = bump_eoq_trace_turn(game)
    result["eoq_trace_seq"] = seq
    result["eoq_trace_turn_in_seq"] = turn_in_seq
    result["eoq_trace_role"] = role


def snapshot_time(game) -> Dict[str, Any]:
    gs = getattr(game, "game_state", None) or {}
    return {
        "quarter": getattr(game, "quarter", None),
        "time_remaining": gs.get("time_remaining"),
        "shot_clock_remaining": gs.get("shot_clock_remaining"),
        "clock_display": gs.get("clock"),
        "offensive_state": gs.get("offensive_state"),
        "final_shot_possession_active": gs.get("final_shot_possession_active"),
        "final_turn_shot_this_turn": gs.get("final_turn_shot_this_turn"),
    }


def snapshot_chain_state(game) -> Dict[str, Any]:
    gs = getattr(game, "game_state", None) or {}
    return {
        "eoq_trace_seq": gs.get("eoq_trace_seq"),
        "eoq_trace_turn_in_seq": gs.get("eoq_trace_turn_in_seq"),
        "late_clock_eoq_chain_active": gs.get("late_clock_eoq_chain_active"),
        "flss_possession_pending": gs.get("flss_possession_pending"),
        "final_shot_possession_active": gs.get("final_shot_possession_active"),
        "final_turn_shot_this_turn": gs.get("final_turn_shot_this_turn"),
        "free_throws_remaining": gs.get("free_throws_remaining"),
        "pending_oreb": bool(gs.get("pending_oreb")),
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
    return {
        "label": label,
        "pos": pos,
        "player_id": getattr(player, "player_id", None),
        "name": get_name_safe(player),
        "coords": _coords_for_player(player),
    }


def _clock_from_schema_block(block: Any) -> Dict[str, Any]:
    if not isinstance(block, dict):
        return {}
    clock = block.get("clock") if isinstance(block.get("clock"), dict) else {}
    return {
        "clock_remaining": clock.get("clock_remaining"),
        "shot_clock_remaining": clock.get("shot_clock_remaining"),
    }


def summarize_animation_step(step: Any, index: int) -> Dict[str, Any]:
    if not isinstance(step, dict):
        return {"index": index, "error": "not_a_dict"}
    start = step.get("start") if isinstance(step.get("start"), dict) else {}
    end = step.get("end") if isinstance(step.get("end"), dict) else {}
    actions = start.get("action") if isinstance(start.get("action"), dict) else {}
    action_summary = {
        pid: act for pid, act in list(actions.items())[:8]
    }
    return {
        "index": index,
        "id": step.get("id"),
        "start_clock": _clock_from_schema_block(start),
        "end_clock": _clock_from_schema_block(end),
        "duration_ms": step.get("duration_ms") or end.get("time_elapsed"),
        "actions": action_summary,
        "next_step_index": step.get("next_step_index"),
        "branch": step.get("branch"),
        "metadata": step.get("metadata") if isinstance(step.get("metadata"), dict) else None,
    }


def summarize_animation_steps(steps: Any) -> List[Dict[str, Any]]:
    if not isinstance(steps, list):
        return []
    return [summarize_animation_step(step, i) for i, step in enumerate(steps)]


def summarize_turn_result(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "eoq_trace_seq": result.get("eoq_trace_seq"),
        "eoq_trace_turn_in_seq": result.get("eoq_trace_turn_in_seq"),
        "eoq_trace_role": result.get("eoq_trace_role"),
        "result_type": result.get("result_type"),
        "current_turn": result.get("current_turn"),
        "text": (result.get("text") or "")[:120],
        "time_elapsed": result.get("time_elapsed"),
        "clock_start": result.get("clock_start"),
        "clock_end": result.get("clock_end"),
        "shot_clock_start": result.get("shot_clock_start"),
        "shot_clock_end": result.get("shot_clock_end"),
        "real_time_elapsed_ms": result.get("real_time_elapsed_ms"),
        "next_play_type": result.get("next_play_type"),
        "next_turn": result.get("next_turn"),
        "quarter_ends_after": result.get("quarter_ends_after"),
        "late_clock_eoq": result.get("late_clock_eoq"),
        "terminal_dreb_eoq": result.get("terminal_dreb_eoq"),
        "flss": result.get("flss"),
        "flss_zone": result.get("flss_zone"),
        "final_turn": result.get("final_turn"),
        "final_shot_possession": result.get("final_shot_possession"),
        "forced_shot_reason": result.get("forced_shot_reason"),
        "final_turn_anchor_clock": result.get("final_turn_anchor_clock"),
        "shooter_id": result.get("shooter_id"),
        "possession_flips": result.get("possession_flips"),
        "animation_step_count": len(result.get("animation_steps") or []),
        "clock_contract_source": result.get("clock_contract_source"),
    }


def _emit_trace(event: str, payload: Dict[str, Any]) -> None:
    try:
        body = json.dumps(payload, default=str)
    except TypeError:
        body = str(payload)
    logger.warning("%s %s %s", _TRACE_PREFIX, event, body)


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
    if not is_eoq_trace_enabled(game):
        return
    payload: Dict[str, Any] = {
        "event": "STEP",
        "flow": flow,
        "step": step,
        "phase": phase,
        "chain": snapshot_chain_state(game),
        "clock": snapshot_time(game),
        "players": snapshot_all_players(game),
    }
    if shooter is not None or shooter_pos is not None:
        payload["shooter"] = snapshot_shooter(game, shooter, pos=shooter_pos)
    if extra:
        payload["extra"] = extra
    _emit_trace("STEP", payload)


def log_eoq_chain_event(
    game,
    event: str,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    if not is_eoq_trace_enabled(game):
        return
    payload: Dict[str, Any] = {
        "event": "CHAIN",
        "chain_event": event,
        "chain": snapshot_chain_state(game),
        "clock": snapshot_time(game),
    }
    if extra:
        payload["extra"] = extra
    _emit_trace("CHAIN", payload)


def log_eoq_turn(
    game,
    role: str,
    result: Dict[str, Any],
    *,
    phase: str,
    turn_num: Optional[int] = None,
    game_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Full turn bundle: flags, clock contract, animation step summaries.

    role: FINAL_SHOT | FLSS | BIP | SIP | DREB_TERMINAL | OREB | FREE_THROW
    phase: PRE_EMIT | POST_EMIT | POST_CLOCK | API_RESPONSE
    """
    if not is_eoq_trace_enabled(game):
        return
    if phase in ("PRE_EMIT", "POST_EMIT", "POST_CLOCK"):
        stamp_eoq_trace_on_turn(game, result, role)
    steps = result.get("animation_steps") or []
    payload: Dict[str, Any] = {
        "event": "TURN",
        "phase": phase,
        "role": role,
        "turn_num": turn_num,
        "game_id": game_id or getattr(game, "game_id", None),
        "chain": snapshot_chain_state(game),
        "clock": snapshot_time(game),
        "turn": summarize_turn_result(result),
        "animation_steps": summarize_animation_steps(steps),
        "players": snapshot_all_players(game),
    }
    if extra:
        payload["extra"] = extra
    _emit_trace("TURN", payload)


def log_eoq_api_response(
    game,
    *,
    game_id: Optional[str],
    turn_num: Optional[int],
    turns_in_response: List[Dict[str, Any]],
    response_meta: Dict[str, Any],
) -> None:
    if not is_eoq_trace_enabled(game):
        return
    eoq_turns = []
    for i, t in enumerate(turns_in_response or []):
        if not isinstance(t, dict):
            continue
        if not (
            t.get("final_turn")
            or t.get("flss")
            or t.get("late_clock_eoq")
            or t.get("final_shot_possession")
            or t.get("eoq_trace_role")
            or t.get("terminal_dreb_eoq")
            or (
                t.get("result_type") in ("BASELINE_INBOUND", "SIDE_INBOUND")
                and t.get("eoq_trace_seq")
            )
        ):
            continue
        eoq_turns.append(
            {
                "batch_index": i,
                "turn": summarize_turn_result(t),
                "animation_steps": summarize_animation_steps(t.get("animation_steps") or []),
            }
        )
    if not eoq_turns and not snapshot_chain_state(game).get("eoq_trace_seq"):
        return
    payload = {
        "event": "API",
        "game_id": game_id,
        "turn_num": turn_num,
        "chain": snapshot_chain_state(game),
        "clock": snapshot_time(game),
        "response_meta": response_meta,
        "eoq_turns_in_response": eoq_turns,
    }
    _emit_trace("API", payload)


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
