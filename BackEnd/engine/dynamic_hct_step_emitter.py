"""Dynamic-HCT animation step emitter.

Assembles a variable-length schema step list for a dynamic HCT turn:

  - **Step 0 — entry walk-up** — universal primitive (``build_walk_up_step``).
    BH cruises from BIP-end inbound position to the engage point ``(44, BH_y)``
    (home) / flipped for away; the other four offensive players sprint toward
    randomized frontcourt targets; defenders settle into the HCT alignment.
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

from BackEnd.constants import (
    HOME_RIM_COORDS,
    AWAY_RIM_COORDS,
    HCT_DRIFT_PROBABILITY,
)
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _player_lookup_by_id,
    drift_or_hold_coord,
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
from BackEnd.engine.shot_micro_movements import inject_shot_micro_before_post_shot
from BackEnd.utils.transition_bridge import (
    _interrupted_coord,
    build_pass_step,
    build_walk_up_step,
)


_OFFENSE_POSITIONS = ("PG", "SG", "SF", "PF", "C")

# Per-step coordinate trace for debugging HCT player-coord jank. When True, every
# emitted step logs its label + each active player's start → destination (the
# engine's intended target) → end (what the emitter actually renders). A
# divergence between destination and end flags coord jank. Toggle off when done.
LOG_HCT_STEP_COORDS = False


def _fmt_xy(c: Optional[Dict[str, Any]]) -> str:
    if not c:
        return "(  -,  -)"
    return f"({int(round(c['x'])):>3},{int(round(c['y'])):>3})"


def _log_hct_step_trace(
    steps: List[AnimationStep],
    loop_segments: List[Dict[str, Any]],
    prior_final_coords: Dict[str, GridCoord],
    setup_coords: Dict[str, GridCoord],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Trace every emitted HCT step's per-player coords for jank debugging.

    For each step: ``Step N: <label>`` then, for all 10 active players,
    ``start -> dest -> end`` where ``start`` is the prior step's rendered end,
    ``dest`` is the engine's intended target for the step (the loop segment end),
    and ``end`` is the coord the emitter actually renders. ``dest`` and ``end``
    should match — a mismatch is the coord jank to chase.
    """
    if not LOG_HCT_STEP_COORDS:
        return
    pid_label: Dict[str, str] = {}
    for side, lineup in (("OFF", off_lineup), ("DEF", def_lineup)):
        for pos in _OFFENSE_POSITIONS:
            pid = _player_id_at_pos(lineup, pos)
            if pid:
                pid_label[pid] = f"{side} {pos}"
    n_loop = len(loop_segments)
    lines: List[str] = []
    prev_end: Dict[str, GridCoord] = dict(prior_final_coords or {})
    for idx, step in enumerate(steps):
        end = (step.get("end") or {}).get("coords") or {}
        if idx == 0:
            label = "walk-up (entry bring-up)"
            dest = setup_coords
        elif idx <= n_loop:
            seg = loop_segments[idx - 1]
            label = seg.get("step_label") or seg.get("reason") or "loop step"
            dest = _seg_end_coords_by_id(seg, off_lineup, def_lineup)
        else:
            label = "shot / post-shot sub-step"
            dest = end
        lines.append(f"  Step {idx + 1}: {label}")
        for pid, lab in pid_label.items():
            lines.append(
                f"      {lab}: start {_fmt_xy(prev_end.get(pid))}"
                f"  ->  dest {_fmt_xy(dest.get(pid))}"
                f"  ->  end {_fmt_xy(end.get(pid))}"
            )
        prev_end = end
    print(f"[HCT STEP COORD TRACE] {len(steps)} steps\n" + "\n".join(lines))


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
    # D8 — emergent steal: ball changes hands, possession flips.
    if result_type == "STEAL":
        return {
            "kind": "turn_stop",
            "event": "STEAL",
            "payload": {
                "stealer_id": turn_result.get("stealer_id"),
                "victim_id": turn_result.get("victim_id"),
            },
        }
    # D8 — emergent foul (offensive charge or defensive reach-in).
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
        # HCT-Task 6 (HCT_UESS_Audit.md #9): floor the shot clock at 0 — a
        # segment crossing zero rendered a negative shot clock before the
        # top-of-loop terminal check caught it.
        "shot_clock_remaining": max(0.0, shot_clock_remaining_at_start - t),
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
    is_away_offense: bool = False,
) -> AnimationStep:
    """The §7/D18 fast-break drive step: the shooter sprints from his drive spot
    to the rim target ending in shot motion; the lone rim protector moves to his
    contest spot; every other (off-ball) player rolls ``HCT_DRIFT_PROBABILITY`` to
    drift toward the rim or hold. Gate = shooter reaching the rim target.
    ``_build_post_shot_sub_steps`` continues the shot from here.
    """
    t = float(seconds)
    off_ids = {_player_id_at_pos(off_lineup, p) for p in _OFFENSE_POSITIONS}
    def_ids = {_player_id_at_pos(def_lineup, p) for p in _OFFENSE_POSITIONS}
    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS

    end_coords: Dict[str, GridCoord] = {pid: dict(c) for pid, c in start_coords.items()}
    end_coords[shooter_id] = {"x": float(bh_target["x"]), "y": float(bh_target["y"])}
    for did, coord in (defender_end or {}).items():
        if did in end_coords:
            end_coords[did] = {"x": float(coord["x"]), "y": float(coord["y"])}

    # Off-ball players (not the shooter, not the rim protector) each roll to drift
    # toward the rim or hold for this step.
    involved = {shooter_id} | set(defender_end or {})
    drifted_ids: set = set()
    for pid, sc in start_coords.items():
        if pid in involved:
            continue
        drift_xy, drifted = drift_or_hold_coord(
            _player_lookup_by_id(off_lineup, def_lineup, pid),
            sc, rim, t, HCT_DRIFT_PROBABILITY,
        )
        if drifted:
            end_coords[pid] = drift_xy
            drifted_ids.add(pid)

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
            actions[pid] = "guard_ball" if (moved and pid not in drifted_ids) else "guard_offball"
            archetype[pid] = "drift" if pid in drifted_ids else ("sprint" if moved else "stationary")
        else:
            actions[pid] = "cut" if pid in drifted_ids else "stationary"
            archetype[pid] = "drift" if pid in drifted_ids else ("sprint" if (moved and pid in off_ids) else "stationary")

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
            "shot_clock_remaining": max(0.0, shot_clock_remaining_at_start - t),
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
            "shot_clock_remaining": max(0.0, shot_clock_remaining_at_start - t),
        },
        "next": {"kind": "next_step", "index": next_step_index},
    }
    stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_ab_drive_step(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    driver_id: str,
    driver_target: GridCoord,
    teammate_targets: Dict[str, GridCoord],
    defender_end: Dict[str, GridCoord],
    driver_shoots: bool,
    seconds: float,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> AnimationStep:
    """The §7 / 2D-2b drive step: the driver sprints to his rim target; x>64
    teammates cut to their inside spots; the defenders collapse (D5). Gate =
    the driver reaching his rim target. When ``driver_shoots`` he ends in shot
    motion (no dish); otherwise he ends handling the ball for the dish pass.
    """
    t = float(seconds)
    off_ids = {_player_id_at_pos(off_lineup, p) for p in _OFFENSE_POSITIONS}
    def_ids = {_player_id_at_pos(def_lineup, p) for p in _OFFENSE_POSITIONS}

    end_coords: Dict[str, GridCoord] = {pid: dict(c) for pid, c in start_coords.items()}
    end_coords[driver_id] = {"x": float(driver_target["x"]), "y": float(driver_target["y"])}
    for oid, coord in (teammate_targets or {}).items():
        if oid in end_coords:
            end_coords[oid] = {"x": float(coord["x"]), "y": float(coord["y"])}
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
        if pid == driver_id:
            actions[pid] = "shoot" if driver_shoots else "handle_ball"
            archetype[pid] = "sprint"
        elif pid in def_ids:
            actions[pid] = "guard_ball" if moved else "guard_offball"
            archetype[pid] = "sprint" if moved else "stationary"
        elif moved and pid in off_ids:
            actions[pid] = "cut"
            archetype[pid] = "sprint"
        else:
            actions[pid] = "stationary"
            archetype[pid] = "stationary"

    ball: BallState = {"owner_player_id": driver_id}
    trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": t,
        "metadata": {
            "target_player_id": driver_id,
            "target_coords": {"x": float(driver_target["x"]), "y": float(driver_target["y"])},
            "reason": "hct_ab_drive",
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
            "shot_clock_remaining": max(0.0, shot_clock_remaining_at_start - t),
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

    FCP turns may supply ``fcp_*`` aliases (see ``build_dynamic_fcp_animation_steps``)
    and ``fcp_skip_walk_up=True`` to omit the entry walk-up.
    """
    # FCP alias keys (dynamic FCP wrapper stamps ``fcp_*`` on the turn result).
    if turn_result.get("fcp_loop_segments") is not None:
        for fcp_key, hct_key in (
            ("fcp_bh_target", "hct_bh_target"),
            ("fcp_other_offense_targets", "hct_other_offense_targets"),
            ("fcp_def_initial_targets", "hct_def_initial_targets"),
            ("fcp_loop_segments", "hct_loop_segments"),
            ("fcp_bh_pos", "hct_bh_pos"),
        ):
            if turn_result.get(fcp_key) is not None:
                turn_result[hct_key] = turn_result[fcp_key]

    skip_walk_up = bool(
        turn_result.get("fcp_skip_walk_up") or turn_result.get("hct_skip_walk_up")
    )
    is_fcp = bool(
        turn_result.get("fcp_skip_walk_up")
        or turn_result.get("fcp_loop_segments") is not None
    )

    # --- Required intermediate data from the engine -----------------------
    bh_target = turn_result.get("hct_bh_target")
    other_offense_targets = turn_result.get("hct_other_offense_targets") or {}
    def_initial_targets = turn_result.get("hct_def_initial_targets") or {}
    loop_segments = turn_result.get("hct_loop_segments") or []
    bh_pos = turn_result.get("hct_bh_pos") or "PG"

    if not bh_target or not loop_segments:
        if is_fcp:
            from BackEnd.engine.fcp_step_trace import log_fcp_emitter_bail

            log_fcp_emitter_bail(
                "missing bh_target or loop_segments",
                bh_target=bool(bh_target),
                loop_segment_count=len(loop_segments),
            )
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
        if is_fcp:
            from BackEnd.engine.fcp_step_trace import log_fcp_emitter_bail

            log_fcp_emitter_bail(
                "missing bh_id or pg_def_id",
                bh_id=bh_id,
                pg_def_id=pg_def_id,
                bh_pos=bh_pos,
            )
        return None

    # --- Prior turn state (BIP-end coords + ball handler) -----------------
    prior_turns = getattr(game, "turns", None) or []
    prior_turn = prior_turns[-1] if prior_turns else None
    prior_final_coords: Dict[str, GridCoord] = {}
    prior_final_bh_id: Optional[str] = None
    prior_final_ball_coords: Optional[GridCoord] = None
    if isinstance(prior_turn, dict):
        prior_final_coords = prior_turn.get("final_coords") or {}
        prior_final_bh_id = prior_turn.get("final_ball_handler_id")
        prior_final_ball_coords = prior_turn.get("final_ball_coords")

    # HCT-Task 1 (HCT_UESS_Audit.md #2): backfill any active player missing from
    # the prior turn's final_coords (build_final_coords drops None-coord players)
    # so the walk-up carries all 10 — otherwise a dropped player is frozen/
    # invisible the entire HCT turn + carries stale into the next turn. Mirrors
    # the inbound seam (BIP-Task 2); the dynamic HCT/FCP callsite never had it.
    if prior_final_coords:
        from BackEnd.engine.skeleton_step_emitter import _backfill_missing_active_coords
        prior_final_coords = _backfill_missing_active_coords(
            prior_final_coords, off_lineup, def_lineup
        )

    walk_up_bh_id = prior_final_bh_id or bh_id

    if not prior_final_coords or walk_up_bh_id not in prior_final_coords:
        if is_fcp:
            from BackEnd.engine.fcp_step_trace import log_fcp_emitter_bail

            log_fcp_emitter_bail(
                "missing prior_turn.final_coords or BH not in map",
                prior_coord_count=len(prior_final_coords),
                walk_up_bh_id=walk_up_bh_id,
                bh_in_map=walk_up_bh_id in prior_final_coords if walk_up_bh_id else False,
            )
        return None

    setup_coords: Dict[str, GridCoord] = {}
    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining_at_turn_start = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining_at_turn_start = float(
        game_state.get("shot_clock_remaining", 0) or 0
    )

    if skip_walk_up:
        prev_end_coords = {
            pid: {"x": float(c["x"]), "y": float(c["y"])}
            for pid, c in prior_final_coords.items()
            if isinstance(c, dict)
        }
        prev_clock_end = {
            "clock_remaining": clock_remaining_at_turn_start,
            "shot_clock_remaining": shot_clock_remaining_at_turn_start,
        }
        steps: List[AnimationStep] = []
        step_clock_seconds: List[float] = []
    else:
        # --- Build setup_coords for the walk-up step --------------------------
        setup_coords[walk_up_bh_id] = {"x": float(bh_target["x"]), "y": float(bh_target["y"])}
        for pos, target in other_offense_targets.items():
            pid = _player_id_at_pos(off_lineup, pos)
            if pid:
                setup_coords[pid] = {"x": float(target["x"]), "y": float(target["y"])}
        for pos, target in def_initial_targets.items():
            pid = _player_id_at_pos(def_lineup, pos)
            if pid:
                setup_coords[pid] = {"x": float(target["x"]), "y": float(target["y"])}

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

        # HCT-Task 2 (HCT_UESS_Audit.md #4, SIP-Task 1 parity): fix the entry
        # ball teleport. `build_walk_up_step` hardcodes the ball ATTACHED to the
        # BH; on an in-flight/loose prior end (or prior_final_bh_id==None →
        # fallback to this turn's BH) the ball's RENDERED rest (final_ball_coords)
        # ≠ the BH's coord, so the attach teleports the ball at the entry seam.
        # ONLY override when they actually diverge (> epsilon): seed the ball
        # loose at its rest so it travels to and attaches to the BH by step end.
        # In the common case (prior handed the ball to the BH) the rest == the
        # BH's coord → keep the default attached-dribble (no visual change).
        _bh_start = prior_final_coords.get(walk_up_bh_id)
        if (
            isinstance(prior_final_ball_coords, dict)
            and prior_final_ball_coords.get("x") is not None
            and prior_final_ball_coords.get("y") is not None
            and isinstance(_bh_start, dict)
            and _bh_start.get("x") is not None
        ):
            _bgap = (
                (float(prior_final_ball_coords["x"]) - float(_bh_start["x"])) ** 2
                + (float(prior_final_ball_coords["y"]) - float(_bh_start["y"])) ** 2
            ) ** 0.5
            if _bgap > 1.5:  # UESS_SEAM_TELEPORT_GRID_EPSILON — only fix real divergence
                walk_step["start"]["ball"] = {
                    "coords": {
                        "x": float(prior_final_ball_coords["x"]),
                        "y": float(prior_final_ball_coords["y"]),
                    },
                }
                walk_step["start"]["ball_motion_style"] = "shot"

        steps = [walk_step]
        step_clock_seconds = [round(float(walk_step["end"]["time_elapsed"]), 2)]
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
                pass_cont_archetype = "sprint"
                step = build_pass_step(
                    off_lineup=off_lineup,
                    def_lineup=def_lineup,
                    start_coords=prev_end_coords,
                    passer_id=passer_id,
                    receiver_id=receiver_id,
                    continuing_targets=continuing_targets,
                    continuing_archetype=pass_cont_archetype,
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

        # Reach-in micro-movement: a contest moment (set by dynamic_hct's
        # _stamp_reach_in) stamps the on-ball defender's render-space reach_in
        # flourish on this step. FE-only visual; never mutates gameplay coords.
        # See Flourish in animation_step_schema.py. Params are FE defaults
        # (animation_config.js flourish block) — backend names the kind + target.
        reach_in_pos = segment.get("reach_in_def_pos")
        if reach_in_pos:
            reach_in_id = _player_id_at_pos(def_lineup, reach_in_pos)
            if reach_in_id:
                step["start"].setdefault("flourish", {})[reach_in_id] = {
                    "kind": "reach_in",
                    "target": "ball",
                }

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
            is_away_offense=is_away_offense,
        )
        steps.append(drive_step)
        step_clock_seconds.append(round(float(drive_step["end"]["time_elapsed"]), 2))

        # Ball flight / variant / hold-or-bounce sub-steps (shared builder).
        inject_shot_micro_before_post_shot(
            steps, turn_result, off_lineup, def_lineup, is_away_offense,
        )
        _build_post_shot_sub_steps(
            steps, turn_result, off_lineup, def_lineup, is_away_offense,
        )
        # Recompute per-step clock list to include the appended sub-steps.
        step_clock_seconds = [
            round(float((s.get("end") or {}).get("time_elapsed") or 0.0), 2)
            for s in steps
        ]

    # --- §7 in-Attack-Basket shot/drive + post-shot sub-steps ------------
    ab_mode = turn_result.get("hct_ab_mode") or "shoot"
    ab_driver_id = str(turn_result.get("hct_ab_driver_id") or "")
    defender_end = turn_result.get("hct_ab_defender_end") or {}

    if is_ab_shot and ab_mode == "shoot" and ab_shooter_id in prev_end_coords:
        # 2D-2a — shoot in place.
        shooter_target = turn_result.get("hct_ab_shooter_target") or {}
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
        inject_shot_micro_before_post_shot(
            steps, turn_result, off_lineup, def_lineup, is_away_offense,
        )
        _build_post_shot_sub_steps(
            steps, turn_result, off_lineup, def_lineup, is_away_offense,
        )
        step_clock_seconds = [
            round(float((s.get("end") or {}).get("time_elapsed") or 0.0), 2)
            for s in steps
        ]

    elif is_ab_shot and ab_mode in ("drive", "drive_dish") and ab_driver_id in prev_end_coords:
        # 2D-2b — drive (and optional drive→dish).
        driver_target = turn_result.get("hct_ab_driver_target") or {}
        teammate_targets = turn_result.get("hct_ab_teammate_targets") or {}
        t_drive = float(turn_result.get("hct_ab_t_drive") or 0.6)
        is_dish = ab_mode == "drive_dish"
        drive_step = _build_ab_drive_step(
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            start_coords=prev_end_coords,
            driver_id=ab_driver_id,
            driver_target={
                "x": float(driver_target.get("x", 0)),
                "y": float(driver_target.get("y", 0)),
            },
            teammate_targets=teammate_targets,
            defender_end=defender_end,
            driver_shoots=not is_dish,
            seconds=t_drive,
            clock_remaining_at_start=prev_clock_end["clock_remaining"],
            shot_clock_remaining_at_start=prev_clock_end["shot_clock_remaining"],
            next_step_index=len(steps) + 1,
        )
        steps.append(drive_step)
        step_clock_seconds.append(round(float(drive_step["end"]["time_elapsed"]), 2))

        if is_dish:
            receiver_id = str(turn_result.get("hct_ab_dish_receiver_id") or "")
            receiver_target = turn_result.get("hct_ab_dish_receiver_target") or {}
            t_shot = float(turn_result.get("hct_ab_t_shot") or 0.8)
            pass_clock = drive_step["end"]["clock"]
            pass_step = build_pass_step(
                off_lineup=off_lineup,
                def_lineup=def_lineup,
                start_coords=drive_step["end"]["coords"],
                passer_id=ab_driver_id,
                receiver_id=receiver_id,
                continuing_targets=None,
                clock_remaining_at_start=pass_clock["clock_remaining"],
                shot_clock_remaining_at_start=pass_clock["shot_clock_remaining"],
                next_step_index=len(steps) + 1,
                metadata_reason="hct_ab_dish",
            )
            steps.append(pass_step)
            step_clock_seconds.append(round(float(pass_step["end"]["time_elapsed"]), 2))

            shot_clock = pass_step["end"]["clock"]
            shot_step = _build_ab_shot_step(
                off_lineup=off_lineup,
                def_lineup=def_lineup,
                start_coords=pass_step["end"]["coords"],
                shooter_id=receiver_id,
                shooter_target={
                    "x": float(receiver_target.get("x", 0)),
                    "y": float(receiver_target.get("y", 0)),
                },
                defender_end=defender_end,
                seconds=t_shot,
                clock_remaining_at_start=shot_clock["clock_remaining"],
                shot_clock_remaining_at_start=shot_clock["shot_clock_remaining"],
                next_step_index=len(steps) + 1,
            )
            steps.append(shot_step)
            step_clock_seconds.append(round(float(shot_step["end"]["time_elapsed"]), 2))

        inject_shot_micro_before_post_shot(
            steps, turn_result, off_lineup, def_lineup, is_away_offense,
        )
        _build_post_shot_sub_steps(
            steps, turn_result, off_lineup, def_lineup, is_away_offense,
        )
        step_clock_seconds = [
            round(float((s.get("end") or {}).get("time_elapsed") or 0.0), 2)
            for s in steps
        ]

    # FCP-Task 1 (FCP_UESS_Audit.md #2, HCT-Task 2 parity for the skip_walk_up
    # path): FCP has no walk-up step, so step-0 is the first loop segment whose
    # ball _build_loop_step hardcodes attached to the BH. Seed step-0's ball from
    # the prior turn's RENDERED ball rest (final_ball_coords) — but ONLY when it
    # diverges (> epsilon) from where the ball currently renders attached (the
    # step-0 ball owner's coord) — so on an in-flight/loose/different-BH prior end
    # the ball comes to the BH from its true rest instead of teleporting there.
    # Common case (no divergence) keeps the attached dribble.
    if skip_walk_up and steps and isinstance(prior_final_ball_coords, dict):
        _s0_start = steps[0].get("start") or {}
        _s0_ball = _s0_start.get("ball") or {}
        _s0_owner = _s0_ball.get("owner_player_id")
        _s0_coords = _s0_start.get("coords") or {}
        _owner_coord = (
            (_s0_coords.get(str(_s0_owner)) or _s0_coords.get(_s0_owner))
            if _s0_owner else (_s0_ball.get("coords"))
        )
        if (
            prior_final_ball_coords.get("x") is not None
            and prior_final_ball_coords.get("y") is not None
            and isinstance(_owner_coord, dict)
            and _owner_coord.get("x") is not None
        ):
            _fcp_bgap = (
                (float(prior_final_ball_coords["x"]) - float(_owner_coord["x"])) ** 2
                + (float(prior_final_ball_coords["y"]) - float(_owner_coord["y"])) ** 2
            ) ** 0.5
            if _fcp_bgap > 1.5:  # UESS_SEAM_TELEPORT_GRID_EPSILON — only fix real divergence
                _s0_start["ball"] = {
                    "coords": {
                        "x": float(prior_final_ball_coords["x"]),
                        "y": float(prior_final_ball_coords["y"]),
                    },
                }
                _s0_start["ball_motion_style"] = "shot"

    # --- Update turn-level time totals (emitter owns these now) ----------
    turn_result["time_elapsed"] = round(sum(step_clock_seconds), 2)
    turn_result["step_clock_seconds"] = step_clock_seconds
    turn_result["resolution_step_index"] = len(steps) - 1
    turn_result["executed_step_count"] = len(steps)

    if is_fcp:
        from BackEnd.engine.fcp_step_trace import log_emitter_step_trace

        log_emitter_step_trace(
            steps,
            loop_segments,
            prior_final_coords,
            off_lineup,
            def_lineup,
            skip_walk_up=skip_walk_up,
        )
    else:
        _log_hct_step_trace(
            steps, loop_segments, prior_final_coords, setup_coords, off_lineup, def_lineup
        )

    # Universal steal → HCO/HCT/FCP handoff (skeleton emitter already does this
    # for legacy HCO steals; dynamic FCP/HCT must match).
    if (turn_result.get("result_type") or "").upper() == "STEAL" and steps:
        from BackEnd.engine.skeleton_step_emitter import _append_post_steal_hco_transition

        _append_post_steal_hco_transition(steps, turn_result, game)

    from BackEnd.engine.dead_ball_fumble import inject_dead_ball_fumble_before_turn_stop

    inject_dead_ball_fumble_before_turn_stop(
        steps, turn_result, away_offense=is_away_offense,
    )

    return steps
