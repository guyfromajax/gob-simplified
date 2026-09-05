"""Transition bridge step builders — emit ``AnimationStep[]`` that close
cross-turn seams where setup logic snaps ``player.coords`` before the
destination turn animates. All bridges read the universal
``prior_turn["final_coords"]`` (stamped by ``_append_turn``) and produce
schema-conformant steps that the destination turn's emitter prepends.

Naming convention: ``build_<source>_to_<destination>_bridge_steps``.

Long-term, each bridge collapses into the destination turn's native
emitter step 0 — the helper interface is identical so the migration is a
no-op rename of the call site.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Union

from BackEnd.constants import (
    INBOUND_PASS_GRID_PER_GAME_SECOND,
    FB_PASS_MIN_GAME_SECONDS,
    HCO_STRING_SPOTS,
    RESET_INBOUND_PASS_GRID_PER_GAME_SECOND,
)
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _euclid,
    _player_lookup_by_id,
    pass_arrival_sfx,
    pass_release_sfx,
    stamp_tween_durations,
)
from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    BallInFlight,
    BallState,
    ClockState,
    GridCoord,
    PlayerAction,
    PlayerArchetype,
    StepEnd,
    StepStart,
)


_HCO_LANE_DRIFT_SPOTS = (
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


# Kickout outlet spot pools — ported from legacy OREB Kickout
# (FrontEnd/static/js/phaser/animation/turnAnimation.js runOffensiveReboundKickoutSetup).
# Receiver outlets are perimeter spots out beyond the lane; passer (BH)
# outlets are the central/lane-adjacent spots from which the kickout pass
# is delivered. Vertical-half pairing constraint (upper / lower / central)
# keeps the BH and receiver on the same side of the floor.
_KICKOUT_RECEIVER_OUTLET_SPOTS = (
    "key",
    "deep key",
    "upper midWing",
    "deep upper wing",
    "lower midWing",
    "deep lower wing",
)
_KICKOUT_PASSER_OUTLET_BASE = ("topLane",)  # always allowed
_KICKOUT_PASSER_OUTLET_KEY = "key"           # allowed unless receiver took it
_KICKOUT_PASSER_OUTLET_UPPER = "upper apex"  # only if receiver upper or central
_KICKOUT_PASSER_OUTLET_LOWER = "lower apex"  # only if receiver lower or central


def _lane_spot_coords(spot_label: str, is_away_offense: bool) -> GridCoord:
    spot = HCO_STRING_SPOTS.get(spot_label, {"x": 50, "y": 25})
    x = float(spot["x"])
    y = float(spot["y"])
    if is_away_offense:
        x = 100.0 - x
    return {"x": x, "y": y}


def _pick_pg_receive_target(
    bh_coord: GridCoord, is_away_offense: bool, radius_grid: float = 10.0
) -> GridCoord:
    """Random point within ``radius_grid`` grid Euclidean of BH (default 10).
    Court-bounds clamped and over-and-back enforced: when BH is at-or-past
    midcourt in the attacking direction, PG cannot be behind midcourt."""
    angle = random.uniform(0.0, 2.0 * math.pi)
    radius = random.uniform(0.0, float(radius_grid))
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
    """Where the player ends up after moving from ``start`` toward ``target``
    at ``rate`` (grid/game-sec) for ``t`` game-seconds. Clamps at target."""
    dist = _euclid(start, target)
    max_traversal = max(0.0, rate * t)
    if dist <= max_traversal or dist < 1e-9:
        return {"x": float(target["x"]), "y": float(target["y"])}
    ratio = max_traversal / dist
    return {
        "x": float(start["x"] + (target["x"] - start["x"]) * ratio),
        "y": float(start["y"] + (target["y"] - start["y"]) * ratio),
    }


def _pick_kickout_receiver_outlet(is_away_offense: bool) -> tuple:
    """Pick a receiver outlet spot (perimeter) at random. Returns
    (spot_label, GridCoord). Label is used downstream to constrain the
    BH outlet to a matching vertical half."""
    label = random.choice(_KICKOUT_RECEIVER_OUTLET_SPOTS)
    return label, _lane_spot_coords(label, is_away_offense)


def _pick_kickout_passer_outlet(
    receiver_spot_label: str,
    is_away_offense: bool,
) -> GridCoord:
    """Pick a passer (BH) outlet spot, constrained to the same vertical
    half as the receiver. Mirrors the legacy logic at
    runOffensiveReboundKickoutSetup."""
    is_receiver_upper = "upper" in receiver_spot_label
    is_receiver_lower = "lower" in receiver_spot_label
    is_receiver_central = receiver_spot_label in ("key", "deep key")

    options: List[str] = list(_KICKOUT_PASSER_OUTLET_BASE)
    if receiver_spot_label != _KICKOUT_PASSER_OUTLET_KEY:
        options.append(_KICKOUT_PASSER_OUTLET_KEY)
    if is_receiver_central or is_receiver_upper:
        options.append(_KICKOUT_PASSER_OUTLET_UPPER)
    if is_receiver_central or is_receiver_lower:
        options.append(_KICKOUT_PASSER_OUTLET_LOWER)

    chosen = random.choice(options)
    return _lane_spot_coords(chosen, is_away_offense)


def build_kickout_non_core_targets(
    *,
    start_coords: Dict[str, GridCoord],
    setup_coords: Optional[Dict[str, GridCoord]],
    key_ids: set[str],
    is_away_offense: bool,
) -> Dict[str, GridCoord]:
    """Build persistent non-core movement targets for kickout sub-steps.

    HCO entry kickout can pass actual HCO step-0 ``setup_coords``. OREB
    kickout is emitted before the next HCO turn exists, so it falls back to
    organic lane drift targets. Either way, targets are chosen once and reused
    across positioning + pass so movement reads continuously.
    """
    targets: Dict[str, GridCoord] = {}
    setup = setup_coords or {}
    for pid in start_coords:
        if pid in key_ids:
            continue
        target = setup.get(pid)
        if isinstance(target, dict) and "x" in target and "y" in target:
            targets[pid] = {"x": float(target["x"]), "y": float(target["y"])}
        else:
            spot_label = random.choice(_HCO_LANE_DRIFT_SPOTS)
            targets[pid] = _lane_spot_coords(spot_label, is_away_offense)
    return targets


def _offense_player_ids(off_lineup: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for player in (off_lineup or {}).values():
        if player is None:
            continue
        pid = getattr(player, "player_id", None)
        if pid is not None:
            ids.append(str(pid))
    return ids


def _offense_arrival_times(
    *,
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    bh_id: str,
    bh_archetype: PlayerArchetype,
    other_archetype: PlayerArchetype,
) -> Dict[str, float]:
    """Per-offense-player natural travel time to ``end_coords`` target (0 if already there)."""
    arrival: Dict[str, float] = {}
    for pid in _offense_player_ids(off_lineup):
        sc = start_coords.get(pid)
        ec = end_coords.get(pid)
        if not sc or not ec:
            arrival[pid] = 0.0
            continue
        dist = _euclid(sc, ec)
        if dist < 1e-6:
            arrival[pid] = 0.0
            continue
        arch = bh_archetype if pid == bh_id else other_archetype
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch)
        arrival[pid] = dist / rate if rate > 0 else 0.0
    return arrival


def build_walk_up_step(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
    bh_id: str,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
    bh_archetype: PlayerArchetype = "standard",
    other_archetype: PlayerArchetype = "standard",
    gate_player_ids: Optional[List[str]] = None,
    gate_offense_required_count: Optional[int] = None,
    gate_mandatory_player_ids: Optional[List[str]] = None,
    metadata_reason: str = "walk_up",
    min_t_game_sec: float = 0.05,
) -> AnimationStep:
    """Universal "walk up" step. All 10 players move from ``start_coords`` to
    ``end_coords``; ``bh_id`` dribbles.

    Step duration (T) is gated on the slowest player in ``gate_player_ids``.
    Non-gate players move at their archetype rate; if their natural travel
    time exceeds T, they end at the interrupted coord (= start + rate × T)
    rather than the full target — preserves natural movement speed and
    avoids snap teleports. If they'd arrive before T, they reach target and
    idle there until T elapses.

    When ``gate_offense_required_count`` is set (FCP BIP setup only today),
    T = the arrival time of the Nth-fastest offensive player among the five
    on-court (e.g. 4 → advance once four offense players reach destination).
    Optional ``gate_mandatory_player_ids`` (combinable with the N-of-M gate)
    raises T to each listed player's natural arrival time so they always
    reach destination — used so the inbound passer reaches the baseline OOB
    spot before the hold/pass steps.

    When ``gate_player_ids`` is ``None`` (default), gates on the slowest of
    ALL players — preserves legacy behavior for callers that want everyone
    to settle before advancing.
    """
    if gate_player_ids and gate_offense_required_count is not None:
        raise ValueError(
            "build_walk_up_step: gate_player_ids and gate_offense_required_count are mutually exclusive"
        )
    # Per-player natural travel time (dist / archetype rate).
    natural_t: Dict[str, float] = {}
    rates: Dict[str, float] = {}
    for pid, sc in start_coords.items():
        ec = end_coords.get(pid)
        if not ec:
            continue
        dist = _euclid(sc, ec)
        if dist < 1e-6:
            continue
        arch = bh_archetype if pid == bh_id else other_archetype
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch)
        if rate <= 0:
            continue
        natural_t[pid] = dist / rate
        rates[pid] = rate

    # Step T = slowest among the gate players (or all players when no gate set).
    # Also record which player drove the slowest_t so the advance_trigger
    # metadata names the actual gate, not whichever player happens to have
    # the longest start→end distance (which can be a non-gate defender when
    # gate_player_ids restricts the timing to a small subset).
    gate_slowest_id: Optional[str] = None
    slowest_t = 0.0
    use_offense_n_of_m = gate_offense_required_count is not None
    if use_offense_n_of_m:
        offense_arrivals = _offense_arrival_times(
            start_coords=start_coords,
            end_coords=end_coords,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            bh_id=bh_id,
            bh_archetype=bh_archetype,
            other_archetype=other_archetype,
        )
        required = max(1, int(gate_offense_required_count or 1))
        sorted_arrivals = sorted(offense_arrivals.items(), key=lambda item: item[1])
        if sorted_arrivals:
            idx = min(required, len(sorted_arrivals)) - 1
            gate_slowest_id, slowest_t = sorted_arrivals[idx]
        else:
            gate_slowest_id, slowest_t = None, 0.0
        mandatory_ids = {str(p) for p in (gate_mandatory_player_ids or []) if p}
        for pid in sorted(mandatory_ids, key=str):  # sorted(): set iteration is hash-ordered; see projects/bugs.md (PYTHONHASHSEED)
            mandatory_t = offense_arrivals.get(pid, natural_t.get(pid, 0.0))
            if mandatory_t > slowest_t:
                slowest_t = mandatory_t
                gate_slowest_id = pid
    elif gate_player_ids:
        gate_set = {str(g) for g in gate_player_ids if g}
        gate_items = [(pid, ti) for pid, ti in natural_t.items() if pid in gate_set]
        if gate_items:
            gate_slowest_id, slowest_t = max(gate_items, key=lambda item: item[1])
    else:
        gate_items = list(natural_t.items())
        if gate_items:
            gate_slowest_id, slowest_t = max(gate_items, key=lambda item: item[1])
    t = max(float(min_t_game_sec), slowest_t)

    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    final_end_coords: Dict[str, GridCoord] = {}

    for pid, sc in start_coords.items():
        target = end_coords.get(pid, sc)
        destinations[pid] = dict(target)
        # End coord: gate players + fast-enough non-gate players → full target.
        # Slower non-gate players → interrupted at their natural rate within T.
        player_rate = rates.get(pid, 0.0)
        if player_rate > 0 and pid in natural_t and natural_t[pid] > t:
            final_end_coords[pid] = _interrupted_coord(sc, target, player_rate, t)
        else:
            final_end_coords[pid] = dict(target)
        if pid == bh_id:
            actions[pid] = "handle_ball"
            archetype[pid] = bh_archetype
        else:
            archetype[pid] = other_archetype
            actions[pid] = "cut" if _is_offense_player(pid, off_lineup) else "guard_offball"

    ball_state: BallState = {"owner_player_id": bh_id}

    # Prefer the gate player that drove slowest_t. Fall back to overall
    # slowest-mover only when no gate player moved (e.g. all gate members
    # were stationary, which would have produced T = min_t floor above).
    gate_id = gate_slowest_id or _slowest_mover_id(start_coords, final_end_coords)
    gate_target = final_end_coords.get(gate_id) if gate_id else None
    if use_offense_n_of_m and gate_offense_required_count:
        n_of_m_meta: Dict[str, Any] = {
            "required_count": int(gate_offense_required_count),
            "total_offense_count": len(_offense_player_ids(off_lineup)),
            "gate_player_id": str(gate_id) if gate_id else None,
            "reason": metadata_reason,
        }
        if gate_mandatory_player_ids:
            n_of_m_meta["mandatory_player_ids"] = [
                str(p) for p in gate_mandatory_player_ids if p
            ]
        advance_trigger: AdvanceTrigger = {
            "condition": "offense_players_reach_position",
            "T_game_seconds": float(t),
            "metadata": n_of_m_meta,
        }
    elif gate_id and gate_target:
        advance_trigger: AdvanceTrigger = {
            "condition": "player_reaches_position",
            "T_game_seconds": float(t),
            "metadata": {
                "target_player_id": str(gate_id),
                "target_coords": {
                    "x": float(gate_target["x"]),
                    "y": float(gate_target["y"]),
                },
                "reason": metadata_reason,
            },
        }
    else:
        advance_trigger = {
            "condition": "fixed_duration",
            "T_game_seconds": float(t),
            "metadata": {"reason": f"{metadata_reason}_fallback"},
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
        "ball": ball_state,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": final_end_coords,
        "ball": ball_state,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    stamp_tween_durations(start, final_end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def build_handoff_step(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    bh_id: str,
    receiver_id: str,
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
    pass_speed_grid_per_game_sec: float = float(RESET_INBOUND_PASS_GRID_PER_GAME_SECOND),
    metadata_reason: str = "handoff",
    setup_coords: Optional[Dict[str, GridCoord]] = None,
    converge_radius_grid: float = 10.0,
) -> List[AnimationStep]:
    """Universal handoff beat — BH delivers ball to ``receiver_id`` (PG).

    Three cases:
    - **BH = PG (hold)**: 1 step. BH stays put holding ball; other 9 drift
      toward HCO lane spots at standard. Duration fixed at 1.0 game-sec.
      Gate = fixed_duration.
    - **BH ≠ PG, sub-step A (PG converge)**: PG sprints to a random spot
      within 10 grid Euclidean of BH (court-clamped, over-and-back
      enforced). BH stationary. Other 8 drift toward lane spots at
      standard (interrupted if step ends first). Gate = PG reaches target.
    - **BH ≠ PG, sub-step B (Inbound pass)**: BH passes to PG at converge
      target. Other 8 continue drifting at standard. Gate = ball reaches PG.

    Lane targets are pre-picked once and persist across all sub-steps.

    Returns ``[]`` when essential data is missing.
    """
    if not bh_id or not receiver_id:
        return []
    if bh_id not in start_coords or receiver_id not in start_coords:
        return []

    # Pre-pick lane targets for non-key players. Persists across sub-steps
    # so the drift reads as continuous motion.
    #
    # When the caller passes `setup_coords` (the actual HCO step 0 positions),
    # we drift non-key players toward THEIR setup spots instead of random
    # `_HCO_LANE_DRIFT_SPOTS`. This makes the Handoff → Walk Up seam
    # continuous: each non-key player has a single target (their setup spot)
    # that they progress toward across Handoff and Walk Up, instead of
    # teleporting from a random lane spot to their setup spot at the
    # Walk Up's start. Falls back to the random lane spots when setup_coords
    # is not provided (e.g., legacy callers).
    key_ids = {bh_id, receiver_id}
    lane_targets: Dict[str, GridCoord] = {}
    for pid in start_coords:
        if pid in key_ids:
            continue
        if setup_coords and pid in setup_coords:
            lane_targets[pid] = dict(setup_coords[pid])
        else:
            spot_label = random.choice(_HCO_LANE_DRIFT_SPOTS)
            lane_targets[pid] = _lane_spot_coords(spot_label, is_away_offense)

    # BH = PG: emit a single "hold" sub-step (BH stays, others drift).
    if bh_id == receiver_id:
        hold_step = _build_handoff_hold_substep(
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            start_coords=start_coords,
            bh_id=bh_id,
            lane_targets=lane_targets,
            hold_seconds=1.0,
            clock_remaining_at_start=clock_remaining_at_start,
            shot_clock_remaining_at_start=shot_clock_remaining_at_start,
            next_step_index=next_step_index,
            metadata_reason=f"{metadata_reason}_hold",
        )
        return [hold_step]

    bh_coord = start_coords[bh_id]
    pg_target = _pick_pg_receive_target(
        bh_coord, is_away_offense, radius_grid=converge_radius_grid
    )

    step_a = _build_handoff_converge_substep(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=start_coords,
        bh_id=bh_id,
        pg_id=receiver_id,
        pg_target=pg_target,
        lane_targets=lane_targets,
        clock_remaining_at_start=clock_remaining_at_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_start,
        next_step_index=next_step_index + 1,
        metadata_reason=f"{metadata_reason}_converge",
    )

    step_b_start_coords = dict(step_a["end"]["coords"])
    a_clock = step_a["end"]["clock"]
    step_b = _build_handoff_pass_substep(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=step_b_start_coords,
        bh_id=bh_id,
        pg_id=receiver_id,
        lane_targets=lane_targets,
        clock_remaining_at_start=a_clock["clock_remaining"],
        shot_clock_remaining_at_start=a_clock["shot_clock_remaining"],
        next_step_index=next_step_index + 2,  # post-fixed by composer
        pass_speed_grid_per_game_sec=pass_speed_grid_per_game_sec,
        metadata_reason=f"{metadata_reason}_pass",
    )
    return [step_a, step_b]


def _build_handoff_hold_substep(
    *,
    off_lineup,
    def_lineup,
    start_coords: Dict[str, GridCoord],
    bh_id: str,
    lane_targets: Dict[str, GridCoord],
    hold_seconds: float,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
    metadata_reason: str,
) -> AnimationStep:
    """BH=PG hold sub-step: BH stays put holding ball; other 9 drift to
    lane spots at standard (interrupted if they don't reach in ``hold_seconds``).
    Gate = fixed_duration."""
    t = float(hold_seconds)

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

    ball_state: BallState = {"owner_player_id": bh_id}
    advance_trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": float(t),
        "metadata": {"reason": metadata_reason},
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
        "ball": ball_state,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_state,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_handoff_converge_substep(
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
    metadata_reason: str,
) -> AnimationStep:
    """Sub-step A: PG sprints to receive target; BH holds ball; others drift."""
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

    ball_state: BallState = {"owner_player_id": bh_id}
    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": pg_id,
            "target_coords": dict(pg_target),
            "reason": metadata_reason,
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
        "ball": ball_state,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_state,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


class _ContinueFromPrevious:
    """Sentinel default for ``build_pass_step(continuing_targets=...)``.

    Means "carry each player's unfinished movement forward from
    ``previous_step``". It exists so that FREEZING the other eight players is
    something a caller has to type, rather than what happens when nobody
    decides. See projects/animation_cleanup_findings.md §2 (root cause #1):
    the old ``None`` default made every non-opted-in builder freeze the court,
    which is why the fast-break freeze survived five or six fixes -- each fix
    populated one call site and the default reintroduced it at the next.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "CONTINUE_FROM_PREVIOUS"


CONTINUE_FROM_PREVIOUS = _ContinueFromPrevious()


def _continuing_targets_from_previous_step(
    *,
    previous_step: Optional[AnimationStep],
    start_coords: Dict[str, GridCoord],
    exclude: tuple = (),
) -> Optional[Dict[str, GridCoord]]:
    """Derive per-player continuing targets from the prior step's intent.

    ``end.coords`` says where a player actually reached; the prior step's
    ``start.destination`` retains where he was still TRYING to go. Continue only
    players with meaningful remaining distance. Mirrors the rule in
    ``rim_runner_step_emitter._initialize_continuing_movement``; kept local so
    ``utils`` does not import from ``engine``.

    Returns ``None`` (freeze) when there is no prior step to read, so a caller
    that cannot supply one degrades to the old behaviour instead of raising.
    """
    if not previous_step:
        return None

    prior_start = previous_step.get("start") or {}
    prior_destinations = prior_start.get("destination") or {}

    targets: Dict[str, GridCoord] = {}
    for pid, start_coord in start_coords.items():
        if pid in exclude:
            continue
        target = prior_destinations.get(pid)
        if not target:
            continue
        try:
            coord: GridCoord = {"x": float(target["x"]), "y": float(target["y"])}
        except (KeyError, TypeError, ValueError):
            continue
        if _euclid(start_coord, coord) < 1e-6:
            continue
        targets[pid] = coord

    return targets or None


def build_pass_step(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    passer_id: str,
    receiver_id: str,
    continuing_targets: Union[Dict[str, GridCoord], None, _ContinueFromPrevious] = (
        CONTINUE_FROM_PREVIOUS
    ),
    previous_step: Optional[AnimationStep] = None,
    continuing_archetype: PlayerArchetype = "standard",
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
    pass_speed_grid_per_game_sec: float = float(RESET_INBOUND_PASS_GRID_PER_GAME_SECOND),
    metadata_reason: str = "pass",
) -> AnimationStep:
    """Universal Pass step. Strict shape: passer + receiver stationary while
    the ball arcs between them; gated on ``ball_reaches_player``.

    Other 8 players drift toward per-player ``continuing_targets`` at
    ``continuing_archetype`` rate (interrupted by step duration).

    ``continuing_targets`` defaults to ``CONTINUE_FROM_PREVIOUS``: targets are
    derived from ``previous_step``'s retained destinations, so players who were
    still moving keep moving. Pass an explicit dict to choose targets, or an
    explicit ``None`` to freeze everyone except passer/receiver -- the freeze is
    now a decision a caller states, not the default nobody chose.

    Step duration = pass distance / pass speed (floor: FB_PASS_MIN_GAME_SECONDS).

    Used wherever one player passes to another with optional non-key drift:
    BIP/SIP inbound passes, Reset's inbound-pass sub-step, future FB lane
    passes (after we settle the leading-pass math separately).
    """
    if passer_id not in start_coords or receiver_id not in start_coords:
        # Degenerate input — caller should fall back.
        raise ValueError(f"build_pass_step: passer or receiver missing from start_coords")

    passer_coord = start_coords[passer_id]
    receiver_coord = start_coords[receiver_id]
    dist = _euclid(passer_coord, receiver_coord)
    rate = max(1e-6, pass_speed_grid_per_game_sec)
    t = max(FB_PASS_MIN_GAME_SECONDS, dist / rate)

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in start_coords}
    archetype: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in start_coords}
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {pid: dict(coord) for pid, coord in start_coords.items()}

    actions[passer_id] = "pass"
    actions[receiver_id] = "receive"

    if continuing_targets is CONTINUE_FROM_PREVIOUS:
        continuing_targets = _continuing_targets_from_previous_step(
            previous_step=previous_step,
            start_coords=start_coords,
            exclude=(passer_id, receiver_id),
        )

    if continuing_targets:
        for pid, target in continuing_targets.items():
            if pid not in start_coords or pid in (passer_id, receiver_id):
                continue
            actions[pid] = "cut" if _is_offense_player(pid, off_lineup) else "guard_offball"
            archetype[pid] = continuing_archetype
            destinations[pid] = dict(target)
            player = _player_lookup_by_id(off_lineup, def_lineup, pid)
            rate_player = _ag_grid_per_game_sec(player, continuing_archetype)
            end_coords[pid] = _interrupted_coord(start_coords[pid], target, rate_player, t)

    ball_start: BallState = {
        "from_player_id": str(passer_id),
        "to_player_id": str(receiver_id),
        "current_coords": dict(passer_coord),
    }
    ball_end: BallState = {"owner_player_id": str(receiver_id)}

    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": str(passer_id),
            "to_player_id": str(receiver_id),
            "reason": metadata_reason,
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
    # Pass / Reception SFX (SFX_System.md). Covers every caller of
    # ``build_pass_step`` — BIP/SIP inbound passes, Reset's inbound-pass
    # sub-step, Handoff/Kickout pass sub-steps. FB outlet passes use a
    # dedicated emitter (covert_release_step_emitter) and don't route
    # through here, so they're correctly excluded per the doc.
    passer_player = _player_lookup_by_id(off_lineup, def_lineup, passer_id)
    receiver_player = _player_lookup_by_id(off_lineup, def_lineup, receiver_id)
    start["sfx_on_ball_release"] = pass_release_sfx(passer_player)
    start["sfx_on_ball_arrival"] = pass_arrival_sfx(receiver_player)
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_handoff_pass_substep(
    *,
    off_lineup,
    def_lineup,
    start_coords: Dict[str, GridCoord],
    bh_id: str,
    pg_id: str,
    lane_targets: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
    pass_speed_grid_per_game_sec: float,
    metadata_reason: str,
) -> AnimationStep:
    """Sub-step B of the handoff beat — thin wrapper around build_pass_step
    that supplies lane drift targets for the non-key 8 players."""
    return build_pass_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=start_coords,
        passer_id=bh_id,
        receiver_id=pg_id,
        continuing_targets=lane_targets,
        continuing_archetype="standard",
        clock_remaining_at_start=clock_remaining_at_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_start,
        next_step_index=next_step_index,
        pass_speed_grid_per_game_sec=pass_speed_grid_per_game_sec,
        metadata_reason=metadata_reason,
    )


def build_kickout_step(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    bh_id: str,
    receiver_id: str,
    setup_coords: Optional[Dict[str, GridCoord]],
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
    pass_speed_grid_per_game_sec: float = float(RESET_INBOUND_PASS_GRID_PER_GAME_SECOND),
    metadata_reason: str = "kickout",
) -> List[AnimationStep]:
    """Universal Kickout beat — current BH (in frontcourt near basket)
    kicks the ball BACK to ``receiver_id`` (the HCO playcall's step 0 BH).
    Fires when HCO entry conditions detect BH past the offensive arc
    threshold (x >= 71 home / <= 29 away).

    Two sub-steps mirror the legacy OREB Kickout shape:

    - **Sub-step A (Outlet positioning)**: BH cruises to a perimeter
      passer outlet; receiver cruises to a perimeter receive outlet
      (constrained to same vertical half). Other 8 cruise toward their
      ``setup_coords`` (= HCO step 0 setup positions); interrupted at T.
      Gate: slower of BH/receiver arrival.
    - **Sub-step B (Pass)**: BH stationary at passer outlet; receiver
      stationary at receive outlet. Ball travels BH → receiver. Other 8
      continue toward setup positions; interrupted at T.
      Gate: ball reaches receiver.

    Returns ``[]`` when BH == receiver or essential data missing.
    """
    if not bh_id or not receiver_id or bh_id == receiver_id:
        return []
    if bh_id not in start_coords or receiver_id not in start_coords:
        return []

    # Pick outlet spots via legacy logic (random + vertical-half pairing).
    receiver_spot_label, receiver_outlet = _pick_kickout_receiver_outlet(is_away_offense)
    bh_outlet = _pick_kickout_passer_outlet(receiver_spot_label, is_away_offense)

    key_ids = {bh_id, receiver_id}
    other_targets = build_kickout_non_core_targets(
        start_coords=start_coords,
        setup_coords=setup_coords,
        key_ids=key_ids,
        is_away_offense=is_away_offense,
    )

    step_a = _build_kickout_positioning_substep(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=start_coords,
        bh_id=bh_id,
        receiver_id=receiver_id,
        bh_outlet=bh_outlet,
        receiver_outlet=receiver_outlet,
        other_targets=other_targets,
        clock_remaining_at_start=clock_remaining_at_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_start,
        next_step_index=next_step_index + 1,
        metadata_reason=f"{metadata_reason}_positioning",
    )

    step_b_start_coords = dict(step_a["end"]["coords"])
    a_clock = step_a["end"]["clock"]

    step_b = build_pass_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=step_b_start_coords,
        passer_id=bh_id,
        receiver_id=receiver_id,
        continuing_targets=other_targets,
        continuing_archetype="cruise",
        clock_remaining_at_start=a_clock["clock_remaining"],
        shot_clock_remaining_at_start=a_clock["shot_clock_remaining"],
        next_step_index=next_step_index + 2,
        pass_speed_grid_per_game_sec=pass_speed_grid_per_game_sec,
        metadata_reason=f"{metadata_reason}_pass",
    )

    return [step_a, step_b]


def _build_kickout_positioning_substep(
    *,
    off_lineup,
    def_lineup,
    start_coords: Dict[str, GridCoord],
    bh_id: str,
    receiver_id: str,
    bh_outlet: GridCoord,
    receiver_outlet: GridCoord,
    other_targets: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
    metadata_reason: str,
) -> AnimationStep:
    """Sub-step A: BH and receiver both cruise to their outlet spots;
    other 8 cruise toward HCO setup positions. Gate = slower of BH/receiver."""
    bh_player = _player_lookup_by_id(off_lineup, def_lineup, bh_id)
    rx_player = _player_lookup_by_id(off_lineup, def_lineup, receiver_id)
    bh_rate = _ag_grid_per_game_sec(bh_player, "cruise")
    rx_rate = _ag_grid_per_game_sec(rx_player, "cruise")

    bh_start = start_coords[bh_id]
    rx_start = start_coords[receiver_id]
    bh_t = _euclid(bh_start, bh_outlet) / bh_rate if bh_rate > 0 else 0.5
    rx_t = _euclid(rx_start, receiver_outlet) / rx_rate if rx_rate > 0 else 0.5
    t = max(0.5, bh_t, rx_t)

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in start_coords}
    archetype: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in start_coords}
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {pid: dict(coord) for pid, coord in start_coords.items()}

    # BH: cruise to passer outlet, holding ball.
    actions[bh_id] = "handle_ball"
    archetype[bh_id] = "cruise"
    destinations[bh_id] = dict(bh_outlet)
    end_coords[bh_id] = dict(bh_outlet)

    # Receiver: cruise to receive outlet.
    actions[receiver_id] = "cut"
    archetype[receiver_id] = "cruise"
    destinations[receiver_id] = dict(receiver_outlet)
    end_coords[receiver_id] = dict(receiver_outlet)

    # Other 8: cruise toward HCO setup; interrupted at T.
    for pid, target in other_targets.items():
        if pid not in start_coords:
            continue
        actions[pid] = "cut" if _is_offense_player(pid, off_lineup) else "guard_offball"
        archetype[pid] = "cruise"
        destinations[pid] = dict(target)
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, "cruise")
        end_coords[pid] = _interrupted_coord(start_coords[pid], target, rate, t)

    ball_state: BallState = {"owner_player_id": bh_id}
    # Gate on the slower of BH/receiver.
    gate_id = bh_id if bh_t >= rx_t else receiver_id
    gate_target = bh_outlet if gate_id == bh_id else receiver_outlet
    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": str(gate_id),
            "target_coords": {"x": float(gate_target["x"]), "y": float(gate_target["y"])},
            "reason": metadata_reason,
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
        "ball": ball_state,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_state,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


_INBOUND_PASSER_HOLD_GAME_SECONDS: float = 1.0


def _build_inbound_passer_hold_step(
    *,
    start_coords: Dict[str, GridCoord],
    sf_id: str,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
    hold_t_game_sec: float = _INBOUND_PASSER_HOLD_GAME_SECONDS,
    metadata_reason: str = "inbound_passer_hold",
    setup_coords: Optional[Dict[str, GridCoord]] = None,
    off_lineup: Optional[Dict[str, Any]] = None,
    def_lineup: Optional[Dict[str, Any]] = None,
    moving_archetype: PlayerArchetype = "standard",
) -> AnimationStep:
    """1-game-sec beat where the inbound passer holds the ball at the
    inbound spot before throwing the pass. SF carries the ball.

    Default (SIP / HCT / HCO BIP): all 10 players stationary at their
    prior-step end positions.

    FCP BIP: pass ``setup_coords`` + lineups so SF holds while the other
    nine continue toward FCP setup destinations at ``moving_archetype``.

    Clock fields here decrement by the hold T (defaults to 1 game-sec).
    Callers may override the end clock to pin one or both clocks (BIP pins
    shot clock; SIP pins both clocks).
    """
    t = float(hold_t_game_sec)
    sf_key = str(sf_id)
    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    end_coords: Dict[str, GridCoord] = {}
    fcp_moving_hold = bool(setup_coords and off_lineup and def_lineup)

    for pid, sc in start_coords.items():
        if fcp_moving_hold and str(pid) != sf_key:
            target = setup_coords.get(pid) if setup_coords else None
            if (
                isinstance(target, dict)
                and "x" in target
                and "y" in target
                and _euclid(sc, target) > 1e-6
            ):
                actions[pid] = (
                    "cut" if _is_offense_player(pid, off_lineup) else "guard_offball"
                )
                archetype[pid] = moving_archetype
                destinations[pid] = dict(target)
                player = _player_lookup_by_id(off_lineup, def_lineup, pid)
                rate = _ag_grid_per_game_sec(player, moving_archetype)
                end_coords[pid] = (
                    _interrupted_coord(sc, target, rate, t) if rate > 0 else dict(target)
                )
                continue
        actions[pid] = "handle_ball" if str(pid) == sf_key else "stationary"
        archetype[pid] = "stationary"
        destinations[pid] = None
        end_coords[pid] = dict(sc)

    trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": t,
        "metadata": {"reason": metadata_reason},
    }

    clock_start: ClockState = {
        "clock_remaining": float(clock_remaining_at_start),
        "shot_clock_remaining": float(shot_clock_remaining_at_start),
    }
    clock_end: ClockState = {
        "clock_remaining": float(clock_remaining_at_start) - t,
        "shot_clock_remaining": float(shot_clock_remaining_at_start) - t,
    }

    start: StepStart = {
        "coords": {pid: dict(c) for pid, c in start_coords.items()},
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": {"owner_player_id": sf_key},
        "clock": clock_start,
        "advance_trigger": trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": {"owner_player_id": sf_key},
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    if fcp_moving_hold and off_lineup and def_lineup:
        stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def build_bip_animation_steps(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    prior_final_coords: Dict[str, GridCoord],
    setup_coords: Dict[str, GridCoord],
    sf_id: str,
    pg_id: str,
    ball_start_coord: GridCoord,
    is_fast_break_after_make: bool = False,
    fcp_setup: bool = False,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    receiver_id: Optional[str] = None,
) -> List[AnimationStep]:
    """Baseline Inbound Pass (BIP) — emits the 4-step "rim pickup" sequence
    that runs after every made-shot transition (HCO / FB / OREB Putback /
    HCT/FCP / made FT):

    - **Step 1 — SF to rim**: SF walks from his post-shot position to the
      rim (= ``ball_start_coord``, where the made shot rested). Other 9
      walk toward their BIP setup positions concurrently. Ball stays LOOSE
      at the rim throughout the step; it attaches to SF at step end via
      ``snapBallToEndState`` when SF arrives. Gate = SF reaches rim.
    - **Step 2 — SF to inbound spot**: SF walks rim → ``setup_coords[sf_id]``
      (the dynamically-chosen inbound baseline spot) carrying the ball.
      Other 9 continue toward their setup positions if not yet there.
      Gate = slower of [SF reaches inbound, PG reaches receive] for normal
      BIP/HCT; **FCP only** = 4 of 5 offensive players reach FCP setup coords
      **and** SF must reach the baseline inbound spot (mandatory passer gate).
    - **Step 3 — Passer hold**: 1-game-sec beat where SF holds the ball at
      the inbound spot before the pass. All 10 stationary for normal BIP;
      **FCP only** SF holds while the other nine continue toward setup.
    - **Step 4 — Inbound pass**: SF passes to PG. Other 8 may continue
      toward setup positions during the pass (``continuing_targets``).

    Clock policy: BOTH clocks are PINNED across all four steps (BIP is a
    dead-ball inbound after a made basket). The GAME clock is frozen through
    the inbound; the authoritative game_state burns only the small post-make
    runoff (0/2s) at the turn level (game_manager bypass:BIP), so the next turn
    ticks down from there — no backward clock snap at the BIP→HCO seam (see
    BIP-Task 1 note at the clock-policy block below). The SHOT clock likewise
    doesn't start until the inbound receiver receives the pass (= the moment
    this turn ends; the next turn burns shot clock as normal), matching the
    real-basketball rule that the shot clock starts on receipt.

    All four steps use ``standard`` archetype for SF (per the dev brief).
    Other players keep their existing archetype (``standard``; ``sprint`` for
    FB-after-make legacy carry-over).

    Caller (``setup_baseline_inbound``) stamps the returned list onto
    ``turn_result["animation_steps"]``.
    """
    if not prior_final_coords or not setup_coords or not sf_id or not pg_id:
        return []
    if sf_id not in prior_final_coords or pg_id not in setup_coords:
        return []
    if sf_id not in setup_coords:
        return []
    if not isinstance(ball_start_coord, dict) or "x" not in ball_start_coord or "y" not in ball_start_coord:
        return []

    # Inbound-pass receiver. Defaults to PG (normal BIP); quick-foul BIP passes
    # the dynamically-chosen candidate receiver so the following HCO turn's ball
    # handler is the intended foul victim.
    recv_id = str(receiver_id) if receiver_id else str(pg_id)
    if recv_id not in setup_coords:
        recv_id = str(pg_id)

    rim_coord: GridCoord = {
        "x": float(ball_start_coord["x"]),
        "y": float(ball_start_coord["y"]),
    }
    sf_inbound_coord = setup_coords[str(sf_id)]

    # Non-SF players' archetype: standard (default), sprint for
    # FB-after-MAKE — kept as a low-impact carry-over flag.
    other_arch: PlayerArchetype = "sprint" if is_fast_break_after_make else "standard"

    # ===== Step 1: SF walks post-shot → rim. Others walk to BIP setup. =====
    step1_end_target = dict(setup_coords)
    step1_end_target[str(sf_id)] = dict(rim_coord)

    step1 = build_walk_up_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=prior_final_coords,
        end_coords=step1_end_target,
        bh_id=str(sf_id),
        clock_remaining_at_start=clock_remaining_at_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_start,
        next_step_index=1,
        bh_archetype="standard",
        other_archetype=other_arch,
        gate_player_ids=[str(sf_id)],  # gate on SF reaching the rim
        metadata_reason="bip_sf_to_rim",
    )
    # Ball is LOOSE at the rim throughout step 1; SF arrives at rim coord at
    # step end, then snapBallToEndState attaches via the BallAttached(SF)
    # end state below. The default build_walk_up_step ball state is
    # BallAttached(bh_id) — we override start to BallLoose at rim.
    step1["start"]["ball"] = {"coords": dict(rim_coord)}

    # ===== Step 2: SF walks rim → inbound spot. Others continue or stay. =====
    step2_start_coords = dict(step1["end"]["coords"])
    step2_end_target = dict(step2_start_coords)
    step2_end_target[str(sf_id)] = dict(sf_inbound_coord)
    # Non-SF players that haven't reached their setup positions yet continue
    # toward them this step. Already-arrived players stay put naturally
    # (start == end → no movement).
    for pid, target in setup_coords.items():
        if pid == str(sf_id):
            continue
        step2_end_target[pid] = dict(target)

    step2 = build_walk_up_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=step2_start_coords,
        end_coords=step2_end_target,
        bh_id=str(sf_id),
        clock_remaining_at_start=step1["end"]["clock"]["clock_remaining"],
        shot_clock_remaining_at_start=step1["end"]["clock"]["shot_clock_remaining"],
        next_step_index=2,
        bh_archetype="standard",
        other_archetype=other_arch,
        gate_player_ids=None if fcp_setup else [str(sf_id), recv_id],
        gate_offense_required_count=4 if fcp_setup else None,
        gate_mandatory_player_ids=[str(sf_id)] if fcp_setup else None,
        metadata_reason="bip_fcp_setup" if fcp_setup else "bip_sf_to_inbound",
    )

    # ===== Step 3: Passer hold (1 game-sec). =====
    step3 = _build_inbound_passer_hold_step(
        start_coords=step2["end"]["coords"],
        sf_id=str(sf_id),
        clock_remaining_at_start=step2["end"]["clock"]["clock_remaining"],
        shot_clock_remaining_at_start=step2["end"]["clock"]["shot_clock_remaining"],
        next_step_index=3,
        metadata_reason="bip_fcp_passer_hold" if fcp_setup else "bip_passer_hold",
        setup_coords=setup_coords if fcp_setup else None,
        off_lineup=off_lineup if fcp_setup else None,
        def_lineup=def_lineup if fcp_setup else None,
        moving_archetype=other_arch,
    )

    # ===== Step 4: Inbound pass SF → PG. =====
    pass_step = build_pass_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=step3["end"]["coords"],
        passer_id=str(sf_id),
        receiver_id=recv_id,
        continuing_targets=setup_coords,
        continuing_archetype=other_arch,
        clock_remaining_at_start=step3["end"]["clock"]["clock_remaining"],
        shot_clock_remaining_at_start=step3["end"]["clock"]["shot_clock_remaining"],
        pass_speed_grid_per_game_sec=float(INBOUND_PASS_GRID_PER_GAME_SECOND),
        next_step_index=999,
        metadata_reason="bip_inbound_pass",
    )

    # ===== Clock policy: pin BOTH clocks across all 4 steps. =====
    # BIP is a DEAD-BALL inbound after a made basket — the game clock is frozen
    # through the inbound (mirrors SIP's build_sip_animation_steps, which pins
    # both clocks). BIP-Task 1 (BIP_UESS_Audit.md HIGH-1): previously only the
    # SHOT clock was pinned and the GAME clock burned the full ~4-8s
    # walk-up+hold+pass, while ``time_elapsed`` carried only the small post-make
    # runoff (0/2s). So the emitted animation ran the clock during a dead ball
    # AND the next turn (which seeds from game_state = clock − runoff) opened
    # ABOVE where BIP's animation ended (clock − ~T_total), snapping the visible
    # clock BACKWARD ~4s at the BIP→HCO seam. Pinning the game clock freezes the
    # emitted steps at the turn-start value; the authoritative game_state still
    # burns the runoff at the turn level (game_manager ``bypass:BIP`` path), so
    # the next turn ticks DOWN from there (no backward jump; no negative emitted
    # clock at low game clock). SHOT clock likewise stays at the turn-start
    # value; the next turn starts burning it on receiver pickup.
    pinned_shot_clock = float(shot_clock_remaining_at_start)
    pinned_game_clock = float(clock_remaining_at_start)
    for step in (step1, step2, step3, pass_step):
        step["start"]["clock"]["shot_clock_remaining"] = pinned_shot_clock
        step["end"]["clock"]["shot_clock_remaining"] = pinned_shot_clock
        step["start"]["clock"]["clock_remaining"] = pinned_game_clock
        step["end"]["clock"]["clock_remaining"] = pinned_game_clock

    return [step1, step2, step3, pass_step]


def build_sip_animation_steps(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    prior_final_coords: Dict[str, GridCoord],
    prior_final_ball_handler_id: Optional[str],
    setup_coords: Dict[str, GridCoord],
    sf_id: str,
    pg_id: str,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    ball_start_coord: Optional[GridCoord] = None,
    receiver_id: Optional[str] = None,
) -> List[AnimationStep]:
    """Side Inbound Pass (SIP) — emits three schema-compliant steps:

    - **Step 1 — Setup walk-in**: All 10 players move from prior-turn end coords
      to SIP setup positions (SF→sideline inbound spot, PG→receive spot,
      others to SIP scatter formation). All players move at ``standard``
      archetype. Gate is *all 10 players* — step T = slowest mover's natural
      travel time. Ball starts loose at the prior turn's ball-handler coord
      and travels to SF's end position at shot-style speed, attaches at end.
    - **Step 2 — Passer hold**: 1-game-sec beat where SF holds the ball at
      the inbound spot before the pass. All 10 stationary at step-1 end coords.
    - **Step 3 — Inbound pass**: SF passes to PG. All 10 players stationary
      at their step 2 coords. Pass T = pass distance / inbound pass speed.

    SIP does not burn game clock — clock fields on all three steps are pinned
    to the turn-start clock state. The visual takes wall-clock time but the
    game clock stays paused until HCO begins.

    Caller (``setup_side_inbound``) stamps the returned list onto
    ``turn_result["animation_steps"]`` and keeps ``time_elapsed = 0``.
    """
    if not prior_final_coords or not setup_coords or not sf_id or not pg_id:
        return []
    if sf_id not in setup_coords or pg_id not in setup_coords:
        return []

    # Inbound-pass receiver. Defaults to PG (normal SIP); quick-foul SIP passes
    # the dynamically-chosen candidate receiver so the following HCO turn's ball
    # handler is the intended foul victim.
    recv_id = str(receiver_id) if receiver_id else str(pg_id)
    if recv_id not in setup_coords:
        recv_id = str(pg_id)

    # Ball start coord. Preference (SIP-Task 1, SIP_UESS_Audit.md #1):
    #   1. Explicit ``ball_start_coord`` = the prior turn's RENDERED ball rest
    #      (``final_ball_coords``), passed by the caller. This is inv.4-correct:
    #      on steal / dead-ball / in-flight prior-end states the ball's rendered
    #      rest ≠ the BH's body coord, so seeding from the body teleports the
    #      ball at the SIP entry seam.
    #   2. Legacy fallback: prior BH's body position (``prior_final_coords[BH]``).
    #   3. SF's start coord (ball appears with SF, no visible motion).
    if (
        isinstance(ball_start_coord, dict)
        and ball_start_coord.get("x") is not None
        and ball_start_coord.get("y") is not None
    ):
        ball_start_coord = {"x": float(ball_start_coord["x"]), "y": float(ball_start_coord["y"])}
    elif (
        prior_final_ball_handler_id
        and str(prior_final_ball_handler_id) in prior_final_coords
    ):
        ball_start_coord = prior_final_coords[str(prior_final_ball_handler_id)]
    elif sf_id in prior_final_coords:
        ball_start_coord = prior_final_coords[sf_id]
    else:
        return []

    # --- Step 1 — Setup walk-in (gate = all 10 players, standard archetype) ---
    setup_step = build_walk_up_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=prior_final_coords,
        end_coords=setup_coords,
        bh_id=str(sf_id),
        clock_remaining_at_start=clock_remaining_at_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_start,
        next_step_index=1,  # → hold step
        bh_archetype="standard",
        other_archetype="standard",
        # SIP gates on every player — no one teleports, step T = slowest.
        gate_player_ids=[str(pid) for pid in prior_final_coords.keys()],
        metadata_reason="sip_setup_walkin",
    )

    # Ball: loose at prior BH coord at step start, attaches to SF at step end
    # (default build_walk_up_step behavior). Shot-style motion → fixed
    # wall-clock rate, independent of step T.
    setup_step["start"]["ball"] = {
        "coords": {
            "x": float(ball_start_coord["x"]),
            "y": float(ball_start_coord["y"]),
        },
    }
    setup_step["start"]["ball_motion_style"] = "shot"

    # --- Step 2 — Passer hold (1 game-sec). ---
    hold_step = _build_inbound_passer_hold_step(
        start_coords=setup_step["end"]["coords"],
        sf_id=str(sf_id),
        clock_remaining_at_start=clock_remaining_at_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_start,
        next_step_index=2,  # → pass step
        metadata_reason="sip_passer_hold",
    )

    # --- Step 3 — Inbound pass (SF→PG, all others stationary) ---
    pass_step = build_pass_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=hold_step["end"]["coords"],
        passer_id=str(sf_id),
        receiver_id=recv_id,
        # No continuing_targets → other 8 stationary at their step 2 end coords.
        continuing_targets=None,
        clock_remaining_at_start=clock_remaining_at_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_start,
        pass_speed_grid_per_game_sec=float(INBOUND_PASS_GRID_PER_GAME_SECOND),
        # End of SIP turn — index past array signals turn-end.
        next_step_index=999,
        metadata_reason="sip_inbound_pass",
    )

    # SIP burns no game clock. Pin every clock field on all three steps to the
    # turn-start clock state (the moment the dead-ball whistle blew). Tween
    # wall-clock durations are unchanged; only the game-clock readings flat.
    pinned_clock: ClockState = {
        "clock_remaining": float(clock_remaining_at_start),
        "shot_clock_remaining": float(shot_clock_remaining_at_start),
    }
    for step in (setup_step, hold_step, pass_step):
        step["start"]["clock"] = dict(pinned_clock)
        step["end"]["clock"] = dict(pinned_clock)

    return [setup_step, hold_step, pass_step]


def build_ot_to_hco_bridge_steps(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    prior_final_coords: Dict[str, GridCoord],
    setup_coords: Dict[str, GridCoord],
    bh_id: str,
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> List[AnimationStep]:
    """OT → HCO seam. Composes ``build_handoff_step`` (hold when BH = PG,
    converge + pass when BH ≠ PG) + ``build_walk_up_step``.
    """
    if not prior_final_coords or not setup_coords or not bh_id:
        return []
    if bh_id not in prior_final_coords or bh_id not in setup_coords:
        return []

    pg = (off_lineup or {}).get("PG")
    pg_id = str(getattr(pg, "player_id", "")) if pg is not None else ""
    if not pg_id or pg_id not in prior_final_coords:
        # Degenerate lineup — skip handoff; walk-up keeps current BH.
        pg_id = ""

    steps: List[AnimationStep] = []
    clock_r = float(clock_remaining_at_start)
    shot_r = float(shot_clock_remaining_at_start)

    if pg_id:
        handoff_steps = build_handoff_step(
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            start_coords=prior_final_coords,
            bh_id=str(bh_id),
            receiver_id=pg_id,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_r,
            shot_clock_remaining_at_start=shot_r,
            next_step_index=0,  # internal pointers; final fixed below
            metadata_reason="ot_to_hco_handoff",
        )
        steps.extend(handoff_steps)
        if handoff_steps:
            tail_clock = handoff_steps[-1]["end"]["clock"]
            clock_r = tail_clock["clock_remaining"]
            shot_r = tail_clock["shot_clock_remaining"]

    # After handoff, PG is the ball carrier (whether it was hold or pass).
    walk_bh_id = pg_id or str(bh_id)

    walk_up = build_walk_up_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=(steps[-1]["end"]["coords"] if steps else prior_final_coords),
        end_coords=setup_coords,
        bh_id=walk_bh_id,
        clock_remaining_at_start=clock_r,
        shot_clock_remaining_at_start=shot_r,
        next_step_index=next_step_index,
        bh_archetype="standard",
        other_archetype="sprint",
        metadata_reason="ot_to_hco_walkup",
    )
    steps.append(walk_up)

    # Fix internal next-pointers so each step points to the next slot in the
    # final array. The LAST step keeps its `next_step_index` (= skeleton 0).
    for i, s in enumerate(steps[:-1]):
        s["end"]["next"] = {"kind": "next_step", "index": i + 1}
    return steps


def _is_offense_player(pid: str, off_lineup: Dict[str, Any]) -> bool:
    target = str(pid)
    for player in (off_lineup or {}).values():
        if player is None:
            continue
        if str(getattr(player, "player_id", "")) == target:
            return True
    return False


def _slowest_mover_id(
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
) -> Optional[str]:
    slowest_pid: Optional[str] = None
    max_dist = -1.0
    for pid, sc in start_coords.items():
        ec = end_coords.get(pid)
        if not ec:
            continue
        d = _euclid(sc, ec)
        if d > max_dist:
            max_dist = d
            slowest_pid = pid
    return slowest_pid
