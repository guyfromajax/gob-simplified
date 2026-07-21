"""Fast Break StepState builder.

Additive bridge toward the Fast Break UESS target:

    resolve once -> freeze into StepState -> project to animation schema -> draw.

For this migration step, Fast Break emitters still build ``AnimationStep``
schema first. This module freezes those emitted facts into a shared
``FastBreakStepState`` shape and can project them back to schema without
behavior changes.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional


def build_fast_break_step_states(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Freeze emitted FB ``AnimationStep`` data into FastBreakStepState.

    This deliberately copies from rendered schema instead of recomputing. That
    keeps the bridge additive and lets parity tests compare projection against
    the exact frontend contract currently emitted by the FB helpers.
    """
    if not isinstance(result, dict):
        return []

    steps = result.get("animation_steps") or []
    if not isinstance(steps, list) or not steps:
        return []

    step_states: List[Dict[str, Any]] = []
    terminal_count = 0
    play_key = result.get("fast_break_play") or (result.get("roles") or {}).get(
        "fast_break_play"
    )

    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        state = _state_from_step(
            step,
            index=index,
            result=result,
            play_key=play_key,
        )
        if state["outcome"].get("kind") not in (None, "none"):
            terminal_count += 1
        step_states.append(state)

    result["fb_step_states"] = step_states
    logging.debug(
        "🔬 [FB STEPSTATE] stamped play=%s states=%d terminal=%d",
        play_key or "unknown",
        len(step_states),
        terminal_count,
    )
    return step_states


def project_fast_break_step_states_to_animation_steps(
    step_states: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Project FastBreakStepState values back into AnimationStep schema.

    During the additive bridge phase, ``schema_projection`` is a complete copy
    of the emitted step. Later migration slices can shrink that snapshot as
    formal StepState fields become the source for individual primitives.
    """
    projected: List[Dict[str, Any]] = []
    for state in step_states or []:
        if not isinstance(state, dict):
            continue
        if state.get("projection_source") == "formal":
            step = _project_from_formal_state(state)
        else:
            step = copy.deepcopy(state.get("schema_projection") or {})
            if not step:
                step = _project_from_formal_state(state)
        step["_fb_step_state"] = state
        projected.append(step)
    return projected


def project_animation_step_through_fast_break_state(
    step: Dict[str, Any],
    *,
    index: int,
    result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Freeze one emitted FB step and immediately project it through StepState."""
    if not isinstance(step, dict):
        return step
    result = result or {}
    state = _state_from_step(
        step,
        index=index,
        result=result,
        play_key=result.get("fast_break_play") or (result.get("roles") or {}).get(
            "fast_break_play"
        ),
    )
    projected = project_fast_break_step_states_to_animation_steps([state])
    return projected[0] if projected else step


def _state_from_step(
    step: Dict[str, Any],
    *,
    index: int,
    result: Dict[str, Any],
    play_key: Optional[str],
) -> Dict[str, Any]:
    start = step.get("start") or {}
    end = step.get("end") or {}
    state = {
        "index": index,
        "turn_type": "FAST_BREAK",
        "play_key": play_key,
        "players": _players_state(start, end),
        "ball": _ball_state(start, end),
        "timing": _timing_state(start, end),
        "advance_gate": _advance_gate_state(start),
        "outcome": _outcome_state(end, result),
        "next": _next_state(end),
        "cosmetics": _cosmetics_state(start, end),
        "render": _render_state(start),
        "projection_source": _projection_source(start),
        "schema_projection": _schema_projection(step),
    }
    step["_fb_step_state"] = state
    return state


def _players_state(start: Dict[str, Any], end: Dict[str, Any]) -> Dict[str, Any]:
    start_coords = start.get("coords") or {}
    end_coords = end.get("coords") or {}
    destinations = start.get("destination") or {}
    actions = start.get("action") or {}
    archetypes = start.get("archetype") or {}
    player_ids = sorted(
        {
            str(pid)
            for pid in (
                set(start_coords.keys())
                | set(end_coords.keys())
                | set(destinations.keys())
                | set(actions.keys())
                | set(archetypes.keys())
            )
            if pid is not None
        }
    )
    return {
        pid: {
            "start_coord": _coord(start_coords.get(pid)),
            "target_dest": _coord(destinations.get(pid)),
            "end_coord": _coord(end_coords.get(pid)),
            "action": actions.get(pid),
            "archetype": archetypes.get(pid),
        }
        for pid in player_ids
    }


def _ball_state(start: Dict[str, Any], end: Dict[str, Any]) -> Dict[str, Any]:
    start_ball = start.get("ball") or {}
    end_ball = end.get("ball") or {}
    trigger = start.get("advance_trigger") or {}
    metadata = trigger.get("metadata") or {}

    from_owner = (
        start_ball.get("from_player_id")
        or start_ball.get("owner_player_id")
    )
    to_owner = (
        start_ball.get("to_player_id")
        or end_ball.get("owner_player_id")
        or start_ball.get("owner_player_id")
    )
    from_coord = (
        _coord(start_ball.get("current_coords"))
        or _coord(start_ball.get("coords"))
        or _coord((start.get("coords") or {}).get(str(from_owner)) if from_owner else None)
    )
    arrival_coord = (
        _coord(start.get("ball_arrival_coord"))
        or _coord(metadata.get("target_coords"))
        or _coord(end_ball.get("coords"))
        or _coord((end.get("coords") or {}).get(str(to_owner)) if to_owner else None)
    )
    motion_style = start.get("ball_motion_style")
    motion_style_explicit = motion_style is not None
    if not motion_style and (
        start_ball.get("from_player_id")
        or start_ball.get("to_player_id")
        or trigger.get("condition") == "ball_reaches_player"
    ):
        motion_style = "pass"

    return {
        "from_owner": str(from_owner) if from_owner is not None else None,
        "to_owner": str(to_owner) if to_owner is not None else None,
        "from_coord": from_coord,
        "arrival_coord": arrival_coord,
        "arrival_coord_explicit": start.get("ball_arrival_coord") is not None,
        "motion_style": motion_style or "held",
        "motion_style_explicit": motion_style_explicit,
        "resolved_by": (
            str(end_ball.get("owner_player_id"))
            if end_ball.get("owner_player_id") is not None
            else None
        ),
        "end_coord": _coord(end_ball.get("coords")),
    }


def _timing_state(start: Dict[str, Any], end: Dict[str, Any]) -> Dict[str, Any]:
    start_clock = start.get("clock") or {}
    end_clock = end.get("clock") or {}
    return {
        "step_t": _num(end.get("time_elapsed")),
        "game_clock_start": _num(start_clock.get("clock_remaining")),
        "game_clock_end": _num(end_clock.get("clock_remaining")),
        "shot_clock_start": _num(start_clock.get("shot_clock_remaining")),
        "shot_clock_end": _num(end_clock.get("shot_clock_remaining")),
    }


def _advance_gate_state(start: Dict[str, Any]) -> Dict[str, Any]:
    trigger = copy.deepcopy(start.get("advance_trigger") or {})
    metadata = trigger.get("metadata") or {}
    return {
        "condition": trigger.get("condition"),
        "step_t": _num(trigger.get("T_game_seconds")),
        "target_player": metadata.get("target_player_id") or metadata.get("to_player_id"),
        "target_coord": _coord(metadata.get("target_coords")),
        "metadata": metadata,
    }


def _outcome_state(end: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    next_state = end.get("next") or {}
    if next_state.get("kind") == "turn_stop":
        event = next_state.get("event")
        return {
            "kind": _event_to_kind(event),
            "event": event,
            "payload": copy.deepcopy(next_state.get("payload") or {}),
        }
    return {
        "kind": "none",
        "event": None,
        "payload": {"result_type": result.get("result_type")},
    }


def _next_state(end: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy((end or {}).get("next") or {})


def _cosmetics_state(start: Dict[str, Any], end: Dict[str, Any]) -> Dict[str, Any]:
    sfx = []
    for key in (
        "sfx_on_ball_release",
        "sfx_on_ball_arrival",
        "sfx_on_step_start",
        "timed_sfx",
    ):
        if start.get(key):
            sfx.append({"trigger": key, "payload": copy.deepcopy(start.get(key))})
    announcement = (
        copy.deepcopy(start.get("announcement") or {})
        or copy.deepcopy(end.get("announcement") or {})
        or None
    )
    flourishes = copy.deepcopy(
        start.get("flourish")
        or start.get("flourish_triggers")
        or end.get("flourish_triggers")
        or {}
    )
    return {
        "flourish_triggers": flourishes,
        "sfx_triggers": sfx,
        "announcement_triggers": [announcement] if announcement else [],
    }


def _render_state(start: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tween_durations": copy.deepcopy(start.get("tween_durations") or {}),
    }


def _schema_projection(step: Dict[str, Any]) -> Dict[str, Any]:
    """Copy emitted schema without StepState stamp to avoid recursion."""
    return {
        key: copy.deepcopy(value)
        for key, value in (step or {}).items()
        if key != "_fb_step_state"
    }


def _projection_source(start: Dict[str, Any]) -> str:
    # Initial bridge is schema-projection first. Formal projection can be opened
    # one primitive at a time after parity coverage is in place.
    return "schema_projection"


def _project_from_formal_state(state: Dict[str, Any]) -> Dict[str, Any]:
    players = state.get("players") or {}
    ball = state.get("ball") or {}
    timing = state.get("timing") or {}
    gate = state.get("advance_gate") or {}
    next_state = state.get("next") or {}

    start = {
        "coords": {
            pid: copy.deepcopy(data.get("start_coord"))
            for pid, data in players.items()
            if data.get("start_coord") is not None
        },
        "destination": {
            pid: copy.deepcopy(data.get("target_dest"))
            for pid, data in players.items()
        },
        "action": {pid: data.get("action") for pid, data in players.items()},
        "archetype": {pid: data.get("archetype") for pid, data in players.items()},
        "clock": {
            "clock_remaining": timing.get("game_clock_start"),
            "shot_clock_remaining": timing.get("shot_clock_start"),
        },
        "advance_trigger": {
            "condition": gate.get("condition"),
            "T_game_seconds": gate.get("step_t"),
            "metadata": copy.deepcopy(gate.get("metadata") or {}),
        },
    }
    if ball.get("from_owner"):
        start["ball"] = {"owner_player_id": ball.get("from_owner")}
    else:
        start["ball"] = {"coords": copy.deepcopy(ball.get("from_coord"))}

    end = {
        "coords": {
            pid: copy.deepcopy(data.get("end_coord"))
            for pid, data in players.items()
            if data.get("end_coord") is not None
        },
        "ball": (
            {"owner_player_id": ball.get("resolved_by")}
            if ball.get("resolved_by")
            else {"coords": copy.deepcopy(ball.get("end_coord"))}
        ),
        "time_elapsed": timing.get("step_t"),
        "clock": {
            "clock_remaining": timing.get("game_clock_end"),
            "shot_clock_remaining": timing.get("shot_clock_end"),
        },
        "next": copy.deepcopy(next_state)
        or {"kind": "next_step", "index": int(state.get("index") or 0) + 1},
    }
    return {"start": start, "end": end}


def _event_to_kind(event: Optional[str]) -> str:
    normalized = (event or "").upper()
    if normalized == "STEAL":
        return "steal"
    if normalized == "FOUL":
        return "foul"
    if normalized == "DEAD_BALL_TURNOVER":
        return "dead_ball_turnover"
    if normalized in {"MAKE", "MISS", "BLOCK", "SHOT_ATTEMPT"}:
        return "shot"
    return normalized.lower() if normalized else "none"


def _coord(value: Any) -> Optional[Dict[str, float]]:
    if not isinstance(value, dict) or "x" not in value or "y" not in value:
        return None
    try:
        return {"x": float(value["x"]), "y": float(value["y"])}
    except (TypeError, ValueError):
        return None


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
