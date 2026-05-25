"""Triangle Fast Break animation step emitter (UESS / SS&S).

Triangle reuses Rim Runner burst + outlet pass (DREB entry), then diverges:
  burst → outlet (optional) → triangle setup → decision lead-in → shot motion.

Outlet-denied and ``triangle_enter_hco`` (hold-up) reuse the RR branch steps
from ``rim_runner_step_emitter``.

See ``rim_runner_step_emitter`` module docstring for shared step builders.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import (
    FB_PASS_GRID_SPOTS_PER_GAME_SECOND,
    FB_PASS_MIN_GAME_SECONDS,
)
from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    Announcement,
    BallState,
    ClockState,
    GridCoord,
    NextStep,
    PlayerAction,
    PlayerArchetype,
    StepEnd,
    StepStart,
)

from BackEnd.engine.rim_runner_step_emitter import (
    _all_player_start_coords,
    _build_burst_step,
    _build_hold_up_step,
    _build_outlet_denied_defender_step,
    _build_outlet_pass_step,
    _build_player_data,
    _decision_pill_meta,
    _euclid,
    _fb_play_label,
    _finalize_rr_steps,
    _interrupted_coord,
    _is_offense_player,
    _movement_end_coord,
    _player_lookup_by_id,
    _resolve_shot_next,
    _safe_id,
    _stamp_tween_durations,
    _traversal_seconds,
    _ag_grid_per_game_sec,
)


def _next_step_index(steps: List[AnimationStep]) -> int:
    return len(steps) + 1


def _coord_dict(raw: Any) -> Optional[GridCoord]:
    if not isinstance(raw, dict) or "x" not in raw or "y" not in raw:
        return None
    return {"x": float(raw["x"]), "y": float(raw["y"])}


def _triangle_setup_payload(fb_roles: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    payload = fb_roles.get("triangle_setup_phase")
    return payload if isinstance(payload, dict) else None


def _triangle_branch(turn_result: Dict[str, Any], payload: Dict[str, Any]) -> str:
    return str(
        turn_result.get("triangle_branch")
        or (turn_result.get("roles") or {}).get("triangle_branch")
        or payload.get("triangle_branch")
        or ""
    ).strip()


def _collect_setup_moves(
    payload: Dict[str, Any],
) -> List[Tuple[str, GridCoord, PlayerArchetype, PlayerAction]]:
    """(player_id, target, archetype, action) for triangle setup tweens."""
    moves: List[Tuple[str, GridCoord, PlayerArchetype, PlayerAction]] = []

    def add(pid: Any, target: Any, *, burst: bool = False) -> None:
        sid = _safe_id(pid)
        coord = _coord_dict(target)
        if not sid or coord is None:
            return
        arch: PlayerArchetype = "burst" if burst else "standard"
        action: PlayerAction = "cut" if burst else "cut"
        moves.append((sid, coord, arch, action))

    add(payload.get("ball_handler_id"), payload.get("ball_handler_to"))
    add(payload.get("rim_runner_id"), payload.get("rim_runner_to"))
    add(payload.get("trailer_id"), payload.get("trailer_to"))
    for corner in payload.get("corner_players") or []:
        if not isinstance(corner, dict):
            continue
        add(
            corner.get("player_id"),
            corner.get("to"),
            burst=bool(corner.get("burst")),
        )
    add(payload.get("rr_defender_id"), payload.get("rr_defender_to"))
    add(payload.get("bh_defender_id"), payload.get("bh_defender_to"))
    for helper in payload.get("helper_defenders") or []:
        if not isinstance(helper, dict):
            continue
        add(
            helper.get("player_id"),
            helper.get("to"),
            burst=bool(helper.get("burst")),
        )
    return moves


def _build_parallel_move_step(
    *,
    step_start_coords: Dict[str, GridCoord],
    movers: List[Tuple[str, GridCoord, PlayerArchetype, PlayerAction]],
    gate_player_id: str,
    ball_owner_id: str,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step: NextStep,
    announcement: Optional[Announcement] = None,
) -> Optional[AnimationStep]:
    if gate_player_id not in step_start_coords:
        return None
    gate_target = next((m[1] for m in movers if m[0] == gate_player_id), None)
    if gate_target is None:
        return None

    gate_player = _player_lookup_by_id(off_lineup, def_lineup, gate_player_id)
    gate_rate = _ag_grid_per_game_sec(gate_player, "standard")
    t = max(
        0.2,
        _traversal_seconds(step_start_coords[gate_player_id], gate_target, gate_rate),
    )

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in step_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in step_start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }

    for pid, target, arch, action in movers:
        if pid not in step_start_coords:
            continue
        actions[pid] = action
        archetype[pid] = arch
        destinations[pid] = dict(target)
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch)
        end_coords[pid] = _interrupted_coord(step_start_coords[pid], target, rate, t)

    if ball_owner_id in step_start_coords:
        actions[ball_owner_id] = "handle_ball"
        archetype[ball_owner_id] = "standard"

    ball: BallState = {"owner_player_id": ball_owner_id}
    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": gate_player_id,
            "target_coords": dict(gate_target),
            "reason": "triangle_parallel_move",
        },
    }
    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }
    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    if announcement is not None:
        start["announcement"] = announcement
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball,
        "time_elapsed": t,
        "clock": clock_end,
        "next": next_step,
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_triangle_setup_step(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    payload: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_start_coords: Dict[str, GridCoord],
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> Optional[AnimationStep]:
    bh_id = _safe_id(payload.get("ball_handler_id"))
    if not bh_id:
        return None
    movers = _collect_setup_moves(payload)
    if not movers:
        return None

    phase = fb_roles.get("rim_runner_burst_phase") or {}
    bh_player = _player_lookup_by_id(off_lineup, def_lineup, bh_id)
    announcement: Announcement = {
        "text": "Fast Break!",
        "team": "away" if is_away_offense else "home",
        "player_data": _build_player_data(bh_player, fallback_id=bh_id),
        "meta": {
            **_decision_pill_meta(turn_result),
            "eventSubtitle": _fb_play_label("triangle"),
        },
        "hold_ms": 1000,
        "style": "secondary",
    }
    return _build_parallel_move_step(
        step_start_coords=step_start_coords,
        movers=movers,
        gate_player_id=bh_id,
        ball_owner_id=bh_id,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        clock_remaining_at_start=clock_remaining_at_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_start,
        next_step={"kind": "next_step", "index": next_step_index},
        announcement=announcement,
    )


def _build_branch_pass_step(
    *,
    passer_id: str,
    receiver_id: str,
    receiver_target: GridCoord,
    step_start_coords: Dict[str, GridCoord],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> Optional[AnimationStep]:
    if passer_id not in step_start_coords or receiver_id not in step_start_coords:
        return None
    passer_coord = step_start_coords[passer_id]
    dist = _euclid(passer_coord, receiver_target)
    t = max(FB_PASS_MIN_GAME_SECONDS, dist / float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND))

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in step_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in step_start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }

    actions[passer_id] = "pass"
    actions[receiver_id] = "receive"
    archetype[receiver_id] = "sprint"
    destinations[receiver_id] = dict(receiver_target)
    end_coords[receiver_id] = dict(receiver_target)

    ball_start: BallState = {"owner_player_id": passer_id}
    ball_end: BallState = {"owner_player_id": receiver_id}
    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": passer_id,
            "to_player_id": receiver_id,
            "target_coords": dict(receiver_target),
            "reason": "triangle_branch_pass",
        },
    }
    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }
    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
        "ball_motion_style": "pass",
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_triangle_decision_steps(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    payload: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_start_coords: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> List[AnimationStep]:
    """Zero or more decision lead-in steps (pass and/or drive)."""
    out: List[AnimationStep] = []
    branch = _triangle_branch(turn_result, payload)
    bh_id = _safe_id(payload.get("ball_handler_id"))
    rr_id = _safe_id(payload.get("rim_runner_id"))
    corner_id = _safe_id(payload.get("same_side_corner_id"))
    cursor_clock = clock_remaining_at_start
    cursor_sc = shot_clock_remaining_at_start
    cursor_coords = dict(step_start_coords)
    next_idx = next_step_index

    def append_step(step: Optional[AnimationStep]) -> bool:
        nonlocal cursor_clock, cursor_sc, cursor_coords, next_idx
        if step is None:
            return False
        step["end"]["next"] = {"kind": "next_step", "index": next_idx + 1}
        out.append(step)
        dt = float(step["end"]["time_elapsed"])
        cursor_clock -= dt
        cursor_sc -= dt
        cursor_coords = dict(step["end"]["coords"])
        next_idx += 1
        return True

    if branch == "triangle_bh_wing_three":
        return out

    if branch == "triangle_rr_post" and bh_id and rr_id:
        target = _coord_dict(payload.get("rim_runner_to"))
        if target:
            append_step(
                _build_branch_pass_step(
                    passer_id=bh_id,
                    receiver_id=rr_id,
                    receiver_target=target,
                    step_start_coords=cursor_coords,
                    off_lineup=off_lineup,
                    def_lineup=def_lineup,
                    clock_remaining_at_start=cursor_clock,
                    shot_clock_remaining_at_start=cursor_sc,
                    next_step_index=next_idx,
                )
            )
        return out

    if branch == "triangle_corner_three" and bh_id and corner_id:
        target = _coord_dict(payload.get("same_side_corner_to"))
        if target:
            append_step(
                _build_branch_pass_step(
                    passer_id=bh_id,
                    receiver_id=corner_id,
                    receiver_target=target,
                    step_start_coords=cursor_coords,
                    off_lineup=off_lineup,
                    def_lineup=def_lineup,
                    clock_remaining_at_start=cursor_clock,
                    shot_clock_remaining_at_start=cursor_sc,
                    next_step_index=next_idx,
                )
            )
        return out

    if branch not in (
        "triangle_bh_drive",
        "triangle_drive_rr_feed",
        "triangle_drive_corner_kick",
    ):
        return out

    movers: List[Tuple[str, GridCoord, PlayerArchetype, PlayerAction]] = []
    drive_bh = _coord_dict(payload.get("triangle_drive_to"))
    drive_rr = _coord_dict(payload.get("triangle_rr_drive_to"))
    if bh_id and drive_bh:
        movers.append((bh_id, drive_bh, "standard", "handle_ball"))
    if rr_id and drive_rr:
        movers.append((rr_id, drive_rr, "sprint", "cut"))
    if not movers or not bh_id:
        return out

    drive_step = _build_parallel_move_step(
        step_start_coords=cursor_coords,
        movers=movers,
        gate_player_id=bh_id,
        ball_owner_id=bh_id,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        clock_remaining_at_start=cursor_clock,
        shot_clock_remaining_at_start=cursor_sc,
        next_step={"kind": "next_step", "index": next_idx},
    )
    if not append_step(drive_step):
        return out

    if branch == "triangle_drive_rr_feed" and rr_id and drive_rr:
        append_step(
            _build_branch_pass_step(
                passer_id=bh_id,
                receiver_id=rr_id,
                receiver_target=drive_rr,
                step_start_coords=cursor_coords,
                off_lineup=off_lineup,
                def_lineup=def_lineup,
                clock_remaining_at_start=cursor_clock,
                shot_clock_remaining_at_start=cursor_sc,
                next_step_index=next_idx,
            )
        )
    elif branch == "triangle_drive_corner_kick" and corner_id:
        corner_target = _coord_dict(payload.get("same_side_corner_to"))
        if corner_target:
            append_step(
                _build_branch_pass_step(
                    passer_id=bh_id,
                    receiver_id=corner_id,
                    receiver_target=corner_target,
                    step_start_coords=cursor_coords,
                    off_lineup=off_lineup,
                    def_lineup=def_lineup,
                    clock_remaining_at_start=cursor_clock,
                    shot_clock_remaining_at_start=cursor_sc,
                    next_step_index=next_idx,
                )
            )
    return out


def _build_triangle_shot_motion_step(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    animations: List[Dict[str, Any]],
    step_start_coords: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
) -> Optional[AnimationStep]:
    shooter = turn_result.get("shooter") or fb_roles.get("shooter")
    shooter_id = _safe_id(shooter)
    if not shooter_id or shooter_id not in step_start_coords:
        return None

    end_coords: Dict[str, GridCoord] = {
        pid: dict(step_start_coords[pid]) for pid in step_start_coords
    }
    for pid in step_start_coords:
        anim_end = _movement_end_coord(animations, pid)
        if anim_end is not None:
            end_coords[pid] = anim_end

    shooter_start = step_start_coords[shooter_id]
    shooter_end = end_coords.get(shooter_id, shooter_start)
    shooter_player = _player_lookup_by_id(off_lineup, def_lineup, shooter_id)
    shooter_rate = _ag_grid_per_game_sec(shooter_player, "sprint")
    t = max(0.2, _traversal_seconds(shooter_start, shooter_end, shooter_rate))

    defender_id = _safe_id(turn_result.get("defender") or fb_roles.get("defender"))
    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in step_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in step_start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(end_coords.get(pid, step_start_coords[pid]))
        for pid in step_start_coords
    }

    actions[shooter_id] = "shoot"
    archetype[shooter_id] = "sprint"
    if defender_id and defender_id in step_start_coords:
        actions[defender_id] = "guard_ball"
        archetype[defender_id] = "sprint"

    for pid in step_start_coords:
        if pid in (shooter_id, defender_id):
            continue
        if _movement_end_coord(animations, pid) is not None:
            if _is_offense_player(pid, off_lineup):
                actions[pid] = "cut"
                archetype[pid] = "standard"
            else:
                actions[pid] = "guard_offball"
                archetype[pid] = "standard"

    for pid, start_coord in step_start_coords.items():
        if pid == shooter_id:
            continue
        target = end_coords.get(pid)
        if target is None:
            continue
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, archetype[pid])
        end_coords[pid] = _interrupted_coord(start_coord, target, rate, t)

    ball: BallState = {"owner_player_id": shooter_id}
    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": shooter_id,
            "target_coords": dict(shooter_end),
            "reason": "triangle_shot_motion",
        },
    }
    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }
    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball,
        "time_elapsed": t,
        "clock": clock_end,
        "next": _resolve_shot_next(turn_result),
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def build_triangle_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Convert a Triangle FB ``turn_result`` into ``AnimationStep[]``."""
    if turn_result.get("fast_break_play") != "triangle":
        return None
    if game.game_state.get("_is_full_simulation", False):
        return None

    fb_roles = turn_result.get("roles") or {}
    burst_phase = fb_roles.get("rim_runner_burst_phase")
    if not burst_phase:
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}
    is_away_offense = bool(
        fb_roles.get("is_away_offense") or burst_phase.get("is_away_offense")
    )

    all_start_coords = _all_player_start_coords(off_lineup, def_lineup)
    if not all_start_coords:
        return None

    from BackEnd.utils.animation_step_helpers import log_fb_emitter_entry
    log_fb_emitter_entry("TRIANGLE", all_start_coords, game, off_lineup, def_lineup)

    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining = float(game_state.get("shot_clock_remaining", 0) or 0)

    outlet_failed = bool(turn_result.get("rim_runner_outlet_failed"))
    triangle_enter_hco = bool(turn_result.get("triangle_enter_hco"))
    result_type = str(turn_result.get("result_type") or "").upper()

    steps: List[AnimationStep] = []
    elapsed = 0.0

    import logging as _tri_log

    burst_step = _build_burst_step(
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        all_start_coords=all_start_coords,
        is_away_offense=is_away_offense,
        clock_remaining_at_start=clock_remaining,
        shot_clock_remaining_at_start=shot_clock_remaining,
        next_step_index=_next_step_index(steps),
    )
    if burst_step is None:
        _tri_log.warning(
            "🐛 [TRIANGLE_NONE site=burst_step] outlet_failed=%s triangle_enter_hco=%s result_type=%s skip_outlet_pass=%s",
            outlet_failed, triangle_enter_hco, result_type,
            bool(burst_phase.get("skip_outlet_pass")),
        )
        return None
    steps.append(burst_step)
    elapsed += float(burst_step["end"]["time_elapsed"])
    last_end_coords = dict(burst_step["end"]["coords"])

    if outlet_failed:
        denied = _build_outlet_denied_defender_step(
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_start_coords=last_end_coords,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_remaining - elapsed,
            shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
            next_step_index=999,
        )
        if denied is None:
            _tri_log.warning(
                "🐛 [TRIANGLE_NONE site=outlet_denied_defender_step] outlet_failed=%s triangle_enter_hco=%s result_type=%s",
                outlet_failed, triangle_enter_hco, result_type,
            )
            return None
        steps.append(denied)
        return _finalize_rr_steps(turn_result, game, steps)

    skip_outlet_pass = bool(burst_phase.get("skip_outlet_pass"))
    if not skip_outlet_pass:
        outlet_step = _build_outlet_pass_step(
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_start_coords=last_end_coords,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_remaining - elapsed,
            shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
            next_step_index=_next_step_index(steps),
        )
        if outlet_step is None:
            _tri_log.warning(
                "🐛 [TRIANGLE_NONE site=outlet_pass_step] outlet_failed=%s triangle_enter_hco=%s result_type=%s skip_outlet_pass=%s passer_id=%s receiver_id=%s",
                outlet_failed, triangle_enter_hco, result_type, skip_outlet_pass,
                burst_phase.get("outlet_passer_id"),
                burst_phase.get("outlet_receiver_id"),
            )
            return None
        steps.append(outlet_step)
        elapsed += float(outlet_step["end"]["time_elapsed"])
        last_end_coords = dict(outlet_step["end"]["coords"])

    if triangle_enter_hco or result_type == "DEFENSIVE_STOP":
        hold_up = _build_hold_up_step(
            turn_result=turn_result,
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_start_coords=last_end_coords,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_remaining - elapsed,
            shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
        )
        if hold_up is not None:
            steps.append(hold_up)
        else:
            _tri_log.warning(
                "🐛 [TRIANGLE_HOLD_UP_NONE] triangle_enter_hco=%s result_type=%s — proceeding with %d steps",
                triangle_enter_hco, result_type, len(steps),
            )
        return _finalize_rr_steps(turn_result, game, steps)

    payload = _triangle_setup_payload(fb_roles)
    if not payload:
        _tri_log.warning(
            "🐛 [TRIANGLE_NONE site=setup_payload] outlet_failed=%s triangle_enter_hco=%s result_type=%s triangle_branch=%s",
            outlet_failed, triangle_enter_hco, result_type,
            turn_result.get("triangle_branch"),
        )
        return None

    setup_step = _build_triangle_setup_step(
        turn_result=turn_result,
        fb_roles=fb_roles,
        payload=payload,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        step_start_coords=last_end_coords,
        is_away_offense=is_away_offense,
        clock_remaining_at_start=clock_remaining - elapsed,
        shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
        next_step_index=_next_step_index(steps),
    )
    if setup_step is None:
        _tri_log.warning(
            "🐛 [TRIANGLE_NONE site=setup_step] triangle_branch=%s payload_keys=%s",
            turn_result.get("triangle_branch"), list(payload.keys()) if payload else None,
        )
        return None
    steps.append(setup_step)
    elapsed += float(setup_step["end"]["time_elapsed"])
    last_end_coords = dict(setup_step["end"]["coords"])

    decision_steps = _build_triangle_decision_steps(
        turn_result=turn_result,
        fb_roles=fb_roles,
        payload=payload,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        step_start_coords=last_end_coords,
        clock_remaining_at_start=clock_remaining - elapsed,
        shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
        next_step_index=_next_step_index(steps),
    )
    for decision_step in decision_steps:
        steps.append(decision_step)
        elapsed += float(decision_step["end"]["time_elapsed"])
        last_end_coords = dict(decision_step["end"]["coords"])

    shot_motion = _build_triangle_shot_motion_step(
        turn_result=turn_result,
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        animations=turn_result.get("animations") or [],
        step_start_coords=last_end_coords,
        clock_remaining_at_start=clock_remaining - elapsed,
        shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
    )
    if shot_motion is not None:
        steps.append(shot_motion)

    return _finalize_rr_steps(turn_result, game, steps)
