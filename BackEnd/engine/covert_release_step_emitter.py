"""Covert Release Fast Break animation step emitter.

Converts a Covert Release FB turn_result into the unified AnimationStep[]
payload defined in ``BackEnd/utils/animation_step_schema.py``.

Covert Release shape:
- DREB-initiated FB. The rebounder (outlet passer) outlets to a release
  player (outlet receiver = ball handler).
- Step 0: outlet pass (ball flies passer → receiver; per current frontend
  ``animateOutletPhase``, no players move during this step).
- Step 1: outcome
  - Shot Attempt (MAKE / MISS / BLOCK): shooter (BH) runs to shot spot,
    `next: turn_stop SHOT_ATTEMPT`. HCT pattern — no separate shot
    resolution step.
  - Defensive Stop: BH and defensive stopper both run to their stop
    spots. Slower of the two is the gate; `next: next_step` past array
    (implicit end of turn).
  - FOUL / STEAL / DEAD_BALL_TURNOVER: BH runs to outcome spot,
    `next: turn_stop` for the corresponding event.

Edge case: when the rebounder == release player (no distinct outlet passer),
the outlet pass step is skipped and the emitter produces only the outcome
step.

See ``_documentation_master/05_Animation_System/Advance_Triggers.md`` —
"Fast Break / Covert Release" — for the per-step trigger spec.
"""

from typing import Any, Dict, List, Optional

from BackEnd.constants import PASS_GRID_SPOTS_PER_GAME_SECOND
from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    BallInFlight,
    BallState,
    ClockState,
    GridCoord,
    NextStep,
    PlayerAction,
    PlayerArchetype,
    StepEnd,
    StepStart,
)


# --- Vocabulary helpers ----------------------------------------------------


_OFFENSE_POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def _safe_id(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    pid = getattr(obj, "player_id", None)
    return str(pid) if pid is not None else None


def _coord(obj: Any, fallback: Optional[GridCoord] = None) -> Optional[GridCoord]:
    """Read ``{x, y}`` off a player object or dict; return None if missing."""
    if obj is None:
        return fallback
    coords = getattr(obj, "coords", None) if not isinstance(obj, dict) else obj
    if not coords or "x" not in coords or "y" not in coords:
        return fallback
    return {"x": float(coords["x"]), "y": float(coords["y"])}


def _player_lookup_by_id(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    player_id: Optional[str],
) -> Optional[Any]:
    if not player_id:
        return None
    target = str(player_id)
    for lineup in (off_lineup, def_lineup):
        for player in lineup.values():
            if player is None:
                continue
            pid = getattr(player, "player_id", None)
            if pid is not None and str(pid) == target:
                return player
    return None


def _all_player_start_coords(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> Dict[str, GridCoord]:
    """Per-player start coords for step 0. Reads ``player.coords`` for every
    player in both lineups. Skips players without coords (defensive)."""
    out: Dict[str, GridCoord] = {}
    for lineup in (off_lineup, def_lineup):
        for player in lineup.values():
            if player is None:
                continue
            pid = getattr(player, "player_id", None)
            if pid is None:
                continue
            c = _coord(player)
            if c is None:
                continue
            out[str(pid)] = c
    return out


def _movement_end_coord(
    animations: List[Dict[str, Any]],
    player_id: str,
) -> Optional[GridCoord]:
    """Read ``animations[i].movement[-1].coords`` for the given player_id.
    Returns None if the player has no animation entry or no movement."""
    target = str(player_id)
    for anim in animations:
        if str(anim.get("playerId")) != target:
            continue
        movement = anim.get("movement") or []
        if not movement:
            return None
        last = movement[-1] or {}
        coords = last.get("coords") or {}
        if "x" not in coords or "y" not in coords:
            return None
        return {"x": float(coords["x"]), "y": float(coords["y"])}
    return None


def _euclid(a: GridCoord, b: GridCoord) -> float:
    dx = a["x"] - b["x"]
    dy = a["y"] - b["y"]
    return (dx * dx + dy * dy) ** 0.5


# --- Outcome → next pointer ------------------------------------------------


def _ball_bounce_coords(turn_result: Dict[str, Any]) -> Optional[GridCoord]:
    bx = turn_result.get("ball_bounce_x")
    by = turn_result.get("ball_bounce_y")
    if bx is None or by is None:
        return None
    return {"x": float(bx), "y": float(by)}


def _resolve_outcome_next(turn_result: Dict[str, Any]) -> NextStep:
    """Map the FB result_type to the outcome step's ``next`` pointer."""
    result_type = (turn_result.get("result_type") or "").upper()

    if result_type in ("MAKE", "MISS", "BLOCK"):
        return {
            "kind": "turn_stop",
            "event": "SHOT_ATTEMPT",
            "payload": {
                "result": result_type,
                "shooter_id": _safe_id(turn_result.get("shooter")),
                "defender_id": _safe_id(turn_result.get("defender")),
                "ball_bounce_coords": _ball_bounce_coords(turn_result),
            },
        }

    if result_type == "FOUL":
        return {
            "kind": "turn_stop",
            "event": "FOUL",
            "payload": {
                "foul_team": turn_result.get("foul_team"),
                "fouler_id": turn_result.get("foul_player_id"),
                "victim_id": turn_result.get("victim_id"),
            },
        }

    if result_type == "STEAL":
        return {
            "kind": "turn_stop",
            "event": "STEAL",
            "payload": {
                "stealer_id": turn_result.get("stealer_id"),
                "victim_id": turn_result.get("victim_id"),
            },
        }

    if result_type in ("DEAD_BALL", "DEAD BALL", "DEAD_BALL_TURNOVER", "TURNOVER"):
        return {
            "kind": "turn_stop",
            "event": "DEAD_BALL_TURNOVER",
            "payload": {"victim_id": turn_result.get("victim_id")},
        }

    # DEFENSIVE_STOP and any unrecognized: implicit end of turn (HCT
    # "continue to HCO" pattern). Caller transitions to next turn (HCO).
    return {"kind": "next_step", "index": 999}


# --- Step builders ---------------------------------------------------------


def _build_outlet_pass_step(
    *,
    passer_id: str,
    receiver_id: str,
    passer_coord: GridCoord,
    receiver_coord: GridCoord,
    all_start_coords: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    is_first_step: bool,
    next_step_index: int,
) -> AnimationStep:
    """Step 0: ball flies passer → receiver. No players move
    (current ``animateOutletPhase`` only animates the ball).

    T = euclidean(passer, receiver) ÷ pass speed.
    """
    distance = _euclid(passer_coord, receiver_coord)
    t = distance / float(PASS_GRID_SPOTS_PER_GAME_SECOND) if distance > 0 else 0.0

    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    for pid, coord in all_start_coords.items():
        actions[pid] = "stationary"
        archetype[pid] = "stationary"
        destinations[pid] = coord  # No movement during outlet pass.
    actions[passer_id] = "pass"
    actions[receiver_id] = "receive"

    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": passer_id,
            "to_player_id": receiver_id,
            "target_coords": dict(receiver_coord),
        },
    }

    ball_start: BallState = {"owner_player_id": passer_id}
    ball_end: BallState = {"owner_player_id": receiver_id}
    # Note: schema supports BallInFlight mid-step, but legacy parity treats
    # the pass as instant transfer at step end (same as HCT emitter).

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(all_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": dict(all_start_coords),
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    return {"start": start, "end": end}


def _ag_grid_per_game_sec(player: Any, archetype: PlayerArchetype) -> float:
    """Look up grid/game-sec rate for the given player + archetype.

    Defers to ``BackEnd.utils.shared.ag_to_grid_per_game_sec`` when available;
    falls back to a baseline if shared.py is unreachable in test contexts.
    """
    try:
        from BackEnd.utils.shared import ag_to_grid_per_game_sec
        return float(ag_to_grid_per_game_sec(player, archetype=archetype))
    except Exception:
        # Test-context fallback: AG=50, sprint baseline ~20 grid/sec.
        return 20.0


def _traversal_seconds(start: GridCoord, end: GridCoord, rate: float) -> float:
    """Time to traverse start→end at a given grid/game-sec rate."""
    if rate <= 0:
        return 0.0
    return _euclid(start, end) / rate


def _build_outcome_step(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    animations: List[Dict[str, Any]],
    step_start_coords: Dict[str, GridCoord],
    ball_owner_id: str,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
) -> AnimationStep:
    """Step 1: outcome step. Computes per-player end coords, gating player,
    and outcome `next` pointer based on the FB result_type.
    """
    result_type = (turn_result.get("result_type") or "").upper()
    is_defensive_stop = result_type == "DEFENSIVE_STOP"

    bh = fb_roles.get("ball_handler")
    bh_id = _safe_id(bh)
    stopper_id = turn_result.get("stopper_id") or fb_roles.get("stopper_id")
    stopper = _player_lookup_by_id(off_lineup, def_lineup, stopper_id)

    # End coords: prefer animations[].movement[-1] (already computed by the
    # legacy animator); fall back to player.coords (no movement).
    end_coords: Dict[str, GridCoord] = {}
    for pid, start_coord in step_start_coords.items():
        anim_end = _movement_end_coord(animations, pid)
        end_coords[pid] = anim_end if anim_end is not None else start_coord

    # Per-player action + archetype.
    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    for pid, coord in step_start_coords.items():
        actions[pid] = "stationary"
        archetype[pid] = "stationary"
        destinations[pid] = end_coords.get(pid, coord)

    if bh_id:
        if is_defensive_stop:
            actions[bh_id] = "handle_ball"
            archetype[bh_id] = "sprint"
        elif result_type in ("MAKE", "MISS", "BLOCK"):
            actions[bh_id] = "shoot"
            archetype[bh_id] = "sprint"  # FB run-up dominates the wind-up.
        else:
            # FOUL / STEAL / DEAD_BALL — BH still drives toward outcome spot.
            actions[bh_id] = "handle_ball"
            archetype[bh_id] = "sprint"

    if stopper_id:
        sid = str(stopper_id)
        if sid in actions:
            actions[sid] = "guard_ball"
            archetype[sid] = "sprint"

    # Defenders default to guard_offball (overrides "stationary" only when
    # they have a movement end recorded by the animator).
    for player in def_lineup.values():
        if player is None:
            continue
        pid = _safe_id(player)
        if pid is None or pid not in actions:
            continue
        if pid == str(stopper_id) if stopper_id else False:
            continue
        if pid == bh_id:
            continue
        if _movement_end_coord(animations, pid) is not None:
            actions[pid] = "guard_offball"
            archetype[pid] = "sprint"

    # Gating player + T.
    bh_coord_start = step_start_coords.get(bh_id) if bh_id else None
    bh_coord_end = end_coords.get(bh_id) if bh_id else None
    bh_traversal = (
        _traversal_seconds(bh_coord_start, bh_coord_end, _ag_grid_per_game_sec(bh, "sprint"))
        if bh_coord_start and bh_coord_end and bh
        else 0.0
    )

    if is_defensive_stop and stopper:
        stopper_pid = str(stopper_id)
        st_start = step_start_coords.get(stopper_pid)
        st_end = end_coords.get(stopper_pid)
        st_traversal = (
            _traversal_seconds(st_start, st_end, _ag_grid_per_game_sec(stopper, "sprint"))
            if st_start and st_end
            else 0.0
        )
        if st_traversal >= bh_traversal:
            gate_id = stopper_pid
            gate_coord = st_end or step_start_coords[stopper_pid]
            t = st_traversal
        else:
            gate_id = bh_id
            gate_coord = bh_coord_end or bh_coord_start
            t = bh_traversal
    else:
        gate_id = bh_id
        gate_coord = bh_coord_end or bh_coord_start
        t = bh_traversal

    # Defensive fallback if gating data is missing.
    if not gate_id or not gate_coord:
        gate_id = bh_id or ball_owner_id or "unknown"
        gate_coord = bh_coord_end or bh_coord_start or {"x": 50.0, "y": 25.0}
        t = max(t, 0.0)

    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": str(gate_id),
            "target_coords": dict(gate_coord),
        },
    }

    next_step = _resolve_outcome_next(turn_result)

    ball_start: BallState = {"owner_player_id": ball_owner_id}
    ball_end: BallState = {"owner_player_id": ball_owner_id}

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
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": next_step,
    }
    return {"start": start, "end": end}


# --- Top-level emitter -----------------------------------------------------


def build_covert_release_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Convert a Covert Release FB turn_result into AnimationStep[].

    Returns None when required data is missing (graceful degradation
    during parallel-build phase — caller falls back to legacy renderer).
    """
    fb_roles: Dict[str, Any] = turn_result.get("roles") or {}

    fast_break_play = turn_result.get("fast_break_play")
    if fast_break_play != "covert_release":
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}

    bh = fb_roles.get("ball_handler")
    bh_id = _safe_id(bh)
    if not bh_id:
        return None

    outlet_passer_id = fb_roles.get("outlet_passer")
    outlet_receiver_id = fb_roles.get("outlet_receiver")

    # All-player start coords (every player in both lineups).
    all_start_coords = _all_player_start_coords(off_lineup, def_lineup)
    if not all_start_coords:
        return None

    # Override outlet passer's start coord with fb_roles outlet_passer_x/y
    # when present — the animator stores the canonical pre-pass position
    # there (rebounder coords at the moment of outlet).
    op_x = fb_roles.get("outlet_passer_x")
    op_y = fb_roles.get("outlet_passer_y")
    if outlet_passer_id and op_x is not None and op_y is not None:
        all_start_coords[str(outlet_passer_id)] = {"x": float(op_x), "y": float(op_y)}

    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining = float(game_state.get("shot_clock_remaining", 0) or 0)

    steps: List[AnimationStep] = []
    elapsed = 0.0

    # Step 0: outlet pass (skipped when rebounder == release player).
    has_outlet_pass = bool(
        outlet_passer_id
        and outlet_receiver_id
        and str(outlet_passer_id) != str(outlet_receiver_id)
    )

    if has_outlet_pass:
        passer_id = str(outlet_passer_id)
        receiver_id = str(outlet_receiver_id)
        passer_coord = all_start_coords.get(passer_id)
        receiver_coord = all_start_coords.get(receiver_id)
        if passer_coord is None or receiver_coord is None:
            return None

        outlet_step = _build_outlet_pass_step(
            passer_id=passer_id,
            receiver_id=receiver_id,
            passer_coord=passer_coord,
            receiver_coord=receiver_coord,
            all_start_coords=all_start_coords,
            clock_remaining_at_start=clock_remaining,
            shot_clock_remaining_at_start=shot_clock_remaining,
            is_first_step=True,
            next_step_index=1,
        )
        steps.append(outlet_step)
        elapsed += float(outlet_step["end"]["time_elapsed"])

    # Step 1 (or step 0 if no outlet pass): outcome.
    outcome_start_coords = (
        dict(steps[-1]["end"]["coords"]) if steps else dict(all_start_coords)
    )
    ball_owner_for_outcome = str(outlet_receiver_id) if has_outlet_pass else bh_id

    outcome_step = _build_outcome_step(
        turn_result=turn_result,
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        animations=turn_result.get("animations") or [],
        step_start_coords=outcome_start_coords,
        ball_owner_id=ball_owner_for_outcome,
        clock_remaining_at_start=clock_remaining - elapsed,
        shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
    )
    steps.append(outcome_step)

    return steps
