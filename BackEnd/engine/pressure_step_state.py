"""Pressure StepState builder for dynamic FCP/HCT turns.

This is the additive bridge toward the FCP/HCT UESS target:

    resolve once -> freeze into StepState -> project to animation schema -> draw.

For the current migration step, HCT/FCP still build ``AnimationStep`` from their
existing loop segments first. This module freezes those emitted schema facts
into a shared ``PressureStepState`` shape and stamps it back onto each emitted
step. No consumer reads it yet, so this is behavior-neutral.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional


def build_pressure_step_states(
    result: Dict[str, Any],
    turn_type: str,
) -> List[Dict[str, Any]]:
    """Freeze emitted HCT/FCP ``AnimationStep`` data into pressure StepState.

    The builder deliberately copies from schema instead of recomputing. That
    keeps this step additive and makes any future StepState->schema projection
    compare against the exact contract currently rendered by the frontend.
    """
    if not isinstance(result, dict):
        return []

    steps = result.get("animation_steps") or []
    if not isinstance(steps, list) or not steps:
        return []

    normalized = (turn_type or result.get("current_turn") or "").upper()
    step_states: List[Dict[str, Any]] = []
    terminal_count = 0

    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        start = step.get("start") or {}
        end = step.get("end") or {}
        state = {
            "index": index,
            "turn_type": normalized,
            "players": _players_state(start, end),
            "ball": _ball_state(start, end),
            "timing": _timing_state(start, end),
            "advance_gate": _advance_gate_state(start),
            "outcome": _outcome_state(end, result),
            "next": _next_state(end),
            "cosmetics": _cosmetics_state(start, end),
            "render": _render_state(start, end),
            "projection_source": _projection_source(start),
            # Transitional Step 8 bridge: keep a full render projection snapshot
            # so ``PressureStepState -> AnimationStep`` can be parity-tested
            # before individual HCT/FCP builders produce StepState upstream.
            "schema_projection": _schema_projection(step),
        }
        if state["outcome"].get("kind") not in (None, "none"):
            terminal_count += 1
        step["_pressure_step_state"] = state
        step_states.append(state)

    result["pressure_step_states"] = step_states
    logging.debug(
        "🔬 [PRESSURE STEPSTATE] stamped %s states=%d terminal=%d",
        normalized or "PRESSURE",
        len(step_states),
        terminal_count,
    )
    return step_states


def project_pressure_step_states_to_animation_steps(
    step_states: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Project pressure StepState values back into AnimationStep schema.

    During the migration, ``schema_projection`` is a complete snapshot of the
    emitted step. Later steps should shrink that snapshot as the formal
    StepState fields become the actual source of projection.
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
        step["_pressure_step_state"] = state
        projected.append(step)
    return projected


def project_animation_step_through_pressure_state(
    step: Dict[str, Any],
    *,
    index: int,
    turn_type: str,
    result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Freeze one emitted step and immediately project it through StepState.

    This is the incremental Step 8 migration seam for individual pressure
    builders. The caller still builds the current schema first, but the returned
    value is now produced by ``PressureStepState -> AnimationStep`` for any step
    whose reason is covered by formal projection.
    """
    if not isinstance(step, dict):
        return step
    state = _state_from_step(step, index=index, turn_type=turn_type, result=result or {})
    projected = project_pressure_step_states_to_animation_steps([state])
    return projected[0] if projected else step


def _state_from_step(
    step: Dict[str, Any],
    *,
    index: int,
    turn_type: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    start = step.get("start") or {}
    end = step.get("end") or {}
    state = {
        "index": index,
        "turn_type": (turn_type or result.get("current_turn") or "").upper(),
        "players": _players_state(start, end),
        "ball": _ball_state(start, end),
        "timing": _timing_state(start, end),
        "advance_gate": _advance_gate_state(start),
        "outcome": _outcome_state(end, result),
        "next": _next_state(end),
        "cosmetics": _cosmetics_state(start, end),
        "render": _render_state(start, end),
        "projection_source": _projection_source(start),
        "schema_projection": _schema_projection(step),
    }
    step["_pressure_step_state"] = state
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


def _schema_projection(step: Dict[str, Any]) -> Dict[str, Any]:
    """Copy the rendered schema without the StepState stamp to avoid recursion."""
    return {
        key: copy.deepcopy(value)
        for key, value in (step or {}).items()
        if key != "_pressure_step_state"
    }


def _project_from_formal_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort formal projection fallback.

    This is intentionally conservative and currently exists as a fallback only;
    the parity path uses ``schema_projection`` until StepState fields become the
    upstream source for every emitted schema field.
    """
    players = state.get("players") or {}
    ball = state.get("ball") or {}
    timing = state.get("timing") or {}
    gate = state.get("advance_gate") or {}
    outcome = state.get("outcome") or {}
    next_state = state.get("next") or {}
    cosmetics = state.get("cosmetics") or {}
    render = state.get("render") or {}

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
        "action": {
            pid: data.get("action")
            for pid, data in players.items()
        },
        "archetype": {
            pid: data.get("archetype")
            for pid, data in players.items()
        },
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
    tween_durations = render.get("tween_durations")
    if tween_durations:
        start["tween_durations"] = copy.deepcopy(tween_durations)
    flourish = cosmetics.get("flourish_triggers")
    if flourish:
        start["flourish"] = copy.deepcopy(flourish)
    for sfx in cosmetics.get("sfx_triggers") or []:
        trigger = sfx.get("trigger")
        payload = sfx.get("payload")
        if trigger and payload:
            start[trigger] = copy.deepcopy(payload)

    if ball.get("motion_style") == "pass":
        if ball.get("from_owner") or ball.get("to_owner"):
            start["ball"] = {
                "from_player_id": ball.get("from_owner"),
                "to_player_id": ball.get("to_owner"),
                "current_coords": copy.deepcopy(ball.get("from_coord")),
            }
        else:
            start["ball"] = {"coords": copy.deepcopy(ball.get("from_coord"))}
        if ball.get("motion_style_explicit"):
            start["ball_motion_style"] = "pass"
        if ball.get("arrival_coord_explicit") and ball.get("arrival_coord") is not None:
            start["ball_arrival_coord"] = copy.deepcopy(ball.get("arrival_coord"))
    elif ball.get("motion_style_explicit") and ball.get("from_coord"):
        start["ball"] = {"coords": copy.deepcopy(ball.get("from_coord"))}
        start["ball_motion_style"] = ball.get("motion_style")
    elif ball.get("from_owner"):
        start["ball"] = {"owner_player_id": ball.get("from_owner")}
    else:
        start["ball"] = {"coords": copy.deepcopy(ball.get("from_coord"))}

    end_next = copy.deepcopy(next_state)
    if not end_next:
        end_next = {"kind": "next_step", "index": int(state.get("index") or 0) + 1}
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
        "next": end_next,
    }
    announcements = cosmetics.get("announcement_triggers") or []
    if announcements:
        end["announcement"] = copy.deepcopy(announcements[0])
    return {"start": start, "end": end}


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
    contact_point = (
        _coord(metadata.get("contact_coords"))
        or _coord(metadata.get("target_coords"))
        if metadata.get("reason") in {"hct_interception", "hct_bat_oob_contact"}
        else None
    )
    motion_style = start.get("ball_motion_style")
    motion_style_explicit = motion_style is not None
    if not motion_style and (
        start_ball.get("from_player_id")
        or start_ball.get("to_player_id")
        or (trigger.get("condition") == "ball_reaches_player")
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
        "contact_point": contact_point,
        "resolved_by": str(end_ball.get("owner_player_id")) if end_ball.get("owner_player_id") is not None else None,
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
    if next_state.get("kind") == "next_step":
        index = next_state.get("index")
        if index == 999:
            return {
                "kind": "pressure_break",
                "event": "HCO_CONTINUATION",
                "payload": {"result_type": result.get("result_type")},
            }
    return {
        "kind": "none",
        "event": None,
        "payload": {},
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
        copy.deepcopy((start.get("announcement") or {}))
        or copy.deepcopy((end.get("announcement") or {}))
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


def _render_state(start: Dict[str, Any], end: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tween_durations": copy.deepcopy(start.get("tween_durations") or {}),
    }


def _projection_source(start: Dict[str, Any]) -> str:
    trigger = start.get("advance_trigger") or {}
    metadata = (trigger.get("metadata") or {})
    reason = metadata.get("reason")
    kind = metadata.get("kind")
    if trigger.get("condition") == "dead_ball_fumble":
        return "formal"
    if trigger.get("condition") == "shot_resolved":
        return "formal"
    if kind in {
        "make_hold",
        "bounce",
        "rattle_hop",
        "rattle_settle",
        "bank_settle",
        "bank_graze",
        "airball_oob",
    }:
        return "formal"
    if reason in {
        "hct_entry_walkup",
        "hct_advance",
        "hct_pass",
        "hct_interception",
        "hct_bat_oob_contact",
        "hct_bat_oob_drift",
        "hct_steal",
        "hct_foul",
        "hct_reach_in",
        "hct_dead_ball",
        "hct_dead_ball_turnover",
        "hct_fb_drive",
        "hct_ab_drive",
        "hct_ab_dish",
        "hct_ab_shot",
    }:
        return "formal"
    return "schema_projection"


def _event_to_kind(event: Optional[str]) -> str:
    normalized = (event or "").upper()
    if normalized == "STEAL":
        return "steal"
    if normalized == "FOUL":
        return "foul"
    if normalized == "DEAD_BALL_TURNOVER":
        return "dead_ball_turnover"
    if normalized in {"MAKE", "MISS", "BLOCK"}:
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
