"""Skeleton-driven animation step emitter.

Converts a turn's skeleton-shaped animation data (skeleton.steps[] +
per-player animations[] + step_clock_seconds[] + roles{}) into the
unified AnimationStep[] payload defined in
``BackEnd/utils/animation_step_schema.py``.

Used by HCO and FCP — both are multi-step paced offensive turns where
each skeleton step represents a synchronized player-position transition
gated by the slowest mover. HCT has its own emitter
(``hct_step_emitter.py``) because HCT is a fixed 4-step dynamic structure,
not skeleton-driven.

Status: parallel-build infrastructure for the SS&S animation refactor
(see ``_documentation_master/projects/Animation_System_Updated.md``).
Coexists with the legacy ``animations[]`` payload until per-turn-type
cutover.
"""

from typing import Any, Dict, List, Optional

from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    BallState,
    ClockState,
    GridCoord,
    NextStep,
    PlayerAction,
    PlayerArchetype,
)


# --- Vocabulary mapping ----------------------------------------------------

# Skeleton actions → schema action vocab. ``get_open`` collapses into ``cut``
# (movement-to-space, same precedent as ``cover_ground`` / ``drift``).
# ``post_up`` is first-class: distinct interior-positioning semantics.
_ACTION_MAP: Dict[str, PlayerAction] = {
    "handle_ball": "handle_ball",
    "pass": "pass",
    "receive": "receive",
    "cut": "cut",
    "screen": "screen",
    "shoot": "shoot",
    "stationary": "stationary",
    "post_up": "post_up",
    "get_open": "cut",
    "guard_ball": "guard_ball",
    "guard_offball": "guard_offball",
}

_OFFENSE_POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def _archetype_for_action(action: PlayerAction) -> PlayerArchetype:
    """Per-player archetype derived from action.

    HCO/FCP are paced turns — every player is expected to reach their
    step destination by ``step_clock_seconds[i]``. The slowest mover
    consumes the full step time; faster movers idle. Archetype tags
    rendering pace, not gating.
    """
    if action == "shoot":
        return "shot_motion"
    if action in ("stationary", "post_up"):
        return "stationary"
    return "cruise"


# --- Helpers ---------------------------------------------------------------


def _player_id_at_pos(lineup: Dict[str, Any], pos: str) -> Optional[str]:
    player = lineup.get(pos)
    if player is None:
        return None
    pid = getattr(player, "player_id", None)
    return str(pid) if pid is not None else None


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


def _coords_at_movement_index(
    animations: List[Dict[str, Any]],
    movement_index: int,
) -> Dict[str, GridCoord]:
    """Extract ``{player_id: {x, y}}`` from
    ``animations[i].movement[movement_index].coords`` for every player whose
    movement array reaches that index.
    """
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


# --- Ball-state walk -------------------------------------------------------


def _walk_ball_owners(
    skeleton_steps: List[Dict[str, Any]],
) -> List[tuple]:
    """Walk the skeleton once and produce a list of
    ``(start_owner_pos, end_owner_pos)`` pairs — one per step.

    Continuity rules:
      - A pos with ``handle_ball`` or ``pass`` action holds the ball at step start.
      - A ``pass`` + ``receive`` pair within a step transfers ownership at step end.
      - Otherwise end owner = start owner.

    Maintains a single running owner pointer across the walk to avoid
    off-by-one issues from computing each boundary independently.
    """
    walks: List[tuple] = []
    current_owner: Optional[str] = None
    for step in skeleton_steps:
        pos_actions = step.get("pos_actions") or {}
        for pos in _OFFENSE_POSITIONS:
            action = (pos_actions.get(pos) or {}).get("action")
            if action in ("handle_ball", "pass"):
                current_owner = pos
                break
        start_owner = current_owner
        passers = [
            p for p in _OFFENSE_POSITIONS
            if (pos_actions.get(p) or {}).get("action") == "pass"
        ]
        receivers = [
            p for p in _OFFENSE_POSITIONS
            if (pos_actions.get(p) or {}).get("action") == "receive"
        ]
        if passers and receivers:
            current_owner = receivers[0]
        end_owner = current_owner
        walks.append((start_owner, end_owner))
    return walks


# --- Per-step builders -----------------------------------------------------


def _shooter_pos_in_step(step: Dict[str, Any]) -> Optional[str]:
    """Return the offense position (e.g. ``"PG"``) whose action on this step
    is ``shoot``, or None if no player is shooting. First-match wins.
    """
    pos_actions = step.get("pos_actions") or {}
    for pos in _OFFENSE_POSITIONS:
        action = (pos_actions.get(pos) or {}).get("action")
        if action == "shoot":
            return pos
    return None


def _slowest_mover_id(
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
) -> Optional[str]:
    """Identify the gating player for a paced step — the player with the
    largest start→end traversal distance. Falls back to None if no players
    move (e.g., everyone stationary).
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


def _build_step_destinations_and_actions(
    skeleton_steps: List[Dict[str, Any]],
    step_index: int,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    end_coords: Dict[str, GridCoord],
    bh_defender_pos: Optional[str],
) -> tuple[Dict[str, Optional[GridCoord]], Dict[str, PlayerAction]]:
    """Produce per-player ``destination`` and ``action`` maps for a step.

    Offense actions come from ``skeleton.steps[i].pos_actions``; defender
    actions default to ``guard_offball`` with the BH's defender (when known)
    set to ``guard_ball``.
    """
    destinations: Dict[str, Optional[GridCoord]] = {}
    actions: Dict[str, PlayerAction] = {}

    step_data = skeleton_steps[step_index] if step_index < len(skeleton_steps) else {}
    pos_actions = step_data.get("pos_actions") or {}

    for pos in _OFFENSE_POSITIONS:
        pid = _player_id_at_pos(off_lineup, pos)
        if not pid:
            continue
        skeleton_action = (pos_actions.get(pos) or {}).get("action") or "stationary"
        actions[pid] = _ACTION_MAP.get(skeleton_action, "stationary")
        destinations[pid] = end_coords.get(pid)

    for pos in _OFFENSE_POSITIONS:
        pid = _player_id_at_pos(def_lineup, pos)
        if not pid:
            continue
        if bh_defender_pos and pos == bh_defender_pos:
            actions[pid] = "guard_ball"
        else:
            actions[pid] = "guard_offball"
        destinations[pid] = end_coords.get(pid)

    return destinations, actions


def _build_archetype_map(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    actions: Dict[str, PlayerAction],
) -> Dict[str, PlayerArchetype]:
    """Per-player archetype derived from per-player action."""
    out: Dict[str, PlayerArchetype] = {}
    for lineup in (off_lineup, def_lineup):
        for pos in _OFFENSE_POSITIONS:
            pid = _player_id_at_pos(lineup, pos)
            if not pid:
                continue
            out[pid] = _archetype_for_action(actions.get(pid, "stationary"))
    return out


def _bh_defender_pos(roles: Dict[str, Any]) -> Optional[str]:
    """Resolve the position of the defender on the ball handler from
    ``roles{}``. HCO/FCP roles carry a ``defender`` player object; we read
    its ``.position`` attribute. Returns None if not resolvable.
    """
    defender = roles.get("defender")
    if defender is None:
        return None
    pos = getattr(defender, "position", None)
    return pos if pos in _OFFENSE_POSITIONS else None


# --- Final-step branching --------------------------------------------------


def _resolve_final_step_next(turn_result: Dict[str, Any]) -> NextStep:
    """Map the turn's result_type to the final step's ``next`` pointer.

    Mirrors ``hct_step_emitter._resolve_step_3_next`` — the outcome shape
    is the same. Pre-resolved branching: backend has already computed
    the result; emitter just routes.
    """
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

    if result_type in ("FOUL", "D_FOUL", "O_FOUL"):
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

    if result_type == "SHOT_CLOCK_EXPIRED":
        return {
            "kind": "turn_stop",
            "event": "SHOT_CLOCK_EXPIRED",
            "payload": {},
        }

    # "Continue" / unknown: implicit end of turn — model as next_step past
    # the array so playTurn returns null.
    return {"kind": "next_step", "index": 999}


# --- Top-level emitter -----------------------------------------------------


def build_skeleton_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Convert a skeleton-shaped turn_result (HCO or FCP) into the unified
    AnimationStep[] payload.

    Args:
        turn_result: turn dict containing ``skeleton``, ``animations``,
            ``step_clock_seconds``, ``roles``, ``result_type``.
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

    # Walk over min(skeleton_steps, step_clock_seconds, animation_movements - 1).
    # The legacy animations[] always carries len(skeleton_steps)+1 movement
    # waypoints per player (start + N step ends). step_clock_seconds[] carries
    # one entry per step.
    num_steps = min(len(skeleton_steps), len(step_clock_seconds))
    if num_steps == 0:
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}

    bh_def_pos = _bh_defender_pos(roles)

    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining_at_turn_start = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining_at_turn_start = float(
        game_state.get("shot_clock_remaining", 0) or 0
    )

    ball_walks = _walk_ball_owners(skeleton_steps)

    steps: List[AnimationStep] = []
    elapsed_so_far = 0.0

    for i in range(num_steps):
        start_coords = _coords_at_movement_index(animations, i)
        end_coords = _coords_at_movement_index(animations, i + 1)
        if not start_coords or not end_coords:
            return None

        destinations, actions = _build_step_destinations_and_actions(
            skeleton_steps, i, off_lineup, def_lineup, end_coords, bh_def_pos,
        )
        archetype = _build_archetype_map(off_lineup, def_lineup, actions)

        start_owner_pos, end_owner_pos = (
            ball_walks[i] if i < len(ball_walks) else (None, None)
        )
        owner_id_start = (
            _player_id_at_pos(off_lineup, start_owner_pos) if start_owner_pos else None
        )
        owner_id_end = (
            _player_id_at_pos(off_lineup, end_owner_pos) if end_owner_pos else None
        )

        ball_handler_role = roles.get("ball_handler")
        bh_id_fallback = _safe_id(ball_handler_role) or ""

        ball_start: BallState = (
            {"owner_player_id": owner_id_start} if owner_id_start
            else {"owner_player_id": bh_id_fallback}
        )
        ball_end: BallState = (
            {"owner_player_id": owner_id_end} if owner_id_end
            else {"owner_player_id": bh_id_fallback}
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

        # Per-step trigger: final step gates on the shooter (if any) so the
        # shot motion is the canonical end-of-step event. Other steps and
        # final steps without a shoot action gate on the slowest mover.
        gate_id: Optional[str] = None
        if i == num_steps - 1:
            shooter_pos = _shooter_pos_in_step(skeleton_steps[i])
            if shooter_pos:
                gate_id = _player_id_at_pos(off_lineup, shooter_pos)
        if gate_id is None:
            gate_id = _slowest_mover_id(start_coords, end_coords)
        gate_coord = end_coords.get(gate_id) if gate_id else None
        if gate_id and gate_coord:
            advance_trigger = _build_advance_trigger_player_reaches(gate_id, gate_coord, t)
        else:
            # No movement detected — fall back to ball-handler's end coord.
            fallback_id = bh_id_fallback or "unknown"
            fallback_coord = end_coords.get(fallback_id) or {"x": 50.0, "y": 25.0}
            advance_trigger = _build_advance_trigger_player_reaches(
                fallback_id, fallback_coord, t,
            )

        # Next pointer: linear i+1 except final step (branches on result_type).
        next_step: NextStep
        if i < num_steps - 1:
            next_step = {"kind": "next_step", "index": i + 1}
        else:
            next_step = _resolve_final_step_next(turn_result)

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

    # Movement #1 (post-shot positioning): on the final shot step, override
    # `end.coords` for get-back / release / rebounder players using overlay
    # maps produced by `shot_manager.resolve_shot`. This is how the schema
    # tracks the players' actual post-shot positions (get-back players
    # pulled back to defend, release players ahead toward outlet, rebound
    # attemptors clustered near the rim) — without this, the legacy mid-turn
    # `player.coords` writes (now removed) would leave the schema with stale
    # end positions and the next turn would seed from wrong coords. See
    # `_documentation_master/projects/Animation_System_Updated.md`.
    if steps:
        _apply_post_shot_overlay(steps[-1], turn_result)

    return steps


def _apply_post_shot_overlay(step: AnimationStep, turn_result: Dict[str, Any]) -> None:
    """Override the final shot step's `end.coords` (and start action/archetype)
    for players in shot_manager's post-shot overlay maps.

    Overlay maps:
    - `offense_getback_coords` — offensive players pulled back to defend
    - `defense_release_coords` — defensive players released ahead for outlet
    - `offense_rebounder_coords` — offensive non-get-back players at rebound spots
    """
    end_coords = step.get("end", {}).get("coords")
    start_actions = step.get("start", {}).get("action")
    start_archetype = step.get("start", {}).get("archetype")
    if not isinstance(end_coords, dict):
        return

    for overlay_key in (
        "offense_getback_coords",
        "defense_release_coords",
        "offense_rebounder_coords",
    ):
        overlay = turn_result.get(overlay_key) or {}
        if not isinstance(overlay, dict):
            continue
        for pid, coord in overlay.items():
            if not isinstance(coord, dict):
                continue
            x = coord.get("x")
            y = coord.get("y")
            if x is None or y is None:
                continue
            pid_str = str(pid)
            end_coords[pid_str] = {"x": float(x), "y": float(y)}
            if isinstance(start_actions, dict):
                start_actions[pid_str] = "cut"
            if isinstance(start_archetype, dict):
                start_archetype[pid_str] = "cruise"
