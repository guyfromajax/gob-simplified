"""Dynamic-HCT animation step emitter.

Constructs the three schema steps that render a dynamic HCT turn:

  1. **Entry walk-up** — universal primitive (``build_walk_up_step``). BH
     cruises from BIP-end inbound position to the engage point
     ``(44, BH_y)`` (home offense) or ``(56, BH_y)`` (away offense). Other
     four offensive players sprint toward randomized front-court targets.
     Defenders hold at the HCT alignment BIP planted them at (PG at center
     court; others at ``HCT_STANDARD_NORMAL`` centroids). Gate = BH.
  2. **Converge** — defensive PG slides to ``(BH_x ± 2, BH_y)`` to engage
     the ball handler while everyone else holds. Gate = PG defender.
  3. **Attack** — outcome step. On HCO branch, BH dribbles to deep key; PG
     defender follows. On DEAD BALL branch, BH dribbles partway along the
     deep-key path; PG defender follows. Gate = BH.

The engine (``dynamic_hct.compute_dynamic_hct_turn``) returns intermediate
data — target coords, durations, the result type — and this module
assembles the schema. Reads ``prior_turn.final_coords`` and
``prior_turn.final_ball_handler_id`` to seed step 1's start coords (the
same pattern HCO uses for its entry orchestrator).

Spec context: ``_documentation_master/05_Animation_System/Step_By_Step_System.md``.
"""

from typing import Any, Dict, List, Optional

from BackEnd.utils.animation_step_helpers import stamp_tween_durations
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
from BackEnd.utils.transition_bridge import build_walk_up_step


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


def _build_converge_step(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    pg_def_id: str,
    bh_id: str,
    converge_target: GridCoord,
    converge_seconds: float,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> AnimationStep:
    """HCT step 2: defensive PG converges on the BH; everyone else holds.

    Single-mover step. Gate = PG defender reaching ``converge_target``.
    Other 9 players hold at ``start_coords`` (which seeds from the walk-up
    step's end coords, so converge.start matches walk-up.end exactly).
    """
    t = float(converge_seconds)

    destinations: Dict[str, Optional[GridCoord]] = {}
    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    end_coords: Dict[str, GridCoord] = {}

    for pid, sc in start_coords.items():
        if pid == pg_def_id:
            destinations[pid] = dict(converge_target)
            actions[pid] = "guard_ball"
            archetype[pid] = "standard"
            end_coords[pid] = dict(converge_target)
        else:
            destinations[pid] = dict(sc)
            archetype[pid] = "stationary"
            end_coords[pid] = dict(sc)
            if pid == bh_id:
                actions[pid] = "handle_ball"
            elif pid in {_player_id_at_pos(off_lineup, p) for p in _OFFENSE_POSITIONS}:
                actions[pid] = "stationary"
            else:
                actions[pid] = "guard_offball"

    ball: BallState = {"owner_player_id": bh_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": t,
        "metadata": {
            "target_player_id": pg_def_id,
            "target_coords": {
                "x": float(converge_target["x"]),
                "y": float(converge_target["y"]),
            },
            "reason": "hct_converge",
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
        "coords": {pid: dict(c) for pid, c in start_coords.items()},
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_attack_step(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    start_coords: Dict[str, GridCoord],
    bh_id: str,
    pg_def_id: str,
    bh_target: GridCoord,
    def_target: GridCoord,
    attack_seconds: float,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    turn_result: Dict[str, Any],
) -> AnimationStep:
    """HCT step 3 (attack outcome). BH dribbles toward ``bh_target`` (deep
    key for HCO branch, partway for DEAD BALL branch). PG defender follows
    to ``def_target`` (BH end coord offset toward the basket). Everyone
    else holds. Gate = BH.
    """
    t = float(attack_seconds)

    destinations: Dict[str, Optional[GridCoord]] = {}
    actions: Dict[str, PlayerAction] = {}
    archetype: Dict[str, PlayerArchetype] = {}
    end_coords: Dict[str, GridCoord] = {}

    for pid, sc in start_coords.items():
        if pid == bh_id:
            destinations[pid] = dict(bh_target)
            actions[pid] = "handle_ball"
            archetype[pid] = "standard"
            end_coords[pid] = dict(bh_target)
        elif pid == pg_def_id:
            destinations[pid] = dict(def_target)
            actions[pid] = "guard_ball"
            archetype[pid] = "standard"
            end_coords[pid] = dict(def_target)
        else:
            destinations[pid] = dict(sc)
            archetype[pid] = "stationary"
            end_coords[pid] = dict(sc)
            if pid in {_player_id_at_pos(off_lineup, p) for p in _OFFENSE_POSITIONS}:
                actions[pid] = "stationary"
            else:
                actions[pid] = "guard_offball"

    ball: BallState = {"owner_player_id": bh_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": t,
        "metadata": {
            "target_player_id": bh_id,
            "target_coords": {
                "x": float(bh_target["x"]),
                "y": float(bh_target["y"]),
            },
            "reason": "hct_attack",
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
        "coords": {pid: dict(c) for pid, c in start_coords.items()},
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball,
        "time_elapsed": t,
        "clock": clock_end,
        "next": _resolve_final_step_next(turn_result),
    }
    stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def build_dynamic_hct_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Assemble [walk-up, converge, attack] schema steps for a dynamic HCT turn.

    Returns None if required intermediate data is missing (caller leaves
    the turn without ``animation_steps``).
    """
    # --- Required intermediate data from the engine -----------------------
    bh_target = turn_result.get("hct_bh_target")
    other_offense_targets = turn_result.get("hct_other_offense_targets") or {}
    def_initial_targets = turn_result.get("hct_def_initial_targets") or {}
    converge_target = turn_result.get("hct_converge_target")
    converge_seconds = turn_result.get("hct_converge_seconds")
    attack_bh_target = turn_result.get("hct_attack_bh_target")
    attack_def_target = turn_result.get("hct_attack_def_target")
    attack_seconds = turn_result.get("hct_attack_seconds")
    bh_pos = turn_result.get("hct_bh_pos") or "PG"

    if not bh_target or not converge_target or not attack_bh_target:
        return None
    if converge_seconds is None or attack_seconds is None:
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}

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

    # BH at BIP-end. Prefer the universal stamp; fall back to lineup
    # position for the first cut where dynamic HCT always uses PG.
    walk_up_bh_id = prior_final_bh_id or bh_id

    if not prior_final_coords or walk_up_bh_id not in prior_final_coords:
        # Without a coherent start coord map, we can't build the walk-up.
        # Caller leaves animation_steps unset and the legacy fallback (if
        # any) handles rendering.
        return None

    # --- Build setup_coords for the walk-up step --------------------------
    # Offense BH → engage point; other 4 offense → randomized front-court
    # targets; defenders → HCT centroid alignment (continuing the destination
    # BIP started them toward). BIP step 1's short T usually interrupts
    # defenders mid-travel; the walk-up step gives them the rest of the
    # window (gated on BH cruise) to settle into the trap at sprint rate.
    # Same end coords across BIP step 1, BIP step 2, HCT walk-up — defenders
    # walk continuously, no snap.
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

    # --- Step 1: entry walk-up (universal primitive) ---------------------
    walk_step = build_walk_up_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=prior_final_coords,
        end_coords=setup_coords,
        bh_id=walk_up_bh_id,
        clock_remaining_at_start=clock_remaining_at_turn_start,
        shot_clock_remaining_at_start=shot_clock_remaining_at_turn_start,
        next_step_index=1,
        bh_archetype="cruise",
        other_archetype="sprint",
        gate_player_ids=[walk_up_bh_id],
        metadata_reason="hct_entry_walkup",
    )

    walk_up_t = float(walk_step["end"]["time_elapsed"])
    walk_up_end_coords = walk_step["end"]["coords"]
    walk_up_clock_end = walk_step["end"]["clock"]

    # --- Step 2: converge (PG defender slides onto BH) -------------------
    converge_step = _build_converge_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=walk_up_end_coords,
        pg_def_id=pg_def_id,
        bh_id=walk_up_bh_id,
        converge_target=converge_target,
        converge_seconds=float(converge_seconds),
        clock_remaining_at_start=walk_up_clock_end["clock_remaining"],
        shot_clock_remaining_at_start=walk_up_clock_end["shot_clock_remaining"],
        next_step_index=2,
    )

    converge_clock_end = converge_step["end"]["clock"]
    converge_end_coords = converge_step["end"]["coords"]

    # --- Step 3: attack outcome (BH drives, PG defender follows) ---------
    attack_step = _build_attack_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=converge_end_coords,
        bh_id=walk_up_bh_id,
        pg_def_id=pg_def_id,
        bh_target=attack_bh_target,
        def_target=attack_def_target,
        attack_seconds=float(attack_seconds),
        clock_remaining_at_start=converge_clock_end["clock_remaining"],
        shot_clock_remaining_at_start=converge_clock_end["shot_clock_remaining"],
        turn_result=turn_result,
    )

    # --- Update turn-level time totals (emitter owns these now) ----------
    total_elapsed = walk_up_t + float(converge_seconds) + float(attack_seconds)
    turn_result["time_elapsed"] = round(total_elapsed, 2)
    turn_result["step_clock_seconds"] = [
        round(walk_up_t, 2),
        round(float(converge_seconds), 2),
        round(float(attack_seconds), 2),
    ]
    turn_result["resolution_step_index"] = 2
    turn_result["executed_step_count"] = 3

    return [walk_step, converge_step, attack_step]
