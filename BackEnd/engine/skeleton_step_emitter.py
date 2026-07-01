"""Skeleton-driven animation step emitter.

Converts a turn's skeleton-shaped animation data (skeleton.steps[] +
per-player animations[] + step_clock_seconds[] + roles{}) into the
unified AnimationStep[] payload defined in
``BackEnd/utils/animation_step_schema.py``.

Used by HCO and FCP — both are multi-step paced offensive turns where
each skeleton step represents a synchronized player-position transition
gated by the slowest offensive mover (defense runs in parallel).
HCT has its own emitter
(``hct_step_emitter.py``) because HCT is a fixed 4-step dynamic structure,
not skeleton-driven.

Status: parallel-build infrastructure for the SS&S animation refactor
(see ``_documentation_master/projects/Animation_System_Updated.md``).
Coexists with the legacy ``animations[]`` payload until per-turn-type
cutover.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import (
    AIRBALL_OOB_AWAY_COORDS,
    AIRBALL_OOB_GAME_SECONDS,
    AIRBALL_OOB_HOME_COORDS,
    AWAY_RIM_COORDS,
    BANK_MAKE_SETTLE_GAME_SECONDS,
    BANK_MISS_GRAZE_GAME_SECONDS,
    BOUNCE_STEP_GAME_SECONDS,
    HCO_STEP_T_FLOOR_GAME_SECONDS,
    HOME_RIM_COORDS,
    MADE_SHOT_SWEET_SPOT_AWAY_RIM,
    MADE_SHOT_SWEET_SPOT_HOME_RIM,
    PASS_GRID_SPOTS_PER_GAME_SECOND,
    RATTLE_HOP_GAME_SECONDS,
    RATTLE_MAKE_SETTLE_GAME_SECONDS,
)
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _euclid,
    _player_lookup_by_id,
    build_foul_announcement,
    pass_arrival_sfx,
    pass_release_sfx,
    rattle_hop_sfx,
    rattle_make_settle_sfx,
    shot_followup_timed_sfx,
    shot_launch_sfx,
    shot_result_sfx,
    stamp_hot_shot_trail_metadata,
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
    "drive": "cut",
    "screen": "screen",
    "shoot": "shoot",
    "stationary": "stationary",
    "post_up": "post_up",
    "get_open": "cut",
    "guard_ball": "guard_ball",
    "guard_offball": "guard_offball",
}

_OFFENSE_POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def _archetype_for_action(action: PlayerAction, turn_type: str = "HCO") -> PlayerArchetype:
    """Per-player archetype derived from action.

    HCO/FCP are paced turns — every player is expected to reach their step
    destination by the gate. The slowest gate-eligible mover consumes the
    full step time; faster movers idle. Archetype tags rendering pace, not
    gating.

    Per-turn-type rules:
      - ``shoot`` → ``shot_motion`` (both HCO + FCP)
      - ``stationary`` / ``post_up`` → ``stationary``
      - HCO default → ``cruise``
      - FCP default → ``standard`` (base movement pace for press-break skeleton)
    """
    if action == "shoot":
        return "shot_motion"
    if action in ("stationary", "post_up"):
        return "stationary"
    if turn_type == "FCP":
        return "standard"
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


def _normalize_player_coord_map(
    coords: Optional[Dict[str, Any]],
) -> Dict[str, GridCoord]:
    """Normalize ``{player_id: {x,y}}`` keys to strings for cross-turn lookups."""
    if not isinstance(coords, dict):
        return {}
    out: Dict[str, GridCoord] = {}
    for pid, coord in coords.items():
        if not isinstance(coord, dict):
            continue
        x, y = coord.get("x"), coord.get("y")
        if x is None or y is None:
            continue
        out[str(pid)] = {"x": float(x), "y": float(y)}
    return out


def _attached_owner_from_step_end(step: Optional[Dict[str, Any]]) -> Optional[str]:
    """Return ``owner_player_id`` when a step ends with the ball attached."""
    if not isinstance(step, dict):
        return None
    end_ball = (step.get("end") or {}).get("ball") or {}
    if not isinstance(end_ball, dict):
        return None
    owner = end_ball.get("owner_player_id")
    return str(owner) if owner else None


def _resolve_prior_ball_handler_id(
    prior_turn: Optional[Dict[str, Any]],
    turn_result: Dict[str, Any],
) -> Optional[str]:
    """Resolve who held the ball at the prior turn's end for HCO entry."""
    if not isinstance(prior_turn, dict):
        return None
    stamped = prior_turn.get("final_ball_handler_id")
    if stamped:
        return str(stamped)
    from BackEnd.utils.animation_step_helpers import build_final_ball_handler_id

    rebuilt = build_final_ball_handler_id(prior_turn)
    if rebuilt:
        return str(rebuilt)
    hco_setup = turn_result.get("hco_setup") if isinstance(turn_result, dict) else None
    inbound = (
        hco_setup.get("inbound_pass")
        if isinstance(hco_setup, dict)
        else None
    )
    if isinstance(inbound, dict) and inbound.get("from_player_id"):
        return str(inbound["from_player_id"])
    return None


def _apply_hco_setup_entry_ids(
    current_bh_id: Optional[str],
    step0_bh_id: Optional[str],
    turn_result: Dict[str, Any],
) -> tuple:
    """Align entry BH / receiver when ``hco_setup.inbound_pass`` was propagated."""
    hco_setup = turn_result.get("hco_setup") if isinstance(turn_result, dict) else None
    inbound = (
        hco_setup.get("inbound_pass")
        if isinstance(hco_setup, dict)
        else None
    )
    if not isinstance(inbound, dict):
        return current_bh_id, step0_bh_id
    from_id = inbound.get("from_player_id")
    to_id = inbound.get("to_player_id")
    if from_id and not current_bh_id:
        current_bh_id = str(from_id)
    if to_id and not step0_bh_id:
        step0_bh_id = str(to_id)
    return current_bh_id, step0_bh_id


def _wire_prepended_step_chain(steps: List[AnimationStep]) -> None:
    """Linear next pointers: prepended chain → skeleton step 0."""
    for i, step in enumerate(steps[:-1]):
        step["end"]["next"] = {"kind": "next_step", "index": i + 1}
    if steps:
        steps[-1]["end"]["next"] = {"kind": "next_step", "index": len(steps)}


def _append_hco_minimum_entry_walkup(
    *,
    steps: List[AnimationStep],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    prior_final_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
    bh_id: str,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    elapsed_so_far: float,
    metadata_reason: str = "hco_entry_walkup_minimum",
) -> float:
    """Last-resort entry beat: animate all 10 from prior end → setup targets."""
    from BackEnd.utils.transition_bridge import build_walk_up_step

    clock_r = clock_remaining_at_start - elapsed_so_far
    shot_r = shot_clock_remaining_at_start - elapsed_so_far
    walk_step = build_walk_up_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=prior_final_coords,
        end_coords=end_coords,
        bh_id=str(bh_id),
        clock_remaining_at_start=clock_r,
        shot_clock_remaining_at_start=shot_r,
        next_step_index=len(steps) + 1,
        bh_archetype="cruise",
        other_archetype="sprint",
        gate_player_ids=[str(pid) for pid in prior_final_coords.keys()],
        metadata_reason=metadata_reason,
    )
    if walk_step:
        steps.append(walk_step)
        return float(walk_step["end"]["time_elapsed"])
    return 0.0


# --- Ball-state walk -------------------------------------------------------


def _walk_ball_owners(
    skeleton_steps: List[Dict[str, Any]],
    seed_owner_pos: Optional[str] = None,
) -> List[tuple]:
    """Walk the skeleton once and produce a list of
    ``(start_owner_pos, end_owner_pos)`` pairs — one per step.

    Continuity rules:
      - A pos with ``handle_ball`` or ``pass`` action holds the ball at step start.
      - A ``pass`` + ``receive`` pair within a step transfers ownership at step end.
      - Otherwise end owner = start owner.

    Maintains a single running owner pointer across the walk to avoid
    off-by-one issues from computing each boundary independently.

    ``seed_owner_pos`` seeds the running owner before step 0. Used by FCP
    to carry the BIP-end BH (per ``prior_turn["final_ball_handler_id"]``)
    into the first FCP skeleton step — otherwise FCP step 0 falls back to
    ``roles["ball_handler"]`` (the late-skeleton BH, often a different
    player), which causes the ball to teleport at step 0 end.
    """
    walks: List[tuple] = []
    current_owner: Optional[str] = seed_owner_pos
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


def _final_turn_skeleton_bh_id(
    skeleton_steps: List[Dict[str, Any]],
    off_lineup: Dict[str, Any],
) -> Optional[str]:
    """Return the player id for the Final Turn skeleton step-0 ball handler."""
    if not skeleton_steps:
        return None
    pos_actions = skeleton_steps[0].get("pos_actions") or {}
    for pos in _OFFENSE_POSITIONS:
        action = (pos_actions.get(pos) or {}).get("action")
        if action == "handle_ball":
            return _player_id_at_pos(off_lineup, pos)
    return None


def _append_final_turn_entry_pass_if_needed(
    *,
    steps: List[AnimationStep],
    turn_result: Dict[str, Any],
    prior_turn: Optional[Dict[str, Any]],
    skeleton_steps: List[Dict[str, Any]],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    clock_remaining_at_turn_start: float,
    shot_clock_remaining_at_turn_start: float,
    elapsed_so_far: float,
) -> float:
    """After Final Turn alignment (schema step 0), pass from the live prior-turn
    owner to the skeleton ball handler when they differ (e.g. PG holds after SIP
    but the skeleton drew SF/SG as BH). Uses the universal ``build_pass_step``
    helper at ``PASS_GRID_SPOTS_PER_GAME_SECOND``.
    """
    if not turn_result.get("final_turn") or not steps or not isinstance(prior_turn, dict):
        return elapsed_so_far
    if turn_result.get("final_turn_include_entry_pass") is False:
        return elapsed_so_far
    prior_owner = _resolve_prior_ball_handler_id(prior_turn, turn_result)
    bh_id = _final_turn_skeleton_bh_id(skeleton_steps, off_lineup)
    if not prior_owner or not bh_id or str(prior_owner) == str(bh_id):
        return elapsed_so_far
    from BackEnd.utils.transition_bridge import build_pass_step

    clock_r = clock_remaining_at_turn_start - elapsed_so_far
    shot_r = shot_clock_remaining_at_turn_start - elapsed_so_far
    try:
        entry_index = len(steps)
        skeleton_step_one_index = entry_index + 1
        entry = build_pass_step(
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            start_coords=steps[-1]["end"]["coords"],
            passer_id=str(prior_owner),
            receiver_id=str(bh_id),
            clock_remaining_at_start=clock_r,
            shot_clock_remaining_at_start=shot_r,
            next_step_index=skeleton_step_one_index,
            pass_speed_grid_per_game_sec=float(PASS_GRID_SPOTS_PER_GAME_SECOND),
            metadata_reason="final_turn_entry_pass",
        )
    except ValueError:
        return elapsed_so_far
    entry.setdefault("start", {})["ball_motion_style"] = "pass"
    # Defensive: ``build_pass_step`` must not point back at this step.
    entry["end"]["next"] = {"kind": "next_step", "index": skeleton_step_one_index}
    steps.append(entry)
    return elapsed_so_far + float(entry["end"]["time_elapsed"])


def _append_final_turn_walkup_if_needed(
    *,
    steps: List[AnimationStep],
    turn_result: Dict[str, Any],
    prior_turn: Optional[Dict[str, Any]],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    animations: List[Dict[str, Any]],
    clock_remaining_at_turn_start: float,
    shot_clock_remaining_at_turn_start: float,
    elapsed_so_far: float,
) -> float:
    """Bring the ball upcourt before Final Turn alignment when entering from BIP/SIP."""
    if not turn_result.get("final_turn") or not turn_result.get("final_turn_include_walkup"):
        return elapsed_so_far
    if not isinstance(prior_turn, dict):
        return elapsed_so_far
    prior_final_coords = _normalize_player_coord_map(prior_turn.get("final_coords") or {})
    if not prior_final_coords:
        return elapsed_so_far
    setup_coords = _coords_at_movement_index(animations, 0)
    if not setup_coords:
        return elapsed_so_far
    bh_id = _resolve_prior_ball_handler_id(prior_turn, turn_result)
    if not bh_id:
        from BackEnd.engine.phase_resolution import get_ball_handler_from_skeleton

        skeleton = turn_result.get("skeleton") or {}
        bh_player = get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=0)
        if bh_player is not None:
            pid = getattr(bh_player, "player_id", None)
            bh_id = str(pid) if pid is not None else None
    if not bh_id:
        return elapsed_so_far
    delta = _append_hco_minimum_entry_walkup(
        steps=steps,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        prior_final_coords=prior_final_coords,
        end_coords=setup_coords,
        bh_id=str(bh_id),
        clock_remaining_at_start=clock_remaining_at_turn_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_turn_start,
        elapsed_so_far=elapsed_so_far,
        metadata_reason="final_turn_entry_walkup",
    )
    return elapsed_so_far + delta


def _normalize_flss_terminal_clock_burn(
    steps: List[AnimationStep],
    clock_remaining_at_turn_start: float,
    shot_clock_remaining_at_turn_start: float,
) -> None:
    """Terminal FLSS turns must burn the full remaining game clock to 0:00.

    Sprint-drive FLSS steps carry explicit per-step floors (drive budget + 1s
    shot window); only restamp ``clock`` fields. Legacy stationary FLSS still
    extends step 0 when emitted step times under-burn the remaining clock.
    """
    if not steps:
        return
    clock_start = max(0.0, float(clock_remaining_at_turn_start))
    shot_start = max(0.0, float(shot_clock_remaining_at_turn_start))
    if clock_start <= 0:
        return
    current_sum = sum(float((s.get("end") or {}).get("time_elapsed") or 0) for s in steps)
    if current_sum <= 0:
        return
    has_sprint_drive = any(
        (s.get("start") or {})
        .get("advance_trigger", {})
        .get("metadata", {})
        .get("reason") == "flss_sprint_drive"
        for s in steps
    )
    shortfall = clock_start - current_sum
    if shortfall > 0 and not has_sprint_drive:
        first_end = steps[0].setdefault("end", {})
        first_end["time_elapsed"] = float(first_end.get("time_elapsed") or 0) + shortfall
    elapsed = 0.0
    for step in steps:
        t = float((step.get("end") or {}).get("time_elapsed") or 0)
        step.setdefault("start", {}).setdefault("clock", {})
        step["start"]["clock"]["clock_remaining"] = max(0.0, clock_start - elapsed)
        step["start"]["clock"]["shot_clock_remaining"] = max(0.0, shot_start - elapsed)
        elapsed += t
        step.setdefault("end", {}).setdefault("clock", {})
        step["end"]["clock"]["clock_remaining"] = max(0.0, clock_start - elapsed)
        step["end"]["clock"]["shot_clock_remaining"] = max(0.0, shot_start - elapsed)


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
    turn_type: str = "HCO",
    pos_actions: Optional[Dict[str, Any]] = None,
) -> Dict[str, PlayerArchetype]:
    """Per-player archetype: explicit ``pos_action["archetype"]`` override (offense only) else
    derived from per-player action + turn type. The override lets specific beats render at a
    distinct pace — e.g. Dynamic HCO Motion subtle movers use ``drift`` for a deliberate feel."""
    pos_actions = pos_actions or {}
    out: Dict[str, PlayerArchetype] = {}
    for lineup in (off_lineup, def_lineup):
        for pos in _OFFENSE_POSITIONS:
            pid = _player_id_at_pos(lineup, pos)
            if not pid:
                continue
            override = (pos_actions.get(pos) or {}).get("archetype") if lineup is off_lineup else None
            out[pid] = override or _archetype_for_action(
                actions.get(pid, "stationary"), turn_type
            )
    return out


# --- FCP-specific gate helpers ---------------------------------------------

_FCP_STOPPER_EVENT_TYPES = frozenset({
    "o_foul", "d_foul", "dead_ball_turnover", "steal",
})


def _offensive_player_ids(off_lineup: Dict[str, Any]) -> List[str]:
    """Return all 5 offensive player IDs from the lineup, in PG..C order."""
    out: List[str] = []
    for pos in _OFFENSE_POSITIONS:
        pid = _player_id_at_pos(off_lineup, pos)
        if pid:
            out.append(pid)
    return out


def _slowest_among(
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
    eligible_ids: List[str],
) -> Optional[str]:
    """Pick the player from ``eligible_ids`` with the longest start→end
    distance. Returns None if no eligible player has movement data."""
    longest: Optional[str] = None
    max_dist_sq = -1.0
    for pid in eligible_ids:
        start = start_coords.get(pid)
        end = end_coords.get(pid)
        if start is None or end is None:
            continue
        dx = end["x"] - start["x"]
        dy = end["y"] - start["y"]
        dist_sq = dx * dx + dy * dy
        if dist_sq > max_dist_sq:
            max_dist_sq = dist_sq
            longest = pid
    return longest


def _natural_t(
    pid: str,
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
    archetype: Dict[str, PlayerArchetype],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> float:
    """Compute the natural travel time for a player to reach his step-end
    coord at his archetype rate. Returns 0 if data is missing or distance
    is zero."""
    sc = start_coords.get(pid)
    ec = end_coords.get(pid)
    if sc is None or ec is None:
        return 0.0
    dist = _euclid(sc, ec)
    if dist < 1e-6:
        return 0.0
    arch = archetype.get(pid, "standard")
    player = _player_lookup_by_id(off_lineup, def_lineup, pid)
    rate = _ag_grid_per_game_sec(player, arch)
    if rate <= 0:
        return 0.0
    return dist / rate


def _build_step_end_coords_with_interrupts(
    start_coords: Dict[str, GridCoord],
    destinations: Dict[str, Optional[GridCoord]],
    archetype: Dict[str, PlayerArchetype],
    step_t: float,
    gate_id: Optional[str],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> Dict[str, GridCoord]:
    """UESS §9.5 — gate player reaches full ``destination``; all others end at
    interrupted coord (``start + rate × step_t`` toward destination, clamped).

    UESS §3.2 + §4 decision 10: end.coords MUST include every on-court player
    in start_coords. Players whose ``destinations[pid]`` is None (stationary
    by intent OR missing from the animator's partial movement output)
    carry their start coord forward as their end coord. Without this carry,
    ``_build_post_shot_sub_steps`` would early-bail when the shooter is
    dropped (motion offense's synthetic shoot step often omits the shooter
    from the animator's destinations map → shot_spot=None → no sub-steps
    → no overlay motion + teleport on the next turn).
    """
    final: Dict[str, GridCoord] = {}
    for pid, sc in start_coords.items():
        dest = destinations.get(pid)
        if dest is None:
            # Stationary OR missing destination — keep player at start so
            # they appear in end.coords and downstream sub-steps + overlay
            # logic can find them.
            final[pid] = {"x": float(sc["x"]), "y": float(sc["y"])}
            continue
        if pid == gate_id:
            final[pid] = {"x": float(dest["x"]), "y": float(dest["y"])}
            continue
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        arch = archetype.get(pid, "standard")
        rate = _ag_grid_per_game_sec(player, arch)
        ec, _ = _interpolate_step_end(sc, dest, rate, step_t)
        final[pid] = ec
    return final


def _is_fcp_stopper_action_step(
    skeleton_steps: List[Dict[str, Any]], i: int, num_steps: int,
) -> bool:
    """True iff step ``i`` is the truncated final skeleton step preceding
    the appended event-marker step (the one with ``events`` containing a
    stopper-action type). For FCP, this step gates on the players involved
    in the stop action rather than the slowest offensive player."""
    if i + 1 >= num_steps:
        return False
    next_step = skeleton_steps[i + 1]
    events = next_step.get("events") or []
    for e in events:
        if isinstance(e, dict) and e.get("type") in _FCP_STOPPER_EVENT_TYPES:
            return True
    return False


def _position_of_player_id(
    lineup: Dict[str, Any], player_id: Optional[str],
) -> Optional[str]:
    """Find the lineup position (PG/SG/SF/PF/C) for a given player_id."""
    if not player_id:
        return None
    target = str(player_id)
    for pos, player in (lineup or {}).items():
        if player is None:
            continue
        pid = getattr(player, "player_id", None)
        if pid is not None and str(pid) == target:
            return pos
    return None


def _resolve_fcp_stopper_gate_ids(
    skeleton_steps: List[Dict[str, Any]],
    action_step_index: int,
    turn_result: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    roles: Dict[str, Any],
) -> List[str]:
    """Return the list of player IDs that gate the FCP stopper action step,
    per the FCP gate spec:

      - o_foul: ``foul_player_id`` (offense) + his same-position defender
      - d_foul: ``foul_player_id`` (defense) + his same-position offense
      - steal: ``victim_id`` (offense) + ``stealer_id`` (defense)
      - dead_ball_turnover: BH at stop step + his same-position defender.
        Also covers SHOT_CLOCK_VIOLATION (same event type per
        ``apply_stopper_system_to_skeleton``).

    Defender ↔ offense matchup is strictly 1:1 by lineup position
    (matches ``_position_fcp_defenders`` shadowing rule).
    """
    event_marker_idx = action_step_index + 1
    if event_marker_idx >= len(skeleton_steps):
        return []

    event_marker = skeleton_steps[event_marker_idx]
    events = event_marker.get("events") or []
    stopper_type: Optional[str] = None
    for e in events:
        if isinstance(e, dict) and e.get("type") in _FCP_STOPPER_EVENT_TYPES:
            stopper_type = str(e["type"])
            break
    if stopper_type is None:
        return []

    if stopper_type == "o_foul":
        offense_id = str(turn_result.get("foul_player_id") or "")
        if not offense_id:
            return []
        offense_pos = _position_of_player_id(off_lineup, offense_id)
        defender_id = _player_id_at_pos(def_lineup, offense_pos) if offense_pos else None
        return [pid for pid in (offense_id, defender_id) if pid]

    if stopper_type == "d_foul":
        defender_id = str(turn_result.get("foul_player_id") or "")
        if not defender_id:
            return []
        defender_pos = _position_of_player_id(def_lineup, defender_id)
        offense_id = _player_id_at_pos(off_lineup, defender_pos) if defender_pos else None
        return [pid for pid in (defender_id, offense_id) if pid]

    if stopper_type == "steal":
        victim_id = str(turn_result.get("victim_id") or "")
        stealer_id = str(turn_result.get("stealer_id") or "")
        return [pid for pid in (victim_id, stealer_id) if pid]

    if stopper_type == "dead_ball_turnover":
        # BH at stop step = offense position with a pos_action on the
        # appended event marker (apply_stopper_system_to_skeleton stamps
        # only the BH there with action=handle_ball).
        em_pos_actions = event_marker.get("pos_actions") or {}
        bh_pos: Optional[str] = None
        for pos in _OFFENSE_POSITIONS:
            if em_pos_actions.get(pos):
                bh_pos = pos
                break
        bh_id = _player_id_at_pos(off_lineup, bh_pos) if bh_pos else None
        if not bh_id:
            # Fallback: take BH from roles.
            bh_player = (roles or {}).get("ball_handler")
            bh_id = _safe_id(bh_player)
        if not bh_id:
            return []
        bh_pos_resolved = bh_pos or _position_of_player_id(off_lineup, bh_id)
        defender_id = _player_id_at_pos(def_lineup, bh_pos_resolved) if bh_pos_resolved else None
        return [pid for pid in (bh_id, defender_id) if pid]

    return []


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
    turn_type: str = "HCO",
) -> Optional[List[AnimationStep]]:
    """Convert a skeleton-shaped turn_result (HCO or FCP) into the unified
    AnimationStep[] payload.

    Args:
        turn_result: turn dict containing ``skeleton``, ``animations``,
            ``step_clock_seconds``, ``roles``, ``result_type``.
        game: GameManager (for clock state at turn start).
        turn_type: ``"HCO"`` (default) or ``"FCP"``. Drives whether the entry
            orchestrator (Handoff / Kickout / Walk Up) runs. HCO turns run the
            orchestrator universally; FCP turns skip it (BIP setup positions
            handle their entry seam).

    Returns:
        List[AnimationStep] in step order, or None if required data is
        missing (graceful degradation during parallel-build phase).
    """
    skeleton = turn_result.get("skeleton") or {}
    skeleton_steps: List[Dict[str, Any]] = skeleton.get("steps") or []
    animations: List[Dict[str, Any]] = turn_result.get("animations") or []
    step_clock_seconds: List[float] = turn_result.get("step_clock_seconds") or []
    roles: Dict[str, Any] = turn_result.get("roles") or {}

    # Phase 2 of HCO UESS migration: if the caller didn't stamp ``animations``
    # on the turn_result (HCO drops legacy ``animations[]`` from the payload),
    # build them locally via the animator using the skeleton + lineups. The
    # animator's offense + man/zone defender placement logic is unchanged;
    # only the call site moved from ``resolve_half_court_offense_logic`` to
    # here. ``animations`` stays internal to this emitter and is not written
    # back to ``turn_result``.
    if not animations and skeleton_steps:
        off_team_check = getattr(game, "offense_team", None)
        def_team_check = getattr(game, "defense_team", None)
        off_lineup_check = getattr(off_team_check, "lineup", {}) if off_team_check else {}
        def_lineup_check = getattr(def_team_check, "lineup", {}) if def_team_check else {}
        try:
            from BackEnd.models.animator import Animator
            animations = Animator(game).skeleton_to_animations(
                skeleton,
                off_lineup_check,
                def_lineup_check,
                add_defenders=True,
                is_fcp=(turn_type == "FCP"),
                is_hct=False,
            )
        except Exception as _anim_err:
            import logging as _anim_log
            _anim_log.warning(
                "skeleton_step_emitter: internal animator build failed: %s",
                _anim_err,
            )

    if not skeleton_steps or not animations:
        return None

    # Walk one step per skeleton step. Phase 3 of HCO UESS migration: step T
    # is computed from the gate player's natural travel time inside the loop
    # below, not from the legacy ``step_clock_seconds`` timing contract.
    num_steps = len(skeleton_steps)
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

    # FCP-specific walker seed: carry the BIP-end BH into the first FCP
    # skeleton step's `current_owner` so that early steps without an
    # explicit `handle_ball`/`pass` action don't fall back to
    # ``roles["ball_handler"]`` (which for FCP non-shot turns is the
    # late-skeleton BH, often a different player than the BIP-end BH and
    # causes a visible ball teleport at step 0 end). HCO uses its entry
    # orchestrator for this seam and doesn't need the seed.
    walker_seed_pos: Optional[str] = None
    prior_turns_for_seed = getattr(game, "turns", None) or []
    prior_turn_for_seed = prior_turns_for_seed[-1] if prior_turns_for_seed else None
    if turn_type == "FCP" and isinstance(prior_turn_for_seed, dict):
        prior_bh_id = prior_turn_for_seed.get("final_ball_handler_id")
        if prior_bh_id:
            walker_seed_pos = _position_of_player_id(off_lineup, str(prior_bh_id))

    ball_walks = _walk_ball_owners(skeleton_steps, seed_owner_pos=walker_seed_pos)

    steps: List[AnimationStep] = []
    elapsed_so_far = 0.0
    final_turn_entry_inserted = 0
    final_turn_walkup_prepended = 0

    # =========================================================================
    # HCO Entry Orchestrator — dynamically determines whether to prepend
    # Handoff, Kickout, and/or Walk Up steps before the HCO skeleton fires.
    # Spec: _documentation_master/05_Animation_System/Step_By_Step_System.md
    #
    # Inputs read at HCO start:
    #   current_bh_id    — from prior_turn.final_ball_handler_id (universal)
    #   step0_bh_id      — from current turn's roles.ball_handler (playcall)
    #   bh_start_coord   — from prior_turn.final_coords[current_bh_id]
    #   in_back_court    — bh_start_coord.x < 71 (home) or > 29 (away)
    #
    # Decision tree (mutually exclusive per row, all evaluated):
    #   bh ≠ step0_bh AND in_back_court  → Handoff fires
    #   bh ≠ step0_bh AND NOT in_back   → Kickout fires
    #   in_back_court                   → Walk Up fires (after Handoff if both)
    #
    # Handoff + Kickout are mutually exclusive (opposite x-coord conditions).
    # =========================================================================
    import logging as _hco_entry_log
    prior_turns = getattr(game, "turns", None) or []
    prior_turn = prior_turns[-1] if prior_turns else None
    away_offense = bool(
        getattr(off_team, "team_id", None) == getattr(getattr(game, "away_team", None), "team_id", None)
    )

    # Run the HCO entry orchestrator universally for HCO turns. The decision
    # tree (Handoff / Kickout / Walk Up) is self-deciding — if the BH is
    # already at step 0 position and in frontcourt, nothing prepends. The
    # ``turn_type`` parameter scopes this to HCO; FCP turns skip the
    # orchestrator (their entry seam is the BIP setup positions path).
    # Final Turn carries its own alignment + pass/shoot skeleton; skip the
    # generic HCO entry orchestrator (Handoff/Kickout/Walk Up) so step 0
    # seeds from prior_final_coords and ball ownership stays on the live
    # handler until the skeleton pass step fires.
    is_hco_turn = (
        (turn_type == "HCO")
        and isinstance(prior_turn, dict)
        and not turn_result.get("final_turn")
        and not turn_result.get("flss")
    )
    if is_hco_turn:
        prior_final_coords = _normalize_player_coord_map(
            prior_turn.get("final_coords") or {}
        )
        current_bh_id = _resolve_prior_ball_handler_id(prior_turn, turn_result)

        # Step 0 skeleton BH — the player the HCO playcall expects to handle
        # the ball at step 0. NOTE: ``roles.ball_handler`` resolves to the
        # SHOOTER (final-step BH), not step 0's. Use the helper that walks
        # the skeleton from step 0 specifically.
        from BackEnd.engine.phase_resolution import get_ball_handler_from_skeleton
        step0_bh_player = get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=0)
        step0_bh_id: Optional[str] = None
        if step0_bh_player is not None:
            pid = getattr(step0_bh_player, "player_id", None)
            step0_bh_id = str(pid) if pid is not None else None

        current_bh_id, step0_bh_id = _apply_hco_setup_entry_ids(
            current_bh_id, step0_bh_id, turn_result
        )

        # HCO step 0 setup coords (where the playcall expects players to be
        # at step 0 start). Resolved from animations[0].movement[0].
        setup_coords = _coords_at_movement_index(animations, 0)

        has_entry_inputs = (
            bool(current_bh_id)
            and bool(step0_bh_id)
            and str(current_bh_id) in prior_final_coords
        )

        if not has_entry_inputs:
            # current_bh=None should never happen — every prior turn type
            # should resolve a final ball handler (animation_steps[-1].end.ball,
            # turn_result.ball_handler_id, or roles.ball_handler). When it
            # does, the orchestrator can't fire Handoff/Kickout and the
            # fallback Walk Up below is the only thing keeping HCO from
            # cold-starting (= teleport). Log loudly so we catch the gap.
            if not current_bh_id:
                _last_step_ball = None
                _last_step_next = None
                _last_step_ball_owner = None
                if isinstance(prior_turn, dict):
                    _anim_steps = prior_turn.get("animation_steps") or []
                    if _anim_steps and isinstance(_anim_steps[-1], dict):
                        _last_step_end = _anim_steps[-1].get("end") or {}
                        _last_step_ball = _last_step_end.get("ball")
                        _last_step_next = _last_step_end.get("next")
                        if isinstance(_last_step_ball, dict):
                            _last_step_ball_owner = _last_step_ball.get("owner_player_id")
                _hco_entry_log.error(
                    "❌❌❌ [HCO ENTRY BUG] current_bh_id is None — prior turn "
                    "failed to stamp a final ball handler. step0_bh=%s "
                    "prior_turn.result_type=%s prior_turn.current_turn=%s "
                    "prior_turn.fast_break_play=%s "
                    "prior_turn.has_animation_steps=%s "
                    "prior_turn.final_ball_handler_id=%s "
                    "prior_turn.ball_handler_id=%s prior_turn.roles.ball_handler=%s "
                    "prior_turn.rebounderId=%s prior_turn.rebound_type=%s "
                    "prior_turn.ball_bounce_x=%s prior_turn.ball_bounce_y=%s "
                    "prior_turn.next_play_type=%s "
                    "prior_turn.last_step.end.next=%s "
                    "prior_turn.last_step.end.ball=%s "
                    "prior_turn.last_step.end.ball.owner_player_id=%s. "
                    "Falling back to minimum walk-up; investigate the "
                    "prior emitter's final_ball_handler_id resolution AND whether "
                    "_build_dreb_turn_from_miss should have fired but didn't.",
                    step0_bh_id,
                    prior_turn.get("result_type") if isinstance(prior_turn, dict) else None,
                    prior_turn.get("current_turn") if isinstance(prior_turn, dict) else None,
                    prior_turn.get("fast_break_play") if isinstance(prior_turn, dict) else None,
                    bool(prior_turn.get("animation_steps")) if isinstance(prior_turn, dict) else False,
                    prior_turn.get("final_ball_handler_id") if isinstance(prior_turn, dict) else None,
                    prior_turn.get("ball_handler_id") if isinstance(prior_turn, dict) else None,
                    (prior_turn.get("roles") or {}).get("ball_handler") if isinstance(prior_turn, dict) else None,
                    prior_turn.get("rebounderId") if isinstance(prior_turn, dict) else None,
                    prior_turn.get("rebound_type") if isinstance(prior_turn, dict) else None,
                    prior_turn.get("ball_bounce_x") if isinstance(prior_turn, dict) else None,
                    prior_turn.get("ball_bounce_y") if isinstance(prior_turn, dict) else None,
                    prior_turn.get("next_play_type") if isinstance(prior_turn, dict) else None,
                    _last_step_next,
                    _last_step_ball,
                    _last_step_ball_owner,
                )
            _hco_entry_log.warning(
                "🏠 [ENTRY] SKIP missing inputs: current_bh=%s step0_bh=%s "
                "current_bh_in_final_coords=%s",
                current_bh_id, step0_bh_id,
                current_bh_id in prior_final_coords if current_bh_id else False,
            )
            end_targets = setup_coords or {}
            walk_bh = step0_bh_id or current_bh_id
            if end_targets and prior_final_coords and walk_bh:
                elapsed_delta = _append_hco_minimum_entry_walkup(
                    steps=steps,
                    off_lineup=off_lineup,
                    def_lineup=def_lineup,
                    prior_final_coords=prior_final_coords,
                    end_coords=end_targets,
                    bh_id=str(walk_bh),
                    clock_remaining_at_start=clock_remaining_at_turn_start,
                    shot_clock_remaining_at_start=shot_clock_remaining_at_turn_start,
                    elapsed_so_far=elapsed_so_far,
                    metadata_reason="hco_entry_walkup_fallback",
                )
                if elapsed_delta:
                    elapsed_so_far += elapsed_delta
                    _hco_entry_log.warning(
                        "🏠 [ENTRY WALKUP FALLBACK FIRED] bh=%s", walk_bh,
                    )
        else:
            bh_start_coord = prior_final_coords[str(current_bh_id)]
            bh_x = float(bh_start_coord.get("x", 50.0))
            in_back_court = (bh_x < 71.0) if not away_offense else (bh_x > 29.0)
            bh_neq_step0 = (str(current_bh_id) != str(step0_bh_id))

            _hco_entry_log.warning(
                "🏠 [ENTRY] current_bh=%s step0_bh=%s bh_x=%.1f away=%s "
                "in_back_court=%s bh_neq_step0=%s",
                current_bh_id, step0_bh_id, bh_x, away_offense,
                in_back_court, bh_neq_step0,
            )

            clock_r = clock_remaining_at_turn_start - elapsed_so_far
            shot_r = shot_clock_remaining_at_turn_start - elapsed_so_far
            kickout_appended = False

            # --- Handoff (BH ≠ PG: converge + pass) / Handoff hold (BH == PG:
            # hold beat per tempo) / Kickout. Handoff fires in backcourt for
            # both BH≠PG and BH==PG cases — `build_handoff_step` internally
            # branches on bh_id == receiver_id to emit the hold variant
            # (Step_By_Step §Handoff Step). Kickout fires only when BH ≠ PG
            # AND in frontcourt. ---
            if in_back_court:
                from BackEnd.utils.transition_bridge import build_handoff_step
                handoff_steps = build_handoff_step(
                    off_lineup=off_lineup,
                    def_lineup=def_lineup,
                    start_coords=prior_final_coords,
                    bh_id=str(current_bh_id),
                    receiver_id=str(step0_bh_id),
                    is_away_offense=away_offense,
                    clock_remaining_at_start=clock_r,
                    shot_clock_remaining_at_start=shot_r,
                    next_step_index=len(steps),
                    metadata_reason="hco_entry_handoff",
                    # Drift non-key players toward their actual HCO step 0
                    # positions so the Handoff → Walk Up seam is continuous
                    # (no random lane drift → setup_coords teleport).
                    setup_coords=setup_coords,
                )
                if handoff_steps:
                    steps.extend(handoff_steps)
                    tail_clock = handoff_steps[-1]["end"]["clock"]
                    elapsed_so_far += sum(s["end"]["time_elapsed"] for s in handoff_steps)
                    clock_r = tail_clock["clock_remaining"]
                    shot_r = tail_clock["shot_clock_remaining"]
                    _hco_entry_log.warning(
                        "🏠 [ENTRY HANDOFF FIRED] steps=%d bh_eq_step0=%s",
                        len(handoff_steps), not bh_neq_step0,
                    )
            elif bh_neq_step0:
                from BackEnd.utils.transition_bridge import build_kickout_step
                if setup_coords:
                    kickout_steps = build_kickout_step(
                        off_lineup=off_lineup,
                        def_lineup=def_lineup,
                        start_coords=prior_final_coords,
                        bh_id=str(current_bh_id),
                        receiver_id=str(step0_bh_id),
                        setup_coords=setup_coords,
                        is_away_offense=away_offense,
                        clock_remaining_at_start=clock_r,
                        shot_clock_remaining_at_start=shot_r,
                        next_step_index=len(steps),
                        metadata_reason="hco_entry_kickout",
                    )
                    if kickout_steps:
                        kickout_appended = True
                        steps.extend(kickout_steps)
                        tail_clock = kickout_steps[-1]["end"]["clock"]
                        elapsed_so_far += sum(s["end"]["time_elapsed"] for s in kickout_steps)
                        clock_r = tail_clock["clock_remaining"]
                        shot_r = tail_clock["shot_clock_remaining"]
                        _hco_entry_log.warning(
                            "🏠 [ENTRY KICKOUT FIRED] steps=%d", len(kickout_steps),
                        )

            # --- Walk Up (fires after Handoff, OR alone if BH = step0_bh in
            # backcourt, OR as fallback when neither Handoff nor Kickout
            # fired — e.g. FB Defensive Stop → HCO where BH = step 0 BH
            # AND BH is in frontcourt). Skip only when Kickout actually
            # appended steps (not merely when the kickout branch was evaluated).
            if setup_coords and not kickout_appended:
                from BackEnd.utils.transition_bridge import build_walk_up_step
                # After Handoff, the receiver (step0_bh) has the ball.
                # Without Handoff, current_bh is still the carrier.
                handoff_fired = bool(steps)
                walk_bh_id = str(step0_bh_id) if (bh_neq_step0 and handoff_fired) else str(current_bh_id)
                walk_start_coords = (
                    dict(steps[-1]["end"]["coords"]) if steps else prior_final_coords
                )
                walk_step = build_walk_up_step(
                    off_lineup=off_lineup,
                    def_lineup=def_lineup,
                    start_coords=walk_start_coords,
                    end_coords=setup_coords,
                    bh_id=walk_bh_id,
                    clock_remaining_at_start=clock_r,
                    shot_clock_remaining_at_start=shot_r,
                    next_step_index=len(steps) + 1,
                    bh_archetype="standard",
                    other_archetype="standard",
                    gate_player_ids=[walk_bh_id],
                    metadata_reason="hco_entry_walkup",
                )
                steps.append(walk_step)
                elapsed_so_far += walk_step["end"]["time_elapsed"]
                _hco_entry_log.warning(
                    "🏠 [ENTRY WALKUP FIRED] bh=%s", walk_bh_id,
                )

        # Never cold-start HCO: if the decision tree prepended nothing, force
        # a minimum walk-up from prior end → setup targets (all 10 gated).
        if not steps and prior_final_coords:
            end_targets = setup_coords or _coords_at_movement_index(animations, 0)
            walk_bh = step0_bh_id or current_bh_id
            if not walk_bh:
                pg = off_lineup.get("PG")
                walk_bh = str(getattr(pg, "player_id", "")) if pg else None
            if end_targets and walk_bh:
                elapsed_delta = _append_hco_minimum_entry_walkup(
                    steps=steps,
                    off_lineup=off_lineup,
                    def_lineup=def_lineup,
                    prior_final_coords=prior_final_coords,
                    end_coords=end_targets,
                    bh_id=str(walk_bh),
                    clock_remaining_at_start=clock_remaining_at_turn_start,
                    shot_clock_remaining_at_start=shot_clock_remaining_at_turn_start,
                    elapsed_so_far=elapsed_so_far,
                    metadata_reason="hco_entry_walkup_minimum",
                )
                if elapsed_delta:
                    elapsed_so_far += elapsed_delta
                    _hco_entry_log.warning(
                        "🏠 [ENTRY MINIMUM WALKUP FIRED] bh=%s", walk_bh,
                    )

        _wire_prepended_step_chain(steps)

    reset_count = len(steps)

    # FCP turns enter with BIP-end coords randomized per
    # `_build_fcp_setup_positions` — these don't match the skeleton's
    # authored step-0 locations, so the first emitted step's start_coords
    # must seed from `prior_turn.final_coords` (not the skeleton). Players
    # animate from BIP-end toward step 0's authored destinations at their
    # archetype rate; non-gate movers end at the interrupted coord per
    # §9.5. Without this, the visual would teleport from BIP-end to step 0.
    # HCO already handles the BIP→step-0 seam via the entry orchestrator
    # (Handoff / Kickout / Walk Up). When that still prepends nothing,
    # seed skeleton step 0 from prior final_coords (FCP-style fallback).
    fcp_seed_coords: Optional[Dict[str, GridCoord]] = None
    hco_seed_coords: Optional[Dict[str, GridCoord]] = None
    flss_seed_coords: Optional[Dict[str, GridCoord]] = None
    if turn_result.get("flss") and isinstance(prior_turn, dict):
        shooter_id = turn_result.get("shooter_id")
        shooter_coords = turn_result.get("shooter_coords") or {}
        if shooter_id and isinstance(shooter_coords, dict):
            flss_seed_coords = _normalize_player_coord_map(
                prior_turn.get("final_coords") or {}
            )
            flss_seed_coords[str(shooter_id)] = {
                "x": float(shooter_coords.get("x", 50)),
                "y": float(shooter_coords.get("y", 25)),
            }
    elif turn_type == "FCP" and isinstance(prior_turn, dict):
        prior_fc = prior_turn.get("final_coords") or {}
        if isinstance(prior_fc, dict) and prior_fc:
            fcp_seed_coords = _normalize_player_coord_map(prior_fc)
    elif turn_type == "HCO" and reset_count == 0 and isinstance(prior_turn, dict) and not turn_result.get("flss"):
        prior_fc = _normalize_player_coord_map(prior_turn.get("final_coords") or {})
        if prior_fc:
            hco_seed_coords = prior_fc

    if turn_result.get("final_turn") and reset_count == 0:
        before_walk = len(steps)
        elapsed_so_far = _append_final_turn_walkup_if_needed(
            steps=steps,
            turn_result=turn_result,
            prior_turn=prior_turn if isinstance(prior_turn, dict) else None,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            animations=animations,
            clock_remaining_at_turn_start=clock_remaining_at_turn_start,
            shot_clock_remaining_at_turn_start=shot_clock_remaining_at_turn_start,
            elapsed_so_far=elapsed_so_far,
        )
        if len(steps) > before_walk:
            final_turn_walkup_prepended = 1
            hco_seed_coords = None

    # All prepended steps (Reset, Final Turn walk-up) shift skeleton indices in
    # the emitted ``animation_steps`` array. Capture once here — walk-up is
    # appended after ``reset_count`` is set above.
    skeleton_base_index = len(steps)

    for i in range(num_steps):
        # When Reset or Final Turn walk-up prepended, skeleton step 0's start
        # coords = prior prepended step end coords.
        if i == 0 and (reset_count > 0 or final_turn_walkup_prepended) and steps:
            start_coords = dict(steps[-1]["end"]["coords"])
        elif i == 0 and flss_seed_coords:
            anim_step0 = _coords_at_movement_index(animations, i)
            start_coords = dict(anim_step0) if anim_step0 else {}
            for pid, coord in flss_seed_coords.items():
                start_coords[pid] = dict(coord)
        elif i == 0 and fcp_seed_coords:
            # FCP: step 0 starts from BIP-end (randomized setup). See
            # comment above the loop. Falls back to the legacy animations
            # source if final_coords is missing any player.
            anim_step0 = _coords_at_movement_index(animations, i)
            start_coords = dict(anim_step0)
            for pid, coord in fcp_seed_coords.items():
                start_coords[pid] = dict(coord)
        elif i == 0 and hco_seed_coords:
            anim_step0 = _coords_at_movement_index(animations, i)
            start_coords = dict(anim_step0)
            for pid, coord in hco_seed_coords.items():
                start_coords[pid] = dict(coord)
        elif i >= 1 and steps:
            # UESS §8.1: step N+1 start.coords MUST equal step N end.coords
            # per player. Without this, non-gate movers interrupted at step N
            # (per §9.5) would teleport to the animator's skeleton waypoint
            # at step N+1 start. Fall back to the animator's coord per-pid
            # only when prior end is missing that pid (e.g., stationary
            # players currently dropped from end.coords until decision 10
            # ships).
            prior_end = steps[-1]["end"]["coords"]
            anim_start = _coords_at_movement_index(animations, i)
            start_coords = {**anim_start, **prior_end}
        else:
            start_coords = _coords_at_movement_index(animations, i)
        end_coords = _coords_at_movement_index(animations, i + 1)
        # Legacy animations[].movement is often 1 waypoint short of the
        # schema's contract (N steps need N+1 waypoints, legacy provides N).
        # On the final step, fall back to start_coords (stationary) when
        # end_coords is empty — _apply_post_shot_overlay then overrides
        # rebounder/getback positions for shot turns. Without this fallback,
        # any prepended Reset steps would be nuked along with the rest.
        if not end_coords and i == num_steps - 1:
            end_coords = dict(start_coords)
        if not start_coords or not end_coords:
            import logging as _emitter_bail_log
            _emitter_bail_log.warning(
                "🔍 [EMITTER BAIL] returning None at step i=%d num_steps=%d "
                "start_coords_present=%s (n=%d) end_coords_present=%s (n=%d) "
                "reset_count=%d steps_built=%d animations_len=%d",
                i, num_steps,
                bool(start_coords), len(start_coords or {}),
                bool(end_coords), len(end_coords or {}),
                reset_count, len(steps), len(animations),
            )
            return None

        destinations, actions = _build_step_destinations_and_actions(
            skeleton_steps, i, off_lineup, def_lineup, end_coords, bh_def_pos,
        )
        archetype = _build_archetype_map(
            off_lineup, def_lineup, actions, turn_type,
            pos_actions=(skeleton_steps[i].get("pos_actions") if i < len(skeleton_steps) else None),
        )

        start_owner_pos, end_owner_pos = (
            ball_walks[i] if i < len(ball_walks) else (None, None)
        )
        owner_id_start = (
            _player_id_at_pos(off_lineup, start_owner_pos) if start_owner_pos else None
        )
        owner_id_end = (
            _player_id_at_pos(off_lineup, end_owner_pos) if end_owner_pos else None
        )

        # Entry-chain seam: player coords for skeleton step 0 already seed
        # from ``steps[reset_count - 1].end.coords`` when prepended Reset
        # steps exist. Carry ball ownership the same way — otherwise
        # ``_walk_ball_owners`` reads skeleton step 0's PG ``pass`` action and
        # re-stamps PG as holder even though Handoff/Walk Up already delivered
        # to ``step0_bh_id`` (the playcall's step-0 receiver).
        if i == 0 and reset_count > 0:
            prepended_owner = _attached_owner_from_step_end(steps[reset_count - 1])
            if prepended_owner:
                owner_id_start = prepended_owner

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

        # Final Turn step 0: keep the live prior-turn ball owner on the ball
        # through alignment + clock hold. Do not transfer to the skeleton BH
        # here — ``_append_final_turn_entry_pass_if_needed`` emits a canonical
        # pass step when prior owner ≠ BH (e.g. SIP receiver SG → BH PG).
        if (
            i == 0
            and reset_count == 0
            and turn_result.get("final_turn")
            and isinstance(prior_turn, dict)
        ):
            prior_owner = _resolve_prior_ball_handler_id(prior_turn, turn_result)
            if prior_owner:
                ball_start = {"owner_player_id": prior_owner}
                ball_end = {"owner_player_id": prior_owner}
                owner_id_start = prior_owner
                owner_id_end = prior_owner

        # Detect pass step (ball ownership transfer) early — used both by
        # gate selection (FCP) and by the later ball_motion_style /
        # ball_arrival_coord / SFX stamping block. Use resolved player ids
        # (not skeleton positions) so the entry-chain seam override above
        # suppresses a duplicate PG→receiver pass when the ball already
        # arrived via Handoff/Walk Up.
        is_pass_step = (
            bool(owner_id_start)
            and bool(owner_id_end)
            and str(owner_id_start) != str(owner_id_end)
        )

        # === Gate selection ====================================================
        # HCO + FCP: shooter on the shot step; otherwise slowest offensive player
        # (matches main-branch offense-gated step advance). FCP stopper-action
        # steps gate on players involved in the stop event. Pass steps also
        # factor ball pass time at PASS_GRID_SPOTS_PER_GAME_SECOND below.
        gate_id: Optional[str] = None
        gate_kind: str = "slowest"
        is_fcp = (turn_type == "FCP")

        # 1) Shot step — shooter is always the gate (HCO and FCP).
        if i == num_steps - 1:
            shooter_pos = _shooter_pos_in_step(skeleton_steps[i])
            if shooter_pos:
                gate_id = _player_id_at_pos(off_lineup, shooter_pos)
                gate_kind = "shooter"

        # 1b) Motion attack drive step — gate on the driver explicitly.
        if gate_id is None and turn_type == "HCO":
            attack_meta = skeleton_steps[i].get("_attack_drive") or {}
            if attack_meta.get("driver_gate"):
                driver_pos = attack_meta.get("gate_driver_pos")
                if driver_pos:
                    gate_id = _player_id_at_pos(off_lineup, driver_pos)
                    gate_kind = "attack_drive_driver"

        # 1c) FLSS sprint drive — gate on ball handler until 1s remains.
        if gate_id is None and turn_type == "HCO" and skeleton_steps[i].get("_flss_sprint_drive"):
            driver_pos = skeleton_steps[i].get("_flss_gate_driver_pos")
            if driver_pos:
                gate_id = _player_id_at_pos(off_lineup, driver_pos)
                gate_kind = "flss_drive_driver"

        # 2) FCP stopper action step (truncated final skeleton step before
        # the appended event marker). Gate on the players involved in the
        # stop action.
        fcp_stopper_ids: List[str] = []
        if gate_id is None and is_fcp and _is_fcp_stopper_action_step(
            skeleton_steps, i, num_steps,
        ):
            fcp_stopper_ids = _resolve_fcp_stopper_gate_ids(
                skeleton_steps, i, turn_result, off_lineup, def_lineup, roles,
            )
            if fcp_stopper_ids:
                gate_id = _slowest_among(start_coords, end_coords, fcp_stopper_ids)
                gate_kind = "fcp_stopper"

        # 3) HCO + FCP non-stopper steps: slowest offensive player (NOT slowest
        # of all 10). Pass step also factors in ball pass time below.
        if gate_id is None and (is_fcp or turn_type == "HCO"):
            offense_ids = _offensive_player_ids(off_lineup)
            gate_id = _slowest_among(start_coords, end_coords, offense_ids)
            gate_kind = "fcp_offense_slowest" if is_fcp else "hco_offense_slowest"

        # === Step T computation ================================================
        # natural_t from the gate player's travel time at their archetype rate.
        # FCP pass step also considers ball travel time at the canonical pass
        # rate; whichever is longer determines step T.
        gate_coord = end_coords.get(gate_id) if gate_id else None
        natural_t = 0.0
        if gate_id and gate_coord:
            natural_t = _natural_t(
                gate_id, start_coords, end_coords, archetype,
                off_lineup, def_lineup,
            )

        # Pass step (HCO + FCP): also gate on the ball reaching the receiver.
        # Step T = max(slowest_player_natural, ball_pass_time, floor) so the
        # FE ball tween (PASS_GRID_SPOTS_PER_GAME_SECOND) completes within
        # step T. Without this gate, short-distance pass steps end before the
        # ball arrives, and the ball appears to animate after players finish.
        ball_pass_t = 0.0
        pass_target_coord: Optional[GridCoord] = None
        if is_pass_step and owner_id_start and owner_id_end:
            passer_start = start_coords.get(owner_id_start)
            receiver_start = start_coords.get(owner_id_end)
            receiver_end = end_coords.get(owner_id_end)
            if passer_start and receiver_start and receiver_end:
                receiver_player = _player_lookup_by_id(
                    off_lineup, def_lineup, owner_id_end,
                )
                receiver_arch = archetype.get(owner_id_end, "standard")
                receiver_rate = _ag_grid_per_game_sec(receiver_player, receiver_arch)
                pass_target_coord = _compute_pass_meet_point(
                    passer_start, receiver_start, receiver_end, receiver_rate,
                )
                ball_pass_t = (
                    _euclid(passer_start, pass_target_coord)
                    / float(PASS_GRID_SPOTS_PER_GAME_SECOND)
                )

        # Shot steps should release as soon as the shooter reaches the shot
        # spot. Applying the generic HCO floor here creates visible dead-air
        # between the shooter settling and the [ball_flight] sub-step.
        # A source step may carry an explicit elapsed FLOOR (Dynamic HCO subtle beats set a
        # tempo-based floor so the deliberate "feeling-out" pace consumes real game/shot clock;
        # a shot-clock-expiry forced shot sets it to the time down to 1s). Honor it over the
        # generic HCO floor; the slowest mover's natural travel can still exceed it.
        step_floor = (
            skeleton_steps[i].get("_step_t_floor_game_seconds")
            if i < len(skeleton_steps) else None
        )
        if gate_kind == "shooter" and not is_pass_step:
            if turn_result.get("flss") and step_floor is not None:
                t = max(float(step_floor), natural_t)
            else:
                t = max(0.05, natural_t)
        elif gate_kind == "attack_drive_driver" and not is_pass_step:
            t = max(0.05, natural_t)
        elif gate_kind == "flss_drive_driver" and not is_pass_step:
            t = max(float(step_floor or 0.05), natural_t)
        elif (
            step_floor is not None
            and turn_result.get("final_turn")
            and i == 0
            and not is_pass_step
        ):
            # Final Shot alignment hold is budgeted to hit the outside/attack
            # anchor — do not let slow movers extend step 0 past the floor.
            t = float(step_floor)
        elif step_floor is not None:
            t = max(float(step_floor), natural_t, ball_pass_t)
        else:
            t = max(HCO_STEP_T_FLOOR_GAME_SECONDS, natural_t, ball_pass_t)

        # UESS §9.5: only the gate player is guaranteed to reach skeleton
        # destination; defenders and other non-gate movers freeze at
        # interrupted coords when step T elapses before they arrive.
        final_end_coords = _build_step_end_coords_with_interrupts(
            start_coords,
            destinations,
            archetype,
            t,
            gate_id,
            off_lineup,
            def_lineup,
        )
        if turn_result.get("flss") and i == num_steps - 1:
            _stamp_flss_shooter_on_step_end(
                final_end_coords,
                turn_result,
                off_lineup,
                skeleton_steps[i],
            )

        clock_start: ClockState = {
            "clock_remaining": clock_remaining_at_turn_start - elapsed_so_far,
            "shot_clock_remaining": shot_clock_remaining_at_turn_start - elapsed_so_far,
        }
        clock_end: ClockState = {
            "clock_remaining": clock_remaining_at_turn_start - elapsed_so_far - t,
            "shot_clock_remaining": shot_clock_remaining_at_turn_start - elapsed_so_far - t,
        }

        # AT condition: when this is a pass step and the ball is the longer
        # gate, report ``ball_reaches_player`` so the FE-visible advance
        # trigger reflects the actual gating event. Otherwise
        # ``player_reaches_position``.
        if (
            is_pass_step and ball_pass_t > 0
            and ball_pass_t >= natural_t
            and pass_target_coord is not None
            and owner_id_end
        ):
            advance_trigger: AdvanceTrigger = {
                "condition": "ball_reaches_player",
                "T_game_seconds": float(t),
                "metadata": {
                    "target_player_id": str(owner_id_end),
                    "target_coords": dict(pass_target_coord),
                },
            }
        elif gate_id and gate_coord:
            advance_trigger = _build_advance_trigger_player_reaches(gate_id, gate_coord, t)
            if skeleton_steps[i].get("_flss_sprint_drive"):
                advance_trigger.setdefault("metadata", {})["reason"] = "flss_sprint_drive"
        else:
            # No movement detected — fall back to ball-handler's end coord.
            fallback_id = bh_id_fallback or "unknown"
            fallback_coord = end_coords.get(fallback_id) or {"x": 50.0, "y": 25.0}
            advance_trigger = _build_advance_trigger_player_reaches(
                fallback_id, fallback_coord, t,
            )

        # Next pointer: linear i+1 except final step (branches on result_type).
        # When Reset is prepended, shift skeleton step indices by reset_count
        # so the chain references the final steps array correctly.
        next_step: NextStep
        if i < num_steps - 1:
            entry_offset = final_turn_entry_inserted if i > 0 else 0
            next_step = {
                "kind": "next_step",
                "index": skeleton_base_index + i + 1 + entry_offset,
            }
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
                "coords": final_end_coords,
                "ball": ball_end,
                "time_elapsed": t,
                "clock": clock_end,
                "next": next_step,
            },
        }
        # Mid-skeleton pass steps: stamp ``ball_motion_style="pass"`` so the
        # ball tweens at the canonical half-court pass rate
        # (PASS_GRID_SPOTS_PER_GAME_SECOND) independent of step T (which is
        # gated by the slowest offensive player and would otherwise drag the
        # ball below the pass rate). Detected via ownership transfer on this step.
        #
        # Also stamp ``ball_arrival_coord`` — the meet-point where the ball
        # intercepts the receiver (their interpolated position at ball
        # arrival time, not their step-end coord). The FE tweens the ball
        # to this point and attaches it to the receiver on tween completion;
        # the ball then follows the receiver via parent transform for the
        # remainder of step T. Critical when the receiver is still moving
        # during the pass — otherwise the ball would land on the receiver's
        # empty step-end position, then jump to the receiver's actual
        # sprite on attach.
        # (``is_pass_step`` was already computed above for gate selection.)
        if is_pass_step:
            step["start"]["ball_motion_style"] = "pass"
            passer_id_mp = owner_id_start
            receiver_id_mp = owner_id_end
            if passer_id_mp and receiver_id_mp:
                passer_start_coord = start_coords.get(passer_id_mp)
                receiver_start_coord = start_coords.get(receiver_id_mp)
                receiver_end_coord = end_coords.get(receiver_id_mp)
                passer_player = _player_lookup_by_id(
                    off_lineup, def_lineup, passer_id_mp,
                )
                receiver_player = _player_lookup_by_id(
                    off_lineup, def_lineup, receiver_id_mp,
                )
                if (passer_start_coord and receiver_start_coord
                    and receiver_end_coord):
                    receiver_archetype = archetype.get(receiver_id_mp, "standard")
                    receiver_rate = _ag_grid_per_game_sec(
                        receiver_player, receiver_archetype,
                    )
                    meet = _compute_pass_meet_point(
                        passer_start_coord,
                        receiver_start_coord,
                        receiver_end_coord,
                        receiver_rate,
                    )
                    step["start"]["ball_arrival_coord"] = meet

                # Pass / Reception SFX (SFX_System.md).
                # Backend resolves the tier from attributes; FE just plays.
                step["start"]["sfx_on_ball_release"] = pass_release_sfx(passer_player)
                step["start"]["sfx_on_ball_arrival"] = pass_arrival_sfx(receiver_player)
        # Dynamic HCO Motion hot-read VO: the resolver flags the initiation skeleton step with
        # ``_hot_read_sfx``. Fire it at step-processing start (not ball motion) so it doesn't
        # collide with the shot/pass launch sound. See SFX_System.md.
        if i < len(skeleton_steps):
            hot_read_clip = (skeleton_steps[i] or {}).get("_hot_read_sfx")
            if hot_read_clip:
                step.setdefault("start", {})["sfx_on_step_start"] = {
                    "file": hot_read_clip, "event": "hot_read", "volume": 0.7,
                }
            # Dynamic HCO steal / reach-in: the resolver tags the stopper step with the on-ball
            # defender (``reach_in_def_id``). Stamp a render-space ``reach_in`` flourish so the FE
            # lunges that defender at the ball + plays the steal cue (click-steal.wav). Mirrors
            # the HCT emitter; render-only, never mutates gameplay coords (UESS-safe).
            reach_in_id = (skeleton_steps[i] or {}).get("reach_in_def_id")
            if reach_in_id:
                step.setdefault("start", {}).setdefault("flourish", {})[reach_in_id] = {
                    "kind": "reach_in", "target": "ball",
                }
            # Dynamic HCO Motion subtle beat: the resolver rolled per-player render-space
            # ``idle_wander`` assignments (cosmetic; fills the frozen tail of the 2-4s beat).
            # Stamp them as flourishes (FE spans each to the step's own duration). Render-only,
            # never mutates gameplay coords (UESS-safe); does not clobber a reach_in.
            idle_motion = ((skeleton_steps[i] or {}).get("_subtle_movement") or {}).get("idle_motion") or {}
            if idle_motion:
                flourish_map = step.setdefault("start", {}).setdefault("flourish", {})
                for _pid, _params in idle_motion.items():
                    if _pid in flourish_map:
                        continue
                    flourish_map[_pid] = {
                        "kind": "idle_wander",
                        "style": _params.get("style", "wander"),
                        "seed": int(_params.get("seed", 0)),
                        "dir_x": float(_params.get("dir_x", 0.0)),
                        "dir_y": float(_params.get("dir_y", 1.0)),
                        "amplitude_grid": float(
                            _params.get("amplitude_grid", _params.get("radius_grid", 1.0))
                        ),
                    }
        stamp_tween_durations(
            step["start"], final_end_coords, t, off_lineup, def_lineup,
        )
        steps.append(step)
        elapsed_so_far += t

        if i == 0 and reset_count == 0 and turn_result.get("final_turn"):
            before_len = len(steps)
            elapsed_so_far = _append_final_turn_entry_pass_if_needed(
                steps=steps,
                turn_result=turn_result,
                prior_turn=prior_turn,
                skeleton_steps=skeleton_steps,
                off_lineup=off_lineup,
                def_lineup=def_lineup,
                clock_remaining_at_turn_start=clock_remaining_at_turn_start,
                shot_clock_remaining_at_turn_start=shot_clock_remaining_at_turn_start,
                elapsed_so_far=elapsed_so_far,
            )
            if len(steps) > before_len:
                final_turn_entry_inserted = 1

    # Post-shot positioning. For MAKE/MISS/BLOCK results, build schema-pure
    # [ball_flight] (+ [bounce] for miss/block) sub-steps that follow the
    # final [shoot] step. Overlay players (rebounder / get-back / release)
    # move toward their overlay destination across all three sub-steps with
    # proper interrupted coords + per-player tween durations per archetype.
    # Shot clock pins on [ball_flight] + [bounce] (shot detached at start of
    # [ball_flight]); game clock burns through all sub-steps.
    #
    # For non-shot result types (FOUL / STEAL / DEAD_BALL_TURNOVER / etc.)
    # the sub-step builder is a no-op; we fall back to the legacy overlay
    # apply (which is itself a no-op when overlay maps are empty — the
    # common case for those result types).
    if steps:
        from BackEnd.engine.shot_micro_movements import inject_shot_micro_before_post_shot

        inject_shot_micro_before_post_shot(
            steps, turn_result, off_lineup, def_lineup, away_offense,
        )
        _build_post_shot_sub_steps(
            steps, turn_result, off_lineup, def_lineup, away_offense,
        )
        result_type_final = (turn_result.get("result_type") or "").upper()
        if result_type_final not in ("MAKE", "MISS", "BLOCK"):
            _apply_post_shot_overlay(steps[-1], turn_result)
            # Bonus / non-shooting FOUL turns (result_type FOUL + next FREE_THROW)
            # announce via finalizeTurnAfterAnimation / announceFromTurnData — not
            # "Shooting Foul!" (Announcement_System.md: true shooting fouls are
            # MISS/MAKE shot-result paths). MISS + FT uses
            # _stamp_shooting_foul_on_miss_end inside _build_post_shot_sub_steps.

            # Post-steal HCO transition: when STEAL leads to HCO/HCT/FCP (not
            # FB), append a silent step-back + 9-player court transition. The
            # step's end.coords becomes the turn's final_coords so the next
            # HCO turn's dynamic handoff reads correct start positions and
            # doesn't teleport. No-op for STEAL → FAST_BREAK (handled by the
            # after_steal FB emitter).
            _append_post_steal_hco_transition(steps, turn_result, game)

    if turn_result.get("flss") and steps:
        _normalize_flss_terminal_clock_burn(
            steps,
            clock_remaining_at_turn_start,
            shot_clock_remaining_at_turn_start,
        )

    from BackEnd.engine.dead_ball_fumble import inject_dead_ball_fumble_before_turn_stop

    inject_dead_ball_fumble_before_turn_stop(
        steps, turn_result, away_offense=away_offense,
    )

    return steps


def _compute_pass_meet_point(
    passer_start: GridCoord,
    receiver_start: GridCoord,
    receiver_end: GridCoord,
    receiver_rate: float,
    ball_rate: float = float(PASS_GRID_SPOTS_PER_GAME_SECOND),
) -> GridCoord:
    """Compute where a ball moving at ``ball_rate`` grid/game-sec from
    ``passer_start`` intercepts a receiver moving from ``receiver_start``
    to ``receiver_end`` at ``receiver_rate`` grid/game-sec.

    Returns the meet-point coord. The ball's natural arrival time is then
    ``|passer_start - meet_point| / ball_rate``.

    Case 1 — receiver already at destination by the time ball would arrive
    at ``receiver_end`` (or receiver stationary): meet = ``receiver_end``.
    Case 2 — receiver still moving when ball would arrive: solve quadratic
    ``(ball_rate · t)² = |R0 - P + α · t|²`` where ``α`` is the receiver's
    velocity vector. Expanding: ``a·t² + b·t + c = 0`` with
    ``a = ball_rate² - |α|²``, ``b = -2 (R0 - P)·α``, ``c = -|R0 - P|²``.
    With ``ball_rate > receiver_rate`` (all HCO archetypes are slower than
    36) and ``c < 0``, the quadratic has exactly one positive root.

    Used by HCO mid-skeleton pass steps so the ball lands on the
    receiver's interpolated position rather than the receiver's step-end
    coord (which the receiver may not have reached yet).
    """
    r_dist = _euclid(receiver_start, receiver_end)
    t_to_end = _euclid(passer_start, receiver_end) / ball_rate

    # Case 1: receiver stationary, or finishes before ball arrives at its
    # step-end position.
    if r_dist < 1e-6 or receiver_rate <= 0:
        return dict(receiver_end)
    receiver_t = r_dist / receiver_rate
    if receiver_t <= t_to_end:
        return dict(receiver_end)

    # Case 2: receiver still moving. Solve quadratic for ball arrival time.
    ax = (receiver_end["x"] - receiver_start["x"]) / receiver_t
    ay = (receiver_end["y"] - receiver_start["y"]) / receiver_t
    alpha_sq = ax * ax + ay * ay

    dx0 = receiver_start["x"] - passer_start["x"]
    dy0 = receiver_start["y"] - passer_start["y"]
    a_q = ball_rate * ball_rate - alpha_sq
    if a_q <= 0:
        # Receiver as fast as / faster than ball — shouldn't happen for HCO
        # (cruise=10, sprint=14, both < 36). Fall back to step-end coord.
        return dict(receiver_end)
    b_q = -2.0 * (dx0 * ax + dy0 * ay)
    c_q = -(dx0 * dx0 + dy0 * dy0)
    discriminant = b_q * b_q - 4.0 * a_q * c_q
    if discriminant < 0:
        return dict(receiver_end)
    sqrt_disc = discriminant ** 0.5
    # With a_q > 0 and c_q < 0: parabola opens up, roots have opposite
    # signs. The positive root is `(-b_q + sqrt_disc) / (2 * a_q)`.
    t = (-b_q + sqrt_disc) / (2.0 * a_q)
    if t <= 0 or t >= receiver_t:
        return dict(receiver_end)
    meet_x = receiver_start["x"] + ax * t
    meet_y = receiver_start["y"] + ay * t
    return {"x": float(meet_x), "y": float(meet_y)}


def _interpolate_step_end(
    start_coord: GridCoord,
    dest_coord: GridCoord,
    rate: float,
    step_t: float,
) -> Tuple[GridCoord, float]:
    """Compute the interrupted end coord + tween duration for a player moving
    toward ``dest_coord`` at ``rate`` grid/game-sec over a step of duration
    ``step_t`` game-sec.

    Returns ``(end_coord, tween_duration_game_seconds)``.

    - If ``natural_t = dist / rate <= step_t``: player reaches dest. Tween
      duration = natural_t (player idles for the remainder of step_t at their
      destination).
    - If ``natural_t > step_t``: player is interrupted at
      ``start + rate × step_t`` along start→dest. Tween duration = step_t.
    - Degenerate inputs (dist ~ 0, rate ≤ 0, step_t ≤ 0): no tween, end = start.

    Enforces UESS §9.5 — non-gate movers freeze at interrupted coord, never
    snap to destination.
    """
    dist = _euclid(start_coord, dest_coord)
    if dist < 1e-6 or rate <= 0 or step_t <= 0:
        return dict(start_coord), 0.0
    natural_t = dist / rate
    if natural_t <= step_t:
        return dict(dest_coord), float(natural_t)
    frac = (rate * step_t) / dist
    x = start_coord["x"] + (dest_coord["x"] - start_coord["x"]) * frac
    y = start_coord["y"] + (dest_coord["y"] - start_coord["y"]) * frac
    return {"x": float(x), "y": float(y)}, float(step_t)


# Per-overlay-map archetype assignment. Rebounders move at standard pace
# (controlled positioning under the rim); release / get-back players sprint
# (outlet / retreat urgency).
_OVERLAY_ARCHETYPES: Tuple[Tuple[str, PlayerArchetype], ...] = (
    ("offense_rebounder_coords", "standard"),
    ("defense_rebounder_coords", "standard"),
    ("offense_getback_coords",   "sprint"),
    ("defense_release_coords",   "sprint"),
)


def _collect_overlay_players(
    turn_result: Dict[str, Any],
) -> Dict[str, Tuple[GridCoord, PlayerArchetype]]:
    """Return ``{pid: (destination_coord, archetype)}`` aggregated from the
    four overlay maps. Each player appears in at most one map by §9.1
    invariant (enforced upstream by ``canonicalize_post_shot_overlays``);
    iteration order matches that invariant's priority.
    """
    out: Dict[str, Tuple[GridCoord, PlayerArchetype]] = {}
    for overlay_key, archetype in _OVERLAY_ARCHETYPES:
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
            out[str(pid)] = ({"x": float(x), "y": float(y)}, archetype)
    return out


def _apply_overlay_motion_to_shoot_step(
    shoot_step: AnimationStep,
    overlay_players: Dict[str, Tuple[GridCoord, PlayerArchetype]],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Rewrite the [shoot] step's overlay player fields in place. Replaces
    the legacy ``_apply_post_shot_overlay`` snap-to-destination behavior with
    interrupted-coord + per-player tween_duration motion.
    """
    end_coords = shoot_step["end"]["coords"]
    start_coords = shoot_step["start"]["coords"]
    destinations = shoot_step["start"]["destination"]
    actions = shoot_step["start"]["action"]
    archetype = shoot_step["start"]["archetype"]
    tween_durations = dict(shoot_step["start"].get("tween_durations") or {})
    step_t = float(shoot_step["end"]["time_elapsed"])

    for pid, (dest_coord, arch) in overlay_players.items():
        sc = start_coords.get(pid)
        if sc is None:
            continue
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch)
        ec, dur = _interpolate_step_end(sc, dest_coord, rate, step_t)
        end_coords[pid] = ec
        destinations[pid] = dict(dest_coord)
        actions[pid] = "cut"
        archetype[pid] = arch
        if dur > 0:
            tween_durations[pid] = dur
        elif pid in tween_durations:
            del tween_durations[pid]

    if tween_durations:
        shoot_step["start"]["tween_durations"] = tween_durations


def _build_ball_motion_sub_step(
    *,
    start_coords_seed: Dict[str, GridCoord],
    overlay_players: Dict[str, Tuple[GridCoord, PlayerArchetype]],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_t: float,
    ball_start_coord: GridCoord,
    ball_end_coord: GridCoord,
    clock_start: ClockState,
    advance_trigger: AdvanceTrigger,
    ball_motion_style: Optional[str],
    next_step: NextStep,
    sfx_on_ball_release: Optional[Dict[str, Any]] = None,
    sfx_on_ball_arrival: Optional[Dict[str, Any]] = None,
    timed_sfx: Optional[List[Dict[str, Any]]] = None,
) -> AnimationStep:
    """Build a [ball_flight] or [bounce] sub-step. Non-overlay players hold
    position (stationary); overlay players continue toward their destination
    at their archetype rate, interrupted at step_t.

    Game clock burns ``step_t``; shot clock is pinned (no decrement) — both
    sub-steps run after the shot has detached from the shooter.
    """
    end_coords: Dict[str, GridCoord] = {}
    destinations: Dict[str, Optional[GridCoord]] = {}
    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    tween_durations: Dict[str, float] = {}

    for pid, sc in start_coords_seed.items():
        overlay_meta = overlay_players.get(pid)
        if overlay_meta is None:
            end_coords[pid] = dict(sc)
            destinations[pid] = None
            actions[pid] = "stationary"
            archetype[pid] = "stationary"
            continue
        dest_coord, arch = overlay_meta
        if _euclid(sc, dest_coord) < 1e-6:
            end_coords[pid] = dict(sc)
            destinations[pid] = None
            actions[pid] = "stationary"
            archetype[pid] = "stationary"
            continue
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch)
        ec, dur = _interpolate_step_end(sc, dest_coord, rate, step_t)
        end_coords[pid] = ec
        destinations[pid] = dict(dest_coord)
        actions[pid] = "cut"
        archetype[pid] = arch
        if dur > 0:
            tween_durations[pid] = dur

    clock_end: ClockState = {
        "clock_remaining": clock_start["clock_remaining"] - step_t,
        # Shot clock pinned — detach happened at start of [ball_flight].
        "shot_clock_remaining": clock_start["shot_clock_remaining"],
    }

    start: Dict[str, Any] = {
        "coords": dict(start_coords_seed),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": {"coords": dict(ball_start_coord)},
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    if ball_motion_style:
        start["ball_motion_style"] = ball_motion_style
    if tween_durations:
        start["tween_durations"] = tween_durations
    if sfx_on_ball_release:
        start["sfx_on_ball_release"] = sfx_on_ball_release
    if sfx_on_ball_arrival:
        start["sfx_on_ball_arrival"] = sfx_on_ball_arrival
    if timed_sfx:
        start["timed_sfx"] = list(timed_sfx)

    return {
        "start": start,
        "end": {
            "coords": end_coords,
            "ball": {"coords": dict(ball_end_coord)},
            "time_elapsed": float(step_t),
            "clock": clock_end,
            "next": next_step,
        },
    }


MAKE_HOLD_MS: float = 1000.0


def _build_make_hold_sub_step(
    *,
    prev_end_coords: Dict[str, GridCoord],
    prev_clock: ClockState,
    ball_coord: GridCoord,
    shooter_id: str,
    away_offense: bool,
    turn_result: Dict[str, Any],
    next_step: NextStep,
) -> AnimationStep:
    """Build the [hold] sub-step that follows [ball_flight] on a MAKE.

    Renders the post-make "ball settles at the rim + announcement"
    beat. Mechanism:
      - All players hold their post-[ball_flight] positions (frozen).
      - Ball sits at the sweet spot.
      - ``start.announcement`` fires "It's Good!" or the And-1 foul card
        (``style: "and_one"``) — the FE's ``runStepAnnouncement`` pauses
        gameClock + shotClock for ``hold_ms`` (1000ms wall-clock), then resumes.
      - Step T = 0 game-sec → no additional wall-clock wait after the
        announcement; ``snapBallToEndState`` then runs and we proceed to
        the SHOT_ATTEMPT turn_stop.
      - Clock fields pinned (no game/shot clock decrement during hold).

    And-one detection mirrors the legacy ``ShotAnimationSystem``: when
    ``next_play_type == "FREE_THROW"`` and a foul player is named on the
    turn result, the announcement text is swapped.
    """
    fouler_id = (
        turn_result.get("foul_player_id")
        or _safe_id(turn_result.get("foul_player"))
    )
    is_and_one = (
        str(turn_result.get("next_play_type") or "").upper() == "FREE_THROW"
        and bool(fouler_id)
    )
    team = "away" if away_offense else "home"

    coords = dict(prev_end_coords)
    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in coords}
    archetype: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in coords}
    destinations: Dict[str, Optional[GridCoord]] = {pid: None for pid in coords}

    if is_and_one:
        announcement: Dict[str, Any] = {
            "text": "It's Good! And 1!",
            "team": team,
            "hold_ms": MAKE_HOLD_MS,
            "style": "and_one",
            "player_data": {
                "playerId": str(shooter_id),
                "foulerId": str(fouler_id),
            },
            # AND-1 whistle carried on payload; FE plays at overlay mount.
            "meta": {"sfx": "foul"},
        }
    else:
        announcement = {
            "text": "It's Good!",
            "team": team,
            "hold_ms": MAKE_HOLD_MS,
            "style": "primary",
            "player_data": {"playerId": str(shooter_id)},
        }
        # Made 3-pointer → random announcer "three" call at the announce mount
        # (SFX_System.md "Made Three Announce"). Backend decides WHEN (the
        # 3-point condition); FE resolves the "three_make" key to a random file
        # and plays it. Keeps the made-3 audio decision off the pure-renderer FE.
        if turn_result.get("is_three_point_shot") is True:
            schema_shooter_coord = prev_end_coords.get(str(shooter_id))
            shooter_model = turn_result.get("shooter")
            shooter_model_coord = getattr(shooter_model, "coords", None)
            logging.warning(
                "[3PT-SFX-STAMP] stamping three_make: result_type=%s points=%s "
                "is_three_point_shot=%s shot_type=%s current_turn=%s fast_break=%s "
                "fast_break_play=%s shooter_id=%s schema_shooter_coord=%s "
                "shooter_model_coord=%s ball_coord=%s hct_ab_shooter_target=%s "
                "hct_fb_bh_target=%s bh_target=%s text=%s",
                turn_result.get("result_type"),
                turn_result.get("points"),
                turn_result.get("is_three_point_shot"),
                turn_result.get("shot_type"),
                turn_result.get("current_turn"),
                turn_result.get("fast_break"),
                turn_result.get("fast_break_play"),
                turn_result.get("shooter_id"),
                schema_shooter_coord,
                shooter_model_coord,
                ball_coord,
                turn_result.get("hct_ab_shooter_target"),
                turn_result.get("hct_fb_bh_target"),
                turn_result.get("bh_target"),
                turn_result.get("text"),
            )
            announcement["meta"] = {"sfx": "three_make"}

    trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": 0.0,
        "metadata": {"kind": "make_hold"},
    }

    step: AnimationStep = {
        "start": {
            "coords": coords,
            "destination": destinations,
            "action": actions,
            "archetype": archetype,
            "ball": {"coords": dict(ball_coord)},
            "clock": dict(prev_clock),
            "advance_trigger": trigger,
            "announcement": announcement,
        },
        "end": {
            "coords": dict(coords),
            "ball": {"coords": dict(ball_coord)},
            "time_elapsed": 0.0,
            "clock": dict(prev_clock),
            "next": next_step,
        },
    }
    return step


_RATTLE_VARIANTS = frozenset({"LITTLE_RATTLE", "NORMAL_RATTLE", "HEAVY_RATTLE"})
_RATTLE_HOP_COUNTS: Dict[str, int] = {
    "LITTLE_RATTLE": 2,
    "NORMAL_RATTLE": 4,
    "HEAVY_RATTLE": 8,
}


def _airball_announcement(
    turn_result: Dict[str, Any],
    away_offense: bool,
) -> Optional[Dict[str, Any]]:
    """``Airball!`` when a miss resolves as the AIRBALL shot variant.

    Fires at [ball_flight] end — same beat as ``airball.wav`` (no duplicate
    announce SFX; SFX_System.md).
    """
    if (turn_result.get("shot_variant") or "").upper() != "AIRBALL":
        return None
    if (turn_result.get("result_type") or "").upper() == "MAKE":
        return None
    shooter_id = turn_result.get("shooter_id") or _safe_id(turn_result.get("shooter"))
    if not shooter_id:
        return None
    return {
        "text": "Airball!",
        "team": "away" if away_offense else "home",
        "hold_ms": 1000.0,
        "style": "primary",
        "player_data": {"playerId": str(shooter_id)},
    }


_SHOOTING_FOUL_ON_MISS_RESULT_TYPES = frozenset({"MISS", "PUTBACK_MISS"})


def _resolve_turn_shooter_grid_coord(turn_result: Dict[str, Any]) -> Optional[GridCoord]:
    """Live shot origin for FLSS / forced shots when skeleton coords are missing."""
    for key in ("shooter_coords", "shot_spot"):
        raw = turn_result.get(key)
        if isinstance(raw, dict) and raw.get("x") is not None:
            return {"x": float(raw["x"]), "y": float(raw.get("y", 25))}
    roles = turn_result.get("roles")
    if isinstance(roles, dict):
        raw = roles.get("shot_spot")
        if isinstance(raw, dict) and raw.get("x") is not None:
            return {"x": float(raw["x"]), "y": float(raw.get("y", 25))}
    shooter = turn_result.get("shooter")
    shooter_coords = getattr(shooter, "coords", None)
    if isinstance(shooter_coords, dict) and shooter_coords.get("x") is not None:
        return {
            "x": float(shooter_coords["x"]),
            "y": float(shooter_coords.get("y", 25)),
        }
    return None


def _resolve_shooter_shot_spot(
    turn_result: Dict[str, Any],
    shoot_step: AnimationStep,
    shooter_id: str,
) -> Optional[GridCoord]:
    """Shooter grid at release — schema step first, then turn-level fallbacks."""
    coords = (shoot_step.get("end") or {}).get("coords") or {}
    shot_spot = coords.get(str(shooter_id)) or coords.get(shooter_id)
    if isinstance(shot_spot, dict) and shot_spot.get("x") is not None:
        return {"x": float(shot_spot["x"]), "y": float(shot_spot.get("y", 25))}
    return _resolve_turn_shooter_grid_coord(turn_result)


def _stamp_flss_shooter_on_step_end(
    final_end_coords: Dict[str, GridCoord],
    turn_result: Dict[str, Any],
    off_lineup: Dict[str, Any],
    skeleton_step: Dict[str, Any],
) -> None:
    """Ensure FLSS terminal shoot step includes the shooter for post-shot sub-steps."""
    shooter_id = _safe_id(turn_result.get("shooter_id")) or _safe_id(turn_result.get("shooter"))
    if not shooter_id:
        shooter_pos = _shooter_pos_in_step(skeleton_step)
        if shooter_pos:
            shooter_id = _safe_id(_player_id_at_pos(off_lineup, shooter_pos))
    coord = _resolve_turn_shooter_grid_coord(turn_result)
    if shooter_id and coord:
        final_end_coords[str(shooter_id)] = dict(coord)


def _find_terminal_shoot_step(steps: List[AnimationStep]) -> Optional[AnimationStep]:
    """Last step whose start actions include ``shoot`` (FB lane-pass may be
    ``steps[-1]`` when shot-motion build failed). Falls back to ``steps[-1]``."""
    if not steps:
        return None
    for step in reversed(steps):
        actions = (step.get("start") or {}).get("action") or {}
        if any(v == "shoot" for v in actions.values()):
            return step
    return steps[-1]


def _shooting_foul_on_miss_announcement(
    turn_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """``Shooting Foul!`` for missed shot-result turns that lead to free throws."""
    if (turn_result.get("result_type") or "").upper() not in _SHOOTING_FOUL_ON_MISS_RESULT_TYPES:
        return None
    next_play = str(turn_result.get("next_play_type") or "").upper()
    has_ft = bool(turn_result.get("free_throws_remaining")) or next_play == "FREE_THROW"
    if not has_ft:
        return None
    fouler_id = (
        turn_result.get("foul_player_id")
        or _safe_id(turn_result.get("foul_player"))
    )
    if not fouler_id:
        return None
    # Canonical UESS foul-announcement builder (single source for foul
    # announcement payloads + meta.sfx). See animation_step_helpers.py.
    return build_foul_announcement(
        text="Shooting Foul!",
        team="neutral",
        fouler_id=fouler_id,
        style="shooting_foul",
    )


def _stamp_shooting_foul_on_miss_end(
    step: AnimationStep,
    turn_result: Dict[str, Any],
) -> None:
    ann = _shooting_foul_on_miss_announcement(turn_result)
    if ann:
        step.setdefault("end", {})["announcement"] = ann


def _variant_flight_end(
    shot_variant: Optional[str],
    result_type: str,
    away_offense: bool,
    turn_result: Dict[str, Any],
) -> GridCoord:
    """Per-variant ball-flight terminal coord. Mirrors SFX_System.md
    §Ball Resolve Animations. Falls back to make=MSSS / miss=rim for unknown
    or missing variant (legacy emitters that haven't rolled a variant).
    """
    result_upper = (result_type or "").upper()
    # Shooting foul during a block attempt: visually use the contact point,
    # but keep the rules result as MISS → FREE_THROW, not BLOCK. This avoids
    # block SFX/announcement/stat side effects while preventing the ball from
    # flying through to the rim.
    if turn_result.get("foul_block_contact"):
        bx = turn_result.get("foul_block_contact_x")
        by = turn_result.get("foul_block_contact_y")
        if bx is not None and by is not None:
            return {"x": float(bx), "y": float(by)}
    # BLOCK: ball is rejected at the block point — never reaches the rim.
    # Terminate ball flight directly at the block spot (= ball_bounce_x/y,
    # stamped by shot_manager). The [bounce] step is suppressed for BLOCK
    # in `_build_post_shot_sub_steps` so the ball doesn't double-animate.
    # Falls through to the legacy rim fallback if bounce coords are missing.
    if result_upper == "BLOCK":
        bx = turn_result.get("ball_bounce_x")
        by = turn_result.get("ball_bounce_y")
        if bx is not None and by is not None:
            return {"x": float(bx), "y": float(by)}
    is_make = result_upper == "MAKE"
    msss = (dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM) if away_offense
            else dict(MADE_SHOT_SWEET_SPOT_HOME_RIM))
    rim = (dict(AWAY_RIM_COORDS) if away_offense else dict(HOME_RIM_COORDS))
    variant = (shot_variant or "").upper()

    if variant in ("SWISH", "FREE_THROW_SWISH"):
        return msss
    if variant in ("CLANK", "FREE_THROW_MISS"):
        return rim
    if variant == "BACK_OF_RIM":
        return msss if is_make else rim
    if variant in _RATTLE_VARIANTS:
        start_mode = str(
            turn_result.get("shot_variant_rattle_start") or "MSSS"
        ).upper()
        return msss if start_mode == "MSSS" else rim
    if variant in ("BANK_MAKE", "BANK_MISS"):
        # Bank point: x = MSSS_x + xSign·3 (toward backboard); y = MSSS_y +
        # shooter-y-conditional offset (already rolled into the result by
        # ``roll_shot_variant_extras``).
        x_sign = -1.0 if away_offense else +1.0
        y_off = float(turn_result.get("shot_variant_backboard_y_offset") or 0)
        return {"x": float(msss["x"]) + x_sign * 3.0,
                "y": float(msss["y"]) + y_off}
    if variant == "AIRBALL":
        # 2 grid units short of MSSS toward midcourt. Home (90,25) → (88,25);
        # away (10,25) → (12,25).
        x_sign = +1.0 if away_offense else -1.0
        return {"x": float(msss["x"]) + x_sign * 2.0, "y": float(msss["y"])}
    # Unknown / missing variant (BLOCK lands here) — legacy fallback.
    return msss if is_make else rim


def _rattle_hop_targets(
    shot_variant: str,
    away_offense: bool,
    turn_result: Dict[str, Any],
) -> List[GridCoord]:
    """Build the ordered list of per-hop end coords for a RATTLE variant.

    MSSS-start: y oscillation. Hops alternate between MSSS_y+1 and MSSS_y-1.
    RIM-start:  x oscillation. Hops alternate between MSSS_x+1 and MSSS_x-1
                (for the home rim that's 91 / 89 — the rim itself is one of
                the two hop points).
    Progression OPT_1: (+, -, +, -, ...). OPT_2: (-, +, -, +, ...).
    Hop count: 2 / 4 / 8 for LITTLE / NORMAL / HEAVY.
    """
    msss = (dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM) if away_offense
            else dict(MADE_SHOT_SWEET_SPOT_HOME_RIM))
    start_mode = str(
        turn_result.get("shot_variant_rattle_start") or "MSSS"
    ).upper()
    progression = str(
        turn_result.get("shot_variant_rattle_progression") or "OPT_1"
    ).upper()
    hop_count = _RATTLE_HOP_COUNTS.get(shot_variant.upper(), 0)
    if hop_count <= 0:
        return []

    if start_mode == "MSSS":
        point_a = {"x": float(msss["x"]), "y": float(msss["y"]) + 1.0}
        point_b = {"x": float(msss["x"]), "y": float(msss["y"]) - 1.0}
    else:
        point_a = {"x": float(msss["x"]) + 1.0, "y": float(msss["y"])}
        point_b = {"x": float(msss["x"]) - 1.0, "y": float(msss["y"])}

    first, second = (point_a, point_b) if progression == "OPT_1" else (point_b, point_a)
    out: List[GridCoord] = []
    pair_count = hop_count // 2
    for _ in range(pair_count):
        out.append(dict(first))
        out.append(dict(second))
    return out


def _build_post_shot_sub_steps(
    steps: List[AnimationStep],
    turn_result: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    away_offense: bool,
) -> None:
    """Append schema-pure post-shot sub-steps for MAKE / MISS / BLOCK
    results. The sequence is variant-aware (SFX_System.md §Ball
    Resolve Animations + §SFX Bindings):

      [shoot]       (already in steps[-1]) — shooter motion
      [ball_flight] — shooter coord → variant flight target; stamps the
                      launch SFX cue (``sfx_on_ball_release``) and the
                      arrival SFX cue (``sfx_on_ball_arrival``, omitted for
                      RATTLE which uses per-hop cues)
      [variant sub-steps] — zero or more of:
          - RATTLE hops    (N=2/4/8, per-hop ``rattle-leather.wav``)
          - RATTLE settle  (make only, swish.wav arrival)
          - BANK_MAKE settle (bank → MSSS, 250ms)
          - BANK_MISS graze  (bank → rim-graze, 200ms)
          - AIRBALL OOB continuation (2-short → OOB resting)
      [hold]   — make only, 1000ms "It's Good!" announcement
      [bounce] — miss/block with bounce_coords (skipped for AIRBALL)

    All sub-steps share the same overlay-motion treatment: non-overlay
    players hold position; overlay players continue toward their overlay
    destination at archetype rate (interrupted coords per §9.5; never
    snapped). Game clock burns; shot clock pinned (detach at start of
    [ball_flight]).

    No-op for result types outside MAKE/MISS/BLOCK.
    """
    if not steps:
        return
    result_type = (turn_result.get("result_type") or "").upper()
    if result_type not in ("MAKE", "MISS", "BLOCK"):
        return

    shoot_step = _find_terminal_shoot_step(steps)
    if shoot_step is None:
        return
    shooter_id = (
        _safe_id(turn_result.get("shooter"))
        or _safe_id(turn_result.get("shooter_id"))
    )
    shot_spot = (
        _resolve_shooter_shot_spot(turn_result, shoot_step, shooter_id)
        if shooter_id
        else None
    )
    if not shooter_id or shot_spot is None:
        return  # Can't build ball flight without shooter coord.

    # Keep shooter coord on the terminal shoot step for downstream readers.
    shoot_end_coords = shoot_step.setdefault("end", {}).setdefault("coords", {})
    shoot_end_coords[str(shooter_id)] = dict(shot_spot)

    overlay_players = _collect_overlay_players(turn_result)
    _apply_overlay_motion_to_shoot_step(
        shoot_step, overlay_players, off_lineup, def_lineup,
    )

    def _shot_attempt_turn_stop() -> NextStep:
        """Build the SHOT_ATTEMPT turn_stop, marking ``schema_rendered_arc`` so
        the FE dispatcher's ``runShotAttempt`` skips its legacy arc/bounce
        rendering (the schema sub-steps already rendered both)."""
        ns = _resolve_final_step_next(turn_result)
        if (isinstance(ns, dict)
            and ns.get("kind") == "turn_stop"
            and ns.get("event") == "SHOT_ATTEMPT"):
            payload = dict(ns.get("payload") or {})
            payload["schema_rendered_arc"] = True
            ns["payload"] = payload
        return ns

    is_make = result_type == "MAKE"
    is_foul_block_contact = bool(turn_result.get("foul_block_contact"))
    shot_variant = None if is_foul_block_contact else turn_result.get("shot_variant")
    variant_upper = (shot_variant or "").upper()
    is_rattle = variant_upper in _RATTLE_VARIANTS
    is_airball = variant_upper == "AIRBALL"

    ball_flight_end = _variant_flight_end(
        shot_variant, result_type, away_offense, turn_result,
    )

    flight_dist = _euclid(shot_spot, ball_flight_end)
    uses_arc_flight = result_type != "BLOCK" and bool(turn_result.get("uses_shot_arc"))
    from BackEnd.utils.shot_ball_arc import (
        shot_ball_flight_grid_rate,
        stamp_shot_ball_arc_metadata,
    )

    flight_rate = shot_ball_flight_grid_rate(uses_arc=uses_arc_flight)
    flight_t = max(0.05, flight_dist / flight_rate)
    flight_trigger: AdvanceTrigger = {
        "condition": "shot_resolved",
        "T_game_seconds": float(flight_t),
        "metadata": {
            "target_coords": dict(ball_flight_end),
            "result": result_type,
            "shot_variant": shot_variant,
        },
    }
    stamp_hot_shot_trail_metadata(
        flight_trigger["metadata"],
        turn_result.get("shot_score_pre_defense"),
    )

    stamp_shot_ball_arc_metadata(
        flight_trigger["metadata"],
        turn_result,
        shot_spot,
        away_offense,
    )

    # Bounce step requires backend-stamped ball_bounce coords. AIRBALL takes
    # the OOB continuation path instead (no rebound visual per spec).
    # BLOCK suppresses the bounce step: `_variant_flight_end` terminates the
    # [ball_flight] step directly at the block spot (= ball_bounce_x/y), so
    # a separate [bounce] would be a 0-distance no-op with a 300ms wait
    # that visually freezes the rejected ball. The post-[ball_flight]
    # terminal pointer becomes the SHOT_ATTEMPT turn_stop directly (the
    # `else` branch at the bottom of this function).
    bx = turn_result.get("ball_bounce_x")
    by = turn_result.get("ball_bounce_y")
    has_bounce_coords = (bx is not None) and (by is not None)
    is_block = result_type == "BLOCK"
    needs_bounce = (
        (not is_make)
        and (not is_airball)
        and (not is_block)
        and (not is_foul_block_contact)
        and has_bounce_coords
    )

    # SFX cues for the [ball_flight] step. Launch cue fires at detach
    # (= step start). Arrival cue fires at the ball's tween onComplete.
    # RATTLE variants leave the arrival cue empty — per-hop SFX fires from
    # the hop sub-steps below.
    launch_sfx = shot_launch_sfx(turn_result.get("shot_score_pre_defense"), result_type)
    arrival_sfx = None if is_foul_block_contact else shot_result_sfx(
        shot_variant,
        result_type,
        bank_miss_sfx_file=turn_result.get("shot_variant_bank_miss_sfx_file"),
    )
    timed_sfx = None if is_foul_block_contact else shot_followup_timed_sfx(
        shot_variant,
        result_type,
    )

    flight_idx = len(steps)
    # Flight's next pointer is filled in after we know how many variant
    # sub-steps are coming (placeholder; rewired below).
    flight_step = _build_ball_motion_sub_step(
        start_coords_seed=dict(shoot_step["end"]["coords"]),
        overlay_players=overlay_players,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        step_t=flight_t,
        ball_start_coord=shot_spot,
        ball_end_coord=ball_flight_end,
        clock_start=dict(shoot_step["end"]["clock"]),
        advance_trigger=flight_trigger,
        ball_motion_style="shot",
        next_step={"kind": "next_step", "index": flight_idx + 1},  # placeholder
        sfx_on_ball_release=launch_sfx,
        sfx_on_ball_arrival=arrival_sfx,
        timed_sfx=timed_sfx,
    )

    # BLOCK announcement fires when ball is blocked at the rim — i.e., at
    # [ball_flight] end (sprite snap moment). Replaces the legacy
    # `announceGameEvent('BLOCK')` in ShotAnimationSystem that the schema
    # short-circuit skips (audit bug 4). Blocker is on the defensive team
    # → opposite of `away_offense`.
    if result_type == "BLOCK" and not turn_result.get("foul_block_contact"):
        blocker_id = turn_result.get("blocker_id")
        if blocker_id:
            flight_step["end"]["announcement"] = {
                "text": "BLOCK!",
                "team": "home" if away_offense else "away",
                "hold_ms": 1000,
                "style": "primary",
                "player_data": {"playerId": str(blocker_id)},
                "meta": {"sfx": "block_announce"},
            }
    elif is_airball:
        airball_ann = _airball_announcement(turn_result, away_offense)
        if airball_ann:
            flight_step["end"]["announcement"] = airball_ann

    # Rewire [shoot]: next → [ball_flight] (was turn_stop SHOT_ATTEMPT).
    shoot_step["end"]["next"] = {"kind": "next_step", "index": flight_idx}
    steps.append(flight_step)

    # Cursor for the running ball position and step start state.
    cursor_coords = dict(flight_step["end"]["coords"])
    cursor_ball = dict(ball_flight_end)
    cursor_clock = dict(flight_step["end"]["clock"])
    last_appended = flight_step

    def _append_motion(
        *,
        ball_end: GridCoord,
        step_t: float,
        trigger_kind: str,
        sfx_release: Optional[Dict[str, Any]] = None,
        sfx_arrival: Optional[Dict[str, Any]] = None,
        ball_motion_style: Optional[str] = None,
    ) -> None:
        """Append a single ball-motion sub-step, wiring the previous step's
        next pointer to it. Placeholder next pointer; finalized later."""
        nonlocal cursor_coords, cursor_ball, cursor_clock, last_appended
        trigger: AdvanceTrigger = {
            "condition": "fixed_duration",
            "T_game_seconds": float(step_t),
            "metadata": {"target_coords": dict(ball_end), "kind": trigger_kind},
        }
        step = _build_ball_motion_sub_step(
            start_coords_seed=dict(cursor_coords),
            overlay_players=overlay_players,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_t=step_t,
            ball_start_coord=dict(cursor_ball),
            ball_end_coord=dict(ball_end),
            clock_start=dict(cursor_clock),
            advance_trigger=trigger,
            ball_motion_style=ball_motion_style,
            next_step={"kind": "next_step", "index": len(steps) + 1},  # placeholder
            sfx_on_ball_release=sfx_release,
            sfx_on_ball_arrival=sfx_arrival,
        )
        # Repoint the previous step's next pointer to THIS step's index.
        last_appended["end"]["next"] = {"kind": "next_step", "index": len(steps)}
        steps.append(step)
        cursor_coords = dict(step["end"]["coords"])
        cursor_ball = dict(ball_end)
        cursor_clock = dict(step["end"]["clock"])
        last_appended = step

    # --- Variant intermediate sub-steps ----------------------------------

    if is_rattle:
        # Per-hop sub-steps: 40 ms wall-clock each, with rattle-leather.wav
        # firing at hop arrival (ball tween onComplete).
        hop_targets = _rattle_hop_targets(
            variant_upper, away_offense, turn_result,
        )
        for hop_target in hop_targets:
            _append_motion(
                ball_end=hop_target,
                step_t=float(RATTLE_HOP_GAME_SECONDS),
                trigger_kind="rattle_hop",
                sfx_arrival=rattle_hop_sfx(),
            )
        # RATTLE make: settle into MSSS with the terminal swish at arrival.
        if is_make:
            msss = (dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM) if away_offense
                    else dict(MADE_SHOT_SWEET_SPOT_HOME_RIM))
            _append_motion(
                ball_end=msss,
                step_t=float(RATTLE_MAKE_SETTLE_GAME_SECONDS),
                trigger_kind="rattle_settle",
                sfx_arrival=rattle_make_settle_sfx(),
            )
    elif variant_upper == "BANK_MAKE":
        # Bank → MSSS settle. Arrival SFX is already handled by the
        # [ball_flight] step's timed_sfx (bb-rim-swish + delayed swish).
        msss = (dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM) if away_offense
                else dict(MADE_SHOT_SWEET_SPOT_HOME_RIM))
        _append_motion(
            ball_end=msss,
            step_t=float(BANK_MAKE_SETTLE_GAME_SECONDS),
            trigger_kind="bank_settle",
        )
    elif variant_upper == "BANK_MISS":
        # Bank → rim-graze. Graze point is MSSS + per-shot rolled offsets.
        msss = (dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM) if away_offense
                else dict(MADE_SHOT_SWEET_SPOT_HOME_RIM))
        graze = {
            "x": float(msss["x"]) + float(
                turn_result.get("shot_variant_backboard_miss_rim_offset_x") or 0
            ),
            "y": float(msss["y"]) + float(
                turn_result.get("shot_variant_backboard_miss_rim_offset_y") or 0
            ),
        }
        _append_motion(
            ball_end=graze,
            step_t=float(BANK_MISS_GRAZE_GAME_SECONDS),
            trigger_kind="bank_graze",
        )
    elif is_airball:
        # AIRBALL: ball continues from 2-short past the rim to the OOB
        # sideline. No rebound bounce.
        oob_target = (dict(AIRBALL_OOB_AWAY_COORDS) if away_offense
                      else dict(AIRBALL_OOB_HOME_COORDS))
        _append_motion(
            ball_end=oob_target,
            step_t=float(AIRBALL_OOB_GAME_SECONDS),
            trigger_kind="airball_oob",
        )

    # --- Terminal sub-step (hold / bounce / direct turn_stop) -----------

    if is_make:
        # MAKE: [hold] at the ball's final settle point (MSSS for all make
        # variants; the bank/back-of-rim/rattle settle steps already moved
        # the ball there).
        hold_step = _build_make_hold_sub_step(
            prev_end_coords=dict(cursor_coords),
            prev_clock=dict(cursor_clock),
            ball_coord=dict(cursor_ball),
            shooter_id=str(shooter_id),
            away_offense=away_offense,
            turn_result=turn_result,
            next_step=_shot_attempt_turn_stop(),
        )
        last_appended["end"]["next"] = {"kind": "next_step", "index": len(steps)}
        steps.append(hold_step)
    elif needs_bounce:
        bounce_target: GridCoord = {"x": float(bx), "y": float(by)}
        bounce_trigger: AdvanceTrigger = {
            "condition": "fixed_duration",
            "T_game_seconds": float(BOUNCE_STEP_GAME_SECONDS),
            "metadata": {
                "target_coords": dict(bounce_target),
                "kind": "bounce",
            },
        }
        bounce_step = _build_ball_motion_sub_step(
            start_coords_seed=dict(cursor_coords),
            overlay_players=overlay_players,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_t=BOUNCE_STEP_GAME_SECONDS,
            ball_start_coord=dict(cursor_ball),
            ball_end_coord=bounce_target,
            clock_start=dict(cursor_clock),
            advance_trigger=bounce_trigger,
            ball_motion_style=None,
            next_step=_shot_attempt_turn_stop(),
        )
        _stamp_shooting_foul_on_miss_end(bounce_step, turn_result)
        last_appended["end"]["next"] = {"kind": "next_step", "index": len(steps)}
        steps.append(bounce_step)
    else:
        # No bounce (AIRBALL, or MISS/BLOCK with no bounce coords): the
        # final variant sub-step (or [ball_flight] if no variant steps)
        # leads directly to the SHOT_ATTEMPT turn_stop.
        if not is_make:
            _stamp_shooting_foul_on_miss_end(last_appended, turn_result)
        last_appended["end"]["next"] = _shot_attempt_turn_stop()


def _apply_post_shot_overlay(step: AnimationStep, turn_result: Dict[str, Any]) -> None:
    """Legacy overlay-snap behavior. Retained for non-MAKE/MISS/BLOCK result
    types (shooting fouls / steals / dead-ball turnovers) until those paths
    migrate to schema-pure sub-stepping. For MAKE/MISS/BLOCK, see
    ``_build_post_shot_sub_steps`` instead.
    """
    end_coords = step.get("end", {}).get("coords")
    start_actions = step.get("start", {}).get("action")
    start_archetype = step.get("start", {}).get("archetype")
    if not isinstance(end_coords, dict):
        return

    for overlay_key in (
        "offense_rebounder_coords",
        "defense_rebounder_coords",
        "offense_getback_coords",
        "defense_release_coords",
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
                start_archetype[pid_str] = "standard"


# --- Post-STEAL → HCO transition step --------------------------------------
#
# When a steal occurs inside an HCO turn and the next play is HCO/HCT/FCP
# (i.e., NOT a fast break — the FB path is handled by the after_steal FB
# emitter), append a silent transition step at the end of the STEAL turn:
#
#   - Stealer step-backs 3-7 grid spots TOWARD the basket they were
#     defending (= the old offense's offensive basket), y drift ±3, clamped
#     to court bounds. Half-court guard: stealer cannot cross x=50 backwards
#     into their own new backcourt once they're in their new frontcourt.
#   - Other 9 players move 5-10 grid spots toward the NEW offense's basket
#     (their setup direction), y drift ±6, clamped to court bounds.
#   - Ball stays attached to the stealer for the entire step.
#   - No announcement (silent).
#
# The step's end.coords becomes the turn's final_coords — so the next HCO
# turn's first step reads correct positions and the dynamic handoff doesn't
# teleport. Replaces the deleted FE-only animateStealHCOSetup tween.

_POST_STEAL_STEALER_MOVE_X_MIN: int = 3
_POST_STEAL_STEALER_MOVE_X_MAX: int = 7
_POST_STEAL_STEALER_MOVE_Y_RANGE: int = 3
_POST_STEAL_OTHERS_MOVE_X_MIN: int = 5
_POST_STEAL_OTHERS_MOVE_X_MAX: int = 10
_POST_STEAL_OTHERS_MOVE_Y_RANGE: int = 6
_POST_STEAL_Y_MIN: int = 3
_POST_STEAL_Y_MAX: int = 47
_POST_STEAL_X_MIN: int = 4
_POST_STEAL_X_MAX: int = 96
_POST_STEAL_STEP_T_GAME_SECONDS: float = 0.5


def _append_post_steal_hco_transition(
    steps: List[AnimationStep],
    turn_result: Dict[str, Any],
    game: Any,
) -> None:
    """If this HCO STEAL turn transitions to HCO/HCT/FCP (not FB), append a
    silent post-steal transition step that moves the stealer back toward
    the old defended basket and shifts the other 9 toward the new
    offensive end. The step's end.coords becomes the turn's authoritative
    coord snapshot for the next HCO turn's handoff. No-op for steals that
    transition to FAST_BREAK (handled by the after_steal FB emitter).
    """
    import random

    if not steps:
        return

    result_type = (turn_result.get("result_type") or "").upper()
    if result_type != "STEAL":
        return

    next_play_type = str(turn_result.get("next_play_type") or "").upper()
    if next_play_type not in ("HCO", "HCT", "FCP"):
        return

    stealer_id = _safe_id(turn_result.get("stealer_id")) or _safe_id(
        turn_result.get("stealer")
    )
    if not stealer_id:
        return

    prior = steps[-1]
    prior_end = prior.get("end") if isinstance(prior, dict) else None
    if not isinstance(prior_end, dict):
        return
    start_coords_raw = prior_end.get("coords") or {}
    if not isinstance(start_coords_raw, dict) or stealer_id not in start_coords_raw:
        return

    # Normalize start_coords to GridCoord dicts and float values.
    start_coords: Dict[str, GridCoord] = {}
    for pid, coord in start_coords_raw.items():
        if isinstance(coord, dict) and "x" in coord and "y" in coord:
            start_coords[str(pid)] = {
                "x": float(coord["x"]),
                "y": float(coord["y"]),
            }
    if stealer_id not in start_coords:
        return

    # NEW offense = the team that just stole = current defense_team (possession
    # flip happens AFTER this turn returns from resolution). The new offense's
    # offensive basket is where they shoot when on offense — the AWAY rim if
    # the new offense IS the away team, else the HOME rim.
    new_off_team = getattr(game, "defense_team", None)
    away_team = getattr(game, "away_team", None)
    if new_off_team is None or away_team is None:
        return
    is_new_away_offense = bool(
        getattr(new_off_team, "team_id", None) == getattr(away_team, "team_id", None)
    )

    # Direction conventions (court is fixed; teams don't flip baskets):
    #   - AWAY shoots at x=9 (AWAY_RIM_COORDS), so AWAY's offensive direction
    #     is -x (toward x=9).
    #   - HOME shoots at x=91, so HOME's offensive direction is +x.
    # Stealer step-back is TOWARD the basket they were defending = the OLD
    # offense's offensive basket = the OPPOSITE of the new offense's offensive
    # direction.
    new_off_direction = -1 if is_new_away_offense else +1  # toward new off rim
    stealer_step_back_dir = -new_off_direction  # toward old defended rim

    # Compute stealer end coord.
    stealer_start = start_coords[stealer_id]
    stealer_move_x = random.randint(
        _POST_STEAL_STEALER_MOVE_X_MIN, _POST_STEAL_STEALER_MOVE_X_MAX
    )
    stealer_move_y = random.randint(
        -_POST_STEAL_STEALER_MOVE_Y_RANGE, _POST_STEAL_STEALER_MOVE_Y_RANGE
    )
    stealer_end_x = stealer_start["x"] + (stealer_step_back_dir * stealer_move_x)

    # Half-court (over-and-back) guard. Only triggers when the stealer is
    # already in their NEW frontcourt — otherwise they're already in
    # backcourt and have free movement within it.
    if is_new_away_offense:
        # AWAY new offense: frontcourt = x<50, step-back goes +x toward x=91.
        # If pre-x < 50 (frontcourt), post-x must stay ≤ 50.
        if stealer_start["x"] < 50.0:
            stealer_end_x = min(50.0, stealer_end_x)
    else:
        # HOME new offense: frontcourt = x>50, step-back goes -x toward x=9.
        # If pre-x > 50 (frontcourt), post-x must stay ≥ 50.
        if stealer_start["x"] > 50.0:
            stealer_end_x = max(50.0, stealer_end_x)

    stealer_end_x = max(float(_POST_STEAL_X_MIN), min(float(_POST_STEAL_X_MAX), stealer_end_x))
    stealer_end_y = max(
        float(_POST_STEAL_Y_MIN),
        min(float(_POST_STEAL_Y_MAX), stealer_start["y"] + stealer_move_y),
    )

    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }
    end_coords[stealer_id] = {"x": stealer_end_x, "y": stealer_end_y}

    # Other 9: move toward NEW offense basket, smaller 5-10 grid range.
    for pid, coord in start_coords.items():
        if pid == stealer_id:
            continue
        move_x = random.randint(
            _POST_STEAL_OTHERS_MOVE_X_MIN, _POST_STEAL_OTHERS_MOVE_X_MAX
        )
        move_y = random.randint(
            -_POST_STEAL_OTHERS_MOVE_Y_RANGE, _POST_STEAL_OTHERS_MOVE_Y_RANGE
        )
        new_x = coord["x"] + (new_off_direction * move_x)
        new_x = max(float(_POST_STEAL_X_MIN), min(float(_POST_STEAL_X_MAX), new_x))
        new_y = max(
            float(_POST_STEAL_Y_MIN),
            min(float(_POST_STEAL_Y_MAX), coord["y"] + move_y),
        )
        end_coords[pid] = {"x": new_x, "y": new_y}

    # Action/archetype maps. Stealer dribbles (cruise); others sprint to setup.
    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in start_coords}
    archetypes: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(end_coords[pid]) for pid in start_coords
    }
    actions[stealer_id] = "dribble"
    archetypes[stealer_id] = "standard"
    for pid in start_coords:
        if pid == stealer_id:
            continue
        actions[pid] = "sprint"
        archetypes[pid] = "sprint"

    t = _POST_STEAL_STEP_T_GAME_SECONDS
    prior_clock = prior_end.get("clock") or {}
    clock_remaining = float(prior_clock.get("clock_remaining", 0) or 0)
    shot_clock_remaining = float(prior_clock.get("shot_clock_remaining", 0) or 0)

    advance_trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": float(t),
        "metadata": {"kind": "post_steal_hco_transition"},
    }

    # Inherit the prior step's turn_stop (the STEAL event) as our terminal
    # next pointer; the prior step now points to this new step instead.
    inherited_next = prior_end.get("next") or {
        "kind": "turn_stop",
        "event": "STEAL",
        "payload": {
            "stealer_id": turn_result.get("stealer_id"),
            "victim_id": turn_result.get("victim_id"),
        },
    }

    new_step: AnimationStep = {
        "start": {
            "coords": dict(start_coords),
            "destination": destinations,
            "action": actions,
            "archetype": archetypes,
            "ball": {"owner_player_id": stealer_id},
            "clock": {
                "clock_remaining": clock_remaining,
                "shot_clock_remaining": shot_clock_remaining,
            },
            "advance_trigger": advance_trigger,
        },
        "end": {
            "coords": dict(end_coords),
            "ball": {"owner_player_id": stealer_id},
            "time_elapsed": float(t),
            "clock": {
                "clock_remaining": clock_remaining - t,
                "shot_clock_remaining": shot_clock_remaining - t,
            },
            "next": inherited_next,
        },
    }

    # Rewire prior step's next pointer to this new step.
    prior_end["next"] = {"kind": "next_step", "index": len(steps)}
    steps.append(new_step)
