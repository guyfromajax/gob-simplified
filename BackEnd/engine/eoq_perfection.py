"""
End-of-quarter / end-of-game perfection helpers (EOQ_Perfection_Brief.md).

Run Out The Clock (Q4/OT) and FLSS (Forced Last Second Shot, all quarters).
"""

from __future__ import annotations

import logging
import math
from BackEnd.utils.sim_random import sim_rng as random
from dataclasses import dataclass
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


def resolve_flss_coach_sfx_stamp(*, flss_heave_sfx: bool) -> Dict[str, Any]:
    """Schema ``sfx_on_step_start`` payload for FLSS coach VO at the terminal shoot step."""
    from BackEnd.constants.flss_sfx import resolve_flss_coach_sfx_stamp as _stamp

    return _stamp(flss_heave_sfx=flss_heave_sfx)


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


FLSS_BASKET_X_HOME = 91.0
FLSS_BASKET_X_AWAY = 9.0
FLSS_SHOT_WINDOW_GAME_SECONDS = 1.0


def _flss_basket_x(*, is_home_offense: bool) -> float:
    return FLSS_BASKET_X_HOME if is_home_offense else FLSS_BASKET_X_AWAY


def _flss_toplane_x(*, is_home_offense: bool) -> float:
    home_x = float(HCO_STRING_SPOTS["topLane"]["x"])
    return home_x if is_home_offense else 100.0 - home_x


@dataclass(frozen=True)
class FlssDrivePlan:
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    drive_budget: float
    pull_up_jumper: bool
    shot_window_seconds: float


def compute_flss_drive_plan(
    shooter: Any,
    start_x: float,
    start_y: float,
    time_remaining: float,
    *,
    is_home_offense: bool,
) -> FlssDrivePlan:
    """Sprint toward the basket until ``time_remaining - 1`` game seconds, then shoot.

    If the BH would reach the rim before that window closes, stop at topLane x
    (when it lies on the drive path) for a pull-up outside jumper instead.
    """
    from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec

    sx = float(start_x)
    sy = float(start_y)
    drive_budget = max(0.0, float(time_remaining) - FLSS_SHOT_WINDOW_GAME_SECONDS)
    sprint_rate = float(_ag_grid_per_game_sec(shooter, "sprint"))
    direction = 1.0 if is_home_offense else -1.0
    basket_x = _flss_basket_x(is_home_offense=is_home_offense)
    toplane_x = _flss_toplane_x(is_home_offense=is_home_offense)

    dist_to_basket = abs(basket_x - sx)
    max_drive_dist = sprint_rate * drive_budget

    if is_home_offense:
        toplane_in_path = sx < toplane_x < basket_x
    else:
        toplane_in_path = basket_x < toplane_x < sx

    pull_up = bool(toplane_in_path and max_drive_dist >= dist_to_basket)
    if pull_up:
        end_x = toplane_x
    elif drive_budget <= 0.0:
        end_x = sx
    else:
        end_x = sx + direction * min(max_drive_dist, dist_to_basket)
        if is_home_offense:
            end_x = min(end_x, basket_x)
        else:
            end_x = max(end_x, basket_x)

    end_x = round(max(1.0, min(99.0, end_x)), 2)
    return FlssDrivePlan(
        start_x=sx,
        start_y=sy,
        end_x=end_x,
        end_y=sy,
        drive_budget=drive_budget,
        pull_up_jumper=pull_up,
        shot_window_seconds=FLSS_SHOT_WINDOW_GAME_SECONDS,
    )


def _compute_flss_drift_endpoint(
    start: Dict[str, float],
    drive_budget: float,
    player: Any,
    *,
    is_home_offense: bool,
) -> Dict[str, float]:
    """Offense teammates drift toward the attacking basket during post-DREB FLSS."""
    from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec

    sx = float(start.get("x", 50))
    sy = float(start.get("y", 25))
    direction = 1.0 if is_home_offense else -1.0
    basket_x = _flss_basket_x(is_home_offense=is_home_offense)
    rate = float(_ag_grid_per_game_sec(player, "cruise"))
    max_dist = rate * max(0.0, float(drive_budget))
    target_x = sx + direction * min(max_dist, abs(basket_x - sx) * 0.85)
    return {"x": round(max(1.0, min(99.0, target_x)), 2), "y": sy}


def build_flss_skeleton_steps(
    shooter_pos: str,
    *,
    spot_start: str,
    spot_end: str,
    start_coords: Dict[str, float],
    end_coords: Dict[str, float],
    drive_plan: FlssDrivePlan,
    off_lineup: Optional[Dict[str, Any]] = None,
    is_home_offense: Optional[bool] = None,
    from_dreb: bool = False,
) -> List[Dict[str, Any]]:
    """Two-step FLSS graph: optional sprint drive, then terminal shot."""
    steps: List[Dict[str, Any]] = []
    stand = {"action": "stand", "location": "key"}

    if drive_plan.drive_budget > 0.0:
        drive_action: Dict[str, Any] = {
            "action": ACTIONS["DRIVE"],
            "location": spot_end,
            "coords": dict(end_coords),
            "archetype": "sprint",
        }
        step0: Dict[str, Any] = {
            "timestamp": 0,
            "pos_actions": {pos: dict(stand) for pos in POSITION_LIST},
            "_flss_sprint_drive": True,
            "_flss_gate_driver_pos": shooter_pos,
            "_step_t_floor_game_seconds": drive_plan.drive_budget,
        }
        step0["pos_actions"][shooter_pos] = drive_action
        if drive_plan.pull_up_jumper:
            step0["_flss_pull_up"] = True
        if from_dreb and off_lineup and is_home_offense is not None:
            for pos, player in off_lineup.items():
                if pos == shooter_pos or not player:
                    continue
                player_start = getattr(player, "coords", None) or {"x": 50, "y": 25}
                drift_end = _compute_flss_drift_endpoint(
                    player_start,
                    drive_plan.drive_budget,
                    player,
                    is_home_offense=is_home_offense,
                )
                step0["pos_actions"][pos] = {
                    "action": ACTIONS["CUT"],
                    "location": spot_end,
                    "coords": dict(drift_end),
                    "archetype": "cruise",
                }
        steps.append(step0)

    shoot_action: Dict[str, Any] = {
        "action": ACTIONS["SHOOT"],
        "location": spot_end,
        "coords": dict(end_coords),
    }
    step_shoot: Dict[str, Any] = {
        "timestamp": 300 if steps else 0,
        "pos_actions": {pos: dict(stand) for pos in POSITION_LIST},
        "_step_t_floor_game_seconds": drive_plan.shot_window_seconds,
    }
    step_shoot["pos_actions"][shooter_pos] = shoot_action
    if drive_plan.pull_up_jumper:
        step_shoot["_flss_pull_up"] = True
    steps.append(step_shoot)
    return steps


def _flss_defender_coords(shooter_coords: Dict[str, float], *, is_home_offense: bool) -> Dict[str, float]:
    sx = float(shooter_coords.get("x", 50))
    sy = float(shooter_coords.get("y", 25))
    if is_home_offense:
        return {"x": round(min(99, sx + 3), 2), "y": sy}
    return {"x": round(max(1, sx - 3), 2), "y": sy}


def _resolve_flss_heave(
    shooter, shooter_x: float, *, is_home_offense: bool
) -> Tuple[bool, int, float, int]:
    basket_x = 91 if is_home_offense else 9
    ch = float((getattr(shooter, "attributes", None) or {}).get("CH", 0))
    distance = abs(float(shooter_x) - basket_x)
    roll = random.randint(1, 100)
    divisor = random.randint(1, 6)
    shot_score = (ch - distance) / divisor
    made = shot_score > roll
    points = 3 if distance > 40 else 2
    return made, points, shot_score, roll


def resolve_flss_shot_logic(game, current_state: str = "HCO") -> dict:
    """
    Forced Last Second Shot: shoot from live ball-handler coords when Final Shot
    could not complete before the game clock expired.
    """
    from BackEnd.constants import POSITION_LIST
    from BackEnd.engine.eoq_debug_log import log_eoq_step
    from BackEnd.utils.position_snapshot_ledger import (
        attach_position_snapshots,
        build_skeleton_pre_resolve_shot_snapshot,
    )

    log_eoq_step(game, "FLSS", "identify_ball_handler", "START", extra={"current_state": current_state})

    game_state = game.game_state
    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup
    def_lineup = def_team.lineup
    is_home_off = _is_home_offense(game)

    ball_handler = game_state.get("last_ball_handler")
    # last_ball_handler holds whoever LAST touched the ball. At an end-of-quarter
    # possession flip (rebound / steal / inbound → new offense) it can still be the
    # prior handler — now a DEFENDER. Using it as the FLSS shooter credits the made
    # basket's FGM/PTS to the wrong team's player while the points go to the current
    # offense, which is the player-PTS-vs-team-score ±2 mismatch. Only keep it if it
    # is actually on the current offense (get_player_position is falsy otherwise).
    if ball_handler is not None and not get_player_position(off_lineup, ball_handler):
        ball_handler = None
    if not ball_handler:
        ball_handler = off_lineup.get("PG") or next((p for p in off_lineup.values() if p), None)
    if not ball_handler:
        log_eoq_step(game, "FLSS", "identify_ball_handler", "END", extra={"error": "no_ball_handler"})
        return {
            "result_type": "MISS",
            "current_turn": current_state,
            "time_elapsed": 1,
            "text": "Clock expires with no shooter.",
            "quarter_ends_after": True,
            "flss": True,
            "suppress_final_shot_sfx": True,  # no stinger on the degenerate no-shooter FLSS
        }

    from_dreb = bool(game_state.pop("flss_from_dreb", False))
    if from_dreb:
        log_eoq_step(
            game,
            "FLSS",
            "post_dreb_start",
            "START",
            extra={"ball_handler_id": getattr(ball_handler, "player_id", None)},
        )

    shooter = ball_handler
    shooter_pos = get_player_position(off_lineup, shooter) or "PG"
    shooter_coords = getattr(shooter, "coords", None) or {"x": 50, "y": 25}
    sx = float(shooter_coords.get("x", 50))
    sy = float(shooter_coords.get("y", 25))
    time_remaining = float(game_state.get("time_remaining") or FLSS_SHOT_WINDOW_GAME_SECONDS)
    drive_plan = compute_flss_drive_plan(
        shooter,
        sx,
        sy,
        time_remaining,
        is_home_offense=is_home_off,
    )
    ex = drive_plan.end_x
    ey = drive_plan.end_y
    shooter_coords = {"x": ex, "y": ey}
    shooter.coords = dict(shooter_coords)
    zone = classify_flss_zone(ex, is_home_offense=is_home_off)
    home_basket = _attacking_home_basket(is_home_off)

    flss_vo = zone != "normal"  # normal zone: no announce/VO; penalty/heave: coach VO
    heave_sfx = flss_heave_sfx_eligible(ex, is_home_offense=is_home_off)

    log_eoq_step(
        game,
        "FLSS",
        "identify_ball_handler",
        "END",
        shooter=shooter,
        shooter_pos=shooter_pos,
        extra={
            "shooter_coords": {"x": sx, "y": sy},
            "drive_end_coords": {"x": ex, "y": ey},
            "drive_budget": drive_plan.drive_budget,
            "pull_up_jumper": drive_plan.pull_up_jumper,
            "flss_zone": zone,
            "flss_vo": flss_vo,
            "flss_heave_sfx": heave_sfx,
            "is_home_offense": is_home_off,
        },
    )

    spot_start = game.turn_manager._coords_to_nearest_spot({"x": sx, "y": sy})
    spot_end = game.turn_manager._coords_to_nearest_spot(shooter_coords)
    log_eoq_step(
        game,
        "FLSS",
        "build_skeleton",
        "START",
        shooter=shooter,
        shooter_pos=shooter_pos,
        extra={"spot_start": spot_start, "spot_end": spot_end},
    )
    skeleton_steps = build_flss_skeleton_steps(
        shooter_pos,
        spot_start=spot_start,
        spot_end=spot_end,
        start_coords={"x": sx, "y": sy},
        end_coords=shooter_coords,
        drive_plan=drive_plan,
        off_lineup=off_lineup if from_dreb else None,
        is_home_offense=is_home_off if from_dreb else None,
        from_dreb=from_dreb,
    )

    defender = None
    if zone == "penalty" and def_lineup:
        defender = select_defender_closest_to_victim(shooter_coords, def_lineup, None)
        if defender:
            d_pos = get_player_position(def_lineup, defender)
            if d_pos:
                d_coords = _flss_defender_coords(shooter_coords, is_home_offense=is_home_off)
                defender.coords = dict(d_coords)

    if zone == "heave":
        from BackEnd.constants.shot_variants import (
            roll_shot_variant_extras,
            select_flss_heave_miss_variant,
        )

        log_eoq_step(game, "FLSS", "heave_resolve", "START", shooter=shooter, shooter_pos=shooter_pos)
        made, points, shot_score, roll = _resolve_flss_heave(shooter, ex, is_home_offense=is_home_off)
        result_type = "MAKE" if made else "MISS"
        result: Dict[str, Any] = {
            "result_type": result_type,
            "current_turn": current_state,
            "time_elapsed": int(max(1, round(time_remaining))),
            "offense_team_id": off_team.team_id,
            "shooter_id": getattr(shooter, "player_id", None),
            "shot_type": "outside",
            "is_three": points == 3,
            "flss": True,
            "suppress_final_shot_sfx": True,  # FLSS heave VO plays instead of the stinger
            "flss_zone": zone,
            "flss_vo": flss_vo,
            "flss_heave_sfx": heave_sfx,
            "flss_pull_up": drive_plan.pull_up_jumper,
            "quarter_ends_after": True,
            "next_play_type": None,
            "possession_flips": False,
            "skeleton": {"steps": skeleton_steps},
            "shooter_coords": dict(shooter_coords),
        }
        if from_dreb:
            result["flss_from_dreb"] = True
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
            miss_margin = float(roll) - float(shot_score)
            shot_variant = select_flss_heave_miss_variant(miss_margin)
            shot_variant_extras = roll_shot_variant_extras(shot_variant, shooter_y=ey)
            result["shot_variant"] = shot_variant
            result["flss_heave_miss_margin"] = miss_margin
            result.update(shot_variant_extras)
            result["text"] = f"{get_name_safe(shooter)} misses the desperation heave."
            ensure_flss_miss_bounce_coords(
                game, result, shooter_coords=shooter_coords
            )
            stamp_flss_airball_animation_coords(game, result)
        strip_terminal_rebound_fields(result)
        log_eoq_step(
            game,
            "FLSS",
            "heave_resolve",
            "END",
            shooter=shooter,
            shooter_pos=shooter_pos,
            extra={
                "result_type": result_type,
                "points": points,
                "made": made,
                "shot_variant": result.get("shot_variant"),
                "flss_heave_miss_margin": result.get("flss_heave_miss_margin"),
            },
        )
        return result

    # normal / penalty — standard shot pipeline
    log_eoq_step(game, "FLSS", "build_skeleton", "END", extra={"zone": zone})
    log_eoq_step(game, "FLSS", "pipeline_resolve_shot", "START", shooter=shooter, shooter_pos=shooter_pos)
    if drive_plan.pull_up_jumper:
        shot_type = "outside"
    elif zone == "normal":
        inside = is_inside_paint_grid(ex, ey, home_basket=home_basket)
        shot_type = "inside" if inside else "outside"
    else:
        shot_type = "outside"

    roles = {
        "skeleton": {"steps": skeleton_steps},
        "steps": skeleton_steps,
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
        "flss_pull_up": drive_plan.pull_up_jumper,
        "shooter_location": spot_end,
        "shot_spot": dict(shooter_coords),
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
    # FLSS coach VO is schema-stamped on the terminal shoot step (sfx_on_step_start);
    # suppress the redundant Final Shot announcement stinger on all FLSS turns.
    result["suppress_final_shot_sfx"] = True
    result["flss_zone"] = zone
    result["flss_vo"] = flss_vo
    result["flss_heave_sfx"] = heave_sfx
    result["flss_pull_up"] = drive_plan.pull_up_jumper
    if from_dreb:
        result["flss_from_dreb"] = True
    from BackEnd.utils.eoq_clock_progression import mark_late_clock_eoq_turn

    mark_late_clock_eoq_turn(result)
    result["forced_shot"] = True
    result["forced_shot_reason"] = "FLSS"
    result["current_turn"] = current_state
    result["shooter_coords"] = dict(shooter_coords)
    ensure_flss_miss_bounce_coords(game, result, shooter_coords=shooter_coords)
    stamp_flss_airball_animation_coords(game, result)
    log_eoq_step(
        game,
        "FLSS",
        "pipeline_resolve_shot",
        "END",
        shooter=shooter,
        shooter_pos=shooter_pos,
        extra={
            "result_type": result.get("result_type"),
            "flss_penalty": roles.get("flss_penalty"),
            "defender_id": getattr(defender, "player_id", None) if defender else None,
        },
    )
    return result


def ensure_flss_miss_bounce_coords(
    game,
    result: Dict[str, Any],
    *,
    shooter_coords: Optional[Dict[str, float]] = None,
) -> None:
    """Stamp ``ball_bounce_x/y`` for FLSS misses that need a schema ``[bounce]`` step.

    Rim-action variants (rattle, BACK_OF_RIM, BANK_MISS) require backend bounce
    coords so ``_build_post_shot_sub_steps`` can append ``[bounce]`` after the
    variant sub-steps. AIRBALL uses the OOB continuation path — no bounce.
    """
    if not result.get("flss"):
        return
    if str(result.get("result_type") or "").upper() != "MISS":
        return
    if str(result.get("shot_variant") or "").upper() == "AIRBALL":
        return
    if result.get("ball_bounce_x") is not None and result.get("ball_bounce_y") is not None:
        return
    from BackEnd.utils.shared import calculate_bounce_spot

    coords = shooter_coords or result.get("shooter_coords")
    if isinstance(coords, dict) and coords.get("x") is not None:
        bounce_spot = calculate_bounce_spot(game, shooter_coords=coords)
    else:
        bounce_spot = calculate_bounce_spot(game)
    result["ball_bounce_x"] = bounce_spot["x"]
    result["ball_bounce_y"] = bounce_spot["y"]


def roll_flss_airball_animation_coords(
    *,
    away_offense: bool,
    rng=None,
) -> Dict[str, float]:
    """Roll FLSS-only AIRBALL flight-end landing + matching OOB resting coords.

    Landing is ``2–5`` grid x-units out from the attacking basket (toward
    midcourt) with y ``basket_y ± FLSS_AIRBALL_LAND_Y_VARIANCE``. OOB
    continuation uses the standard sideline x (``AIRBALL_OOB_*``) at the
    same y as the landing point.
    """
    rng = rng or random
    from BackEnd.constants import (
        AIRBALL_OOB_AWAY_COORDS,
        AIRBALL_OOB_HOME_COORDS,
        FLSS_AIRBALL_LAND_X_OFFSET_MAX,
        FLSS_AIRBALL_LAND_X_OFFSET_MIN,
        FLSS_AIRBALL_LAND_Y_VARIANCE,
    )

    basket_x = _flss_basket_x(is_home_offense=not away_offense)
    basket_y = 25.0
    x_offset = rng.randint(FLSS_AIRBALL_LAND_X_OFFSET_MIN, FLSS_AIRBALL_LAND_X_OFFSET_MAX)
    if away_offense:
        land_x = basket_x + float(x_offset)
        oob_x = float(AIRBALL_OOB_AWAY_COORDS["x"])
    else:
        land_x = basket_x - float(x_offset)
        oob_x = float(AIRBALL_OOB_HOME_COORDS["x"])
    land_y = float(
        max(
            0.0,
            min(
                50.0,
                basket_y + rng.randint(-FLSS_AIRBALL_LAND_Y_VARIANCE, FLSS_AIRBALL_LAND_Y_VARIANCE),
            ),
        )
    )
    return {
        "flss_airball_land_x": round(land_x, 2),
        "flss_airball_land_y": round(land_y, 2),
        "flss_airball_oob_x": round(oob_x, 2),
        "flss_airball_oob_y": round(land_y, 2),
    }


def stamp_flss_airball_animation_coords(
    game,
    result: Dict[str, Any],
) -> None:
    """Stamp rolled FLSS AIRBALL landing/OOB coords when missing (replay-safe)."""
    if not result.get("flss"):
        return
    if str(result.get("result_type") or "").upper() != "MISS":
        return
    if str(result.get("shot_variant") or "").upper() != "AIRBALL":
        return
    if result.get("flss_airball_land_x") is not None and result.get("flss_airball_land_y") is not None:
        return
    away_offense = game.offense_team.team_id == game.away_team.team_id
    result.update(roll_flss_airball_animation_coords(away_offense=away_offense))


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
