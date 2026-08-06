"""Triangle Fast Break animation step emitter (UESS / SS&S).

Triangle reuses Rim Runner burst + outlet pass (DREB entry), then diverges:

  - **Lane-pass quick shot** (``rim_runner_pass_attempted``): shared
    ``append_lane_pass_to_rr_resolution_steps`` — outlet receiver → RR lane
    pass → shot motion → skeleton post-shot chain (same as Rim Runner).
  - **Setup tree** (``pass_attempted`` false): triangle setup → decision
    lead-in → ``_build_triangle_shot_motion_step`` → finalize.

Outlet-denied and ``triangle_enter_hco`` reuse RR branch steps from
``rim_runner_step_emitter``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import (
    FB_PASS_GRID_SPOTS_PER_GAME_SECOND,
    FB_PASS_MIN_GAME_SECONDS,
)
from BackEnd.constants.announcement_constants import ANNOUNCEMENT_FREEZE_HOLD_MS
from BackEnd.engine.fb_uess_debug import mark_fb_emitter_fallback
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
    append_lane_pass_to_rr_resolution_steps,
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
    _initialize_continuing_movement,
    is_lane_pass_to_rr_resolution_turn,
    _player_lookup_by_id,
    closeout_contest_coord,
    shot_spot_from_roles,
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

    def add(pid: Any, target: Any) -> None:
        sid = _safe_id(pid)
        coord = _coord_dict(target)
        if not sid or coord is None:
            return
        moves.append((sid, coord, "sprint", "cut"))

    add(payload.get("ball_handler_id"), payload.get("ball_handler_to"))
    add(payload.get("rim_runner_id"), payload.get("rim_runner_to"))
    add(payload.get("trailer_id"), payload.get("trailer_to"))
    for corner in payload.get("corner_players") or []:
        if not isinstance(corner, dict):
            continue
        add(corner.get("player_id"), corner.get("to"))
    add(payload.get("rr_defender_id"), payload.get("rr_defender_to"))
    add(payload.get("bh_defender_id"), payload.get("bh_defender_to"))
    for helper in payload.get("helper_defenders") or []:
        if not isinstance(helper, dict):
            continue
        add(helper.get("player_id"), helper.get("to"))
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
    arrival_player_ids: Optional[List[str]] = None,
    previous_step: Optional[AnimationStep] = None,
) -> Optional[AnimationStep]:
    if gate_player_id not in step_start_coords:
        return None
    gate_target = next((m[1] for m in movers if m[0] == gate_player_id), None)
    if gate_target is None:
        return None

    gate_player = _player_lookup_by_id(off_lineup, def_lineup, gate_player_id)
    gate_archetype = next((m[2] for m in movers if m[0] == gate_player_id), "standard")
    gate_rate = _ag_grid_per_game_sec(gate_player, gate_archetype)
    t = max(
        0.2,
        _traversal_seconds(step_start_coords[gate_player_id], gate_target, gate_rate),
    )

    # Extend T so any ``arrival_player_ids`` (receivers of the immediately
    # following ``_build_branch_pass_step``) fully reach their destination
    # within this step. Without this, a receiver whose run is longer than the
    # gate player's gets clamped short here, then jetted to his spot in the
    # pass step (which is timed to the ball flight, not his travel). Taking
    # the max of the gate + receiver traversals removes that residual so the
    # receiver is already standing on the pass target when the ball arrives.
    for pid in arrival_player_ids or ():
        if pid == gate_player_id or pid not in step_start_coords:
            continue
        mover = next((m for m in movers if m[0] == pid), None)
        if mover is None:
            continue
        recv_player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        recv_rate = _ag_grid_per_game_sec(recv_player, mover[2])
        t = max(t, _traversal_seconds(step_start_coords[pid], mover[1], recv_rate))

    actions, archetype, destinations, end_coords = _initialize_continuing_movement(
        step_start_coords=step_start_coords,
        previous_step=previous_step,
        step_t=t,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
    )

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
        archetype[ball_owner_id] = gate_archetype if ball_owner_id == gate_player_id else "standard"

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

    # Receivers whose pass fires straight off the setup step must fully arrive
    # within this step so the following ``_build_branch_pass_step`` starts them
    # on-spot (no residual → no jet). The corner-kick branch drives first, but
    # the corner is idle during that drive, so his arrival is gated here too.
    branch = _triangle_branch(turn_result, payload)
    arrival_ids: List[str] = []
    if branch == "triangle_rr_post":
        rr_id = _safe_id(payload.get("rim_runner_id"))
        if rr_id:
            arrival_ids.append(rr_id)
    elif branch in ("triangle_corner_three", "triangle_drive_corner_kick"):
        corner_id = _safe_id(payload.get("same_side_corner_id"))
        if corner_id:
            arrival_ids.append(corner_id)

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
        # Non-blocking: the "Fast Break!" callout rides ALONGSIDE the lane pass to the
        # rim runner instead of freezing the court before it. The FE
        # shows the overlay without a clock pause / hold wait. See Announcement_System.md.
        "hold_ms": ANNOUNCEMENT_FREEZE_HOLD_MS,
        "non_blocking": True,
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
        arrival_player_ids=arrival_ids,
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
    previous_step: Optional[AnimationStep] = None,
) -> Optional[AnimationStep]:
    if passer_id not in step_start_coords or receiver_id not in step_start_coords:
        return None
    passer_coord = step_start_coords[passer_id]
    dist = _euclid(passer_coord, receiver_target)
    t = max(FB_PASS_MIN_GAME_SECONDS, dist / float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND))

    actions, archetype, destinations, end_coords = _initialize_continuing_movement(
        step_start_coords=step_start_coords,
        previous_step=previous_step,
        step_t=t,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
    )

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
    previous_step: AnimationStep,
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
    cursor_previous = previous_step
    next_idx = next_step_index

    logging.warning(
        "🔍 [TRIANGLE DECISION] branch=%s bh_id=%s rr_id=%s corner_id=%s "
        "rim_runner_to=%s same_side_corner_to=%s "
        "triangle_drive_to=%s triangle_rr_drive_to=%s",
        branch, bh_id, rr_id, corner_id,
        payload.get("rim_runner_to"), payload.get("same_side_corner_to"),
        payload.get("triangle_drive_to"), payload.get("triangle_rr_drive_to"),
    )

    def append_step(step: Optional[AnimationStep]) -> bool:
        nonlocal cursor_clock, cursor_sc, cursor_coords, cursor_previous, next_idx
        if step is None:
            return False
        step["end"]["next"] = {"kind": "next_step", "index": next_idx}
        out.append(step)
        dt = float(step["end"]["time_elapsed"])
        cursor_clock -= dt
        cursor_sc -= dt
        cursor_coords = dict(step["end"]["coords"])
        cursor_previous = step
        next_idx += 1
        return True

    if branch == "triangle_bh_wing_three":
        return out

    if branch == "triangle_rr_post":
        if not (bh_id and rr_id):
            logging.warning(
                "🔍 [TRIANGLE SKIP] branch=triangle_rr_post pass step dropped: "
                "bh_id=%s rr_id=%s — ball will teleport to receiver on shot step",
                bh_id, rr_id,
            )
            return out
        target = _coord_dict(payload.get("rim_runner_to"))
        if not target:
            logging.warning(
                "🔍 [TRIANGLE SKIP] branch=triangle_rr_post pass step dropped: "
                "payload.rim_runner_to=%s — ball will teleport on shot step",
                payload.get("rim_runner_to"),
            )
            return out
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
                previous_step=cursor_previous,
            )
        )
        return out

    if branch == "triangle_corner_three":
        if not (bh_id and corner_id):
            logging.warning(
                "🔍 [TRIANGLE SKIP] branch=triangle_corner_three pass step dropped: "
                "bh_id=%s corner_id=%s — ball will teleport on shot step",
                bh_id, corner_id,
            )
            return out
        target = _coord_dict(payload.get("same_side_corner_to"))
        if not target:
            logging.warning(
                "🔍 [TRIANGLE SKIP] branch=triangle_corner_three pass step dropped: "
                "payload.same_side_corner_to=%s — ball will teleport on shot step",
                payload.get("same_side_corner_to"),
            )
            return out
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
                previous_step=cursor_previous,
            )
        )
        return out

    if branch not in (
        "triangle_bh_drive",
        "triangle_drive_rr_feed",
        "triangle_drive_corner_kick",
    ):
        logging.warning(
            "🔍 [TRIANGLE SKIP] unrecognized branch=%s — no decision steps emitted",
            branch,
        )
        return out

    movers: List[Tuple[str, GridCoord, PlayerArchetype, PlayerAction]] = []
    drive_bh = _coord_dict(payload.get("triangle_drive_to"))
    drive_rr = _coord_dict(payload.get("triangle_rr_drive_to"))
    if bh_id and drive_bh:
        movers.append((bh_id, drive_bh, "sprint", "handle_ball"))
    if rr_id and drive_rr:
        movers.append((rr_id, drive_rr, "sprint", "cut"))
    if not movers or not bh_id:
        logging.warning(
            "🔍 [TRIANGLE SKIP] branch=%s drive step dropped: bh_id=%s drive_bh=%s "
            "rr_id=%s drive_rr=%s — no decision steps emitted",
            branch, bh_id, drive_bh, rr_id, drive_rr,
        )
        return out

    # For the RR-feed branch the pass fires straight off this drive step, so the
    # RR must fully reach his drive spot within it (no residual → no jet). The
    # corner-kick branch drives first but kicks to the (idle) corner, whose
    # arrival is already gated in the setup step, not here.
    drive_arrival_ids: List[str] = []
    if branch == "triangle_drive_rr_feed" and rr_id and drive_rr:
        drive_arrival_ids.append(rr_id)

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
        arrival_player_ids=drive_arrival_ids,
        previous_step=cursor_previous,
    )
    if not append_step(drive_step):
        logging.warning(
            "🔍 [TRIANGLE SKIP] branch=%s drive step build returned None — "
            "no decision steps emitted",
            branch,
        )
        return out

    if branch == "triangle_drive_rr_feed":
        if not (rr_id and drive_rr):
            logging.warning(
                "🔍 [TRIANGLE SKIP] branch=triangle_drive_rr_feed pass step dropped: "
                "rr_id=%s drive_rr=%s — ball will teleport on shot step",
                rr_id, drive_rr,
            )
        else:
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
                    previous_step=cursor_previous,
                )
            )
    elif branch == "triangle_drive_corner_kick":
        if not corner_id:
            logging.warning(
                "🔍 [TRIANGLE SKIP] branch=triangle_drive_corner_kick pass step dropped: "
                "corner_id=%s — ball will teleport on shot step",
                corner_id,
            )
        else:
            corner_target = _coord_dict(payload.get("same_side_corner_to"))
            if not corner_target:
                logging.warning(
                    "🔍 [TRIANGLE SKIP] branch=triangle_drive_corner_kick pass step dropped: "
                    "payload.same_side_corner_to=%s — ball will teleport on shot step",
                    payload.get("same_side_corner_to"),
                )
            else:
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
                        previous_step=cursor_previous,
                    )
                )
    return out


# Canonical shot-spot + closeout helpers live in ``rim_runner_step_emitter``
# so Triangle, RR, and the shared lane-pass builder stay in lock-step. Kept
# under the private aliases used throughout this module (and its tests).
_shot_spot_from_roles = shot_spot_from_roles
_closeout_contest_coord = closeout_contest_coord


def _build_triangle_shot_motion_step(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_start_coords: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    previous_step: Optional[AnimationStep] = None,
) -> Optional[AnimationStep]:
    shooter = turn_result.get("shooter") or fb_roles.get("shooter")
    shooter_id = _safe_id(shooter)
    if not shooter_id or shooter_id not in step_start_coords:
        return None

    shooter_start = step_start_coords[shooter_id]
    shot_spot = _shot_spot_from_roles(turn_result, fb_roles)
    shooter_end = shot_spot or dict(shooter_start)
    shooter_player = _player_lookup_by_id(off_lineup, def_lineup, shooter_id)
    shooter_rate = _ag_grid_per_game_sec(shooter_player, "sprint")
    t = max(0.2, _traversal_seconds(shooter_start, shooter_end, shooter_rate))

    defender_id = _safe_id(turn_result.get("defender") or fb_roles.get("defender"))
    actions, archetype, destinations, end_coords = _initialize_continuing_movement(
        step_start_coords=step_start_coords,
        previous_step=previous_step,
        step_t=t,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
    )

    actions[shooter_id] = "shoot"
    archetype[shooter_id] = "sprint"
    end_coords[shooter_id] = dict(shooter_end)

    # Primary defender: deterministic geo closeout toward the shot spot,
    # clamped by the defender's sprint rate × t (no teleport).
    if defender_id and defender_id in step_start_coords:
        actions[defender_id] = "guard_ball"
        archetype[defender_id] = "sprint"
        d_start = step_start_coords[defender_id]
        contest = _closeout_contest_coord(d_start, shooter_end)
        d_player = _player_lookup_by_id(off_lineup, def_lineup, defender_id)
        d_rate = _ag_grid_per_game_sec(d_player, "sprint")
        end_coords[defender_id] = _interrupted_coord(d_start, contest, d_rate, t)

    destinations[shooter_id] = dict(shooter_end)
    if defender_id and defender_id in step_start_coords:
        destinations[defender_id] = dict(contest)

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
        mark_fb_emitter_fallback(
            turn_result,
            "triangle",
            "fast_break_play_mismatch",
            detail=str(turn_result.get("fast_break_play")),
        )
        logging.debug(
            "🚨 [TRIANGLE EMITTER NULL] guard=fast_break_play_mismatch "
            "fast_break_play=%s result_type=%s — FE will fall to LEGACY_HANDLER",
            turn_result.get("fast_break_play"), turn_result.get("result_type"),
        )
        return None
    if game.game_state.get("_is_full_simulation", False):
        # Intentional skip in full-sim mode (no animation needed); not a fallback.
        return None

    fb_roles = turn_result.get("roles") or {}
    burst_phase = fb_roles.get("rim_runner_burst_phase")
    if not burst_phase:
        mark_fb_emitter_fallback(
            turn_result,
            "triangle",
            "missing_burst_phase",
            detail=str(list(fb_roles.keys()) if isinstance(fb_roles, dict) else None),
        )
        logging.debug(
            "🚨 [TRIANGLE EMITTER NULL] guard=missing_burst_phase result_type=%s "
            "fb_roles_keys=%s — FE will fall to LEGACY_HANDLER",
            turn_result.get("result_type"),
            list(fb_roles.keys()) if isinstance(fb_roles, dict) else None,
        )
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
        mark_fb_emitter_fallback(turn_result, "triangle", "empty_start_coords")
        logging.debug(
            "🚨 [TRIANGLE EMITTER NULL] guard=empty_start_coords result_type=%s "
            "— FE will fall to LEGACY_HANDLER",
            turn_result.get("result_type"),
        )
        return None

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
        mark_fb_emitter_fallback(turn_result, "triangle", "burst_step_none")
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
            mark_fb_emitter_fallback(
                turn_result,
                "triangle",
                "outlet_denied_defender_step_none",
            )
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
            # Triangle: RR settles out of the burst into a sprint once the
            # outlet pass goes (Rim Runner keeps its carried-forward archetype).
            rr_archetype_override="sprint",
        )
        if outlet_step is None:
            mark_fb_emitter_fallback(turn_result, "triangle", "outlet_step_none")
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

    # Open-lane quick shot: outlet receiver → RR lane pass + shot (same
    # schema chain as Rim Runner; no triangle_setup_phase on turn_result).
    if is_lane_pass_to_rr_resolution_turn(turn_result, fb_roles):
        lane_pass_steps = append_lane_pass_to_rr_resolution_steps(
            turn_result=turn_result,
            game=game,
            steps=steps,
            last_end_coords=last_end_coords,
            elapsed=elapsed,
            clock_remaining=clock_remaining,
            shot_clock_remaining=shot_clock_remaining,
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            is_away_offense=is_away_offense,
        )
        if lane_pass_steps is None:
            mark_fb_emitter_fallback(turn_result, "triangle", "lane_pass_steps_none")
            _tri_log.warning(
                "🐛 [TRIANGLE_NONE site=lane_pass_to_rr] outlet_failed=%s "
                "result_type=%s skip_outlet_pass=%s pass_attempted=%s",
                outlet_failed,
                result_type,
                skip_outlet_pass,
                turn_result.get("rim_runner_pass_attempted"),
            )
        return lane_pass_steps

    payload = _triangle_setup_payload(fb_roles)
    if not payload:
        mark_fb_emitter_fallback(turn_result, "triangle", "setup_payload_missing")
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
        mark_fb_emitter_fallback(turn_result, "triangle", "setup_step_none")
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
        previous_step=setup_step,
    )
    for decision_step in decision_steps:
        steps.append(decision_step)
        elapsed += float(decision_step["end"]["time_elapsed"])
        last_end_coords = dict(decision_step["end"]["coords"])

    if turn_result.get("fb_drive_resolution"):
        from BackEnd.engine.rim_runner_step_emitter import (
            _build_finisher_drive_resolution_steps,
        )

        dr_steps = _build_finisher_drive_resolution_steps(
            turn_result=turn_result,
            game=game,
            start_coords=last_end_coords,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            is_away_offense=is_away_offense,
            clock_remaining=clock_remaining - elapsed,
            shot_clock_remaining=shot_clock_remaining - elapsed,
            fb_roles=fb_roles,
        )
        if dr_steps:
            from BackEnd.utils.animation_step_helpers import (
                rebase_animation_step_next_indices,
            )

            rebase_animation_step_next_indices(dr_steps, len(steps))
            steps.extend(dr_steps)
            return _finalize_rr_steps(turn_result, game, steps)

    shot_motion = _build_triangle_shot_motion_step(
        turn_result=turn_result,
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        step_start_coords=last_end_coords,
        clock_remaining_at_start=clock_remaining - elapsed,
        shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
        previous_step=steps[-1] if steps else None,
    )
    if shot_motion is not None:
        steps.append(shot_motion)

    return _finalize_rr_steps(turn_result, game, steps)
