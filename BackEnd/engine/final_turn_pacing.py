"""Final Turn shot choreography budget and anchor pacing (UESS).

Preflight simulates game-clock burn for walk-up, alignment, optional entry pass,
move/pass beats, and verifies the anchor step (outside shoot @ randint(1,3)s,
attack drive @ randint(2,4)s) can start on time. When the budget fails, callers route to FLSS instead
of emitting a partial Final Shot play.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import (
    FB_PASS_MIN_GAME_SECONDS,
    FINAL_TURN_HANDOFF_CONVERGE_GRID,
    HCO_STRING_SPOTS,
    PASS_GRID_SPOTS_PER_GAME_SECOND,
)
from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec, _euclid
from BackEnd.utils.shared import _extract_step_location_coords, get_away_player_coords

LATE_TARGET_OUTSIDE = 3.0  # legacy default for tests/docs only
LATE_TARGET_ATTACK = 4.0
BACKCOURT_X_HOME = 71.0
BACKCOURT_X_AWAY = 29.0
ANCHOR_TOLERANCE_SEC = 0.35


def final_turn_attack_drive_reserve_seconds(*, is_away_offense: bool) -> float:
    """Conservative game-clock burn from wing to basket on Final Turn attack drives."""
    wing = _spot_coords("upper wing", is_away_offense=is_away_offense)
    basket = _spot_coords("basketSpot", is_away_offense=is_away_offense)

    class _SlowShooter:
        attributes = {"AG": 1}

    return _travel_seconds(wing, basket, _SlowShooter(), archetype="shot_motion")


def roll_anchor_clock(shot_type: str) -> float:
    """Roll per-possession anchor: outside shoot @ 1–3s, attack drive start @ 2–4s."""
    if str(shot_type).lower() == "attack":
        return float(random.randint(2, 4))
    return float(random.randint(1, 3))


def _late_target(shot_type: str, anchor_clock: Optional[float] = None) -> float:
    if anchor_clock is not None:
        return float(anchor_clock)
    return roll_anchor_clock(shot_type)


@dataclass
class FinalTurnPacingPlan:
    can_meet_anchor: bool          # BASE Final Shot (NO handoff) meets the anchor → the FLSS gate
    step0_hold_floor: float        # hold floor for the no-handoff path (pg_direct / skip_handoff)
    include_entry_pass: bool       # a handoff is NEEDED (the PG wasn't the live handler)
    include_walkup: bool
    anchor_clock: float
    walkup_seconds: float
    alignment_seconds: float
    entry_pass_seconds: float
    pre_anchor_move_seconds: float
    micro_reserve_seconds: float = 0.0
    # Dual verdict: whether the handoff ALSO fits on top of the base Final Shot.
    #   include_entry_pass=False               → pg_direct (PG already had it)
    #   handoff_fits=True                      → handoff mode (bh=PG, deliver via handoff)
    #   handoff_fits=False AND can_meet_anchor → skip_handoff (bh=live handler, PG↔handler swap)
    #   can_meet_anchor=False                  → FLSS / best-effort
    handoff_fits: bool = True
    step0_hold_floor_with_handoff: float = 0.0  # hold floor when the handoff is included
    reason: str = ""


def _spot_coords(spot: str, *, is_away_offense: bool) -> Dict[str, float]:
    raw = HCO_STRING_SPOTS.get(spot, {"x": 64, "y": 25})
    if is_away_offense:
        return get_away_player_coords(raw)
    return {"x": float(raw["x"]), "y": float(raw["y"])}


def _player_id_at_pos(lineup: Dict[str, Any], pos: str) -> Optional[str]:
    player = lineup.get(pos)
    if not player:
        return None
    pid = getattr(player, "player_id", None)
    return str(pid) if pid is not None else None


def _travel_seconds(
    start: Dict[str, float],
    end: Dict[str, float],
    player: Any,
    *,
    archetype: str = "standard",
) -> float:
    dist = _euclid(start, end)
    if dist < 1e-6:
        return 0.0
    rate = _ag_grid_per_game_sec(player, archetype)
    if rate <= 0:
        return 0.05
    return max(0.05, dist / rate)


def _step_action_coords(
    step: Dict[str, Any],
    pos: str,
    *,
    is_away_offense: bool,
) -> Optional[Dict[str, float]]:
    action_info = (step.get("pos_actions") or {}).get(pos) or {}
    coords = _extract_step_location_coords(action_info)
    if coords:
        if is_away_offense:
            return get_away_player_coords(coords)
        return {"x": float(coords["x"]), "y": float(coords["y"])}
    location = action_info.get("location")
    if isinstance(location, str):
        return _spot_coords(location, is_away_offense=is_away_offense)
    return None


def _slowest_offense_move_seconds(
    skeleton_steps: List[Dict[str, Any]],
    step_index: int,
    off_lineup: Dict[str, Any],
    *,
    is_away_offense: bool,
    prev_coords_by_pos: Optional[Dict[str, Dict[str, float]]] = None,
) -> float:
    if step_index <= 0 or step_index >= len(skeleton_steps):
        return 0.0
    prev_step = skeleton_steps[step_index - 1]
    step = skeleton_steps[step_index]
    slowest = 0.0
    for pos in ("PG", "SG", "SF", "PF", "C"):
        player = off_lineup.get(pos)
        if not player:
            continue
        start = None
        if prev_coords_by_pos and pos in prev_coords_by_pos:
            start = prev_coords_by_pos[pos]
        else:
            start = _step_action_coords(prev_step, pos, is_away_offense=is_away_offense)
        end = _step_action_coords(step, pos, is_away_offense=is_away_offense)
        if not start or not end:
            continue
        slowest = max(slowest, _travel_seconds(start, end, player))
    return slowest


def _estimate_pass_step_seconds(
    passer_start: Dict[str, float],
    receiver_start: Dict[str, float],
    receiver_end: Dict[str, float],
    receiver: Any,
    *,
    move_seconds: float,
) -> float:
    receiver_rate = _ag_grid_per_game_sec(receiver, "standard")
    dist_pass = _euclid(passer_start, receiver_end)
    ball_t = max(
        float(FB_PASS_MIN_GAME_SECONDS),
        dist_pass / float(PASS_GRID_SPOTS_PER_GAME_SECOND),
    )
    return max(move_seconds, ball_t)


def _find_anchor_step_index(skeleton_steps: List[Dict[str, Any]], shot_type: str) -> int:
    anchor_action = "drive" if str(shot_type).lower() == "attack" else "shoot"
    for i, step in enumerate(skeleton_steps):
        for action_info in (step.get("pos_actions") or {}).values():
            if (action_info or {}).get("action") == anchor_action:
                return i
    return max(0, len(skeleton_steps) - 1)


def _prior_ball_handler_id(prior_turn: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(prior_turn, dict):
        return None
    for key in ("final_ball_handler_id", "ball_handler_id"):
        val = prior_turn.get(key)
        if val:
            return str(val)
    roles = prior_turn.get("roles") or {}
    bh = roles.get("ball_handler")
    pid = getattr(bh, "player_id", None) if bh is not None else None
    return str(pid) if pid else None


def _needs_walkup(
    prior_turn: Optional[Dict[str, Any]],
    bh_id: Optional[str],
    *,
    is_away_offense: bool,
) -> bool:
    if not isinstance(prior_turn, dict) or not bh_id:
        return False
    prior_coords = prior_turn.get("final_coords") or {}
    bh_coord = prior_coords.get(str(bh_id))
    if not isinstance(bh_coord, dict):
        return False
    bx = float(bh_coord.get("x", 50))
    if is_away_offense:
        return bx > BACKCOURT_X_AWAY
    return bx < BACKCOURT_X_HOME


def _estimate_walkup_seconds(
    game: Any,
    prior_turn: Optional[Dict[str, Any]],
    bh_id: str,
    alignment_coords_by_id: Dict[str, Dict[str, float]],
) -> float:
    if not isinstance(prior_turn, dict):
        return 0.0
    prior_coords = prior_turn.get("final_coords") or {}
    if not prior_coords:
        return 0.0
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    from BackEnd.utils.transition_bridge import build_walk_up_step

    start_coords = {
        str(pid): {"x": float(c["x"]), "y": float(c["y"])}
        for pid, c in prior_coords.items()
        if isinstance(c, dict)
    }
    end_coords = dict(alignment_coords_by_id)
    if not start_coords or not end_coords or bh_id not in start_coords:
        return 0.0
    try:
        step = build_walk_up_step(
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            start_coords=start_coords,
            end_coords=end_coords,
            bh_id=str(bh_id),
            clock_remaining_at_start=float(game.game_state.get("time_remaining") or 0),
            shot_clock_remaining_at_start=float(game.game_state.get("shot_clock_remaining") or 24),
            next_step_index=1,
            bh_archetype="cruise",
            other_archetype="sprint",
            gate_player_ids=[str(bh_id)],
            metadata_reason="final_turn_entry_walkup",
        )
    except ValueError:
        return 0.0
    return float(step["end"]["time_elapsed"])


def _alignment_coords_by_player_id(
    o_destinations: Dict[str, Dict[str, float]],
    off_lineup: Dict[str, Any],
) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for pos, coord in o_destinations.items():
        pid = _player_id_at_pos(off_lineup, pos)
        if pid and isinstance(coord, dict):
            out[pid] = {"x": float(coord["x"]), "y": float(coord["y"])}
    return out


def _estimate_alignment_seconds(
    game: Any,
    prior_turn: Optional[Dict[str, Any]],
    alignment_coords_by_id: Dict[str, Dict[str, float]],
) -> float:
    if not isinstance(prior_turn, dict):
        return 0.05
    prior_coords = prior_turn.get("final_coords") or {}
    off_lineup = game.offense_team.lineup
    slowest = 0.05
    for pid, dest in alignment_coords_by_id.items():
        start = prior_coords.get(pid)
        if not isinstance(start, dict):
            continue
        player = None
        for pos in ("PG", "SG", "SF", "PF", "C"):
            if _player_id_at_pos(off_lineup, pos) == pid:
                player = off_lineup.get(pos)
                break
        if not player:
            continue
        slowest = max(
            slowest,
            _travel_seconds(
                {"x": float(start["x"]), "y": float(start["y"])},
                dest,
                player,
            ),
        )
    return slowest


def _estimate_entry_pass_seconds(
    game: Any,
    prior_turn: Optional[Dict[str, Any]],
    skeleton_bh_id: Optional[str],
    alignment_coords_by_id: Dict[str, Dict[str, float]],
) -> Tuple[float, bool]:
    """Estimate the Final Turn HANDOFF cost (converge + short pass) when the PG
    (always the Final Turn BH) did not hold the ball entering the turn — the
    handoff-first beat that gets the ball to the PG before alignment. Mirrors the
    real emitted movement: the PG sprints from his **prior** (pre-alignment) spot
    to meet the live handler, then a short pass. Returns ``(seconds, needs_handoff)``.
    The ``include_entry_pass`` / ``entry_pass`` names downstream now denote this
    handoff. NOTE the converge is the *full travel* to the handler — NOT capped at
    the 6-grid receive radius — so the budget reflects the true positioning cost
    (see EOQ_System.md). Falls back to alignment coords when prior coords are absent."""
    prior_owner = _prior_ball_handler_id(prior_turn)
    if not prior_owner or not skeleton_bh_id or str(prior_owner) == str(skeleton_bh_id):
        return 0.0, False
    off_lineup = game.offense_team.lineup
    pg_player = None
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if _player_id_at_pos(off_lineup, pos) == str(skeleton_bh_id):
            pg_player = off_lineup.get(pos)
            break
    if not pg_player:
        return 0.0, True
    # Real converge travel: PG's prior spot → the live handler's prior spot. This is
    # the movement-into-position the handoff actually costs (the players must close
    # the gap before the ≤1s pass). Prior coords come from prior_turn.final_coords;
    # fall back to the alignment map when unavailable.
    prior_coords = (prior_turn or {}).get("final_coords") or {}

    def _prior_xy(pid: str) -> Optional[Dict[str, float]]:
        c = prior_coords.get(str(pid)) or prior_coords.get(pid)
        if isinstance(c, dict) and "x" in c and "y" in c:
            return {"x": float(c["x"]), "y": float(c["y"])}
        return alignment_coords_by_id.get(str(pid))

    pg_xy = _prior_xy(str(skeleton_bh_id))
    handler_xy = _prior_xy(str(prior_owner))
    if pg_xy and handler_xy:
        converge_dist = _euclid(pg_xy, handler_xy)
    else:
        converge_dist = float(FINAL_TURN_HANDOFF_CONVERGE_GRID)
    sprint_rate = _ag_grid_per_game_sec(pg_player, "sprint")
    converge_seconds = float(converge_dist) / max(1e-6, float(sprint_rate))
    pass_seconds = max(
        float(FB_PASS_MIN_GAME_SECONDS),
        float(FINAL_TURN_HANDOFF_CONVERGE_GRID) / float(PASS_GRID_SPOTS_PER_GAME_SECOND),
    )
    return converge_seconds + pass_seconds, True


def _estimate_pre_anchor_move_seconds(
    skeleton_steps: List[Dict[str, Any]],
    anchor_index: int,
    off_lineup: Dict[str, Any],
    *,
    is_away_offense: bool,
    position_to_spot: Dict[str, str],
) -> float:
    if anchor_index <= 1:
        return 0.0
    # After alignment, offense players are at step-0 spots.
    aligned_by_pos: Dict[str, Dict[str, float]] = {
        pos: _spot_coords(position_to_spot.get(pos, "key"), is_away_offense=is_away_offense)
        for pos in ("PG", "SG", "SF", "PF", "C")
    }
    total = 0.0
    for step_idx in range(1, anchor_index):
        step = skeleton_steps[step_idx]
        pos_actions = step.get("pos_actions") or {}
        passer_pos = None
        receiver_pos = None
        for pos, info in pos_actions.items():
            action = (info or {}).get("action")
            if action == "pass":
                passer_pos = pos
            elif action == "receive":
                receiver_pos = pos
        if passer_pos and receiver_pos:
            passer = off_lineup.get(passer_pos)
            receiver = off_lineup.get(receiver_pos)
            p_start = aligned_by_pos.get(passer_pos)
            r_start = aligned_by_pos.get(receiver_pos)
            r_end = _step_action_coords(step, receiver_pos, is_away_offense=is_away_offense)
            if passer and receiver and p_start and r_start and r_end:
                move_t = max(
                    _travel_seconds(p_start, _step_action_coords(step, passer_pos, is_away_offense=is_away_offense) or p_start, passer),
                    _travel_seconds(r_start, r_end, receiver),
                )
                total += _estimate_pass_step_seconds(p_start, r_start, r_end, receiver, move_seconds=move_t)
            else:
                total += _slowest_offense_move_seconds(
                    skeleton_steps, step_idx, off_lineup,
                    is_away_offense=is_away_offense,
                    prev_coords_by_pos=aligned_by_pos,
                )
        else:
            total += _slowest_offense_move_seconds(
                skeleton_steps, step_idx, off_lineup,
                is_away_offense=is_away_offense,
                prev_coords_by_pos=aligned_by_pos,
            )
        # Update aligned positions to step end for chained steps (rare on Final Turn).
        for pos in ("PG", "SG", "SF", "PF", "C"):
            end_c = _step_action_coords(step, pos, is_away_offense=is_away_offense)
            if end_c:
                aligned_by_pos[pos] = end_c
    return total


def _build_preflight_final_turn_skeleton(
    *,
    bh_pos: str,
    shooter_pos: str,
    shot_type: str,
    bh_is_shooter: bool,
    position_to_spot: Dict[str, str],
) -> Dict[str, Any]:
    """Minimal Final Turn skeleton for EOQ follow-up runway checks."""
    from BackEnd.constants import ACTIONS

    step0: Dict[str, Any] = {"timestamp": 0, "pos_actions": {}}
    for pos in ("PG", "SG", "SF", "PF", "C"):
        spot = position_to_spot.get(pos, "key")
        step0["pos_actions"][pos] = {
            "action": ACTIONS["HANDLE"] if pos == bh_pos else "stand",
            "location": spot,
        }
    shot_wing = "upper wing"
    step1: Dict[str, Any] = {"timestamp": 300, "pos_actions": {}}
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if bh_is_shooter and pos == bh_pos:
            step1["pos_actions"][pos] = {"action": ACTIONS["HANDLE"], "location": shot_wing}
        elif not bh_is_shooter and pos == bh_pos:
            step1["pos_actions"][pos] = {"action": ACTIONS["PASS"], "location": "deep key"}
        elif pos == shooter_pos:
            step1["pos_actions"][pos] = {"action": ACTIONS["RECEIVE"], "location": shot_wing}
        else:
            step1["pos_actions"][pos] = {
                "action": "stand",
                "location": position_to_spot.get(pos, "key"),
            }
    if str(shot_type).lower() == "attack":
        step2: Dict[str, Any] = {
            "timestamp": 600,
            "pos_actions": {
                shooter_pos: {"action": ACTIONS["DRIVE"], "location": "basketSpot"},
            },
        }
        step3: Dict[str, Any] = {
            "timestamp": 900,
            "pos_actions": {
                shooter_pos: {"action": ACTIONS["SHOOT"], "location": "basketSpot"},
            },
        }
        return {"steps": [step0, step1, step2, step3]}
    step2 = {
        "timestamp": 600,
        "pos_actions": {
            shooter_pos: {"action": ACTIONS["SHOOT"], "location": shot_wing},
        },
    }
    return {"steps": [step0, step1, step2]}


def can_run_final_turn_followup(
    game: Any,
    *,
    o_destinations: Dict[str, Dict[str, float]],
    position_to_spot: Dict[str, str],
    bh_pos: str,
    prior_turn: Optional[Dict[str, Any]] = None,
) -> bool:
    """True when any reasonable Final Turn choreography fits the remaining clock."""
    scenarios = (
        ("Attack", 4.0, False),
        ("Outside", 3.0, False),
        ("Attack", 4.0, True),
        ("Outside", 3.0, True),
    )
    alt_shooter = next((p for p in ("SF", "SG", "PF", "PG") if p != bh_pos), "SF")
    for shot_type, anchor, bh_is_shooter in scenarios:
        shooter_pos = bh_pos if bh_is_shooter else alt_shooter
        skeleton = _build_preflight_final_turn_skeleton(
            bh_pos=bh_pos,
            shooter_pos=shooter_pos,
            shot_type=shot_type,
            bh_is_shooter=bh_is_shooter,
            position_to_spot=position_to_spot,
        )
        pacing = evaluate_final_turn_pacing(
            game,
            skeleton=skeleton,
            o_destinations=o_destinations,
            position_to_spot=position_to_spot,
            bh_pos=bh_pos,
            shooter_pos=shooter_pos,
            shot_type=shot_type,
            bh_is_shooter=bh_is_shooter,
            prior_turn=prior_turn,
            anchor_clock=anchor,
        )
        if pacing.can_meet_anchor:
            return True
    return False


def evaluate_final_turn_pacing(
    game: Any,
    *,
    skeleton: Dict[str, Any],
    o_destinations: Dict[str, Dict[str, float]],
    position_to_spot: Dict[str, str],
    bh_pos: str,
    shooter_pos: str,
    shot_type: str,
    bh_is_shooter: bool,
    prior_turn: Optional[Dict[str, Any]] = None,
    anchor_clock: Optional[float] = None,
) -> FinalTurnPacingPlan:
    """Return whether standard Final Shot choreography can hit the anchor clock."""
    skeleton_steps = skeleton.get("steps") or []
    time_remaining = float((getattr(game, "game_state", None) or {}).get("time_remaining") or 0)
    anchor = float(anchor_clock) if anchor_clock is not None else roll_anchor_clock(shot_type)
    off_lineup = game.offense_team.lineup
    is_away_offense = game.offense_team.team_id == game.away_team.team_id
    alignment_by_id = _alignment_coords_by_player_id(o_destinations, off_lineup)
    skeleton_bh_id = _player_id_at_pos(off_lineup, bh_pos)
    live_bh_id = _prior_ball_handler_id(prior_turn) or skeleton_bh_id

    include_walkup = _needs_walkup(prior_turn, live_bh_id, is_away_offense=is_away_offense)
    walkup_seconds = (
        _estimate_walkup_seconds(game, prior_turn, str(live_bh_id), alignment_by_id)
        if include_walkup
        else 0.0
    )
    alignment_seconds = _estimate_alignment_seconds(game, prior_turn, alignment_by_id)
    entry_seconds, needs_entry = _estimate_entry_pass_seconds(
        game, prior_turn, skeleton_bh_id, alignment_by_id,
    )
    anchor_index = _find_anchor_step_index(skeleton_steps, shot_type)
    pre_anchor_move = _estimate_pre_anchor_move_seconds(
        skeleton_steps,
        anchor_index,
        off_lineup,
        is_away_offense=is_away_offense,
        position_to_spot=position_to_spot,
    )

    from BackEnd.engine.shot_micro_movements import worst_case_final_turn_micro_reserve

    micro_reserve = worst_case_final_turn_micro_reserve(
        shot_type, is_away_offense=is_away_offense,
    )
    if str(shot_type).lower() == "attack":
        micro_reserve += final_turn_attack_drive_reserve_seconds(is_away_offense=is_away_offense)

    # Two budgets. A path "fits" when its fixed pre-anchor cost + alignment + anchor
    # + micro reserve ≤ time_remaining; the hold floor is the leftover slack.
    def _fits_and_hold(fixed_before_hold: float) -> Tuple[bool, float]:
        step0_budget = time_remaining - fixed_before_hold - anchor - micro_reserve
        fits = step0_budget >= alignment_seconds - 1e-6
        return fits, (max(0.0, step0_budget) if fits else 0.0)

    base_fixed = walkup_seconds + pre_anchor_move
    base_fits, base_hold = _fits_and_hold(base_fixed)
    if needs_entry:
        handoff_fits, handoff_hold = _fits_and_hold(base_fixed + entry_seconds)
    else:
        handoff_fits, handoff_hold = base_fits, base_hold

    if not base_fits:
        reason = "insufficient_time_for_alignment_and_anchor"
    elif needs_entry and not handoff_fits:
        reason = "handoff_skipped_base_fits"  # → skip_handoff (bh = live handler)
    else:
        reason = "ok"

    return FinalTurnPacingPlan(
        can_meet_anchor=base_fits,
        step0_hold_floor=base_hold,
        include_entry_pass=needs_entry,
        include_walkup=include_walkup,
        anchor_clock=anchor,
        walkup_seconds=walkup_seconds,
        alignment_seconds=alignment_seconds,
        entry_pass_seconds=entry_seconds,
        pre_anchor_move_seconds=pre_anchor_move,
        micro_reserve_seconds=micro_reserve,
        handoff_fits=bool(handoff_fits),
        step0_hold_floor_with_handoff=handoff_hold,
        reason=reason,
    )


def apply_step0_hold_floor(skeleton: Dict[str, Any], hold_floor: float) -> None:
    steps = skeleton.get("steps") or []
    if not steps:
        return
    if hold_floor > 0:
        steps[0]["_step_t_floor_game_seconds"] = float(hold_floor)
    else:
        steps[0].pop("_step_t_floor_game_seconds", None)


def find_anchor_animation_step_index(
    animation_steps: List[Dict[str, Any]],
    shot_type: str,
) -> Optional[int]:
    anchor_action = "drive" if str(shot_type).lower() == "attack" else "shoot"
    for i, step in enumerate(animation_steps):
        actions = (step.get("start") or {}).get("action") or {}
        if any(a == anchor_action for a in actions.values()):
            return i
    return None


def verify_animation_steps_anchor(
    animation_steps: List[Dict[str, Any]],
    shot_type: str,
    *,
    anchor_clock: Optional[float] = None,
) -> bool:
    """Post-emit check: anchor step starts near the rolled anchor clock."""
    idx = find_anchor_animation_step_index(animation_steps, shot_type)
    if idx is None:
        return False
    clock = (animation_steps[idx].get("start") or {}).get("clock") or {}
    remaining = clock.get("clock_remaining")
    if remaining is None:
        return False
    target = _late_target(shot_type, anchor_clock)
    return float(remaining) >= target - ANCHOR_TOLERANCE_SEC
