"""Universal Fast Break outlet-pass step emitter (SS&S core).

Shared core for the two **live** FB outlet-pass builders — RR/Triangle
(`rim_runner_step_emitter._build_outlet_pass_step`) and Covert Release
(`covert_release_step_emitter._build_simplified_outlet_pass_step`). Both were
byte-for-byte identical on the pass mechanics (sharp/sloppy rate gating, T,
stationary passer/receiver, ball transfer, `ball_reaches_player` trigger,
interrupted-coord math, tween stamping) and diverged only on **who-moves-where**
for the non-key cast:

  * RR/Triangle: movers are resolver-authored off ``rim_runner_burst_phase``
    (RR sprints to ``rr_to``, outlet defender guards, others cut to explicit
    spots) because the outlet chains into a burst + lane pass.
  * Covert Release: no resolver payload — the cast does a generic forward drift
    before the drive.

That divergence is passed in as ``mover_targets`` (the "flavor"): a
``{player_id: (target_coord, archetype, action)}`` map the caller builds. The
core renders it identically for both.

NOTE: this is scoped to the FB outlet pass on purpose (no dependency on the
engine-wide ``transition_bridge.build_pass_step``) to keep blast radius zero on
HCO/BIP/SIP/Reset. The flag-gated CR *legacy* full outlet builder
(`covert_release._build_outlet_pass_step`) is intentionally NOT migrated — it
dies with the ``USE_FB_DRIVE_RESOLUTION_CR`` retirement.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from BackEnd.constants import (
    FB_OUTLET_QUALITY_THRESHOLD,
    FB_PASS_GRID_SPOTS_PER_GAME_SECOND,
    FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY,
    FB_PASS_MIN_GAME_SECONDS,
)
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _euclid,
    _player_lookup_by_id,
)
from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    BallState,
    ClockState,
    GridCoord,
    PlayerAction,
    PlayerArchetype,
    StepEnd,
    StepStart,
)

# (target_coord, movement archetype, per-player action)
MoverTarget = Tuple[GridCoord, PlayerArchetype, PlayerAction]


def _interrupted_coord(
    start: Optional[GridCoord],
    target: Optional[GridCoord],
    rate: float,
    t: float,
) -> GridCoord:
    """Position along ``start``→``target`` at ``rate × t``; clamped to
    ``target`` if the player completes the traversal within ``t`` seconds."""
    if start is None and target is None:
        return {"x": 50.0, "y": 25.0}
    if start is None:
        return {"x": float(target["x"]), "y": float(target["y"])}
    if target is None:
        return {"x": float(start["x"]), "y": float(start["y"])}
    dist = _euclid(start, target)
    max_traversal = max(0.0, rate * t)
    if dist <= max_traversal or dist == 0.0:
        return {"x": float(target["x"]), "y": float(target["y"])}
    ratio = max_traversal / dist
    return {
        "x": float(start["x"] + (target["x"] - start["x"]) * ratio),
        "y": float(start["y"] + (target["y"] - start["y"]) * ratio),
    }


def _stamp_tween_durations(
    start: StepStart,
    end_coords: Dict[str, GridCoord],
    step_t: float,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Stamp per-player natural tween durations (game-seconds) so fast movers
    idle at their end coord instead of lazily drifting across step T."""
    start_coords = start.get("coords") or {}
    archetype = start.get("archetype") or {}
    durations: Dict[str, float] = {}
    for pid, sc in start_coords.items():
        ec = end_coords.get(pid)
        if ec is None:
            continue
        dist = _euclid(sc, ec)
        if dist < 1e-6:
            continue
        arch = archetype.get(pid, "standard")
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch)
        if rate <= 0:
            continue
        durations[pid] = float(min(dist / rate, step_t))
    if durations:
        start["tween_durations"] = durations


def build_fb_outlet_pass_step(
    *,
    passer_id: str,
    receiver_id: str,
    start_coords: Dict[str, GridCoord],
    mover_targets: Dict[str, MoverTarget],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
    outlet_score: Optional[int] = None,
) -> Optional[AnimationStep]:
    """Build the FB outlet-pass ``AnimationStep`` (rebounder → outlet receiver).

    Passer/receiver stay put while the ball arcs (gated on
    ``ball_reaches_player``); the non-key cast moves per ``mover_targets`` (the
    caller-supplied flavor), interrupted at step T so nobody snaps. Pass speed is
    gated on ``outlet_score`` (sharp vs sloppy). Returns ``None`` if passer /
    receiver are invalid or unseated.
    """
    if (
        not passer_id
        or not receiver_id
        or passer_id == receiver_id
        or passer_id not in start_coords
        or receiver_id not in start_coords
    ):
        logging.warning(
            "🐛 [FB_OUTLET_PASS_NONE] passer_id=%s receiver_id=%s "
            "in_start=(%s,%s)",
            passer_id, receiver_id,
            passer_id in start_coords, receiver_id in start_coords,
        )
        return None

    passer_coord = start_coords[passer_id]
    receiver_coord = start_coords[receiver_id]

    pass_rate = (
        float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND)
        if outlet_score is not None and outlet_score >= FB_OUTLET_QUALITY_THRESHOLD
        else float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY)
    )
    dist = _euclid(passer_coord, receiver_coord)
    t = max(float(FB_PASS_MIN_GAME_SECONDS), dist / pass_rate)

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }

    actions[passer_id] = "pass"
    actions[receiver_id] = "receive"

    for pid, (target, arch, action) in mover_targets.items():
        if pid in (passer_id, receiver_id) or pid not in start_coords:
            continue
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch) if player else 12.0
        end_coords[pid] = _interrupted_coord(start_coords[pid], target, rate, t)
        destinations[pid] = {"x": float(target["x"]), "y": float(target["y"])}
        actions[pid] = action
        archetype[pid] = arch

    # Ball: attached to passer at start (carried from the prior step's
    # BallAttached(passer)), attached to receiver at end. The schema engine's
    # renderBallTransition detects the ownership change, detaches, tweens world
    # coords, and reattaches — without this it renders glued to the passer.
    ball_start: BallState = {"owner_player_id": passer_id}
    ball_end: BallState = {"owner_player_id": receiver_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": passer_id,
            "to_player_id": receiver_id,
            "target_coords": dict(receiver_coord),
            "outlet_score": int(outlet_score) if outlet_score is not None else None,
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
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    step: AnimationStep = {"start": start, "end": end}
    try:
        from BackEnd.engine.fb_step_state import (
            project_animation_step_through_fast_break_state,
        )

        return project_animation_step_through_fast_break_state(
            step,
            index=0,
            result={"current_turn": "FAST_BREAK"},
        )
    except Exception as e:
        logging.warning(
            "🐛 [FB_OUTLET_PASS_STEPSTATE] projection failed passer_id=%s "
            "receiver_id=%s: %s",
            passer_id,
            receiver_id,
            e,
        )
        return step
