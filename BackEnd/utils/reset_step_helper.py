"""Reset step pattern — universal helper for the seam into HCO.

Reset is a **named pattern**, not a new primitive step type. It emits 1 or 2
schema-conformant steps composed of existing step types:

- **PG = BH** (1 step) — Parallel Movement with ``fixed_duration`` T = 2.0
  game-sec. BH (= PG) holds ball stationary; other 9 players drift to random
  lane spots at cruise.

- **PG ≠ BH** (2 steps):
  - **PG converge** (Parallel Movement, gated on PG arrival): BH stationary
    holding ball; PG sprints to a random spot within 10 grid Euclidean of BH
    (over-and-back clamped); other 8 drift to random lane spots at cruise.
  - **Inbound pass** (Pass, gated on ball reaches PG): BH passes to PG; PG
    stationary at converge target; other 8 continue toward lane spots.

Source turn emitters that need this beat call ``build_reset_steps`` at the
HCO seam: CR FB Defensive Stop, RR FB Hold-up + Outlet Denied, DREB → HCO,
Steal → HCO. The helper is call-site agnostic — same API for source-turn
and (future) HCO-turn consumption.

Spec: ``_documentation_master/05_Animation_System/Step_Types_System.md``.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional

from BackEnd.constants import (
    FB_PASS_MIN_GAME_SECONDS,
    HCO_STRING_SPOTS,
    RESET_INBOUND_PASS_GRID_PER_GAME_SECOND,
)
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _euclid,
    _player_lookup_by_id,
    stamp_tween_durations,
)
from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    BallState,
    ClockState,
    GridCoord,
    NextStep,
    PlayerAction,
    PlayerArchetype,
    StepEnd,
    StepStart,
)


_RESET_LANE_SPOTS = (
    "basketSpot",
    "lower lowPost",
    "upper lowPost",
    "lower midPost",
    "upper midPost",
    "midLane",
    "upper highPost",
    "lower highPost",
    "topLane",
)


def _lane_spot_coords(spot_label: str, is_away_offense: bool) -> GridCoord:
    spot = HCO_STRING_SPOTS.get(spot_label, {"x": 50, "y": 25})
    x = float(spot["x"])
    y = float(spot["y"])
    if is_away_offense:
        x = 100.0 - x
    return {"x": x, "y": y}


def _pick_pg_target(bh_coord: GridCoord, is_away_offense: bool) -> GridCoord:
    """Random point within 10 grid Euclidean of BH. Court-bounds clamped and
    over-and-back enforced: when BH is at-or-past midcourt in the attacking
    direction, PG cannot be behind midcourt."""
    angle = random.uniform(0.0, 2.0 * math.pi)
    radius = random.uniform(0.0, 10.0)
    x = float(bh_coord["x"]) + radius * math.cos(angle)
    y = float(bh_coord["y"]) + radius * math.sin(angle)
    x = max(0.0, min(100.0, x))
    y = max(0.0, min(50.0, y))
    if not is_away_offense and float(bh_coord["x"]) >= 50.0:
        x = max(50.0, x)
    elif is_away_offense and float(bh_coord["x"]) <= 50.0:
        x = min(50.0, x)
    return {"x": x, "y": y}


def _interrupted_coord(
    start: GridCoord, target: GridCoord, rate: float, t: float
) -> GridCoord:
    dist = _euclid(start, target)
    max_traversal = max(0.0, rate * t)
    if dist <= max_traversal or dist < 1e-9:
        return {"x": float(target["x"]), "y": float(target["y"])}
    ratio = max_traversal / dist
    return {
        "x": float(start["x"] + (target["x"] - start["x"]) * ratio),
        "y": float(start["y"] + (target["y"] - start["y"]) * ratio),
    }


def _is_offense_player(pid: str, off_lineup: Dict[str, Any]) -> bool:
    target = str(pid)
    for player in (off_lineup or {}).values():
        if player is None:
            continue
        if str(getattr(player, "player_id", "")) == target:
            return True
    return False


def _make_clock_pair(clock_remaining: float, shot_clock: float, t: float):
    return (
        {"clock_remaining": clock_remaining, "shot_clock_remaining": shot_clock},
        {"clock_remaining": clock_remaining - t, "shot_clock_remaining": shot_clock - t},
    )


def build_reset_steps(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    is_away_offense: bool,
    bh_id: str,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    start_index: int,
    next_step_index_after_reset: int,
) -> List[AnimationStep]:
    """Emit the Reset step(s). 1 step when BH is the PG, 2 steps otherwise.

    Args:
        off_lineup, def_lineup: Lineup dicts (positions → player objects).
        start_coords: {player_id: {x, y}} for all 10 players at Reset start
            (= end coords of the prior step).
        is_away_offense: Used for lane-spot mirroring + over-and-back clamp.
        bh_id: Ball handler at Reset start.
        clock_remaining_at_start, shot_clock_remaining_at_start: Clock state.
        start_index: Index where Reset-A will sit in the caller's steps
            array. Used to set Reset-A's ``next`` → Reset-B (= start_index+1).
        next_step_index_after_reset: Where the chain continues after Reset's
            final step. Becomes the ``next`` pointer on the last Reset step.

    Returns empty list when essential data is missing (no PG in lineup, BH
    missing from start_coords, etc.) — caller falls back to whatever they
    do when Reset isn't emitted.
    """
    pg = (off_lineup or {}).get("PG")
    pg_id = str(getattr(pg, "player_id", "")) if pg is not None else ""
    if not pg_id or bh_id not in start_coords or pg_id not in start_coords:
        return []

    bh_coord = start_coords[bh_id]
    same_player = bh_id == pg_id
    key_ids = {bh_id} if same_player else {bh_id, pg_id}

    # Pre-pick each non-key player's lane target. Persists across both
    # Reset sub-steps so the drift reads continuously.
    lane_targets: Dict[str, GridCoord] = {}
    for pid in start_coords:
        if pid in key_ids:
            continue
        spot_label = random.choice(_RESET_LANE_SPOTS)
        lane_targets[pid] = _lane_spot_coords(spot_label, is_away_offense)

    if same_player:
        return [
            _build_reset_hold_step(
                off_lineup=off_lineup,
                def_lineup=def_lineup,
                start_coords=start_coords,
                bh_id=bh_id,
                lane_targets=lane_targets,
                clock_remaining_at_start=clock_remaining_at_start,
                shot_clock_remaining_at_start=shot_clock_remaining_at_start,
                next_step_index=next_step_index_after_reset,
            )
        ]

    pg_target = _pick_pg_target(bh_coord, is_away_offense)

    step_a = _build_reset_pg_converge_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=start_coords,
        bh_id=bh_id,
        pg_id=pg_id,
        pg_target=pg_target,
        lane_targets=lane_targets,
        clock_remaining_at_start=clock_remaining_at_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_start,
        next_step_index=start_index + 1,
    )

    step_b_start_coords = dict(step_a["end"]["coords"])
    a_clock = step_a["end"]["clock"]
    step_b = _build_reset_inbound_pass_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=step_b_start_coords,
        bh_id=bh_id,
        pg_id=pg_id,
        pg_target=pg_target,
        lane_targets=lane_targets,
        clock_remaining_at_start=a_clock["clock_remaining"],
        shot_clock_remaining_at_start=a_clock["shot_clock_remaining"],
        next_step_index=next_step_index_after_reset,
    )

    return [step_a, step_b]


def _build_reset_hold_step(
    *,
    off_lineup,
    def_lineup,
    start_coords: Dict[str, GridCoord],
    bh_id: str,
    lane_targets: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> AnimationStep:
    """PG = BH single step: 2-second hold, others drift to lane spots."""
    t = 2.0
    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in start_coords}
    archetype: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in start_coords}
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {pid: dict(coord) for pid, coord in start_coords.items()}

    actions[bh_id] = "handle_ball"

    for pid, target in lane_targets.items():
        if pid not in start_coords:
            continue
        actions[pid] = "cut" if _is_offense_player(pid, off_lineup) else "guard_offball"
        archetype[pid] = "standard"
        destinations[pid] = dict(target)
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, "standard")
        end_coords[pid] = _interrupted_coord(start_coords[pid], target, rate, t)

    ball_start: BallState = {"owner_player_id": bh_id}
    ball_end: BallState = {"owner_player_id": bh_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": float(t),
        "metadata": {"reason": "reset_pg_eq_bh_hold"},
    }

    clock_start, clock_end = _make_clock_pair(
        clock_remaining_at_start, shot_clock_remaining_at_start, t
    )

    start: StepStart = {
        "coords": dict(start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_reset_pg_converge_step(
    *,
    off_lineup,
    def_lineup,
    start_coords: Dict[str, GridCoord],
    bh_id: str,
    pg_id: str,
    pg_target: GridCoord,
    lane_targets: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> AnimationStep:
    """Reset-A: PG sprints to receive spot; BH stationary holds ball; others
    drift to lane spots. Gate = PG reaches target."""
    pg_player = _player_lookup_by_id(off_lineup, def_lineup, pg_id)
    pg_rate = _ag_grid_per_game_sec(pg_player, "sprint")
    pg_start = start_coords[pg_id]
    t = max(0.1, _euclid(pg_start, pg_target) / pg_rate if pg_rate > 0 else 0.5)

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in start_coords}
    archetype: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in start_coords}
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {pid: dict(coord) for pid, coord in start_coords.items()}

    actions[bh_id] = "handle_ball"

    actions[pg_id] = "cut"
    archetype[pg_id] = "sprint"
    destinations[pg_id] = dict(pg_target)
    end_coords[pg_id] = dict(pg_target)

    for pid, target in lane_targets.items():
        if pid not in start_coords:
            continue
        actions[pid] = "cut" if _is_offense_player(pid, off_lineup) else "guard_offball"
        archetype[pid] = "standard"
        destinations[pid] = dict(target)
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, "standard")
        end_coords[pid] = _interrupted_coord(start_coords[pid], target, rate, t)

    ball_start: BallState = {"owner_player_id": bh_id}
    ball_end: BallState = {"owner_player_id": bh_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": pg_id,
            "target_coords": dict(pg_target),
        },
    }

    clock_start, clock_end = _make_clock_pair(
        clock_remaining_at_start, shot_clock_remaining_at_start, t
    )

    start: StepStart = {
        "coords": dict(start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_reset_inbound_pass_step(
    *,
    off_lineup,
    def_lineup,
    start_coords: Dict[str, GridCoord],
    bh_id: str,
    pg_id: str,
    pg_target: GridCoord,
    lane_targets: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> AnimationStep:
    """Reset-B: BH passes to PG; PG stationary at converge target; other 8
    continue toward lane spots. Gate = ball reaches PG."""
    bh_coord = start_coords[bh_id]
    pg_coord = start_coords[pg_id]  # = pg_target after Reset-A
    dist = _euclid(bh_coord, pg_coord)
    t = max(FB_PASS_MIN_GAME_SECONDS, dist / float(RESET_INBOUND_PASS_GRID_PER_GAME_SECOND))

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in start_coords}
    archetype: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in start_coords}
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {pid: dict(coord) for pid, coord in start_coords.items()}

    actions[bh_id] = "pass"
    actions[pg_id] = "receive"

    for pid, target in lane_targets.items():
        if pid not in start_coords:
            continue
        actions[pid] = "cut" if _is_offense_player(pid, off_lineup) else "guard_offball"
        archetype[pid] = "standard"
        destinations[pid] = dict(target)
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, "standard")
        end_coords[pid] = _interrupted_coord(start_coords[pid], target, rate, t)

    ball_start: BallState = {"owner_player_id": bh_id}
    ball_end: BallState = {"owner_player_id": pg_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": bh_id,
            "to_player_id": pg_id,
            "target_coords": dict(pg_target),
        },
    }

    clock_start, clock_end = _make_clock_pair(
        clock_remaining_at_start, shot_clock_remaining_at_start, t
    )

    start: StepStart = {
        "coords": dict(start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}
