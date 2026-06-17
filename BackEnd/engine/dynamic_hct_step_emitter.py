"""Dynamic-HCT animation step emitter.

Assembles a variable-length schema step list for a dynamic HCT turn:

  - **Step 0 — entry walk-up** — universal primitive (``build_walk_up_step``).
    BH cruises from BIP-end inbound position to the engage point ``(44, BH_y)``
    (home) / flipped for away; the other four offensive players sprint toward
    randomized front-court targets; defenders settle into the HCT alignment.
    Gate = BH.
  - **Steps 1..N — loop segments** — one generic movement step per engine
    ``loop_segment`` (converge, advances, attack). Movers go to their segment
    end coords; holders keep their start coord. Gate = the segment's gate
    player; roles set actions (BH handle_ball, PG defender guard_ball, other
    offense stationary, other defenders guard_offball). The final segment's
    ``next`` pointer encodes the turn outcome (DEAD BALL turn-stop vs. HCO end).

The engine (``dynamic_hct.compute_dynamic_hct_turn``) returns intermediate
data — the walk-up targets plus the ``loop_segments`` list — and this module
assembles the schema. Reads ``prior_turn.final_coords`` and
``prior_turn.final_ball_handler_id`` to seed step 0's start coords (the same
pattern HCO uses for its entry orchestrator).

Spec context: ``_documentation_master/05_Animation_System/Step_By_Step_System.md``.
"""

from typing import Any, Dict, List, Optional

from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
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
from BackEnd.engine.skeleton_step_emitter import _build_post_shot_sub_steps
from BackEnd.utils.transition_bridge import (
    _interrupted_coord,
    build_pass_step,
    build_walk_up_step,
)


_OFFENSE_POSITIONS = ("PG", "SG", "SF", "PF", "C")


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


def _resolve_final_step_next(turn_result: Dict[str, Any]) -> NextStep:
    """Map the dynamic HCT result_type to the attack step's ``next`` pointer."""
    result_type = (turn_result.get("result_type") or "").upper()
    if result_type in ("DEAD_BALL", "DEAD BALL", "DEAD_BALL_TURNOVER", "TURNOVER"):
        return {
            "kind": "turn_stop",
            "event": "DEAD_BALL_TURNOVER",
            "payload": {"victim_id": turn_result.get("victim_id")},
        }
    # HCO continuation: implicit end-of-turn.
    return {"kind": "next_step", "index": 999}


def _seg_end_coords_by_id(
    segment: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> Dict[str, GridCoord]:
    """Map a loop segment's per-position end coords to player ids."""
    out: Dict[str, GridCoord] = {}
    for pos, xy in (segment.get("off_end") or {}).items():
        pid = _player_id_at_pos(off_lineup, pos)
        if pid:
            out[pid] = {"x": float(xy["x"]), "y": float(xy["y"])}
    for pos, xy in (segment.get("def_end") or {}).items():
        pid = _player_id_at_pos(def_lineup, pos)
        if pid:
            out[pid] = {"x": float(xy["x"]), "y": float(xy["y"])}
    return out


def _build_loop_step(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
    bh_id: str,
    pg_def_id: str,
    gate_id: str,
    seconds: float,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step: NextStep,
    reason: str,
) -> AnimationStep:
    """Generic dynamic-HCT loop step. Movers progress toward their
    ``end_coords`` target, clamped to their archetype rate over the step
    duration (interrupted coord = start + rate × T); holders keep their start
    coord. Gate = ``gate_id`` reaching its end coord.

    ``bh_id`` is the segment's ball owner (changes after a pass). Actions by
    role: ball owner → handle_ball, defender nearest the ball owner →
    guard_ball, other offense → stationary, other defenders → guard_offball.
    Move-rate archetype by role: ball owner / defenders → ``standard``;
    off-ball offense → ``sprint`` (they keep hustling toward their setup
    spots). Anyone who didn't move this segment is ``stationary``.

    The interrupted-coord clamp is the universal safety net that prevents any
    player from being rendered faster than their archetype within a step — in
    particular the off-ball offense, who the BH-gated walk-up leaves partway
    to their setup spots and who would otherwise be snapped the full remaining
    distance over a short defender-gated segment ("the jet").
    """
    t = float(seconds)
    off_ids = {_player_id_at_pos(off_lineup, p) for p in _OFFENSE_POSITIONS}
    def_ids = {_player_id_at_pos(def_lineup, p) for p in _OFFENSE_POSITIONS}

    # Defender nearest the ball owner's end coord guards the ball.
    guard_ball_id: Optional[str] = None
    bh_end = end_coords.get(bh_id) or start_coords.get(bh_id)
    if bh_end is not None:
        best = None
        for did in def_ids:
            if not did:
                continue
            dc = end_coords.get(did) or start_coords.get(did)
            if dc is None:
                continue
            d = (dc["x"] - bh_end["x"]) ** 2 + (dc["y"] - bh_end["y"]) ** 2
            if best is None or d < best:
                best = d
                guard_ball_id = did

    destinations: Dict[str, Optional[GridCoord]] = {}
    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    step_end_coords: Dict[str, GridCoord] = {}

    for pid, sc in start_coords.items():
        target = end_coords.get(pid, sc)
        # Role + action, plus the archetype rate this player moves at.
        if pid == bh_id:
            action: PlayerAction = "handle_ball"
            move_arch: PlayerArchetype = "standard"
        elif pid == guard_ball_id:
            action = "guard_ball"
            move_arch = "standard"
        elif pid in off_ids:
            # Off-ball offense are still hustling toward their setup spots —
            # the walk-up gates on the BH only and interrupts them partway, so
            # they keep progressing at sprint across loop steps rather than
            # being snapped to the full target every segment.
            action = "stationary"
            move_arch = "sprint"
        else:
            action = "guard_offball"
            move_arch = "standard"

        # Universal speed clamp: no player may travel past their archetype
        # rate within the step. If the intended target is farther than the
        # rate covers in T, end at the interrupted coord (= start + rate × T)
        # and carry it forward next step — mirrors build_walk_up_step and
        # kills the off-ball "jet". Gate players (whose T == their natural
        # travel time) still reach their full target.
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, move_arch)
        ec = _interrupted_coord(sc, target, rate, t) if rate > 0 else dict(target)

        moved = (
            int(round(ec["x"])) != int(round(sc["x"]))
            or int(round(ec["y"])) != int(round(sc["y"]))
        )
        destinations[pid] = dict(target)
        step_end_coords[pid] = dict(ec)
        actions[pid] = action
        archetype[pid] = move_arch if moved else "stationary"

    ball: BallState = {"owner_player_id": bh_id}

    gate_start = start_coords.get(gate_id)
    gate_target = step_end_coords.get(gate_id) or gate_start or {"x": 50.0, "y": 25.0}
    gate_moves = bool(gate_start) and (
        int(round(gate_target["x"])) != int(round(gate_start["x"]))
        or int(round(gate_target["y"])) != int(round(gate_start["y"]))
    )
    if gate_moves:
        # Gate on the mover arriving at its target (e.g. converge / advance / attack).
        advance_trigger: AdvanceTrigger = {
            "condition": "player_reaches_position",
            "T_game_seconds": t,
            "metadata": {
                "target_player_id": gate_id,
                "target_coords": {"x": float(gate_target["x"]), "y": float(gate_target["y"])},
                "reason": reason,
            },
        }
    else:
        # Stationary beat (e.g. hold): gate purely on elapsed time.
        advance_trigger = {
            "condition": "fixed_duration",
            "T_game_seconds": t,
            "metadata": {"reason": reason},
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
        "coords": {pid: dict(c) for pid, c in start_coords.items()},
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": step_end_coords,
        "ball": ball,
        "time_elapsed": t,
        "clock": clock_end,
        "next": next_step,
    }
    stamp_tween_durations(start, step_end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_fb_drive_step(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    shooter_id: str,
    bh_target: GridCoord,
    defender_end: Dict[str, GridCoord],
    seconds: float,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> AnimationStep:
    """The §7/D18 fast-break drive step: the shooter sprints from his topLane
    spot to the rim target ending in shot motion; the lone rim protector moves
    to his contest spot; everyone else holds. Gate = shooter reaching the rim
    target. ``_build_post_shot_sub_steps`` continues the shot from here.
    """
    t = float(seconds)
    off_ids = {_player_id_at_pos(off_lineup, p) for p in _OFFENSE_POSITIONS}
    def_ids = {_player_id_at_pos(def_lineup, p) for p in _OFFENSE_POSITIONS}

    end_coords: Dict[str, GridCoord] = {pid: dict(c) for pid, c in start_coords.items()}
    end_coords[shooter_id] = {"x": float(bh_target["x"]), "y": float(bh_target["y"])}
    for did, coord in (defender_end or {}).items():
        if did in end_coords:
            end_coords[did] = {"x": float(coord["x"]), "y": float(coord["y"])}

    destinations: Dict[str, Optional[GridCoord]] = {}
    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    for pid, sc in start_coords.items():
        ec = end_coords.get(pid, sc)
        moved = (
            int(round(ec["x"])) != int(round(sc["x"]))
            or int(round(ec["y"])) != int(round(sc["y"]))
        )
        destinations[pid] = dict(ec)
        if pid == shooter_id:
            actions[pid] = "shoot"
            archetype[pid] = "sprint"
        elif pid in def_ids:
            actions[pid] = "guard_ball" if moved else "guard_offball"
            archetype[pid] = "sprint" if moved else "stationary"
        else:
            actions[pid] = "stationary"
            archetype[pid] = "sprint" if (moved and pid in off_ids) else "stationary"

    ball: BallState = {"owner_player_id": shooter_id}
    trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": t,
        "metadata": {
            "target_player_id": shooter_id,
            "target_coords": {"x": float(bh_target["x"]), "y": float(bh_target["y"])},
            "reason": "hct_fb_drive",
        },
    }
    start: StepStart = {
        "coords": {pid: dict(c) for pid, c in start_coords.items()},
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball,
        "clock": {
            "clock_remaining": clock_remaining_at_start,
            "shot_clock_remaining": shot_clock_remaining_at_start,
        },
        "advance_trigger": trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball,
        "time_elapsed": t,
        "clock": {
            "clock_remaining": clock_remaining_at_start - t,
            "shot_clock_remaining": shot_clock_remaining_at_start - t,
        },
        "next": {"kind": "next_step", "index": next_step_index},
    }
    return {"start": start, "end": end}


def _build_ab_shot_step(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    shooter_id: str,
    shooter_target: GridCoord,
    defender_end: Dict[str, GridCoord],
    seconds: float,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> AnimationStep:
    """The §7 / 2D-2a in-Attack-Basket shot step: the shooter rises and shoots
    from his spot (no translation); the defenders collapse to their D5
    rim-protection release coords (computed by the resolver); everyone else
    holds. Gate = the shot-motion beat (``fixed_duration``).
    ``_build_post_shot_sub_steps`` continues the shot from here.
    """
    t = float(seconds)
    off_ids = {_player_id_at_pos(off_lineup, p) for p in _OFFENSE_POSITIONS}
    def_ids = {_player_id_at_pos(def_lineup, p) for p in _OFFENSE_POSITIONS}

    end_coords: Dict[str, GridCoord] = {pid: dict(c) for pid, c in start_coords.items()}
    end_coords[shooter_id] = {
        "x": float(shooter_target["x"]),
        "y": float(shooter_target["y"]),
    }
    for did, coord in (defender_end or {}).items():
        if did in end_coords:
            end_coords[did] = {"x": float(coord["x"]), "y": float(coord["y"])}

    destinations: Dict[str, Optional[GridCoord]] = {}
    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    for pid, sc in start_coords.items():
        ec = end_coords.get(pid, sc)
        moved = (
            int(round(ec["x"])) != int(round(sc["x"]))
            or int(round(ec["y"])) != int(round(sc["y"]))
        )
        destinations[pid] = dict(ec)
        if pid == shooter_id:
            actions[pid] = "shoot"
            archetype[pid] = "stationary"  # shoots in place
        elif pid in def_ids:
            actions[pid] = "guard_ball" if moved else "guard_offball"
            archetype[pid] = "standard" if moved else "stationary"
        else:
            actions[pid] = "stationary"
            archetype[pid] = "sprint" if (moved and pid in off_ids) else "stationary"

    ball: BallState = {"owner_player_id": shooter_id}
    trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": t,
        "metadata": {"reason": "hct_ab_shot"},
    }
    start: StepStart = {
        "coords": {pid: dict(c) for pid, c in start_coords.items()},
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball,
        "clock": {
            "clock_remaining": clock_remaining_at_start,
            "shot_clock_remaining": shot_clock_remaining_at_start,
        },
        "advance_trigger": trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball,
        "time_elapsed": t,
        "clock": {
            "clock_remaining": clock_remaining_at_start - t,
            "shot_clock_remaining": shot_clock_remaining_at_start - t,
        },
        "next": {"kind": "next_step", "index": next_step_index},
    }
    stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def build_dynamic_hct_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Assemble [walk-up, *loop segments] schema steps for a dynamic HCT turn.

    The engine returns a variable-length ``hct_loop_segments`` list (converge,
    advances, attack); this builds the entry walk-up plus one generic step per
    segment. Returns None if required intermediate data is missing.
    """
    # --- Required intermediate data from the engine -----------------------
    bh_target = turn_result.get("hct_bh_target")
    other_offense_targets = turn_result.get("hct_other_offense_targets") or {}
    def_initial_targets = turn_result.get("hct_def_initial_targets") or {}
    loop_segments = turn_result.get("hct_loop_segments") or []
    bh_pos = turn_result.get("hct_bh_pos") or "PG"

    if not bh_target or not loop_segments:
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}
    is_away_offense = bool(
        off_team is not None
        and getattr(off_team, "team_id", None)
        == getattr(getattr(game, "away_team", None), "team_id", None)
    )

    # §7 — an HCT possession can end in a real shot. Two shot paths today:
    #   • D18 broken-HCT fast break (drive to the rim) — `hct_fb_*` seed.
    #   • 2D-2a in-Attack-Basket shoot-in-place — `hct_ab_*` seed.
    # Either way the loop segments stay non-terminal and the shot + post-shot
    # sub-steps are appended after them.
    fb_shooter_id = turn_result.get("hct_fb_shooter_id")
    ab_shooter_id = turn_result.get("hct_ab_shooter_id")
    is_fb_shot = bool(fb_shooter_id)
    is_ab_shot = bool(ab_shooter_id)
    is_shot = is_fb_shot or is_ab_shot

    bh_id = _player_id_at_pos(off_lineup, bh_pos)
    pg_def_id = _player_id_at_pos(def_lineup, "PG")
    if not bh_id or not pg_def_id:
        return None

    # --- Prior turn state (BIP-end coords + ball handler) -----------------
    prior_turns = getattr(game, "turns", None) or []
    prior_turn = prior_turns[-1] if prior_turns else None
    prior_final_coords: Dict[str, GridCoord] = {}
    prior_final_bh_id: Optional[str] = None
    if isinstance(prior_turn, dict):
        prior_final_coords = prior_turn.get("final_coords") or {}
        prior_final_bh_id = prior_turn.get("final_ball_handler_id")

    walk_up_bh_id = prior_final_bh_id or bh_id

    if not prior_final_coords or walk_up_bh_id not in prior_final_coords:
        return None

    # --- Build setup_coords for the walk-up step --------------------------
    setup_coords: Dict[str, GridCoord] = {}
    setup_coords[walk_up_bh_id] = {"x": float(bh_target["x"]), "y": float(bh_target["y"])}
    for pos, target in other_offense_targets.items():
        pid = _player_id_at_pos(off_lineup, pos)
        if pid:
            setup_coords[pid] = {"x": float(target["x"]), "y": float(target["y"])}
    for pos, target in def_initial_targets.items():
        pid = _player_id_at_pos(def_lineup, pos)
        if pid:
            setup_coords[pid] = {"x": float(target["x"]), "y": float(target["y"])}

    # --- Clock state at turn start ---------------------------------------
    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining_at_turn_start = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining_at_turn_start = float(
        game_state.get("shot_clock_remaining", 0) or 0
    )

    # --- Step 0: entry walk-up (universal primitive) ---------------------
    walk_step = build_walk_up_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=prior_final_coords,
        end_coords=setup_coords,
        bh_id=walk_up_bh_id,
        clock_remaining_at_start=clock_remaining_at_turn_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_turn_start,
        next_step_index=1,
        bh_archetype="standard",
        other_archetype="sprint",
        gate_player_ids=[walk_up_bh_id],
        metadata_reason="hct_entry_walkup",
    )

    steps: List[AnimationStep] = [walk_step]
    step_clock_seconds: List[float] = [round(float(walk_step["end"]["time_elapsed"]), 2)]

    prev_end_coords = walk_step["end"]["coords"]
    prev_clock_end = walk_step["end"]["clock"]

    # --- Steps 1..N: one generic step per loop segment ------------------
    n = len(loop_segments)
    for i, segment in enumerate(loop_segments):
        reason = segment.get("reason") or "hct_advance"
        end_coords = _seg_end_coords_by_id(segment, off_lineup, def_lineup)
        gate = segment.get("gate") or ["off", bh_pos]
        gate_side, gate_pos = gate[0], gate[1]
        gate_id = _player_id_at_pos(
            off_lineup if gate_side == "off" else def_lineup, gate_pos
        ) or walk_up_bh_id
        seconds = float(segment.get("seconds") or 0.3)

        is_last = i == n - 1
        next_index = len(steps) + 1
        # For an FB shot the loop never terminates the turn — the drive +
        # post-shot sub-steps that follow own the terminal pointer.
        next_step: NextStep = (
            _resolve_final_step_next(turn_result)
            if (is_last and not is_shot)
            else {"kind": "next_step", "index": next_index}
        )

        # Ball owner for this segment (changes after a pass).
        ball_owner_pos = segment.get("ball_owner_pos") or bh_pos
        ball_owner_id = _player_id_at_pos(off_lineup, ball_owner_pos) or walk_up_bh_id

        if reason == "hct_pass":
            # Ball-in-flight: render via the universal pass primitive. Offense
            # holds; defenders drift toward their persisted pass-defense targets.
            passer_id = _player_id_at_pos(off_lineup, segment.get("pass_from_pos") or bh_pos)
            receiver_id = _player_id_at_pos(off_lineup, segment.get("pass_to_pos") or ball_owner_pos)
            continuing_targets = {
                did: end_coords[did]
                for did in (_player_id_at_pos(def_lineup, p) for p in _OFFENSE_POSITIONS)
                if did and did in end_coords
            }
            if passer_id and receiver_id and passer_id in prev_end_coords and receiver_id in prev_end_coords:
                step = build_pass_step(
                    off_lineup=off_lineup,
                    def_lineup=def_lineup,
                    start_coords=prev_end_coords,
                    passer_id=passer_id,
                    receiver_id=receiver_id,
                    continuing_targets=continuing_targets,
                    continuing_archetype="standard",
                    clock_remaining_at_start=prev_clock_end["clock_remaining"],
                    shot_clock_remaining_at_start=prev_clock_end["shot_clock_remaining"],
                    next_step_index=next_index,
                    metadata_reason="hct_pass",
                )
                if is_last and not is_shot:
                    step["end"]["next"] = _resolve_final_step_next(turn_result)
            else:
                # Degenerate pass input — fall back to a generic hold beat.
                step = _build_loop_step(
                    off_lineup=off_lineup,
                    def_lineup=def_lineup,
                    start_coords=prev_end_coords,
                    end_coords=end_coords,
                    bh_id=ball_owner_id,
                    pg_def_id=pg_def_id,
                    gate_id=gate_id,
                    seconds=seconds,
                    clock_remaining_at_start=prev_clock_end["clock_remaining"],
                    shot_clock_remaining_at_start=prev_clock_end["shot_clock_remaining"],
                    next_step=next_step,
                    reason=reason,
                )
        else:
            step = _build_loop_step(
                off_lineup=off_lineup,
                def_lineup=def_lineup,
                start_coords=prev_end_coords,
                end_coords=end_coords,
                bh_id=ball_owner_id,
                pg_def_id=pg_def_id,
                gate_id=gate_id,
                seconds=seconds,
                clock_remaining_at_start=prev_clock_end["clock_remaining"],
                shot_clock_remaining_at_start=prev_clock_end["shot_clock_remaining"],
                next_step=next_step,
                reason=reason,
            )

        steps.append(step)
        step_clock_seconds.append(round(float(step["end"]["time_elapsed"]), 2))
        prev_end_coords = step["end"]["coords"]
        prev_clock_end = step["end"]["clock"]

    # --- §7/D18 fast-break drive + post-shot sub-steps -------------------
    if is_fb_shot and fb_shooter_id in prev_end_coords:
        bh_target = turn_result.get("hct_fb_bh_target") or {}
        defender_end = turn_result.get("hct_fb_defender_end") or {}
        t_shooter = float(turn_result.get("hct_fb_t_shooter") or 0.5)
        drive_step = _build_fb_drive_step(
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            start_coords=prev_end_coords,
            shooter_id=str(fb_shooter_id),
            bh_target={"x": float(bh_target.get("x", 0)), "y": float(bh_target.get("y", 0))},
            defender_end=defender_end,
            seconds=t_shooter,
            clock_remaining_at_start=prev_clock_end["clock_remaining"],
            shot_clock_remaining_at_start=prev_clock_end["shot_clock_remaining"],
            next_step_index=len(steps) + 1,
        )
        steps.append(drive_step)
        step_clock_seconds.append(round(float(drive_step["end"]["time_elapsed"]), 2))

        # Ball flight / variant / hold-or-bounce sub-steps (shared builder).
        _build_post_shot_sub_steps(
            steps, turn_result, off_lineup, def_lineup, is_away_offense,
        )
        # Recompute per-step clock list to include the appended sub-steps.
        step_clock_seconds = [
            round(float((s.get("end") or {}).get("time_elapsed") or 0.0), 2)
            for s in steps
        ]

    # --- §7 / 2D-2a in-Attack-Basket shot + post-shot sub-steps ----------
    if is_ab_shot and ab_shooter_id in prev_end_coords:
        shooter_target = turn_result.get("hct_ab_shooter_target") or {}
        defender_end = turn_result.get("hct_ab_defender_end") or {}
        t_shot = float(turn_result.get("hct_ab_t_shot") or 0.8)
        shot_step = _build_ab_shot_step(
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            start_coords=prev_end_coords,
            shooter_id=str(ab_shooter_id),
            shooter_target={
                "x": float(shooter_target.get("x", 0)),
                "y": float(shooter_target.get("y", 0)),
            },
            defender_end=defender_end,
            seconds=t_shot,
            clock_remaining_at_start=prev_clock_end["clock_remaining"],
            shot_clock_remaining_at_start=prev_clock_end["shot_clock_remaining"],
            next_step_index=len(steps) + 1,
        )
        steps.append(shot_step)
        step_clock_seconds.append(round(float(shot_step["end"]["time_elapsed"]), 2))

        _build_post_shot_sub_steps(
            steps, turn_result, off_lineup, def_lineup, is_away_offense,
        )
        step_clock_seconds = [
            round(float((s.get("end") or {}).get("time_elapsed") or 0.0), 2)
            for s in steps
        ]

    # --- Update turn-level time totals (emitter owns these now) ----------
    turn_result["time_elapsed"] = round(sum(step_clock_seconds), 2)
    turn_result["step_clock_seconds"] = step_clock_seconds
    turn_result["resolution_step_index"] = len(steps) - 1
    turn_result["executed_step_count"] = len(steps)

    return steps
