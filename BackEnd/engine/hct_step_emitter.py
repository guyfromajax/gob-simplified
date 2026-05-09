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


def _ball_owner_at_step_start(
    skeleton_steps: List[Dict[str, Any]],
    step_index: int,
    off_lineup: Dict[str, Any],
) -> Optional[str]:
    """Walk skeleton.steps[0..step_index] and return the player_id of whoever
    is holding the ball at the START of `step_index`. Continuity rule: if a
    prior step's pos_actions assigned `pass` to player A and `receive` to
    player B, the ball transfers to B at that step's end (= step+1 start)."""
    if not skeleton_steps:
        return None
    # Find initial owner: first pos with handle_ball action.
    current_owner_pos: Optional[str] = None
    for step in skeleton_steps[: step_index + 1]:
        pos_actions = step.get("pos_actions") or {}
        # Resolve transfer: if any pos has `pass` with a corresponding
        # `receive`, the ball moves to the receive pos at end of THIS step.
        # Until the transfer fires, owner = whichever pos has handle_ball.
        for pos in _OFFENSE_POSITIONS:
            action_entry = pos_actions.get(pos) or {}
            action = action_entry.get("action")
            if action == "handle_ball":
                current_owner_pos = pos
        # Apply transfer at step end if pass+receive pair present.
        passers = [p for p in _OFFENSE_POSITIONS if (pos_actions.get(p) or {}).get("action") == "pass"]
        receivers = [p for p in _OFFENSE_POSITIONS if (pos_actions.get(p) or {}).get("action") == "receive"]
        if passers and receivers:
            current_owner_pos = receivers[0]
    if current_owner_pos is None:
        return None
    return _player_id_at_pos(off_lineup, current_owner_pos)


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


def _build_advance_trigger_fixed(t_game_seconds: float) -> AdvanceTrigger:
    return {
        "condition": "fixed_duration",
        "T_game_seconds": float(t_game_seconds),
        "metadata": {},
    }


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

    # Game-clock state at turn start. Subsequent steps decrement by step T.
    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining_at_turn_start = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining_at_turn_start = float(
        game_state.get("shot_clock_remaining", 0) or 0
    )

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

        owner_id_start = _ball_owner_at_step_start(skeleton_steps, i, off_lineup)
        owner_id_end = _ball_owner_at_step_start(skeleton_steps, i + 1, off_lineup) if (i + 1) < len(skeleton_steps) else owner_id_start

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

        step: AnimationStep = {
            "start": {
                "coords": start_coords,
                "destination": destinations,
                "action": actions,
                "archetype": archetype,
                "ball": ball_start,
                "clock": clock_start,
                "advance_trigger": _build_advance_trigger_fixed(t),
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
