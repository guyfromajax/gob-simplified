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
    calculate_outlet_pass_score,
    unpack_game_context,
    update_player_coords_from_animations,
)
from BackEnd.engine.phase_resolution import (
    _record_fast_break_stats,
    apply_energy_decay,
    apply_fast_break_cg_time,
    get_in_play_defenders,
)

logger = logging.getLogger(__name__)


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
    release_player = game_state.get("last_release_player")

    is_away_offense = off_team.team_id == game.away_team.team_id

    fb_roles: Dict[str, Any] = {
        "offense": [],
        "defense": [],
        "ball_handler": None,
        "outlet_passer": None,
        "outlet_receiver": None,
        "fast_break_play": fb_play_key,
        "rim_runner_sequence": True,
    }

    pg = off_lineup.get("PG")
    sg = off_lineup.get("SG")
    rr = resolve_rim_runner_player(off_lineup, game_state, off_team, rebounder, is_away_offense)

    rid = getattr(rebounder, "player_id", None) if rebounder else None
    pg_id = getattr(pg, "player_id", None) if pg else None
    sg_id = getattr(sg, "player_id", None) if sg else None
    rr_id = getattr(rr, "player_id", None) if rr else None

    # SG rebounds + PG is rim runner → SG dribbles to outlet spot (no pass to PG)
    sg_rebounds_pg_rr = bool(
        sg and rid == sg_id and rr_id == pg_id
    )

    outlet_defender = _pick_outlet_defender(def_lineup, rebounder) if rebounder else None

    # --- Outlet chain ---
    ball_handler: Any = None
    if sg_rebounds_pg_rr:
        ball_handler = sg
        fb_roles["outlet_passer"] = None
        # Treat as outlet-style receiver for FB_A stats (no pass; ball starts with SG)
        fb_roles["outlet_receiver"] = getattr(ball_handler, "player_id", None)
        fb_roles["outlet_score"] = None
        game_state["last_release_player"] = None
    elif rebounder and (rid == pg_id or rr_id == pg_id):
        # PG rebounded OR PG is rim runner → outlet to SG
        first = sg or pg
        ball_handler = first
        if rebounder != first:
            fb_roles["outlet_passer"] = rid
            fb_roles["outlet_receiver"] = getattr(first, "player_id", None)
            rc = getattr(rebounder, "coords", None) or {}
            fb_roles["outlet_passer_x"] = rc.get("x")
            fb_roles["outlet_passer_y"] = rc.get("y")
            fb_roles["outlet_score"] = calculate_outlet_pass_score(rebounder)
        game_state["last_release_player"] = None
    else:
        # Covert release receiver or fallback PG
        ball_handler = release_player or pg
        if rebounder and ball_handler and rebounder != ball_handler:
            fb_roles["outlet_passer"] = rid
            fb_roles["outlet_receiver"] = getattr(ball_handler, "player_id", None)
            rc = getattr(rebounder, "coords", None) or {}
            fb_roles["outlet_passer_x"] = rc.get("x")
            fb_roles["outlet_passer_y"] = rc.get("y")
            fb_roles["outlet_score"] = calculate_outlet_pass_score(rebounder)
        else:
            fb_roles["outlet_passer"] = None
            fb_roles["outlet_receiver"] = None
            fb_roles["outlet_score"] = None
        game_state["last_release_player"] = None

    if ball_handler is None:
        ball_handler = pg or next(p for p in off_lineup.values() if p)

    fb_roles["ball_handler"] = ball_handler
    fb_roles["ball_handler_id"] = getattr(ball_handler, "player_id", None)
    fb_roles["rim_runner_id"] = rr_id

    # Outlet coords for animation (reuse release coords if present)
    most_recent = _find_most_recent_shot_turn(game)
    bh_id = getattr(ball_handler, "player_id", None)
    bh_x, bh_y = None, None
    if most_recent and bh_id:
        rel = most_recent.get("defense_release_coords") or {}
        if bh_id in rel:
            bh_x = rel[bh_id].get("x")
            bh_y = rel[bh_id].get("y")
        if bh_x is None:
            gb = most_recent.get("offense_getback_coords") or {}
            if bh_id in gb:
                bh_x = gb[bh_id].get("x")
                bh_y = gb[bh_id].get("y")
    if bh_x is None:
        bh_x = _player_x(ball_handler)
        bh_y = float((getattr(ball_handler, "coords", {}) or {}).get("y", 25))

    fb_roles["ball_handler_outlet_x"] = bh_x
    fb_roles["ball_handler_outlet_y"] = bh_y
    fb_roles["ball_handler_move_x"] = 0
    fb_roles["ball_handler_move_y"] = 0
    fb_roles["is_away_offense"] = is_away_offense
    fb_roles["is_steal_entry"] = False
    fb_roles["getback_player_ids"] = (most_recent or {}).get("offense_getback") or []

    fb_roles["defense"] = []  # animator may need; fill minimally
    target_is_away = is_away_offense

    fb_roles["defense"] = get_in_play_defenders(ball_handler, def_lineup, target_is_away)

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

    fb_eff = int(off_team.team_attributes.get("fb_efficiency", 0) or 0)
    fb_opp = int(def_team.team_attributes.get("fb_opp_modifier", 0) or 0)
    fb_eff = max(-10, min(10, fb_eff))
    fb_opp = max(-10, min(10, fb_opp))

    outlet_ok = (
        outlet_offense_score + (3 * fb_eff)
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
            "fast_break_play": RIM_RUNNER,
            "rim_runner_outlet_failed": True,
        }
        _record_fast_break_stats(fb_roles, result, game)
        apply_fast_break_cg_time(result, shot_attempted=False)
        return result

    # --- Burst ---
    most_recent = _find_most_recent_shot_turn(game)
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
            "fast_break_play": RIM_RUNNER,
            "rim_runner_fb_open": fb_open,
            "rim_runner_correct_read": correct_read,
        }
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

        update_player_coords_from_animations(game, [])
        turn_result = game.shot_manager.resolve_shot(roles)
        game_state.pop("fast_break_shot_threshold_override", None)

        turn_result["animations"] = fb_animations
        turn_result["roles"] = fb_roles
        turn_result["fast_break"] = True
        turn_result["fast_break_play"] = RIM_RUNNER
        turn_result["text"] = "Fast Break! " + turn_result.get("text", "")

        if turn_result.get("result_type") == "MAKE":
            off_team.scouting_data["offense"]["Fast_Break_Success"] = (
                off_team.scouting_data["offense"].get("Fast_Break_Success", 0) + 1
            )
            from BackEnd.constants.fast_break_play_types import ensure_fast_break_plays

            ensure_fast_break_plays(off_team.scouting_data["offense"])[RIM_RUNNER]["S"] += 1
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
        update_player_coords_from_animations(game, [])
        turn_result = game.shot_manager.resolve_shot(roles)
        game_state.pop("fast_break_shot_threshold_override", None)
        turn_result["animations"] = fb_animations
        turn_result["roles"] = fb_roles
        turn_result["fast_break"] = True
        turn_result["fast_break_play"] = RIM_RUNNER
        turn_result["text"] = "Fast Break! " + turn_result.get("text", "")
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
        tr["fast_break_play"] = RIM_RUNNER
        tr["roles"] = fb_roles
        tr["rim_runner_interception"] = True
        _record_fast_break_stats(fb_roles, tr, game)
        return tr

    if intercept_score > tier_mid:
        game_state["offensive_state"] = "HCO"
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
            "fast_break_play": RIM_RUNNER,
            "rim_runner_bat_oob": True,
            "roles": fb_roles,
            "animations": Animator(game).capture_fast_break_animation(fb_roles, False, None),
        }
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
    update_player_coords_from_animations(game, [])
    turn_result = game.shot_manager.resolve_shot(roles)
    game_state.pop("fast_break_shot_threshold_override", None)
    turn_result["animations"] = fb_animations
    turn_result["roles"] = fb_roles
    turn_result["fast_break"] = True
    turn_result["fast_break_play"] = RIM_RUNNER
    turn_result["text"] = "Fast Break! " + turn_result.get("text", "")
    if turn_result.get("result_type") == "MAKE":
        off_team.scouting_data["offense"]["Fast_Break_Success"] = (
            off_team.scouting_data["offense"].get("Fast_Break_Success", 0) + 1
        )
        from BackEnd.constants.fast_break_play_types import ensure_fast_break_plays

        ensure_fast_break_plays(off_team.scouting_data["offense"])[RIM_RUNNER]["S"] += 1
    elif turn_result.get("result_type") == "MISS":
        def_team.scouting_data["defense"]["vs_Fast_Break"]["success"] = (
            def_team.scouting_data["defense"]["vs_Fast_Break"].get("success", 0) + 1
        )
    _record_fast_break_stats(fb_roles, turn_result, game)
    apply_fast_break_cg_time(turn_result, shot_attempted=True)
    return turn_result
