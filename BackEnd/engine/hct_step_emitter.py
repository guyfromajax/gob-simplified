"""HCT animation step emitter.

Converts an HCT turn's existing animation data (skeleton + per-player
animations + step_clock_seconds + roles) into the unified AnimationStep[]
payload defined in `BackEnd/utils/animation_step_schema.py`.

This module is parallel-build infrastructure for the SS&S animation
refactor (see `_documentation_master/projects/Animation_System_Updated.md`).
It does not replace existing HCT animation generation. Cutover happens in
a later PR — until then, both the legacy `animations[]` payload and the
new `steps[]` payload coexist on the HCT turn dict, with the frontend
choosing which to consume.

Status: skeleton implementation. Some pieces are deliberately stubbed where
the existing data path needs more tracing — those are marked TODO and the
function returns `None` rather than producing a malformed payload.
"""

from typing import Any, Dict, List, Optional

from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    BallAttached,
    BallState,
    ClockState,
    GridCoord,
    NextStep,
    PlayerAction,
    PlayerArchetype,
    StepEnd,
    StepStart,
)


# --- Vocabulary mapping ----------------------------------------------------

# HCT skeleton actions → schema action vocab (1:1 for HCT; HCO terms are
# handled in HCO migration).
_HCT_ACTION_MAP: Dict[str, PlayerAction] = {
    "handle_ball": "handle_ball",
    "pass": "pass",
    "receive": "receive",
    "cut": "cut",
    "screen": "screen",
    "shoot": "shoot",
    "stationary": "stationary",
    "guard_ball": "guard_ball",
    "guard_offball": "guard_offball",
}

_OFFENSE_POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def _archetype_for_hct_step(
    step_index: int,
    pos: str,
    is_offense: bool,
    is_ball_handler: bool,
    is_pg_defender_vs_bh: bool,
) -> PlayerArchetype:
    """Per `Animation_System_Updated.md` HCT scoping table:

    | Step | BH | Non-BH offense | PG defender vs BH | Other defenders |
    | 0 (setup)        | cruise | cruise  | cruise  | cruise  |
    | 1 (BH advance)   | cruise | cruise  | cruise  | cruise  |
    | 2 (PG converge)  | default| default | default | default |
    | 3 (outcome)      | drive  | default | default | default |
    """
    if step_index in (0, 1):
        return "cruise"
    if step_index == 2:
        return "default"
    if step_index == 3:
        if is_ball_handler:
            return "drive"
        return "default"
    # Defensive default (shouldn't hit for the 4-step HCT model).
    return "default"


# --- Ball-state walk -------------------------------------------------------


def _player_id_at_pos(lineup: Dict[str, Any], pos: str) -> Optional[str]:
    player = lineup.get(pos)
    if player is None:
        return None
    pid = getattr(player, "player_id", None)
    return str(pid) if pid is not None else None


def _walk_ball_owners(
    skeleton_steps: List[Dict[str, Any]],
) -> List[tuple]:
    """Walk the skeleton once and produce a list of (start_owner_pos,
    end_owner_pos) pairs — one per step. Continuity rules:
      - A pos with `handle_ball` or `pass` action holds the ball at step start.
      - A `pass` + `receive` pair within a step transfers ownership at step end.
      - Otherwise end owner = start owner.

    Avoids the off-by-one issues of computing each step boundary independently
    by maintaining a single running owner pointer across the walk.
    """
    walks: List[tuple] = []
    current_owner: Optional[str] = None
    for step in skeleton_steps:
        pos_actions = step.get("pos_actions") or {}
        # Step start: holder = pos with handle_ball or pass (both indicate
        # the holder at step start; the pass action means "starts with ball,
        # passes during step").
        for pos in _OFFENSE_POSITIONS:
            action = (pos_actions.get(pos) or {}).get("action")
            if action in ("handle_ball", "pass"):
                current_owner = pos
                break
        start_owner = current_owner
        # Step end: transfer to receiver if pass+receive pair present.
        passers = [p for p in _OFFENSE_POSITIONS if (pos_actions.get(p) or {}).get("action") == "pass"]
        receivers = [p for p in _OFFENSE_POSITIONS if (pos_actions.get(p) or {}).get("action") == "receive"]
        if passers and receivers:
            current_owner = receivers[0]
        end_owner = current_owner
        walks.append((start_owner, end_owner))
    return walks


# --- Coord extraction from existing animations[] payload --------------------


def _coords_at_movement_index(
    animations: List[Dict[str, Any]],
    movement_index: int,
) -> Dict[str, GridCoord]:
    """Extract `{player_id: {x, y}}` from `animations[i].movement[movement_index].coords`
    for every player whose movement array reaches that index."""
    out: Dict[str, GridCoord] = {}
    for anim in animations:
        movement = anim.get("movement") or []
        if movement_index >= len(movement):
            continue
        waypoint = movement[movement_index] or {}
        coords = waypoint.get("coords") or {}
        x = coords.get("x")
        y = coords.get("y")
        if x is None or y is None:
            continue
        pid = anim.get("playerId")
        if pid is None:
            continue
        out[str(pid)] = {"x": float(x), "y": float(y)}
    return out


# --- Per-step builders -----------------------------------------------------


def _build_advance_trigger_player_reaches(
    player_id: str,
    target_coords: GridCoord,
    t_game_seconds: float,
) -> AdvanceTrigger:
    return {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t_game_seconds),
        "metadata": {
            "target_player_id": str(player_id),
            "target_coords": {
                "x": float(target_coords["x"]),
                "y": float(target_coords["y"]),
            },
        },
    }


def _slowest_setup_player_id(
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
) -> Optional[str]:
    """Identify the slowest mover for step 0 (setup) — the player with the
    largest start→end traversal distance. All players use the `cruise`
    archetype during setup, so distance is a reasonable proxy for gating.
    """
    longest: Optional[str] = None
    max_dist_sq = -1.0
    for pid, start in start_coords.items():
        end = end_coords.get(pid)
        if end is None:
            continue
        dx = end["x"] - start["x"]
        dy = end["y"] - start["y"]
        dist_sq = dx * dx + dy * dy
        if dist_sq > max_dist_sq:
            max_dist_sq = dist_sq
            longest = pid
    return longest


def _build_step_destinations_and_actions(
    skeleton_steps: List[Dict[str, Any]],
    step_index: int,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    end_coords: Dict[str, GridCoord],
) -> tuple[Dict[str, Optional[GridCoord]], Dict[str, PlayerAction]]:
    """Produce per-player `destination` and `action` maps for a step.

    destinations = end coords for players who move; None for stationary.
    actions = mapped from skeleton.steps[step_index].pos_actions for the
    offense; defenders default to guard_ball / guard_offball based on whether
    they're the BH defender. (HCT skeleton currently doesn't carry defender
    actions explicitly — that's a downstream refinement.)
    """
    destinations: Dict[str, Optional[GridCoord]] = {}
    actions: Dict[str, PlayerAction] = {}

    step_data = skeleton_steps[step_index] if step_index < len(skeleton_steps) else {}
    pos_actions = step_data.get("pos_actions") or {}

    # Offense: read action from skeleton; destination = end coord (if moving).
    for pos in _OFFENSE_POSITIONS:
        pid = _player_id_at_pos(off_lineup, pos)
        if not pid:
            continue
        skeleton_action = (pos_actions.get(pos) or {}).get("action") or "stationary"
        actions[pid] = _HCT_ACTION_MAP.get(skeleton_action, "stationary")
        destinations[pid] = end_coords.get(pid)

    # Defense: TODO — skeleton doesn't carry defender actions today; for now
    # default everyone to `guard_offball` and refine later. The PG defender vs
    # BH gets `guard_ball` (computed by the caller, not the skeleton).
    for pos in _OFFENSE_POSITIONS:  # using same key list since lineups are 5 each
        pid = _player_id_at_pos(def_lineup, pos)
        if not pid:
            continue
        actions[pid] = "guard_offball"  # TODO: refine PG defender → guard_ball
        destinations[pid] = end_coords.get(pid)

    return destinations, actions


def _build_archetype_map(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_index: int,
    ball_handler_id: Optional[str],
) -> Dict[str, PlayerArchetype]:
    """Per-player archetype based on HCT scoping table."""
    out: Dict[str, PlayerArchetype] = {}
    for pos in _OFFENSE_POSITIONS:
        pid = _player_id_at_pos(off_lineup, pos)
        if not pid:
            continue
        is_bh = ball_handler_id is not None and pid == ball_handler_id
        out[pid] = _archetype_for_hct_step(
            step_index, pos, is_offense=True, is_ball_handler=is_bh,
            is_pg_defender_vs_bh=False,
        )
    for pos in _OFFENSE_POSITIONS:
        pid = _player_id_at_pos(def_lineup, pos)
        if not pid:
            continue
        # TODO: PG defender vs BH — refine when we wire defender role data.
        out[pid] = _archetype_for_hct_step(
            step_index, pos, is_offense=False, is_ball_handler=False,
            is_pg_defender_vs_bh=False,
        )
    return out


# --- Top-level emitter -----------------------------------------------------


def build_hct_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Convert an HCT turn_result into the unified AnimationStep[] payload.

    Args:
        turn_result: existing HCT turn dict containing `skeleton`,
            `animations`, `step_clock_seconds`, `roles`, `result_type`.
        game: GameManager (for clock state at turn start).

    Returns:
        List[AnimationStep] in step order, or None if required data is
        missing (graceful degradation during parallel-build phase).
    """
    skeleton = turn_result.get("skeleton") or {}
    skeleton_steps: List[Dict[str, Any]] = skeleton.get("steps") or []
    animations: List[Dict[str, Any]] = turn_result.get("animations") or []
    step_clock_seconds: List[float] = turn_result.get("step_clock_seconds") or []
    roles: Dict[str, Any] = turn_result.get("roles") or {}

    if not skeleton_steps or not animations or not step_clock_seconds:
        return None

    # HCT is canonically 4 steps. Trim or refuse on mismatch.
    if len(skeleton_steps) < 4:
        return None
    num_steps = 4

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}

    ball_handler = roles.get("ball_handler")
    ball_handler_id = (
        str(getattr(ball_handler, "player_id", "")) if ball_handler else None
    ) or None

    defender = roles.get("defender")
    defender_id = (
        str(getattr(defender, "player_id", "")) if defender else None
    ) or None

    # Game-clock state at turn start. Subsequent steps decrement by step T.
    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining_at_turn_start = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining_at_turn_start = float(
        game_state.get("shot_clock_remaining", 0) or 0
    )

    # Walk ball owners once across the skeleton — produces (start_owner,
    # end_owner) pos pairs per step. Avoids the off-by-one of computing each
    # boundary independently.
    ball_walks = _walk_ball_owners(skeleton_steps)

    steps: List[AnimationStep] = []
    elapsed_so_far = 0.0

    for i in range(num_steps):
        # Coords from existing animations payload. The schema asserts:
        #   step[i].start.coords == animations[*].movement[i].coords
        #   step[i].end.coords   == animations[*].movement[i+1].coords
        start_coords = _coords_at_movement_index(animations, i)
        end_coords = _coords_at_movement_index(animations, i + 1)
        if not start_coords or not end_coords:
            return None

        destinations, actions = _build_step_destinations_and_actions(
            skeleton_steps, i, off_lineup, def_lineup, end_coords,
        )
        archetype = _build_archetype_map(off_lineup, def_lineup, i, ball_handler_id)

        start_owner_pos, end_owner_pos = ball_walks[i] if i < len(ball_walks) else (None, None)
        owner_id_start = _player_id_at_pos(off_lineup, start_owner_pos) if start_owner_pos else None
        owner_id_end = _player_id_at_pos(off_lineup, end_owner_pos) if end_owner_pos else None

        ball_start: BallState = (
            {"owner_player_id": owner_id_start} if owner_id_start
            else {"owner_player_id": ball_handler_id or ""}
        )
        ball_end: BallState = (
            {"owner_player_id": owner_id_end} if owner_id_end
            else {"owner_player_id": ball_handler_id or ""}
        )

        t = float(step_clock_seconds[i])
        clock_start: ClockState = {
            "clock_remaining": clock_remaining_at_turn_start - elapsed_so_far,
            "shot_clock_remaining": shot_clock_remaining_at_turn_start - elapsed_so_far,
        }
        clock_end: ClockState = {
            "clock_remaining": clock_remaining_at_turn_start - elapsed_so_far - t,
            "shot_clock_remaining": shot_clock_remaining_at_turn_start - elapsed_so_far - t,
        }

        # Next pointer: linear i+1 for steps 0..2; step 3 branches on outcome.
        next_step: NextStep
        if i < num_steps - 1:
            next_step = {"kind": "next_step", "index": i + 1}
        else:
            next_step = _resolve_step_3_next(turn_result)

        # Advance trigger: per step, identify the gating player (whose arrival
        # at their target coord ends the step). Per HCT scoping in
        # Animation_System_Updated.md → Advance_Triggers.md.
        if i == 0:
            gate_id = _slowest_setup_player_id(start_coords, end_coords) or ball_handler_id
        elif i == 1:
            gate_id = ball_handler_id
        elif i == 2:
            gate_id = defender_id or ball_handler_id
        else:  # i == 3 outcome
            gate_id = ball_handler_id
        gate_coord = end_coords.get(gate_id) if gate_id else None
        if gate_id and gate_coord:
            advance_trigger = _build_advance_trigger_player_reaches(gate_id, gate_coord, t)
        else:
            # Defensive fallback — if no gate could be resolved, anchor on
            # the ball handler's end coord (or court center as last resort).
            fallback_coord = end_coords.get(ball_handler_id) or {"x": 50.0, "y": 25.0}
            advance_trigger = _build_advance_trigger_player_reaches(
                ball_handler_id or "unknown", fallback_coord, t,
            )

        step: AnimationStep = {
            "start": {
                "coords": start_coords,
                "destination": destinations,
                "action": actions,
                "archetype": archetype,
                "ball": ball_start,
                "clock": clock_start,
                "advance_trigger": advance_trigger,
            },
            "end": {
                "coords": end_coords,
                "ball": ball_end,
                "time_elapsed": t,
                "clock": clock_end,
                "next": next_step,
            },
        }
        steps.append(step)
        elapsed_so_far += t

    return steps


# --- Step 3 branching ------------------------------------------------------


def _resolve_step_3_next(turn_result: Dict[str, Any]) -> NextStep:
    """Map the HCT result to step 3's `next` pointer.

    See `Animation_System_Updated.md` HCT scoping → Step 3 outcome → next
    pointer table. Pre-resolved branching: backend has already computed
    the result; emitter just routes.
    """
    result_type = (turn_result.get("result_type") or "").upper()

    # Shot outcomes → SHOT_ATTEMPT turn-stop. Caller's handler renders shot
    # arc + ball-on-rim. Rebound is a separate DREB/OREB turn (post-cutover).
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

    # Foul.
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

    if result_type in ("DEAD_BALL", "DEAD_BALL_TURNOVER", "TURNOVER"):
        return {
            "kind": "turn_stop",
            "event": "DEAD_BALL_TURNOVER",
            "payload": {"victim_id": turn_result.get("victim_id")},
        }

    if result_type == "SHOT_CLOCK_EXPIRED":
        return {
            "kind": "turn_stop",
            "event": "SHOT_CLOCK_EXPIRED",
            "payload": {},
        }

    # "Continue to HCO" path: implicit end of turn. We model it as
    # `next_step` pointing past the array — `playTurn` returns null.
    return {"kind": "next_step", "index": 999}


def _safe_id(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    pid = getattr(obj, "player_id", None)
    return str(pid) if pid is not None else None


def _ball_bounce_coords(turn_result: Dict[str, Any]) -> Optional[GridCoord]:
    bx = turn_result.get("ball_bounce_x")
    by = turn_result.get("ball_bounce_y")
    if bx is None or by is None:
        return None
    return {"x": float(bx), "y": float(by)}
