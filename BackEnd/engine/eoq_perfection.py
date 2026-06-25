"""
End-of-quarter / end-of-game perfection helpers (EOQ_Perfection_Brief.md).

Run Out The Clock (Q4/OT) and FLSS (Forced Last Second Shot, all quarters).
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import (
    ACTIONS,
    FLSS_DEEP_KEY_X_HOME,
    FLSS_HEAVE_MAX_X_HOME,
    FLSS_NORMAL_SHOT_MIN_X_HOME,
    HCO_STRING_SPOTS,
    POSITION_LIST,
    is_inside_paint_grid,
)
from BackEnd.engine.phase_resolution import select_defender_closest_to_victim
from BackEnd.utils.shared import apply_scoring, get_away_player_coords, get_name_safe, get_player_position

logger = logging.getLogger(__name__)

RUN_OUT_OFFENSE_SPOTS = (
    "key",
    "upper midWing",
    "lower midWing",
    "upper wing",
    "lower wing",
    "upper midCorner",
    "lower midCorner",
    "upper corner",
    "lower corner",
    "topLane",
    "deep key",
    "deep upper wing",
    "deep lower wing",
    "deep upper baseline",
    "deep lower baseline",
)

RUN_OUT_OFFENSE_DEEP_SPOTS = (
    "deep key",
    "deep upper wing",
    "deep lower wing",
    "deep upper baseline",
    "deep lower baseline",
)

# Lane anchor spots for defense run-out positioning.
RUN_OUT_LANE_ANCHORS = ("key", "midLane", "topLane")


def _is_home_offense(game) -> bool:
    return game.offense_team.team_id == game.home_team.team_id


def _attacking_home_basket(is_home_offense: bool) -> bool:
    return bool(is_home_offense)


def classify_flss_zone(shooter_x: float, *, is_home_offense: bool) -> str:
    """Return 'normal' | 'penalty' | 'heave' for FLSS x-band logic."""
    x = float(shooter_x)
    if is_home_offense:
        if x >= FLSS_NORMAL_SHOT_MIN_X_HOME:
            return "normal"
        if x >= FLSS_DEEP_KEY_X_HOME:
            return "penalty"
        return "heave"
    normal_max = 100 - FLSS_NORMAL_SHOT_MIN_X_HOME
    deep_max = 100 - FLSS_DEEP_KEY_X_HOME
    if x <= normal_max:
        return "normal"
    if x <= deep_max:
        return "penalty"
    return "heave"


def flss_heave_sfx_eligible(shooter_x: float, *, is_home_offense: bool) -> bool:
    x = float(shooter_x)
    if is_home_offense:
        return x <= FLSS_HEAVE_MAX_X_HOME
    return x >= (100 - FLSS_HEAVE_MAX_X_HOME)


def _random_grid_near(anchor: Dict[str, float], radius: float = 5.0) -> Dict[str, float]:
    for _ in range(24):
        dx = random.uniform(-radius, radius)
        dy = random.uniform(-radius, radius)
        if math.hypot(dx, dy) <= radius:
            return {
                "x": round(max(0, min(100, anchor["x"] + dx)), 2),
                "y": round(max(0, min(50, anchor["y"] + dy)), 2),
            }
    return dict(anchor)


def _resolve_spot_collisions(
    assignments: Dict[str, Dict[str, float]],
) -> Dict[str, Dict[str, float]]:
    """No two players on the same spot; displaced player moves ~5 grid away."""
    by_coord: Dict[Tuple[float, float], List[str]] = {}
    for pos, coord in assignments.items():
        key = (round(coord["x"], 1), round(coord["y"], 1))
        by_coord.setdefault(key, []).append(pos)

    for positions in by_coord.values():
        if len(positions) <= 1:
            continue
        random.shuffle(positions)
        keep, *displaced = positions
        anchor = assignments[keep]
        for pos in displaced:
            assignments[pos] = _random_grid_near(anchor, radius=5.0)
    return assignments


def build_run_out_clock_destinations(game) -> Tuple[Dict[str, Dict], Dict[str, Dict], str]:
    """
    Assign run-out destinations for all ten players (display orientation).
    Returns (oDestinations, dDestinations, ball_handler_pos).
    """
    off_lineup = game.offense_team.lineup
    def_lineup = game.defense_team.lineup
    is_away = not _is_home_offense(game)

    bh = game.game_state.get("last_ball_handler")
    if not bh:
        bh = off_lineup.get("PG") or next((p for p in off_lineup.values() if p), None)
    bh_pos = get_player_position(off_lineup, bh) or "PG"

    o_assign: Dict[str, Dict[str, float]] = {}
    for pos in POSITION_LIST:
        player = off_lineup.get(pos)
        if not player:
            continue
        if pos == bh_pos:
            spot = random.choice(RUN_OUT_OFFENSE_DEEP_SPOTS)
        else:
            spot = random.choice(RUN_OUT_OFFENSE_SPOTS)
        coords = HCO_STRING_SPOTS.get(spot, {"x": 64, "y": 25})
        o_assign[pos] = get_away_player_coords(coords) if is_away else dict(coords)

    d_assign: Dict[str, Dict[str, float]] = {}
    for pos in POSITION_LIST:
        if not def_lineup.get(pos):
            continue
        if random.random() < 0.5:
            lane = HCO_STRING_SPOTS.get(random.choice(RUN_OUT_LANE_ANCHORS), {"x": 64, "y": 25})
            coord = {
                "x": random.uniform(lane["x"] - 2, lane["x"] + 2),
                "y": random.uniform(lane["y"] - 3, lane["y"] + 3),
            }
        else:
            lane = HCO_STRING_SPOTS.get(random.choice(RUN_OUT_LANE_ANCHORS), {"x": 64, "y": 25})
            coord = _random_grid_near(lane, radius=5.0)
        d_assign[pos] = get_away_player_coords(coord) if is_away else {
            "x": round(coord["x"], 2),
            "y": round(coord["y"], 2),
        }

    o_assign = _resolve_spot_collisions(o_assign)
    d_assign = _resolve_spot_collisions(d_assign)
    return o_assign, d_assign, bh_pos


def build_run_out_clock_result(game, time_remaining_sec: int) -> dict:
    o_dest, d_dest, bh_pos = build_run_out_clock_destinations(game)
    tr = int(time_remaining_sec)
    return {
        "result_type": "RUN_OUT_CLOCK",
        "current_turn": "HCO",
        "time_elapsed": tr,
        "offense_team_id": game.offense_team.team_id,
        "possession_flips": False,
        "next_play_type": None,
        "next_turn": None,
        "quarter_ends_after": True,
        "oDestinations": o_dest,
        "dDestinations": d_dest,
        "ball_handler_pos": bh_pos,
        "run_out_clock": True,
    }


def _flss_defender_coords(shooter_coords: Dict[str, float], *, is_home_offense: bool) -> Dict[str, float]:
    sx = float(shooter_coords.get("x", 50))
    sy = float(shooter_coords.get("y", 25))
    if is_home_offense:
        return {"x": round(min(99, sx + 3), 2), "y": sy}
    return {"x": round(max(1, sx - 3), 2), "y": sy}


def _resolve_flss_heave(shooter, shooter_x: float, *, is_home_offense: bool) -> Tuple[bool, int]:
    basket_x = 91 if is_home_offense else 9
    ch = float((getattr(shooter, "attributes", None) or {}).get("CH", 0))
    distance = abs(float(shooter_x) - basket_x)
    roll = random.randint(1, 100)
    divisor = random.randint(1, 6)
    shot_score = (ch - distance) / divisor
    made = shot_score > roll
    points = 3 if distance > 40 else 2
    return made, points


def resolve_flss_shot_logic(game, current_state: str = "HCO") -> dict:
    """
    Forced Last Second Shot: shoot from live ball-handler coords when Final Shot
    could not complete before the game clock expired.
    """
    from BackEnd.constants import POSITION_LIST
    from BackEnd.utils.position_snapshot_ledger import (
        attach_position_snapshots,
        build_skeleton_pre_resolve_shot_snapshot,
    )

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup
    def_lineup = def_team.lineup
    is_home_off = _is_home_offense(game)

    ball_handler = game_state.get("last_ball_handler")
    if not ball_handler:
        ball_handler = off_lineup.get("PG") or next((p for p in off_lineup.values() if p), None)
    if not ball_handler:
        return {
            "result_type": "MISS",
            "current_turn": current_state,
            "time_elapsed": 1,
            "text": "Clock expires with no shooter.",
            "quarter_ends_after": True,
            "flss": True,
        }

    shooter = ball_handler
    shooter_pos = get_player_position(off_lineup, shooter) or "PG"
    shooter_coords = getattr(shooter, "coords", None) or {"x": 50, "y": 25}
    sx = float(shooter_coords.get("x", 50))
    sy = float(shooter_coords.get("y", 25))
    shooter.coords = {"x": sx, "y": sy}
    zone = classify_flss_zone(sx, is_home_offense=is_home_off)
    home_basket = _attacking_home_basket(is_home_off)

    flss_vo = zone != "normal"
    heave_sfx = flss_heave_sfx_eligible(sx, is_home_offense=is_home_off)

    spot_label = game.turn_manager._coords_to_nearest_spot({"x": sx, "y": sy})
    step0 = {"timestamp": 0, "pos_actions": {}}
    step1 = {"timestamp": 300, "pos_actions": {}}
    for pos in POSITION_LIST:
        if pos == shooter_pos:
            step0["pos_actions"][pos] = {"action": ACTIONS["HANDLE"], "location": spot_label}
            step1["pos_actions"][pos] = {"action": ACTIONS["SHOOT"], "location": spot_label}
        else:
            step0["pos_actions"][pos] = {"action": "stand", "location": "key"}
            step1["pos_actions"][pos] = {"action": "stand", "location": "key"}

    defender = None
    if zone == "penalty" and def_lineup:
        defender = select_defender_closest_to_victim(shooter_coords, def_lineup, None)
        if defender:
            d_pos = get_player_position(def_lineup, defender)
            if d_pos:
                d_coords = _flss_defender_coords(shooter_coords, is_home_offense=is_home_off)
                defender.coords = dict(d_coords)

    if zone == "heave":
        made, points = _resolve_flss_heave(shooter, sx, is_home_offense=is_home_off)
        result_type = "MAKE" if made else "MISS"
        result: Dict[str, Any] = {
            "result_type": result_type,
            "current_turn": current_state,
            "time_elapsed": 1,
            "offense_team_id": off_team.team_id,
            "shooter_id": getattr(shooter, "player_id", None),
            "shot_type": "outside",
            "is_three": points == 3,
            "flss": True,
            "flss_zone": zone,
            "flss_vo": flss_vo,
            "flss_heave_sfx": heave_sfx,
            "quarter_ends_after": True,
            "next_play_type": None,
            "possession_flips": False,
            "skeleton": {"steps": [step0, step1]},
            "shooter_coords": {"x": sx, "y": sy},
        }
        if made:
            apply_scoring(
                game,
                off_team,
                shooter,
                points,
                ["FGM", "3PTM"] if points == 3 else ["FGM"],
            )
            result["text"] = f"{get_name_safe(shooter)} hits the desperation heave!"
        else:
            shooter.record_stat("FGA")
            if points == 3:
                shooter.record_stat("3PTA")
            result["ball_bounce_x"] = sx + (2 if is_home_off else -2)
            result["ball_bounce_y"] = sy
            result["text"] = f"{get_name_safe(shooter)} misses the desperation heave."
        strip_terminal_rebound_fields(result)
        return result

    # normal / penalty — standard shot pipeline
    if zone == "normal":
        inside = is_inside_paint_grid(sx, sy, home_basket=home_basket)
        shot_type = "inside" if inside else "outside"
    else:
        shot_type = "outside"

    roles = {
        "skeleton": {"steps": [step0, step1]},
        "steps": [step0, step1],
        "ball_handler": ball_handler,
        "shooter": shooter,
        "passer": None,
        "screener": None,
        "defender": defender,
        "shot_type": shot_type,
        "forced_shot": True,
        "flss": True,
        "flss_zone": zone,
        "flss_vo": flss_vo,
        "flss_heave_sfx": heave_sfx,
        "shooter_location": spot_label,
        "shot_spot": {"x": sx, "y": sy},
    }

    if zone == "penalty":
        chem = float(off_team.team_attributes.get("team_chemistry", 7))
        ch = float((getattr(shooter, "attributes", None) or {}).get("CH", 0))
        roles["flss_penalty"] = 100.0 - (chem + (ch / 5.0))

    game_state["final_turn"] = True
    try:
        sc_snap = build_skeleton_pre_resolve_shot_snapshot(
            game,
            off_lineup,
            def_lineup,
            roles.get("skeleton"),
            roles,
            current_state,
            "flss_pre_resolve_shot",
        )
        result = game.shot_manager.resolve_shot(roles)
        attach_position_snapshots(result, [sc_snap])
    finally:
        game_state.pop("final_turn", None)

    if zone == "penalty" and roles.get("flss_penalty"):
        # Penalty applied inside resolve_shot via roles flag — see shot_manager.
        pass

    result["flss"] = True
    result["flss_zone"] = zone
    result["flss_vo"] = flss_vo
    result["flss_heave_sfx"] = heave_sfx
    result["time_elapsed"] = 1
    result["quarter_ends_after"] = True
    result["next_play_type"] = None
    result["forced_shot"] = True
    result["forced_shot_reason"] = "FLSS"
    result["current_turn"] = current_state
    return result


def strip_terminal_rebound_fields(result: dict) -> None:
    """Remove rebound follow-up payload when the quarter ends on this shot."""
    for key in (
        "rebounderId",
        "rebound_type",
        "offense_rebounders",
        "defense_rebounders",
        "offense_getback",
        "defense_release",
        "offense_getback_coords",
        "defense_release_coords",
        "offense_rebounder_coords",
        "defense_rebounder_coords",
        "force_foul_after_dreb",
    ):
        result.pop(key, None)


def log_block_bounce_debug(turn_result: dict, *, context: str) -> None:
    """Structured log for debugging wrong-side block bounce coords."""
    if (turn_result.get("result_type") or "").upper() != "BLOCK":
        return
    logger.info(
        "[EOQ BLOCK BOUNCE DEBUG] context=%s blocker_id=%s ball_bounce_x=%s ball_bounce_y=%s "
        "block_spot=%s shooter_id=%s offense_team_id=%s",
        context,
        turn_result.get("blocker_id"),
        turn_result.get("ball_bounce_x"),
        turn_result.get("ball_bounce_y"),
        turn_result.get("block_spot"),
        turn_result.get("shooter_id"),
        turn_result.get("offense_team_id"),
    )
