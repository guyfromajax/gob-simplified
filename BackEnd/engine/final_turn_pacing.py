"""Final Turn shot choreography budget and anchor pacing (UESS).

Preflight simulates game-clock burn for walk-up, alignment, optional entry pass,
move/pass beats, and verifies the anchor step (outside shoot @ 3s, attack drive
@ 4s) can start on time. When the budget fails, callers route to FLSS instead
of emitting a partial Final Shot play.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import (
    FB_PASS_MIN_GAME_SECONDS,
    HCO_STRING_SPOTS,
    PASS_GRID_SPOTS_PER_GAME_SECOND,
)
from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec, _euclid
from BackEnd.utils.shared import _extract_step_location_coords, get_away_player_coords

LATE_TARGET_OUTSIDE = 3.0
LATE_TARGET_ATTACK = 4.0
BACKCOURT_X_HOME = 71.0
BACKCOURT_X_AWAY = 29.0
ANCHOR_TOLERANCE_SEC = 0.35


@dataclass
class FinalTurnPacingPlan:
    can_meet_anchor: bool
    step0_hold_floor: float
    include_entry_pass: bool
    include_walkup: bool
    anchor_clock: float
    walkup_seconds: float
    alignment_seconds: float
    entry_pass_seconds: float
    pre_anchor_move_seconds: float
    reason: str = ""


def _late_target(shot_type: str) -> float:
    return LATE_TARGET_ATTACK if str(shot_type).lower() == "attack" else LATE_TARGET_OUTSIDE


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
    prior_owner = _prior_ball_handler_id(prior_turn)
    if not prior_owner or not skeleton_bh_id or str(prior_owner) == str(skeleton_bh_id):
        return 0.0, False
    passer_coord = alignment_coords_by_id.get(str(prior_owner))
    receiver_coord = alignment_coords_by_id.get(str(skeleton_bh_id))
    if not passer_coord or not receiver_coord:
        return 0.0, True
    off_lineup = game.offense_team.lineup
    receiver = None
    for pos in ("PG", "SG", "SF", "PF", "C"):
        if _player_id_at_pos(off_lineup, pos) == str(skeleton_bh_id):
            receiver = off_lineup.get(pos)
            break
    if not receiver:
        return 0.0, True
    dist = _euclid(passer_coord, receiver_coord)
    seconds = max(
        float(FB_PASS_MIN_GAME_SECONDS),
        dist / float(PASS_GRID_SPOTS_PER_GAME_SECOND),
    )
    return seconds, True


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
) -> FinalTurnPacingPlan:
    """Return whether standard Final Shot choreography can hit the anchor clock."""
    skeleton_steps = skeleton.get("steps") or []
    time_remaining = float((getattr(game, "game_state", None) or {}).get("time_remaining") or 0)
    anchor = _late_target(shot_type)
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

    fixed_before_hold = walkup_seconds + entry_seconds + pre_anchor_move
    step0_budget = time_remaining - fixed_before_hold - anchor

    if step0_budget < alignment_seconds - 1e-6:
        return FinalTurnPacingPlan(
            can_meet_anchor=False,
            step0_hold_floor=0.0,
            include_entry_pass=needs_entry,
            include_walkup=include_walkup,
            anchor_clock=anchor,
            walkup_seconds=walkup_seconds,
            alignment_seconds=alignment_seconds,
            entry_pass_seconds=entry_seconds,
            pre_anchor_move_seconds=pre_anchor_move,
            reason="insufficient_time_for_alignment_and_anchor",
        )

    hold_floor = max(0.0, step0_budget)
    step0_duration = max(alignment_seconds, hold_floor)
    clock_at_anchor = time_remaining - walkup_seconds - step0_duration - entry_seconds - pre_anchor_move
    can_meet = math.isclose(clock_at_anchor, anchor, abs_tol=ANCHOR_TOLERANCE_SEC) or clock_at_anchor >= anchor - ANCHOR_TOLERANCE_SEC

    include_entry_pass = needs_entry
    if needs_entry and not can_meet:
        # Retry budget without entry pass — treat live owner as BH for the rest.
        retry_entry = 0.0
        retry_budget = time_remaining - walkup_seconds - retry_entry - pre_anchor_move - anchor
        if retry_budget >= alignment_seconds - 1e-6:
            retry_hold = max(0.0, retry_budget)
            retry_step0 = max(alignment_seconds, retry_hold)
            retry_clock = time_remaining - walkup_seconds - retry_step0 - retry_entry - pre_anchor_move
            if retry_clock >= anchor - ANCHOR_TOLERANCE_SEC:
                return FinalTurnPacingPlan(
                    can_meet_anchor=True,
                    step0_hold_floor=retry_hold,
                    include_entry_pass=False,
                    include_walkup=include_walkup,
                    anchor_clock=anchor,
                    walkup_seconds=walkup_seconds,
                    alignment_seconds=alignment_seconds,
                    entry_pass_seconds=0.0,
                    pre_anchor_move_seconds=pre_anchor_move,
                    reason="entry_pass_omitted_for_anchor",
                )

    if not can_meet:
        return FinalTurnPacingPlan(
            can_meet_anchor=False,
            step0_hold_floor=hold_floor,
            include_entry_pass=include_entry_pass,
            include_walkup=include_walkup,
            anchor_clock=anchor,
            walkup_seconds=walkup_seconds,
            alignment_seconds=alignment_seconds,
            entry_pass_seconds=entry_seconds,
            pre_anchor_move_seconds=pre_anchor_move,
            reason="anchor_unreachable",
        )

    return FinalTurnPacingPlan(
        can_meet_anchor=True,
        step0_hold_floor=hold_floor,
        include_entry_pass=include_entry_pass,
        include_walkup=include_walkup,
        anchor_clock=anchor,
        walkup_seconds=walkup_seconds,
        alignment_seconds=alignment_seconds,
        entry_pass_seconds=entry_seconds,
        pre_anchor_move_seconds=pre_anchor_move,
        reason="ok",
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
) -> bool:
    """Post-emit check: anchor step starts near 3s (outside) or 4s (attack)."""
    idx = find_anchor_animation_step_index(animation_steps, shot_type)
    if idx is None:
        return False
    clock = (animation_steps[idx].get("start") or {}).get("clock") or {}
    remaining = clock.get("clock_remaining")
    if remaining is None:
        return False
    target = _late_target(shot_type)
    return float(remaining) >= target - ANCHOR_TOLERANCE_SEC
