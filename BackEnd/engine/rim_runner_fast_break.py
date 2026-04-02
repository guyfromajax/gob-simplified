"""
Rim Runner fast break — DREB outlet → burst → PG read → pass / HCO / shot / intercept / bat OOB.

See docs discussion + Fast_Break_System. Covert Release path remains in resolve_fast_break_logic.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants.fast_break_play_types import RIM_RUNNER
from BackEnd.models.animator import Animator
from BackEnd.utils.shared import (
    apply_coords_from_animations_list,
    calculate_outlet_pass_score,
    unpack_game_context,
)
from BackEnd.utils.position_snapshot_ledger import (
    attach_position_snapshots,
    build_fast_break_pre_shot_snapshot,
    build_phase_post_stopper_snapshot,
)
from BackEnd.engine.phase_resolution import (
    _record_fast_break_stats,
    apply_energy_decay,
    apply_fast_break_cg_time,
    get_in_play_defenders,
)

logger = logging.getLogger(__name__)


def _apply_rr_decision_metadata(payload: Dict[str, Any], *, pass_attempted: bool, fb_open: bool) -> None:
    """
    Attach Rim Runner read-decision metadata for frontend announcement/UI.
    Good decision rule: pass_attempted == fb_open.
    """
    good_decision = bool(pass_attempted) == bool(fb_open)
    payload["rim_runner_pass_attempted"] = bool(pass_attempted)
    payload["rim_runner_fb_open"] = bool(fb_open)
    payload["rim_runner_decision_good"] = good_decision
    payload["rim_runner_decision_label"] = "Good Decision" if good_decision else "Bad Decision"


def _find_most_recent_shot_turn(game: Any, max_turns: int = 10) -> Optional[dict]:
    if not getattr(game, "turns", None):
        return None
    for turn in reversed(game.turns[-max_turns:]):
        if turn.get("result_type") in ["MISS", "MAKE", "BLOCK"]:
            return turn
    return None


def _basket_x_for_offense(is_away_offense: bool) -> float:
    return 9.0 if is_away_offense else 91.0


def _player_x(p: Any, default: float = 50.0) -> float:
    c = getattr(p, "coords", None) or {}
    if isinstance(c, dict):
        try:
            return float(c.get("x", default))
        except (TypeError, ValueError):
            return default
    return default


def _player_y(p: Any, default: float = 25.0) -> float:
    c = getattr(p, "coords", None) or {}
    if isinstance(c, dict):
        try:
            return float(c.get("y", default))
        except (TypeError, ValueError):
            return default
    return default


def _rebound_spot_x_for_rr(rebounder: Any, most_recent: Optional[dict]) -> float:
    """Prefer ball bounce x from recent MAKE/MISS/BLOCK turn; else rebounder grid x."""
    if most_recent:
        bx = most_recent.get("ball_bounce_x")
        if bx is not None:
            try:
                return float(bx)
            except (TypeError, ValueError):
                pass
    return _player_x(rebounder) if rebounder else 50.0


def _use_dynamic_rr_outlet_placement(is_away_offense: bool, rebound_x: float) -> bool:
    """
    When True, outlet receiver target x = rebound + 12 (home FB) or rebound - 12 (away FB),
    and rim runner sprint x is offset from that receiver target (not from RR's pre-burst x).

    Home attacking right: trigger on left/away half with rebound x > 25.
    Away attacking left: trigger on right/home half with rebound x < 75.
    """
    if not is_away_offense:
        return 25.0 < rebound_x < 50.0
    return 50.0 < rebound_x < 75.0


def _y_toward_25(py: float, max_step: int = 6) -> float:
    """Move defensive y at most ``max_step`` toward 25 (grid)."""
    target = 25.0
    delta = target - py
    if delta == 0:
        return py
    step = int(max(-max_step, min(max_step, delta)))
    return float(max(1, min(49, int(round(py + step)))))


def _y_toward_rr_clamped(py: float, rr_y: float, max_step: int = 6) -> float:
    """Move y up to ``max_step`` toward rim runner y without crossing past ``rr_y``."""
    dy = float(rr_y) - float(py)
    if abs(dy) < 1e-6:
        return float(py)
    direction = 1.0 if dy > 0 else -1.0
    step = min(float(max_step), abs(dy))
    ny = py + direction * step
    if direction > 0:
        ny = min(ny, float(rr_y))
    else:
        ny = max(ny, float(rr_y))
    return float(max(1, min(49, round(ny))))


def _defender_x_toward_basket(
    px: float, x_dir: int, steps: int, basket_x: float
) -> float:
    """Move defender ``steps`` grid spots toward the attacking basket; do not cross ``basket_x``."""
    raw = float(px) + float(x_dir) * float(steps)
    if x_dir > 0:
        capped = min(raw, float(basket_x))
    elif x_dir < 0:
        capped = max(raw, float(basket_x))
    else:
        capped = raw
    return float(max(4, min(97, round(capped))))


def resolve_rim_runner_player(
    off_lineup: Dict[str, Any],
    game_state: dict,
    off_team: Any,
    rebounder: Any,
    is_away_offense: bool,
) -> Any:
    """
    Rim runner finisher at DREB: designated lineup id if set and on floor, else closest
    offensive player to attacking basket (excluding rebounder for the transfer rule).
    If designated rim runner is the rebounder, transfer to closest *other* teammate to basket.
    """
    basket_x = _basket_x_for_offense(is_away_offense)
    by_team = game_state.get("rim_runner_by_team_id") or {}
    designated = by_team.get(str(getattr(off_team, "team_id", "")))

    def _dist_to_basket(pl: Any) -> float:
        return abs(_player_x(pl) - basket_x)

    players: List[Any] = [p for p in off_lineup.values() if p is not None]

    if designated:
        for p in players:
            if str(getattr(p, "player_id", None)) == str(designated):
                rr = p
                break
        else:
            rr = None
        if rr is not None and rebounder and getattr(rr, "player_id", None) == getattr(
            rebounder, "player_id", None
        ):
            others = [p for p in players if getattr(p, "player_id", None) != getattr(rebounder, "player_id", None)]
            if not others:
                return rr
            return min(others, key=_dist_to_basket)
        if rr is not None:
            return rr

    # Default: closest to attacking basket among teammates != rebounder when possible
    pool = [p for p in players if not rebounder or getattr(p, "player_id", None) != getattr(rebounder, "player_id", None)]
    if not pool:
        pool = players
    if not pool:
        return off_lineup.get("PG")
    return min(pool, key=_dist_to_basket)


def _pick_outlet_defender(def_lineup: Dict[str, Any], passer: Any) -> Optional[Any]:
    """Defender nearest to passer by x (HOME) for outlet pressure."""
    px = _player_x(passer)
    best = None
    best_dx = float("inf")
    for d in def_lineup.values():
        if not d:
            continue
        dx = abs(_player_x(d) - px)
        if dx < best_dx:
            best_dx = dx
            best = d
    return best


def _primary_burst_defender(
    def_lineup: Dict[str, Any],
    getback_ids: List[Any],
    is_away_offense: bool,
    rim_runner: Any,
) -> Tuple[Optional[Any], bool]:
    """
    Single primary defender for burst + intercept; True if they were in get-back set.
    Prefer get-back defender in LOS (same pool as main FB); else closest to attacking basket.
    """
    id_set = {str(x) for x in (getback_ids or [])}
    basket_x = _basket_x_for_offense(is_away_offense)
    rr_x = _player_x(rim_runner)

    candidates: List[Any] = []
    for d in def_lineup.values():
        if not d:
            continue
        did = getattr(d, "player_id", None)
        if did is not None and str(did) in id_set:
            candidates.append(d)

    if candidates:
        primary = min(candidates, key=lambda d: abs(_player_x(d) - rr_x))
        return primary, True

    pool = [d for d in def_lineup.values() if d]
    if not pool:
        return None, False
    primary = min(pool, key=lambda d: abs(_player_x(d) - basket_x))
    return primary, False


def resolve_rim_runner_fast_break(game: Any, fb_play_key: str) -> dict:
    """
    Full Rim Runner resolution for one FAST_BREAK turn (DREB only). Caller increments scouting.
    """
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    apply_energy_decay(off_lineup, def_lineup)
    game_state["last_rebound"] = ""

    rebounder = game_state.get("last_rebounder")
    game_state.pop("last_release_player", None)

    is_away_offense = off_team.team_id == game.away_team.team_id

    fb_roles: Dict[str, Any] = {
        "offense": [],
        "defense": [],
        "ball_handler": None,
        "outlet_passer": None,
        "outlet_receiver": None,
        "fast_break_play": fb_play_key,
        "rim_runner_sequence": fb_play_key == RIM_RUNNER,
    }

    pg = off_lineup.get("PG")
    rr = resolve_rim_runner_player(off_lineup, game_state, off_team, rebounder, is_away_offense)

    rid = getattr(rebounder, "player_id", None) if rebounder else None
    rr_id = getattr(rr, "player_id", None) if rr else None

    if not rr:
        rr = off_lineup.get("PG")

    outlet_defender = _pick_outlet_defender(def_lineup, rebounder) if rebounder else None

    x_dir = -1 if is_away_offense else 1
    rr_x0 = _player_x(rr)
    rr_y0 = _player_y(rr)
    rr_attrs = getattr(rr, "attributes", {}) or {}
    movement_factor = random.randint(1, 100)
    burst_threshold_anim = (
        0.6 * float(rr_attrs.get("AG", 0) or 0)
        + 0.2 * float(rr_attrs.get("IQ", 0) or 0)
        + 0.2 * float(rr_attrs.get("CH", 0) or 0)
    )
    burst_anim_success = movement_factor < burst_threshold_anim
    dx_burst = random.randint(20, 25) if burst_anim_success else random.randint(9, 14)

    if rr_y0 > 24:
        rr_new_y = float(random.randint(30, 35))
    else:
        rr_new_y = float(random.randint(15, 20))

    receive_ty = 15.0 if rr_new_y > 24 else 35.0

    most_recent = _find_most_recent_shot_turn(game)
    rebound_x = _rebound_spot_x_for_rr(rebounder, most_recent)
    use_dynamic = _use_dynamic_rr_outlet_placement(is_away_offense, rebound_x)

    offense_players = [p for p in off_lineup.values() if p is not None]
    best_p: Any = None
    best_d2 = float("inf")
    best_tx = 50.0

    if use_dynamic:
        # Outlet receiver x from rebound; RR ends dx_burst spots toward basket from receiver target.
        if not is_away_offense:
            base_tx = float(max(4, min(97, int(round(rebound_x + 12)))))
        else:
            base_tx = float(max(4, min(97, int(round(rebound_x - 12)))))
        best_tx = base_tx
        for p in offense_players:
            pid = getattr(p, "player_id", None)
            if rr_id is not None and pid is not None and str(pid) == str(rr_id):
                continue
            px = _player_x(p)
            py = _player_y(p)
            dy = receive_ty - py
            d2 = (best_tx - px) ** 2 + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                best_p = p
        if best_p is None:
            best_p = pg or rebounder
            if best_p is None:
                best_p = next(p for p in offense_players if p)
        rr_new_x = float(max(4, min(97, int(round(best_tx + x_dir * dx_burst)))))
    else:
        rr_new_x = float(max(4, min(97, int(round(rr_x0 + x_dir * dx_burst)))))
        for p in offense_players:
            pid = getattr(p, "player_id", None)
            if rr_id is not None and pid is not None and str(pid) == str(rr_id):
                continue
            px = _player_x(p)
            py = _player_y(p)
            tx_raw = px + 8 * x_dir
            tx = min(tx_raw, 40.0) if not is_away_offense else max(tx_raw, 60.0)
            tx = float(max(4, min(97, int(round(tx)))))
            dy = receive_ty - py
            d2 = (tx - px) ** 2 + dy * dy
            if d2 < best_d2:
                best_d2 = d2
                best_p = p
                best_tx = tx

        if best_p is None:
            best_p = pg or rebounder
            if best_p is None:
                best_p = next(p for p in offense_players if p)
            px = _player_x(best_p)
            tx_raw = px + 8 * x_dir
            tx_clamped = min(tx_raw, 40.0) if not is_away_offense else max(tx_raw, 60.0)
            best_tx = float(max(4, min(97, int(round(tx_clamped)))))

    skip_outlet_pass = bool(
        rebounder is not None
        and best_p is not None
        and getattr(rebounder, "player_id", None) == getattr(best_p, "player_id", None)
    )

    ball_handler = best_p
    if ball_handler is None:
        ball_handler = pg or next(p for p in off_lineup.values() if p)

    if skip_outlet_pass:
        fb_roles["outlet_passer"] = None
        fb_roles["outlet_receiver"] = rid
        fb_roles["outlet_score"] = None
    else:
        fb_roles["outlet_passer"] = rid
        fb_roles["outlet_receiver"] = getattr(ball_handler, "player_id", None)
        fb_roles["outlet_score"] = calculate_outlet_pass_score(rebounder) if rebounder else None

    rc = getattr(rebounder, "coords", None) or {}
    fb_roles["outlet_passer_x"] = rc.get("x") if rebounder else None
    fb_roles["outlet_passer_y"] = rc.get("y") if rebounder else None

    od_id = None
    od_to: Optional[Dict[str, float]] = None
    if rebounder and outlet_defender:
        od_id = getattr(outlet_defender, "player_id", None)
        px_passer = _player_x(rebounder)
        py_passer = _player_y(rebounder)
        od_tx = float(max(4, min(97, int(round(px_passer + (2 if not is_away_offense else -2))))))
        od_to = {"x": od_tx, "y": py_passer}

    off_ids = {str(getattr(p, "player_id", None)) for p in off_lineup.values() if p}
    passer_id = str(rid) if rid is not None else None
    recv_id = str(getattr(ball_handler, "player_id", None)) if ball_handler else None
    od_id_s = str(od_id) if od_id is not None else None
    rr_id_s = str(rr_id) if rr_id is not None else ""

    fb_eff = int(off_team.team_attributes.get("fb_efficiency", 0) or 0)
    fb_opp = int(def_team.team_attributes.get("fb_opp_modifier", 0) or 0)
    fb_eff = max(-10, min(10, fb_eff))
    fb_opp = max(-10, min(10, fb_opp))

    basket_x = _basket_x_for_offense(is_away_offense)
    getback_set = {str(x) for x in (most_recent or {}).get("offense_getback") or []}

    other_moves: List[Dict[str, Any]] = []
    for pl in list(off_lineup.values()) + list(def_lineup.values()):
        if not pl:
            continue
        pid = str(getattr(pl, "player_id", None))
        if pid == rr_id_s or pid == passer_id or pid == recv_id or (od_id_s and pid == od_id_s):
            continue
        px = _player_x(pl)
        py = _player_y(pl)
        if pid in off_ids:
            nx = max(4, min(97, int(round(px + x_dir * random.randint(1, 4)))))
            ny = float(py)
        elif pid in getback_set:
            nx = _defender_x_toward_basket(px, x_dir, 15, basket_x)
            ny = _y_toward_rr_clamped(py, float(rr_new_y), max_step=6)
        else:
            attrs = getattr(pl, "attributes", {}) or {}
            iq = float(attrs.get("IQ", 0) or 0)
            ag = float(attrs.get("AG", 0) or 0)
            roll_adj = random.randint(1, 100) - fb_opp
            check = 0.5 * iq + 0.5 * ag
            if check > roll_adj:
                dx = random.randint(15, 20)
            else:
                dx = random.randint(8, 12)
            nx = _defender_x_toward_basket(px, x_dir, dx, basket_x)
            ny = float(_y_toward_25(py))
        other_moves.append(
            {"player_id": getattr(pl, "player_id", None), "to_x": float(nx), "to_y": float(ny)}
        )

    recv_id_val = getattr(ball_handler, "player_id", None)
    fb_roles["rim_runner_burst_phase"] = {
        "rr_id": rr_id,
        "rr_from": {"x": rr_x0, "y": rr_y0},
        "rr_to": {"x": rr_new_x, "y": rr_new_y},
        "burst_success": burst_anim_success,
        "movement_factor": movement_factor,
        "burst_threshold": burst_threshold_anim,
        "skip_outlet_pass": skip_outlet_pass,
        "outlet_passer_id": None if skip_outlet_pass else rid,
        "outlet_receiver_id": recv_id_val,
        "receiver_to": {"x": best_tx, "y": receive_ty},
        "outlet_defender_id": od_id,
        "outlet_defender_to": od_to,
        "other_players": other_moves,
        "is_away_offense": is_away_offense,
    }

    fb_roles["ball_handler"] = ball_handler
    fb_roles["ball_handler_id"] = getattr(ball_handler, "player_id", None)
    fb_roles["rim_runner_id"] = rr_id

    fb_roles["ball_handler_outlet_x"] = best_tx
    fb_roles["ball_handler_outlet_y"] = receive_ty
    fb_roles["ball_handler_move_x"] = 0
    fb_roles["ball_handler_move_y"] = 0
    fb_roles["is_away_offense"] = is_away_offense
    fb_roles["is_steal_entry"] = False
    fb_roles["getback_player_ids"] = (most_recent or {}).get("offense_getback") or []

    fb_roles["defense"] = get_in_play_defenders(ball_handler, def_lineup, is_away_offense)

    # --- Step A: outlet contest ---
    off_attrs = getattr(rebounder, "attributes", {}) if rebounder else {}
    outlet_off_base = (
        off_attrs.get("PS", 0) * 0.5 + off_attrs.get("ST", 0) * 0.3 + off_attrs.get("IQ", 0) * 0.2
    )
    outlet_offense_score = outlet_off_base * random.randint(1, 6)

    if outlet_defender:
        da = outlet_defender.attributes
        outlet_def_base = da.get("IQ", 0) * 0.5 + da.get("OD", 0) * 0.3 + da.get("ST", 0) * 0.2
        outlet_defense_score = outlet_def_base * random.randint(1, 6)
    else:
        outlet_defense_score = 0.0

    outlet_ok = (
        (1.5 * outlet_offense_score) + (3 * fb_eff)
        > outlet_defense_score + (2 * fb_opp)
    )

    if not outlet_ok:
        game_state["offensive_state"] = "HCO"
        def_scouting = def_team.scouting_data
        def_scouting["defense"]["vs_Fast_Break"]["success"] = (
            def_scouting["defense"]["vs_Fast_Break"].get("success", 0) + 1
        )
        animator = Animator(game)
        animations = animator.capture_fast_break_animation(fb_roles, False, None)
        result = {
            "result_type": "DEFENSIVE_STOP",
            "ball_handler": ball_handler,
            "defender": outlet_defender,
            "text": "Fast Break! Outlet denied — settling into half court.",
            "possession_flips": False,
            "time_elapsed": 0,
            "animations": animations,
            "current_turn": "FAST_BREAK",
            "next_play_type": "HCO",
            "next_turn": "HCO",
            "offense_team_id": off_team.team_id,
            "roles": fb_roles,
            "fast_break": True,
            "fast_break_play": fb_play_key,
            "rim_runner_outlet_failed": True,
        }
        _record_fast_break_stats(fb_roles, result, game)
        apply_fast_break_cg_time(result, shot_attempted=False)
        return result

    bp = fb_roles.get("rim_runner_burst_phase") or {}
    rr_to = bp.get("rr_to")
    recv_to = bp.get("receiver_to")
    if rr and isinstance(rr_to, dict):
        rr.coords = {"x": rr_to["x"], "y": rr_to["y"]}
    if ball_handler and isinstance(recv_to, dict):
        ball_handler.coords = {"x": recv_to["x"], "y": recv_to["y"]}

    # --- Burst ---
    getback_ids = (most_recent or {}).get("offense_getback") or []
    primary_def, in_getback = _primary_burst_defender(
        def_lineup, list(getback_ids), is_away_offense, rr
    )

    rr_attrs = getattr(rr, "attributes", {}) if rr else {}
    burst_off_base = rr_attrs.get("AG", 0) * 0.7 + rr_attrs.get("IQ", 0) * 0.3
    burst_offense_score = burst_off_base * random.randint(1, 6)

    if primary_def:
        da = primary_def.attributes
        if in_getback:
            burst_def_base = da.get("IQ", 0) * 1.0 + da.get("AG", 0) * 0.5
        else:
            burst_def_base = da.get("IQ", 0) * 0.5 + da.get("AG", 0) * 0.5
        burst_defense_score = burst_def_base * random.randint(1, 6)
    else:
        burst_defense_score = 0.0

    fb_open = burst_offense_score > burst_defense_score

    # --- PG read (ball handler IQ) ---
    bh_attrs = getattr(ball_handler, "attributes", {})
    read_score = bh_attrs.get("IQ", 0) * random.randint(1, 6)
    read_threshold = 200 - (5 * fb_eff)
    correct_read = read_score > read_threshold

    aggression = int((off_team.strategy_settings or {}).get("aggression", 2) or 2)
    is_aggressive = aggression >= 3

    pass_attempted = False
    if correct_read:
        pass_attempted = fb_open
    else:
        if is_aggressive:
            pass_attempted = random.choice([True, True, False])
        else:
            pass_attempted = random.choice([True, False])

    if not pass_attempted:
        game_state["offensive_state"] = "HCO"
        animator = Animator(game)
        animations = animator.capture_fast_break_animation(fb_roles, False, None)
        result = {
            "result_type": "DEFENSIVE_STOP",
            "ball_handler": ball_handler,
            "defender": primary_def,
            "text": "Fast Break! Rim Runner — holding up.",
            "possession_flips": False,
            "time_elapsed": 0,
            "animations": animations,
            "current_turn": "FAST_BREAK",
            "next_play_type": "HCO",
            "next_turn": "HCO",
            "offense_team_id": off_team.team_id,
            "roles": fb_roles,
            "fast_break": True,
            "fast_break_play": fb_play_key,
            "rim_runner_fb_open": fb_open,
            "rim_runner_correct_read": correct_read,
            # Outlet receiver (ball handler) chose not to pass to the Rim Runner.
            "rim_runner_no_lane_pass": True,
        }
        _apply_rr_decision_metadata(result, pass_attempted=False, fb_open=fb_open)
        _record_fast_break_stats(fb_roles, result, game)
        apply_fast_break_cg_time(result, shot_attempted=False)
        return result

    # Pass attempted
    if fb_open and rr:
        fb_roles["shooter"] = rr
        fb_roles["passer"] = ball_handler
        fb_roles["defender"] = primary_def
        fb_roles["defender_count"] = 1 if primary_def else 0

        roles = {
            "shooter": rr,
            "passer": ball_handler,
            "screener": None,
            "defender": primary_def,
            "shot_type": "attack",
            "is_fast_break": True,
            "motion_playcall": "Attack",
            "defender_count": fb_roles["defender_count"],
        }
        base_threshold = off_team.team_attributes["shot_threshold"]
        def_chemistry = int((def_team.team_attributes.get("team_chemistry") or 0))
        off_fight = int((off_team.team_attributes.get("fight") or 0) * 2)
        dc = fb_roles["defender_count"]
        if dc == 0:
            shot_threshold = 1
        elif dc >= 2:
            shot_threshold = base_threshold + 100 + def_chemistry - off_fight
        else:
            shot_threshold = base_threshold
        game_state["fast_break_shot_threshold_override"] = shot_threshold

        animator = Animator(game)
        fb_animations = animator.capture_fast_break_animation(fb_roles, False, None)
        if fb_roles.get("_bh_final_x") is not None and fb_roles.get("_bh_final_y") is not None:
            shot_spot = {"x": fb_roles["_bh_final_x"], "y": fb_roles["_bh_final_y"]}
            rr.coords = shot_spot
            roles["shot_spot"] = shot_spot

        rr_snap_roles = {**roles, "ball_handler": ball_handler}
        rr_snap = build_fast_break_pre_shot_snapshot(
            game, off_lineup, def_lineup, rr_snap_roles, "fb_rr_pre_shot"
        )
        turn_result = game.shot_manager.resolve_shot(roles)
        game_state.pop("fast_break_shot_threshold_override", None)
        attach_position_snapshots(turn_result, [rr_snap])

        turn_result["animations"] = fb_animations
        turn_result["roles"] = fb_roles
        turn_result["fast_break"] = True
        turn_result["fast_break_play"] = fb_play_key
        turn_result["text"] = "Fast Break! " + turn_result.get("text", "")
        _apply_rr_decision_metadata(turn_result, pass_attempted=True, fb_open=fb_open)

        if turn_result.get("result_type") == "MAKE":
            off_team.scouting_data["offense"]["Fast_Break_Success"] = (
                off_team.scouting_data["offense"].get("Fast_Break_Success", 0) + 1
            )
            from BackEnd.constants.fast_break_play_types import ensure_fast_break_plays

            ensure_fast_break_plays(off_team.scouting_data["offense"])[fb_play_key]["S"] += 1
        elif turn_result.get("result_type") == "MISS":
            def_team.scouting_data["defense"]["vs_Fast_Break"]["success"] = (
                def_team.scouting_data["defense"]["vs_Fast_Break"].get("success", 0) + 1
            )

        _record_fast_break_stats(fb_roles, turn_result, game)
        apply_fast_break_cg_time(turn_result, shot_attempted=True)
        return turn_result

    # fb_open False → intercept tiers
    if not primary_def:
        # No defender — treat as catch-and-shoot
        fb_roles["shooter"] = rr
        fb_roles["passer"] = ball_handler
        roles = {
            "shooter": rr,
            "passer": ball_handler,
            "screener": None,
            "defender": None,
            "shot_type": "attack",
            "is_fast_break": True,
            "motion_playcall": "Attack",
            "defender_count": 0,
        }
        game_state["fast_break_shot_threshold_override"] = 1
        animator = Animator(game)
        fb_animations = animator.capture_fast_break_animation(fb_roles, False, None)
        if fb_roles.get("_bh_final_x") is not None:
            rr.coords = {"x": fb_roles["_bh_final_x"], "y": fb_roles["_bh_final_y"]}
            roles["shot_spot"] = rr.coords
        rr_snap_roles = {**roles, "ball_handler": ball_handler}
        rr_snap = build_fast_break_pre_shot_snapshot(
            game, off_lineup, def_lineup, rr_snap_roles, "fb_rr_pre_shot"
        )
        turn_result = game.shot_manager.resolve_shot(roles)
        game_state.pop("fast_break_shot_threshold_override", None)
        attach_position_snapshots(turn_result, [rr_snap])
        turn_result["animations"] = fb_animations
        turn_result["roles"] = fb_roles
        turn_result["fast_break"] = True
        turn_result["fast_break_play"] = fb_play_key
        turn_result["text"] = "Fast Break! " + turn_result.get("text", "")
        _apply_rr_decision_metadata(turn_result, pass_attempted=True, fb_open=fb_open)
        _record_fast_break_stats(fb_roles, turn_result, game)
        apply_fast_break_cg_time(turn_result, shot_attempted=True)
        return turn_result

    da = primary_def.attributes
    intercept_score = (
        da.get("OD", 0) * 0.6 + da.get("AG", 0) * 0.2 + da.get("IQ", 0) * 0.2
    ) * random.randint(1, 6)

    tier_hi = 250 - fb_opp
    tier_mid = 200 - fb_opp

    if intercept_score > tier_hi:
        # Steal — possession to defense, HCO
        from BackEnd.engine.phase_resolution import resolve_turnover_logic

        game_state["offensive_state"] = "HCO"
        to_roles = {"ball_handler": ball_handler, "defender": primary_def}
        tr = resolve_turnover_logic(to_roles, game, turnover_type="STEAL", from_resolution_system=True)
        # Force HCO (no random FB after Rim Runner pick)
        game_state["offensive_state"] = "HCO"
        if tr.get("next_play_type") == "FAST_BREAK":
            tr["next_play_type"] = "HCO"
            tr["next_turn"] = "HCO"
        tr["text"] = "Fast Break! " + tr.get("text", "")
        tr["fast_break"] = True
        tr["fast_break_play"] = fb_play_key
        tr["roles"] = fb_roles
        tr["rim_runner_interception"] = True
        _apply_rr_decision_metadata(tr, pass_attempted=True, fb_open=fb_open)
        rr_anims = Animator(game).capture_fast_break_animation(fb_roles, False, None)
        tr["animations"] = rr_anims
        if rr_anims:
            apply_coords_from_animations_list(game, rr_anims)
        attach_position_snapshots(
            tr,
            [
                build_phase_post_stopper_snapshot(
                    game,
                    off_lineup,
                    def_lineup,
                    None,
                    fb_roles,
                    "FAST_BREAK",
                    "turnover",
                    "fb_rr_turnover_post_stopper",
                )
            ],
        )
        _record_fast_break_stats(fb_roles, tr, game)
        return tr

    if intercept_score > tier_mid:
        game_state["offensive_state"] = "HCO"
        bat_anims = Animator(game).capture_fast_break_animation(fb_roles, False, None)
        result = {
            "result_type": "DEAD BALL",
            "text": "Fast Break! Batted ball out of bounds!",
            "ball_handler": ball_handler,
            "possession_flips": False,
            "time_elapsed": random.randint(2, 5),
            "next_play_type": "SIDE_INBOUND",
            "next_turn": "SIDE_INBOUND",
            "offense_team_id": off_team.team_id,
            "current_turn": "FAST_BREAK",
            "fast_break": True,
            "fast_break_play": fb_play_key,
            "rim_runner_bat_oob": True,
            "roles": fb_roles,
            "animations": bat_anims,
        }
        _apply_rr_decision_metadata(result, pass_attempted=True, fb_open=fb_open)
        if bat_anims:
            apply_coords_from_animations_list(game, bat_anims)
        attach_position_snapshots(
            result,
            [
                build_phase_post_stopper_snapshot(
                    game,
                    off_lineup,
                    def_lineup,
                    None,
                    fb_roles,
                    "FAST_BREAK",
                    "turnover",
                    "fb_rr_bat_oob_post_stopper",
                )
            ],
        )
        _record_fast_break_stats(fb_roles, result, game)
        apply_fast_break_cg_time(result, shot_attempted=False)
        return result

    # Completion → shot
    fb_roles["shooter"] = rr
    fb_roles["passer"] = ball_handler
    fb_roles["defender"] = primary_def
    fb_roles["defender_count"] = 1
    roles = {
        "shooter": rr,
        "passer": ball_handler,
        "screener": None,
        "defender": primary_def,
        "shot_type": "attack",
        "is_fast_break": True,
        "motion_playcall": "Attack",
        "defender_count": 1,
    }
    base_threshold = off_team.team_attributes["shot_threshold"]
    def_chemistry = int((def_team.team_attributes.get("team_chemistry") or 0))
    off_fight = int((off_team.team_attributes.get("fight") or 0) * 2)
    game_state["fast_break_shot_threshold_override"] = base_threshold + def_chemistry - off_fight
    animator = Animator(game)
    fb_animations = animator.capture_fast_break_animation(fb_roles, False, None)
    if fb_roles.get("_bh_final_x") is not None:
        rr.coords = {"x": fb_roles["_bh_final_x"], "y": fb_roles["_bh_final_y"]}
        roles["shot_spot"] = rr.coords
    rr_snap_roles = {**roles, "ball_handler": ball_handler}
    rr_snap = build_fast_break_pre_shot_snapshot(
        game, off_lineup, def_lineup, rr_snap_roles, "fb_rr_pre_shot"
    )
    turn_result = game.shot_manager.resolve_shot(roles)
    game_state.pop("fast_break_shot_threshold_override", None)
    attach_position_snapshots(turn_result, [rr_snap])
    turn_result["animations"] = fb_animations
    turn_result["roles"] = fb_roles
    turn_result["fast_break"] = True
    turn_result["fast_break_play"] = fb_play_key
    turn_result["text"] = "Fast Break! " + turn_result.get("text", "")
    _apply_rr_decision_metadata(turn_result, pass_attempted=True, fb_open=fb_open)
    if turn_result.get("result_type") == "MAKE":
        off_team.scouting_data["offense"]["Fast_Break_Success"] = (
            off_team.scouting_data["offense"].get("Fast_Break_Success", 0) + 1
        )
        from BackEnd.constants.fast_break_play_types import ensure_fast_break_plays

        ensure_fast_break_plays(off_team.scouting_data["offense"])[fb_play_key]["S"] += 1
    elif turn_result.get("result_type") == "MISS":
        def_team.scouting_data["defense"]["vs_Fast_Break"]["success"] = (
            def_team.scouting_data["defense"]["vs_Fast_Break"].get("success", 0) + 1
        )
    _record_fast_break_stats(fb_roles, turn_result, game)
    apply_fast_break_cg_time(turn_result, shot_attempted=True)
    return turn_result
