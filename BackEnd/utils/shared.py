import math
import random
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.utils.home_crowd import home_crowd_shot_threshold_delta_for_offense
from BackEnd.constants import (
    TURNOVER_CALC_DICT,
    POSITION_LIST,
    HCO_STRING_SPOTS,
    CHARGE_THRESHOLD,
    BLOCKING_FOUL_THRESHOLD,
    ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND,
    PASS_GRID_SPOTS_PER_GAME_SECOND,
    OPEN_FLOOR_GRID_PER_GAME_SECOND,
    CHALLENGED_OPEN_FLOOR_GRID_PER_GAME_SECOND,
    COMPRESSED_HCO_GRID_PER_GAME_SECOND,
    HCO_SHOT_GRID_PER_GAME_SECOND,
)


def format_height(value) -> str:
    """Convert total inches to a feet'inches" string.

    Accepts numbers or numeric strings; invalid or missing values yield
    an empty string.
    """
    if value in (None, ""):
        return ""
    try:
        inches = int(float(value))
    except (TypeError, ValueError):
        return ""
    feet, inches = divmod(inches, 12)
    return f"{feet}'{inches}\""


def format_player_display_name(jersey, first_name: str, last_name: str) -> str:
    """Full name with optional jersey prefix like '#32 Name'. Jersey 0 is valid."""
    name = f"{first_name or ''} {last_name or ''}".strip()
    if jersey is None or jersey == "":
        return name
    try:
        j = int(float(jersey))
    except (TypeError, ValueError):
        return name
    if not name:
        return f"#{j}"
    return f"#{j} {name}"


def weighted_random_from_dict(weight_dict: dict) -> str:
    if not weight_dict:
        raise ValueError("weighted_random_from_dict received an empty dict")

    total = sum(weight_dict.values())
    if total == 0:
        raise ValueError("All weights are zero in weighted_random_from_dict")

    rand_val = random.uniform(0, total)
    cumulative = 0
    for key, weight in weight_dict.items():
        cumulative += weight
        if rand_val <= cumulative:
            return key

    # fallback — should never hit if weights are valid
    return random.choice(list(weight_dict.keys()))


def apply_help_defense_if_triggered(game, playcall, is_three, defender, shot_score):
    """
    Determines if help defense is triggered and applies a penalty to the shot_score.
    Returns: updated_shot_score, help_defender (or None), help_defense_penalty
    """
    if is_three:
        return shot_score, None, 0

    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    base_help_chance_by_playcall = {
        "Attack": 0.70,
        "Inside": 0.20,
        "Set": 0.20,
        "Base": 0.30,
        "Freelance": 0.30,
        "Outside": 0.0
    }

    help_playcall = "Attack" if playcall == "Set" else playcall
    base_help_chance = base_help_chance_by_playcall.get(help_playcall, 0)

    # Adjust for aggression
    aggression = def_team.strategy_calls["aggression_call"]
    if aggression == "passive":
        base_help_chance += 0.20
    elif aggression == "aggressive":
        base_help_chance -= 0.20
    base_help_chance = max(0, min(1, base_help_chance))

    if random.random() >= base_help_chance:
        return shot_score, None, 0

    defender_pos = get_player_position(def_lineup, defender)

    possible_helpers = [pos for pos in def_lineup if pos != defender_pos]
    help_pos = random.choice(possible_helpers)
    help_defender = def_lineup[help_pos]
    help_attrs = help_defender.attributes

    if help_playcall == "Attack":
        help_score = (
            help_attrs["ID"] * 0.2 +
            help_attrs["OD"] * 0.2 +
            help_attrs["AG"] * 0.4 +
            help_attrs["IQ"] * 0.1 +
            help_attrs["CH"] * 0.1
        ) * random.randint(1, 6)
    else:
        help_score = (
            help_attrs["AG"] * 0.2 +
            help_attrs["IQ"] * 0.4 +
            help_attrs["CH"] * 0.4
        ) * random.randint(1, 6)

    penalty = help_score * 0.15
    return shot_score - penalty, help_defender, penalty

# 0–4 strategy sliders → P(initiate fast break) for DREB (fast_breaks) and steals (aggression).
SLIDER_TO_FAST_BREAK_PROB = {0: 0.0, 1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0}


def fast_break_probability_from_slider(level: int) -> float:
    """
    Map a 0–4 Game Plan slider to P(one-shot fast break initiation).
    Used for: DREB path (rebounding team's fast_breaks) and steal path (stealing team's aggression).
    """
    try:
        lv = int(level)
    except (TypeError, ValueError):
        lv = 2
    return SLIDER_TO_FAST_BREAK_PROB.get(lv, 0.5)

def get_time_elapsed(tempo_call):
    from BackEnd.constants import TEMPO_PARAMS
    if tempo_call not in ("slow", "normal", "fast"):
        tempo_call = "normal"
    p = TEMPO_PARAMS[tempo_call]
    return int(max(p["min"], min(p["max"], random.gauss(p["mean"], p["std"]))))


def clamp_turn_time_elapsed(seconds, cap=30):
    """Clamp turn time to [0, cap] and return int."""
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        value = 0
    return max(0, min(cap, value))


def round_fractional_game_seconds(fractional_seconds_list):
    """
    Sum fractional game seconds, then round: down if decimal <= .49, up if >= .50.
    Returns int seconds to add to the final non-rim-hold event.
    """
    if not fractional_seconds_list:
        return 0
    total = sum(float(x) for x in fractional_seconds_list)
    whole = int(total)
    decimal = total - whole
    if decimal <= 0.49:
        return whole
    return whole + 1


def calc_skeleton_time_elapsed(steps, resolution_step_index=None, cap=30):
    """
    Calculate skeleton turn time from per-step random seconds (1..5).
    """
    timing = calc_skeleton_step_timing_contract(
        steps,
        resolution_step_index=resolution_step_index,
        cap=cap,
        include_hco_step1_bringup=False,
    )
    return timing["time_elapsed"]


def _extract_step_location_coords(action_info):
    """Resolve a step action location payload to {x, y} when possible."""
    if not isinstance(action_info, dict):
        return None
    coords = action_info.get("coords")
    if isinstance(coords, dict) and "x" in coords and "y" in coords:
        return {"x": coords.get("x", 50), "y": coords.get("y", 25)}

    spot = action_info.get("location") or action_info.get("spot")
    if isinstance(spot, str):
        spot_coords = HCO_STRING_SPOTS.get(spot)
        if spot_coords:
            return {"x": spot_coords.get("x", 50), "y": spot_coords.get("y", 25)}
    return None


def _get_step_ball_handler_pos(step):
    """Best-effort ball handler position for a skeleton step."""
    pos_actions = (step or {}).get("pos_actions", {})
    for pos, action_info in pos_actions.items():
        action = (action_info or {}).get("action", "")
        if action in ["handle_ball", "receive", "shoot", "pass", "drive"]:
            return pos
    return None


def _calc_hco_bringup_overhead_seconds(steps, prev_offense_positions=None):
    """
    Pre-HCO bring-up time: Open Floor (OF) rate 24 grid/game sec (Real_Time_Clock_System.md).
    When prev_offense_positions is provided (e.g. BIP/SIP oDestinations): max over offense
    players' distance to step 0. When not provided (e.g. DREB→HCO): step0→step1 ball-handler.
    """
    if not steps:
        return 0
    step0 = steps[0]
    pos_actions0 = (step0.get("pos_actions") or {})

    if prev_offense_positions:
        max_seconds = 0.0
        for pos, prev_coords in prev_offense_positions.items():
            if not prev_coords or not isinstance(prev_coords, dict):
                continue
            action_info = pos_actions0.get(pos)
            if not action_info:
                continue
            step0_coords = _extract_step_location_coords(action_info)
            if not step0_coords:
                continue
            seg = calc_isotropic_segment_seconds(prev_coords, step0_coords, OPEN_FLOOR_GRID_PER_GAME_SECOND)
            if seg > max_seconds:
                max_seconds = seg
        return int(round(max_seconds)) if max_seconds > 0 else 0

    if len(steps) < 2:
        return 0
    step1 = steps[1]
    ball_handler_pos = _get_step_ball_handler_pos(step1) or _get_step_ball_handler_pos(step0)
    if not ball_handler_pos:
        return 0
    step0_action = pos_actions0.get(ball_handler_pos, {})
    step1_action = (step1.get("pos_actions", {}) or {}).get(ball_handler_pos, {})
    start = _extract_step_location_coords(step0_action)
    end = _extract_step_location_coords(step1_action)
    if not start or not end:
        return 0
    return int(round(calc_isotropic_segment_seconds(start, end, OPEN_FLOOR_GRID_PER_GAME_SECOND)))


# Minimum game seconds per step when movement cannot be computed (no blanket per-step default).
FALLBACK_STEP_SECONDS = 1


def calc_skeleton_step_timing_contract(
    steps,
    resolution_step_index=None,
    cap=30,
    include_hco_step1_bringup=False,
    prev_offense_positions=None,
    phase_type=None,
):
    """
    Build per-step clock timing per Real_Time_Clock_System.md movement rates.
    phase_type: 'HCO' | 'HCT' | 'FCP' | None. Drive→16, HCO non-drive→16, HCO shoot stationary→1,
    HCT/FCP non-drive→20, fallback→24. Pass in-air added per step. Bring-up uses OF 24 when enabled.
    """
    if not steps:
        one_step = FALLBACK_STEP_SECONDS
        return {
            "step_clock_seconds": [one_step],
            "time_elapsed": clamp_turn_time_elapsed(one_step, cap=cap),
            "resolution_step_index": 0,
            "executed_step_count": 1,
        }

    max_index = len(steps) - 1
    if resolution_step_index is None:
        resolution_step_index = max_index
    resolution_step_index = max(0, min(max_index, int(resolution_step_index)))

    executed_count = resolution_step_index + 1
    step_clock_seconds = []

    for i in range(executed_count):
        step_i = steps[i] if i < len(steps) else None
        if not step_i:
            step_clock_seconds.append(FALLBACK_STEP_SECONDS)
            continue

        mover_durations = []
        pos_actions_i = step_i.get("pos_actions") or {}
        step_has_shoot = any(
            (a or {}).get("action") == "shoot" for a in (pos_actions_i or {}).values()
        )

        if i > 0:
            prev_step = steps[i - 1]
            prev_actions = prev_step.get("pos_actions") or {}
            for pos, action_info in (pos_actions_i or {}).items():
                action_info = action_info or {}
                action = action_info.get("action", "")
                end_coords = _extract_step_location_coords(action_info)
                if not end_coords:
                    continue
                prev_info = prev_actions.get(pos)
                start_coords = _extract_step_location_coords(prev_info) if prev_info else None
                if not start_coords:
                    continue
                dx = abs((end_coords.get("x", 0) or 0) - (start_coords.get("x", 0) or 0))
                dy = abs((end_coords.get("y", 0) or 0) - (start_coords.get("y", 0) or 0))
                has_movement = (dx * dx + dy * dy) > 0

                if action == "drive":
                    sec = calc_drive_segment_seconds(start_coords, end_coords)
                    mover_durations.append(sec)
                elif has_movement:
                    if phase_type == "HCO":
                        rate = (
                            HCO_SHOT_GRID_PER_GAME_SECOND
                            if step_has_shoot
                            else COMPRESSED_HCO_GRID_PER_GAME_SECOND
                        )
                        sec = calc_isotropic_segment_seconds(start_coords, end_coords, rate)
                    elif phase_type in ("HCT", "FCP"):
                        sec = calc_isotropic_segment_seconds(
                            start_coords, end_coords, CHALLENGED_OPEN_FLOOR_GRID_PER_GAME_SECOND
                        )
                    else:
                        sec = calc_isotropic_segment_seconds(
                            start_coords, end_coords, OPEN_FLOOR_GRID_PER_GAME_SECOND
                        )
                    if sec > 0:
                        mover_durations.append(sec)

        step_sec = max(mover_durations) if mover_durations else 0
        if step_sec == 0 and phase_type == "HCO" and step_has_shoot:
            step_sec = 1
        step_sec = max(FALLBACK_STEP_SECONDS, round(step_sec)) if step_sec else FALLBACK_STEP_SECONDS

        # Pass in-air time for this step
        pos_actions_i = step_i.get("pos_actions") or {}
        for ev in step_i.get("events") or []:
            if (ev or {}).get("type") != "pass":
                continue
            from_pos = (ev or {}).get("from")
            to_pos = (ev or {}).get("to")
            if not from_pos or not to_pos:
                continue
            passer_info = pos_actions_i.get(from_pos)
            receiver_info = pos_actions_i.get(to_pos)
            passer_coords = _extract_step_location_coords(passer_info) if passer_info else None
            receiver_coords = _extract_step_location_coords(receiver_info) if receiver_info else None
            if passer_coords and receiver_coords:
                step_sec += round(calc_pass_segment_seconds(passer_coords, receiver_coords))

        step_clock_seconds.append(int(step_sec))

    if include_hco_step1_bringup and len(step_clock_seconds) > 0:
        step_clock_seconds[0] += _calc_hco_bringup_overhead_seconds(steps, prev_offense_positions)

    total = sum(step_clock_seconds)
    if total > cap:
        overflow = total - cap
        for idx in range(len(step_clock_seconds) - 1, -1, -1):
            if overflow <= 0:
                break
            reducible = max(0, step_clock_seconds[idx] - FALLBACK_STEP_SECONDS)
            if reducible <= 0:
                continue
            reduce_by = min(reducible, overflow)
            step_clock_seconds[idx] -= reduce_by
            overflow -= reduce_by

    final_total = clamp_turn_time_elapsed(sum(step_clock_seconds), cap=cap)
    return {
        "step_clock_seconds": step_clock_seconds,
        "time_elapsed": final_total,
        "resolution_step_index": resolution_step_index,
        "executed_step_count": len(step_clock_seconds),
    }


def calc_isotropic_segment_seconds(start, end, rate):
    """
    Segment duration using isotropic rate: sqrt(dx^2 + dy^2) / rate.
    Used for OF (20), COF (16), Drive (12), Compressed HCO (10), HCO shot (10), fallback (20).
    """
    if not start or not end or not rate:
        return 0.0
    dx = abs((end.get("x", 0) or 0) - (start.get("x", 0) or 0))
    dy = abs((end.get("y", 0) or 0) - (start.get("y", 0) or 0))
    return math.sqrt(dx * dx + dy * dy) / float(rate)


def calc_cg_segment_seconds(start, end):
    """
    Legacy anisotropic CG; prefer calc_isotropic_segment_seconds with explicit rate where applicable.
    """
    if not start or not end:
        return 0.0
    dx = abs((end.get("x", 0) or 0) - (start.get("x", 0) or 0))
    dy = abs((end.get("y", 0) or 0) - (start.get("y", 0) or 0))
    return math.sqrt((dx / 20.0) ** 2 + (dy / 10.0) ** 2)


def calc_drive_segment_seconds(start, end):
    """
    Attack drive to basket: 1 game second per ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND
    grid spots (Euclidean distance). Used for motion HCO drive steps.
    """
    if not start or not end:
        return 0.0
    dx = abs((end.get("x", 0) or 0) - (start.get("x", 0) or 0))
    dy = abs((end.get("y", 0) or 0) - (start.get("y", 0) or 0))
    grid_dist = math.sqrt(dx * dx + dy * dy)
    return grid_dist / float(ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND)


def calc_pass_segment_seconds(passer_coords, receiver_coords):
    """
    Ball in air (pass): 1 game second per PASS_GRID_SPOTS_PER_GAME_SECOND grid spots
    (Euclidean). Used for HCO steps that contain a pass event.
    """
    if not passer_coords or not receiver_coords:
        return 0.0
    dx = abs((receiver_coords.get("x", 0) or 0) - (passer_coords.get("x", 0) or 0))
    dy = abs((receiver_coords.get("y", 0) or 0) - (passer_coords.get("y", 0) or 0))
    grid_dist = math.sqrt(dx * dx + dy * dy)
    return grid_dist / float(PASS_GRID_SPOTS_PER_GAME_SECOND)


def calc_cg_time_elapsed_from_movement_points(points, cap=30):
    """
    Round-at-end CG time from ordered movement points.
    """
    if not points or len(points) < 2:
        return 0
    total = 0.0
    for idx in range(1, len(points)):
        total += calc_cg_segment_seconds(points[idx - 1], points[idx])
    return clamp_turn_time_elapsed(round(total), cap=cap)

def oreb_shot_attempt(player_attrs):
    """
    Calculate shot score for OREB putback attempts.
    
    Uses a simplified formula focused on finishing ability:
    - SC (Shooting Close) * 0.5
    - ST (Strength) * 0.3
    - CH (Clutch) * 0.2
    
    Args:
        player_attrs: Player attributes dictionary
        
    Returns:
        float: Shot score for putback attempt
    """
    return (
        player_attrs["SC"] * 0.5 +
        player_attrs["ST"] * 0.3 +
        player_attrs["CH"] * 0.2
    ) * random.randint(1, 6)


def _oreb_putback_distance(a_coords, b_coords):
    ax = float((a_coords or {}).get("x", 50))
    ay = float((a_coords or {}).get("y", 25))
    bx = float((b_coords or {}).get("x", 50))
    by = float((b_coords or {}).get("y", 25))
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def _oreb_defender_is_at_least_as_close_to_basket(defender_x, shooter_x, basket_x):
    if basket_x >= 50:
        return defender_x >= shooter_x
    return defender_x <= shooter_x


def _resolve_oreb_putback_defender(game, rebounder, def_lineup, basket_x):
    """
    Resolve the shot defender for an OREB putback attempt.

    Rules:
    0. Only defenders within 10 Euclidean distance of the shooter are initially eligible.
    1. Among those, defenders at least as close to the basket on the x-axis as the shooter
       are immediate contest candidates.
    2. If multiple immediate contest candidates exist, choose the one closest to the shooter;
       ties are broken randomly.
    3. If none qualify on x-axis, pick the closest initially eligible defender and run an IQ
       read. On success, move that defender one x-grid closer to the basket than the shooter
       and within +/-1 y of the shooter. On failure, the putback is uncontested.
    """
    shooter_coords = getattr(rebounder, "coords", None) or {"x": 50, "y": 25}
    shooter_x = float(shooter_coords.get("x", 50))
    shooter_y = float(shooter_coords.get("y", 25))

    eligible = []
    for defender in (def_lineup or {}).values():
        if defender is None:
            continue
        defender_coords = getattr(defender, "coords", None) or {"x": 50, "y": 25}
        distance = _oreb_putback_distance(shooter_coords, defender_coords)
        if distance <= 10:
            eligible.append((defender, defender_coords, distance))

    if not eligible:
        return None, False

    immediate = []
    for defender, defender_coords, distance in eligible:
        defender_x = float(defender_coords.get("x", 50))
        if _oreb_defender_is_at_least_as_close_to_basket(defender_x, shooter_x, basket_x):
            immediate.append((defender, defender_coords, distance))

    if immediate:
        min_distance = min(distance for _, _, distance in immediate)
        tied = [item for item in immediate if abs(item[2] - min_distance) < 1e-9]
        chosen, _, _ = random.choice(tied)
        return chosen, True

    min_distance = min(distance for _, _, distance in eligible)
    tied = [item for item in eligible if abs(item[2] - min_distance) < 1e-9]
    chosen, _, _ = random.choice(tied)

    iq_roll = random.randint(1, 100)
    if iq_roll <= chosen.attributes.get("IQ", 0):
        new_x = shooter_x + 1 if basket_x >= 50 else shooter_x - 1
        new_y = shooter_y + random.randint(-1, 1)
        chosen.coords = {
            "x": max(0, min(100, new_x)),
            "y": max(0, min(50, new_y)),
        }
        return chosen, True

    return None, False


def resolve_over_the_back_foul(game, rebounder, rebound_team, opposing_lineup):
    """
    Evaluate over-the-back foul eligibility for a rebound battle.

    Rules:
    - Find the nearest opposing player to the rebounder.
    - If that opponent is farther than 4 Euclidean distance away, no OTB foul is in play.
    - Otherwise determine whether an offensive or defensive OTB foul is in play using
      discipline-based thresholds, then an IQ gate, then a final 1-in-2 foul call.

    Returns:
        dict | None with:
          foul_team: "OFFENSE" | "DEFENSE"
          foul_player: Player
          victim: Player
          proximity: float
    """
    if rebounder is None or rebound_team is None or not opposing_lineup:
        return None

    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    rebounder_coords = getattr(rebounder, "coords", None) or {"x": 50, "y": 25}

    nearest_opponent = None
    nearest_distance = float("inf")
    for player in (opposing_lineup or {}).values():
        if player is None:
            continue
        distance = _oreb_putback_distance(rebounder_coords, getattr(player, "coords", None) or {"x": 50, "y": 25})
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_opponent = player

    if nearest_opponent is None or nearest_distance > 4:
        return None

    offense_candidate = rebounder if rebound_team == off_team else nearest_opponent
    defense_candidate = rebounder if rebound_team == def_team else nearest_opponent

    offense_threshold = 90 + off_team.team_attributes.get("discipline", 0)
    defense_threshold = 10 - def_team.team_attributes.get("discipline", 0)
    otb_roll = random.randint(1, 100)

    if otb_roll > offense_threshold:
        foul_team = "OFFENSE"
        foul_player = offense_candidate
        victim = defense_candidate
    elif otb_roll < defense_threshold:
        foul_team = "DEFENSE"
        foul_player = defense_candidate
        victim = offense_candidate
    else:
        return None

    if foul_player is None or victim is None:
        return None

    second_roll = random.randint(1, 100)
    if second_roll <= foul_player.attributes.get("IQ", 0):
        return None

    final_roll = random.randint(1, 2)
    if final_roll != 1:
        return None

    return {
        "foul_team": foul_team,
        "foul_player": foul_player,
        "victim": victim,
        "proximity": nearest_distance,
    }


def resolve_offensive_rebound(game, rebounder):
    """Resolve an offensive rebound by choosing a putback or a kick-out.

    Returns an event dictionary describing the outcome.
    """
    from BackEnd.utils.position_snapshot_ledger import (
        build_oreb_kickout_snapshot,
        build_oreb_putback_attempt_snapshot,
    )

    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    # If no offensive rebounder is available, treat as a defensive rebound.
    if rebounder is None:
        logging.warning("resolve_offensive_rebound called with no rebounder; treating as defensive rebound")
        return {
            "event_type": "DEFENSIVE_REBOUND",
            "rebounderId": None,
            "timeElapsed": 0,
            "possession_flips": True,
        }

    otb = resolve_over_the_back_foul(game, rebounder, off_team, def_lineup)
    if otb:
        return {
            "event_type": "OTB_FOUL",
            "foul_team": otb["foul_team"],
            "foul_player_id": getattr(otb["foul_player"], "player_id", None),
            "victim_id": getattr(otb["victim"], "player_id", None),
            "timeElapsed": random.randint(1, 5),
            "position_snapshots": [],
        }

    if random.random() < 0.90:  # 90% putback attempt, 10% kickout
        oreb_putback_snap = build_oreb_putback_attempt_snapshot(game, off_lineup, def_lineup)
        attrs = rebounder.attributes
        time_elapsed = random.randint(1, 5)

        is_away_offense = off_team.team_id == game.away_team.team_id
        basket_x = 9 if is_away_offense else 91
        defender, has_shot_defender = _resolve_oreb_putback_defender(
            game,
            rebounder,
            def_lineup,
            basket_x,
        )
        shooter_coords = getattr(rebounder, "coords", None) or {"x": 50, "y": 25}
        shooter_x = float(shooter_coords.get("x", 50))
        shooter_y = float(shooter_coords.get("y", 25))
        defender_coords = getattr(defender, "coords", None) or {}
        all_defenders = []
        nearest_defender = None
        nearest_distance = None
        nearest_dx = None
        nearest_dy = None
        for pos, candidate in (def_lineup or {}).items():
            if candidate is None:
                continue
            candidate_coords = getattr(candidate, "coords", None) or {"x": 50, "y": 25}
            candidate_x = float(candidate_coords.get("x", 50))
            candidate_y = float(candidate_coords.get("y", 25))
            all_defenders.append(f"{pos}:{get_name_safe(candidate)}=({candidate_x:.1f},{candidate_y:.1f})")
            dx = abs(candidate_x - shooter_x)
            dy = abs(candidate_y - shooter_y)
            distance = ((candidate_x - shooter_x) ** 2 + (candidate_y - shooter_y) ** 2) ** 0.5
            if nearest_distance is None or distance < nearest_distance:
                nearest_defender = candidate
                nearest_distance = distance
                nearest_dx = dx
                nearest_dy = dy

        d_foul = False
        foul_player = None
        made = False
        contested = bool(has_shot_defender and defender is not None)
        logging.warning(
            "🎯 [SHOT_COORD_DEBUG] turn_type=%s shot_type=oreb_putback shooter_xy=(%.1f,%.1f) shooter_coord_source=rebounder.coords has_contest=%s roles_defender=%s roles_defender_xy=(%.1f,%.1f) roles_second_defender=%s roles_second_defender_xy=(%.1f,%.1f) nearest_defender=%s nearest_distance=%.2f nearest_dx=%.2f nearest_dy=%.2f all_defenders=%s",
            game.game_state.get("offensive_state"),
            shooter_x,
            shooter_y,
            contested,
            get_name_safe(defender) if defender else "NONE",
            float(defender_coords.get("x", 50)) if defender else -1.0,
            float(defender_coords.get("y", 25)) if defender else -1.0,
            "NONE",
            -1.0,
            -1.0,
            get_name_safe(nearest_defender) if nearest_defender else "NONE",
            float(nearest_distance) if nearest_distance is not None else -1.0,
            float(nearest_dx) if nearest_dx is not None else -1.0,
            float(nearest_dy) if nearest_dy is not None else -1.0,
            "; ".join(all_defenders),
        )

        if contested:
            from BackEnd.models.shot_manager import ShotManager

            shot_manager = ShotManager(game)
            shot_score, _, d_foul, foul_player = shot_manager.calculate_shot_score(
                rebounder,
                None,
                None,
                defender,
                "inside",
                game_state.get("defense_call", "Man"),
                False,
                True,
                None,
                "oreb_putback",
                apply_defense=True,
            )
            shot_threshold = off_team.team_attributes["shot_threshold"]
            shot_threshold += home_crowd_shot_threshold_delta_for_offense(off_team, game)
            made = shot_score >= shot_threshold
        else:
            made = random.randint(1, 100) < 100

        if not contested:
            game.game_state["no_defender_shots"] = int(game.game_state.get("no_defender_shots", 0) or 0) + 1
            logging.warning(
                "🟢 [NO_DEFENDER_SHOTS INCREMENT] shot_type=oreb_putback current_turn=%s shooter_xy=(%.1f, %.1f) nearest_defender=%s nearest_distance=%.2f nearest_dx=%.2f nearest_dy=%.2f game_id=%s no_defender_shots=%s",
                game.game_state.get("offensive_state"),
                shooter_x,
                shooter_y,
                get_name_safe(nearest_defender) if nearest_defender else "NONE",
                float(nearest_distance) if nearest_distance is not None else -1.0,
                float(nearest_dx) if nearest_dx is not None else -1.0,
                float(nearest_dy) if nearest_dy is not None else -1.0,
                getattr(game, "game_id", None),
                game.game_state["no_defender_shots"],
            )
        rebounder.record_stat("FGA")

        event = {
            "event_type": "PUTBACK_ATTEMPT",
            "shooterId": getattr(rebounder, "player_id", None),
            "defenderId": getattr(defender, "player_id", None) if defender else None,
            "timeElapsed": time_elapsed,
            "result": "MAKE" if made else "MISS",
            "possession_flips": False,
            "position_snapshots": [oreb_putback_snap],
            "contested": contested,
        }

        if made:
            apply_scoring(game, off_team, rebounder, 2, ["FGM"])
            # Putbacks are always from the paint
            rebounder.record_stat("PIP", amount=2)
            event["points"] = 2
            event["possession_flips"] = True
            if d_foul and foul_player:
                from BackEnd.engine.phase_resolution import check_and_handle_foul_out

                foul_player.record_stat("F")
                def_team.team_fouls += 1
                game.game_state["foul_team"] = "DEFENSE"
                game.game_state["shooter"] = rebounder
                game.game_state["offensive_state"] = "FREE_THROW"
                game.game_state["free_throws"] = 1
                game.game_state["free_throws_remaining"] = 1
                game.game_state["one_and_one"] = False
                foul_out_info = check_and_handle_foul_out(foul_player, game.game_state, def_team)

                event["possession_flips"] = False
                event["foul_player_id"] = getattr(foul_player, "player_id", None)
                event["foul_team"] = "DEFENSE"
                event["next_play_type"] = "FREE_THROW"
                event["free_throws_remaining"] = 1
                event["has_and_one"] = True
                if foul_out_info.get("fouled_out"):
                    event["fouled_out"] = True
                    event["foul_out_player"] = {
                        "player_id": foul_out_info["foul_player_id"],
                        "name": foul_out_info["foul_player_name"],
                        "photo": foul_out_info["foul_player_photo"],
                        "team": foul_out_info["foul_player_team"],
                    }
                    event["foul_count"] = foul_out_info["foul_count"]
        else:
            if d_foul and foul_player:
                from BackEnd.engine.phase_resolution import check_and_handle_foul_out

                foul_player.record_stat("F")
                def_team.team_fouls += 1
                game.game_state["foul_team"] = "DEFENSE"
                game.game_state["shooter"] = rebounder
                game.game_state["offensive_state"] = "FREE_THROW"
                game.game_state["free_throws"] = 2
                game.game_state["free_throws_remaining"] = 2
                game.game_state["one_and_one"] = False
                foul_out_info = check_and_handle_foul_out(foul_player, game.game_state, def_team)

                event["foul_player_id"] = getattr(foul_player, "player_id", None)
                event["foul_team"] = "DEFENSE"
                event["next_play_type"] = "FREE_THROW"
                event["free_throws_remaining"] = 2
                if foul_out_info.get("fouled_out"):
                    event["fouled_out"] = True
                    event["foul_out_player"] = {
                        "player_id": foul_out_info["foul_player_id"],
                        "name": foul_out_info["foul_player_name"],
                        "photo": foul_out_info["foul_player_photo"],
                        "team": foul_out_info["foul_player_team"],
                    }
                    event["foul_count"] = foul_out_info["foul_count"]
                return event

            if contested and defender:
                defender.record_stat("DEF_S")

            # Unified geography-based rebound system for putback misses
            # Putback happens at the same basket where the original shot was taken
            bounce_spot = calculate_bounce_spot(game, basket_x=basket_x, basket_y=25)
            
            # Penalize the rebounder who attempted the putback (20% distance penalty) but don't exclude
            rebounder_id = getattr(rebounder, "player_id", None)
            exclude_player_ids = set()  # Don't exclude putback player anymore
            penalize_player_ids = {rebounder_id} if rebounder_id else set()  # Penalize putback player by 20% distance
            
            new_rebounder, new_team, new_stat = determine_rebounder(game, bounce_spot, exclude_player_ids, penalize_player_ids)
            
            # Get rebounder ID (support both Player and dict for robustness)
            new_rebounder_id = getattr(new_rebounder, "player_id", None)
            if new_rebounder_id is None and isinstance(new_rebounder, dict):
                new_rebounder_id = new_rebounder.get("player_id") or new_rebounder.get("playerId")
            pid_str = str(new_rebounder_id) if new_rebounder_id is not None else None

            # Record stat on canonical roster player so deltas and persistence use the same instance
            canonical = new_team.get_player_by_id(pid_str) if pid_str else None
            if canonical is not None:
                canonical.record_stat(new_stat)
                logging.warning(f"🏀 Putback Miss Rebound: {get_name_safe(canonical)} (ID: {pid_str}) credited with {new_stat} on canonical roster player")
            else:
                new_rebounder.record_stat(new_stat)
                logging.warning(f"🏀 Putback Miss Rebound: {get_name_safe(new_rebounder)} (ID: {pid_str}) credited with {new_stat} on lineup player (canonical lookup failed)")
            # DON'T flip possession here - let turn_manager handle it after the rebound
            # This ensures the shot animates to the correct basket before possession flips
            event["possession_flips"] = False

            # Use calculated bounce spot for frontend animation
            ballSpot = {"x": bounce_spot["x"], "y": bounce_spot["y"]}

            # Add rebound information for frontend animation (use normalized ID)
            event["rebound"] = {
                "rebounderId": pid_str,
                "rebounder_player_id": pid_str,
                "rebound_type": new_stat,
                "ballSpot": ballSpot
            }

        return event

    # Kick out to PG
    pg = off_team.lineup.get("PG")
    duration = random.randint(1, 5)
    from_coords = getattr(rebounder, "coords", {"x": 25, "y": 50})
    to_coords = getattr(pg, "coords", {"x": 25, "y": 50}) if pg else {"x": 25, "y": 50}

    oreb_kick_snap = build_oreb_kickout_snapshot(game, off_lineup, def_lineup)

    return {
        "event_type": "KICKOUT_RESET",
        "rebounderId": getattr(rebounder, "player_id", None),
        "pgId": getattr(pg, "player_id", None) if pg else None,
        "pass": {
            "fromCoords": from_coords,
            "toCoords": to_coords,
            "duration": duration,
        },
        "timeElapsed": duration,
        "position_snapshots": [oreb_kick_snap],
    }

def calculate_screen_score(screen_attrs):
    """
    Calculates screen effectiveness score using weighted attributes:
    ST (0.5), AG (0.2), IQ (0.2), CH (0.1) scaled by RNG 1–6
    """
    base_score = (
        screen_attrs["ST"] * 0.5 +
        screen_attrs["AG"] * 0.2 +
        screen_attrs["IQ"] * 0.2 +
        screen_attrs["CH"] * 0.1
    )
    return base_score * random.randint(1, 6)


def height_to_block_score(height_inches):
    """
    Map player height (inches) to 0-10 for block reconciliation.
    >=82 -> 10, 81 -> 9, ... 73 -> 1, <=72 -> 0.
    """
    if height_inches is None:
        return 0
    try:
        h = int(height_inches)
    except (TypeError, ValueError):
        return 0
    if h >= 82:
        return 10
    if h <= 72:
        return 0
    return 82 - h  # 81->9, 80->8, ..., 73->1


def calculate_block_spot(shooter_x, shooter_y, is_away_offense):
    """
    Block spot: 2-15 back from shooter's x (toward offense's basket), y ± 6.
    Home on offense: x back = -15 to -2. Away on offense: x back = 2 to 15.
    Returns dict {"x", "y"} clamped to court.
    """
    x_back = random.randint(2, 15)
    if is_away_offense:
        block_x = shooter_x + x_back
    else:
        block_x = shooter_x - x_back
    block_y = shooter_y + random.randint(-6, 6)
    block_x = max(0, min(100, block_x))
    block_y = max(0, min(50, block_y))
    return {"x": block_x, "y": block_y}


def calculate_bounce_spot(game, basket_x=None, basket_y=25, shooter_spot=None):
    """
    Calculate the bounce spot coordinates for a missed shot.
    Uses distance-based variance: longer shots have wider bounce variance.
    
    Args:
        game: GameManager instance
        basket_x: X coordinate of the basket (if None, determines from offense team)
        basket_y: Y coordinate of the basket (default 25)
        shooter_spot: Optional string name of shooter's spot (e.g., "key", "upper wing")
                     If provided, calculates distance to determine variance range
    
    Returns:
        dict: {"x": float, "y": float} - bounce spot coordinates
    """
    import math
    from BackEnd.constants import HCO_STRING_SPOTS
    
    if basket_x is None:
        # Determine basket based on which team is on offense
        off_team = game.offense_team
        is_away_offense = off_team.team_id == game.away_team.team_id
        
        # Home team attacks away basket (x=91), away team attacks home basket (x=9)
        # Using standard coordinates: home basket x=91, away basket x=9
        basket_x = 9 if is_away_offense else 91
    
    # Determine variance ranges based on shot distance
    if shooter_spot and shooter_spot in HCO_STRING_SPOTS:
        # Get shooter's coordinates
        shooter_coords = HCO_STRING_SPOTS[shooter_spot]
        
        # Calculate distance from shooter to basket (using actual basket coordinates)
        distance = math.sqrt(
            (shooter_coords["x"] - basket_x) ** 2 + 
            (shooter_coords["y"] - basket_y) ** 2
        )
        
        # Classify shot distance
        if distance < 15:
            # Short shot: x = 2-6 (outward only), y = ±6
            x_variance_max = 6
            y_variance = 6
        elif distance <= 20:
            # Medium shot: x = 2-8 (outward only), y = ±8
            x_variance_max = 8
            y_variance = 8
        else:
            # Long shot: x = 2-10 (outward only), y = ±10
            x_variance_max = 10
            y_variance = 10
    else:
        # Default to medium if shooter spot not provided
        x_variance_max = 8
        y_variance = 8
    
    # X variance: only outward from basket (not inward)
    # Home team attacking away basket (x=91): bounce goes right (x > 91)
    # Away team attacking home basket (x=9): bounce goes left (x < 9)
    if basket_x == 91:  # Home team attacking away basket
        x_offset = random.randint(2, x_variance_max)  # Positive offset (right)
        bounce_x = basket_x + x_offset
    else:  # Away team attacking home basket (x=9)
        x_offset = random.randint(2, x_variance_max)  # Negative offset (left)
        bounce_x = basket_x - x_offset
    
    # Y variance: ±variance from basket
    bounce_y = basket_y + random.randint(-y_variance, y_variance)
    
    # Clamp to valid court bounds
    bounce_x = max(0, min(100, bounce_x))
    bounce_y = max(0, min(50, bounce_y))
    
    return {"x": bounce_x, "y": bounce_y}


def choose_rebounder(lineup, bounce_spot, exclude_player_ids=None, penalize_player_ids=None):
    """
    Choose the player closest to the bounce spot (geography-based).
    
    Args:
        lineup: Dict of position -> Player objects (e.g., {"PG": player, ...})
        bounce_spot: Dict with "x" and "y" keys for bounce coordinates
        exclude_player_ids: Optional set of player_ids to exclude from consideration
        penalize_player_ids: Optional set of player_ids to penalize by 20% distance (e.g., shooter, putback player)
    
    Returns:
        Player object closest to bounce spot, or None if no valid players
    """
    if not lineup:
        logging.warning("choose_rebounder called with empty lineup")
        return None
    
    if exclude_player_ids is None:
        exclude_player_ids = set()
    
    if penalize_player_ids is None:
        penalize_player_ids = set()
    
    bounce_x = bounce_spot["x"]
    bounce_y = bounce_spot["y"]
    
    closest_player = None
    closest_distance = float("inf")
    
    for pos, player in lineup.items():
        if player is None:
            continue
        
        # Skip excluded players
        player_id = getattr(player, "player_id", None)
        if player_id and player_id in exclude_player_ids:
            continue
        
        # Get player's current position
        player_coords = getattr(player, "coords", {"x": 50, "y": 25})
        player_x = player_coords.get("x", 50)
        player_y = player_coords.get("y", 25)
        
        # Calculate Euclidean distance to bounce spot
        distance = ((player_x - bounce_x) ** 2 + (player_y - bounce_y) ** 2) ** 0.5
        
        # Apply 20% penalty to distance for penalized players (shooter, putback player)
        # This penalizes their chances without actually moving them
        if player_id and player_id in penalize_player_ids:
            distance = distance * 1.2
        
        if distance < closest_distance:
            closest_distance = distance
            closest_player = player
    
    return closest_player

def generate_pass_chain(game, shooter_pos):
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    positions = ["PG", "SG", "SF", "PF", "C"]
    chain = ["PG"]  # Start with PG
    last_added = "PG"

    tempo = off_team.strategy_calls["tempo_call"]
    if tempo == "slow":
        num_passes = 3
    elif tempo == "fast":
        num_passes = 1
    else:
        num_passes = 2

    while len(chain) < num_passes:
        candidate = random.choice(positions)
        if candidate != last_added and candidate != shooter_pos:
            chain.append(candidate)
            last_added = candidate

    chain.append(shooter_pos)  # Shooter always last
    return chain

def clean_mongo_ids(doc: dict) -> dict:
    """
    Converts MongoDB ObjectId fields to strings so FastAPI can serialize them.
    """
    if "_id" in doc and hasattr(doc["_id"], "__str__"):
        doc["_id"] = str(doc["_id"])
    return doc

def get_name_safe(p):

    if isinstance(p, dict):
        return p.get("name", "")
    return getattr(p, "name", "")

def default_rebounder_dict():
    return {
        "offense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3},
        "defense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3}
    }

def determine_rebounder(game, bounce_spot=None, exclude_player_ids=None, penalize_player_ids=None):
    """
    Determine rebounder using geography-based system (closest to bounce spot).
    
    Args:
        game: GameManager instance
        bounce_spot: Optional dict with "x" and "y" keys. If None, calculates from basket.
        exclude_player_ids: Optional set of player_ids to exclude (e.g., shooter)
        penalize_player_ids: Optional set of player_ids to penalize by 20% distance (e.g., shooter, putback player)
    
    Returns:
        tuple: (rebounder, team, stat) where stat is "DREB" or "OREB"
    """
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    
    # Calculate bounce spot if not provided
    if bounce_spot is None:
        bounce_spot = calculate_bounce_spot(game)
    
    if exclude_player_ids is None:
        exclude_player_ids = set()
    
    if penalize_player_ids is None:
        penalize_player_ids = set()
    
    # Choose closest player from each team (with penalty for shooter/putback player)
    o_rebounder = choose_rebounder(off_lineup, bounce_spot, exclude_player_ids, penalize_player_ids)
    d_rebounder = choose_rebounder(def_lineup, bounce_spot, exclude_player_ids, penalize_player_ids)
    
    # Handle edge cases
    if o_rebounder is None and d_rebounder is None:
        # No rebounders from either team - find closest player to bounce spot from all players
        logging.warning("determine_rebounder: No valid rebounders found, using closest player from all players")
        all_players_lineup = {}
        # Combine both lineups
        for pos, player in off_lineup.items():
            if player is not None:
                all_players_lineup[f"O_{pos}"] = player
        for pos, player in def_lineup.items():
            if player is not None:
                all_players_lineup[f"D_{pos}"] = player
        
        closest_player = choose_rebounder(all_players_lineup, bounce_spot, exclude_player_ids, penalize_player_ids)
        
        if closest_player is None:
            raise ValueError("No players available for rebound")
        
        # Determine which team the closest player belongs to
        closest_team_id = getattr(closest_player, "team_id", None)
        if closest_team_id == off_team.team_id:
            return closest_player, off_team, "OREB"
        else:
            return closest_player, def_team, "DREB"
    
    if o_rebounder is None:
        # Only defensive rebounders available
        return d_rebounder, def_team, "DREB"
    
    if d_rebounder is None:
        # Only offensive rebounders available
        return o_rebounder, off_team, "OREB"
    
    # Calculate rebound scores for the closest players
    o_score = calculate_rebound_score(o_rebounder)
    d_score = calculate_rebound_score(d_rebounder)

    # Apply team bias
    off_mod = off_team.team_attributes["rebound_modifier"]
    def_mod = def_team.team_attributes["rebound_modifier"]
    bias = def_mod - off_mod
    def_prob = min(0.95, max(0.55, 0.75 + bias))

    # Calculate final weights
    total_score = d_score + o_score
    d_weight = (d_score / total_score) if total_score else 0.5
    d_weight += (def_prob - 0.5)
    d_weight = min(0.95, max(0.05, d_weight))

    # Weighted random selection
    new_team = def_team if random.random() < d_weight else off_team
    new_rebounder = d_rebounder if new_team == def_team else o_rebounder
    new_stat = "DREB" if new_team == def_team else "OREB"

    return new_rebounder, new_team, new_stat

def get_team_thresholds(game):
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    off_attr = off_team.team_attributes
    def_attr = def_team.team_attributes

    return {
        "discipline": off_attr.get("discipline", 10),
        "d_fight": def_attr.get("fight", 10),
        "o_fight": off_attr.get("fight", 10)
    }

def get_foul_and_turnover_positions(pass_count):
    return {
        "turnover": random.choice(TURNOVER_CALC_DICT[pass_count]),
        "o_foul": random.choice(POSITION_LIST),
        "d_foul": random.choice(POSITION_LIST)
    }

def get_player_position(team_lineup, player_obj):
    return next((pos for pos, p in team_lineup.items() if p == player_obj), None)

def get_player_by_pos(pos, offense_lineup, defense_lineup):
    if pos in offense_lineup:
        return offense_lineup[pos]
    elif pos in defense_lineup:
        return defense_lineup[pos]
    else:
        return None


def get_quarter_index_from_game(game):
    return game.game_state["quarter"] - 1

def scale_score_to_100(raw_score):
    """
    Universal helper function to scale raw scores to 1-100 range where midpoint = 50.
    
    Assumes consistent pattern:
    - Attributes range: 1-100 (midpoint = 50)
    - Die roll: 1-6 (midpoint = 3.5)
    - Attribute weights sum to 1.0
    - Raw midpoint: 50 * 3.5 = 175
    - Raw range: 1 (min) to 600 (max)
    
    Scaling formula: ((raw - 175) / 425) * 50 + 50
    - Maps raw 175 → scaled 50 (midpoint)
    - Maps raw 1 → scaled ~29.5 (minimum)
    - Maps raw 600 → scaled 100 (maximum)
    
    Args:
        raw_score: Raw score value (typically 1-600)
    
    Returns:
        int: Scaled score (1-100, with midpoint = 50)
    """
    return int(round(((raw_score - 175) / 425) * 50 + 50))

def calculate_rebound_score(player):
    attr = player.attributes
    return (attr["RB"] * 0.5 + attr["ST"] * 0.3 + attr["IQ"] * 0.2) * random.randint(1, 6)

def calculate_outlet_pass_score(outlet_passer):
    """
    Calculate outlet pass score based on outlet passer's attributes.
    Score is scaled to 1-100 range where midpoint (average attributes + average die) = 50.
    
    Raw formula: (PS * 0.6 + ST * 0.2 + IQ * 0.2) * random(1-6)
    - Attributes range: 1-100 (midpoint = 50)
    - Die roll: 1-6 (midpoint = 3.5)
    - Raw midpoint: (50 * 0.6 + 50 * 0.2 + 50 * 0.2) * 3.5 = 175
    - Raw range: 1 (min) to 600 (max)
    
    Scaling formula: ((raw - 175) / 425) * 50 + 50
    - Maps raw 175 → scaled 50
    - Maps raw 1 → scaled ~29.5
    - Maps raw 600 → scaled 100
    
    Args:
        outlet_passer: Player object making the outlet pass
    
    Returns:
        int: Scaled outlet pass score (1-100, with midpoint = 50)
    """
    attr = outlet_passer.attributes
    # Calculate raw score
    raw_score = (attr["PS"] * 0.6 + attr["ST"] * 0.2 + attr["IQ"] * 0.2) * random.randint(1, 6)
    
    # Scale to 1-100 using universal scaling function
    return scale_score_to_100(raw_score)

def resolve_steal_attempt(offense_value, defense_value, soft_steal, hard_steal, soft_foul, hard_foul):
    """
    Resolve outcome of a steal attempt.
    
    Args:
        offense_value: Ball handler's protection value (bh_score)
        defense_value: Defender's steal attempt value (pressure)
        soft_steal: Soft steal threshold (default: -100)
        hard_steal: Hard steal threshold (default: -200)
        soft_foul: Soft foul threshold (default: 150, from constants.SOFT_FOUL)
        hard_foul: Hard foul threshold (default: 250, from constants.HARD_FOUL)
    
    Returns:
        One of:
        - "STEAL" - Steal successful, possession changes
        - "D_FOUL" - Defensive foul on steal attempt, offense retains possession
        - "NO_EVENT" - No event, play continues normally
    """
    import random
    from BackEnd.constants import SOFT_PROB
    
    delta = offense_value - defense_value  # negative => defense won the contest
    
    # 1) Steal outcomes (defense wins)
    if delta <= hard_steal:
        return "STEAL"
    if delta <= soft_steal:
        # Soft steal band: partial probability to calibrate to baseline rates
        if random.random() < SOFT_PROB:
            return "STEAL"
    
    # 2) Defensive foul outcomes (offense wins / defender reaches)
    if delta >= hard_foul:
        return "D_FOUL"
    if delta >= soft_foul:
        if random.random() < SOFT_PROB:
            return "D_FOUL"
    
    # 3) Otherwise nothing happens; possession continues
    return "NO_EVENT"


def apply_scoring(game, team, player, points, stats):
    """Record player scoring stats and update team points.

    Parameters:
        game: GameManager object
        team: TeamManager object receiving the points
        player: Player object recording the stats
        points: int number of points scored
        stats: iterable of stat strings to record on the player
    """
    for stat in stats:
        player.record_stat(stat)
    
    record_team_points(game, team, points)

def record_team_points(game, team, points):
    """
    Updates total game score and per-quarter score for the given team.
    
    Parameters:
    - game: GameManager object
    - team: TeamManager object (e.g., game.offense_team)
    - points: int, number of points to add
    """
    game.score[team.name] += points
    quarter_index = game.game_state["quarter"] - 1

    # Keep both representations synchronized. team.points_by_quarter is the
    # canonical runtime source; game_state mirror is maintained for compatibility.
    while len(team.points_by_quarter) <= quarter_index:
        team.points_by_quarter.append(0)
    team.points_by_quarter[quarter_index] += points

    points_by_quarter_state = game.game_state.setdefault("points_by_quarter", {})
    team_quarters = points_by_quarter_state.setdefault(team.name, [0, 0, 0, 0])
    while len(team_quarters) <= quarter_index:
        team_quarters.append(0)
    # Defensive: if the mirror list accidentally aliases the canonical list,
    # avoid double-counting. (We still prefer to keep them non-aliased.)
    if team_quarters is not team.points_by_quarter:
        team_quarters[quarter_index] += points

def unpack_game_context(game):
    
    return (
        game.game_state,
        game.offense_team,
        game.defense_team,
        game.offense_team.lineup,
        game.defense_team.lineup,
    )


def serialize_computer_timeouts(data):
    """
    Serialize game_state['computer_timeouts'] for DB persistence.
    Converts checked_conditions sets to lists (JSON-safe).
    Returns None if data is falsy.
    """
    if not data or not isinstance(data, dict):
        return None
    out = {}
    for team_name, quarters in data.items():
        if not isinstance(quarters, dict):
            continue
        out[team_name] = {}
        for quarter, qdata in quarters.items():
            if not isinstance(qdata, dict):
                continue
            out[team_name][str(quarter)] = {
                "count": qdata.get("count", 0),
                "checked_conditions": list(qdata.get("checked_conditions", set())),
            }
    return out if out else None


def deserialize_computer_timeouts(data):
    """
    Deserialize computer_timeouts from saved document into game_state shape.
    Converts checked_conditions lists back to sets. Returns {} if data is falsy.
    """
    if not data or not isinstance(data, dict):
        return {}
    out = {}
    for team_name, quarters in data.items():
        if not isinstance(quarters, dict):
            continue
        out[team_name] = {}
        for quarter, qdata in quarters.items():
            if not isinstance(qdata, dict):
                continue
            checked = qdata.get("checked_conditions", [])
            out[team_name][int(quarter) if str(quarter).isdigit() else quarter] = {
                "count": qdata.get("count", 0),
                "checked_conditions": set(checked) if isinstance(checked, list) else set(),
            }
    return out


def summarize_game_state(game, exclude_animations=True):
    """
    Summarize game state for persistence/API responses.
    Uses nested team structure and always excludes animations from saves.
    
    Args:
        game: GameManager instance
        exclude_animations: Always True for saves (animations only for real-time frontend)
    """
    
    def _collect_player_ids(obj, acc):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("playerId", "player_id"):
                    if isinstance(v, list):
                        acc.update(str(pid) for pid in v if pid is not None)
                    elif v is not None:
                        acc.add(str(v))
                else:
                    _collect_player_ids(v, acc)
        elif isinstance(obj, list):
            for item in obj:
                _collect_player_ids(item, acc)

    referenced_ids = set()
    _collect_player_ids(game.turns, referenced_ids)

    players = []
    for team_key, team_obj in [("home", game.home_team), ("away", game.away_team)]:
        # ✅ SS&S FIX: Save ALL players (lineup + bench) to preserve real-time NG values for all players
        # Previously only saved lineup players, causing bench players to default to 1.0 NG when loading from DB
        # This ensures all players' current energy levels are persisted and available after timeout/quarter breaks
        for player in team_obj.get_all_players():
            # Get position if player is in lineup, otherwise None
            pos = None
            for lineup_pos, lineup_player in team_obj.lineup.items():
                if lineup_player.player_id == player.player_id:
                    pos = lineup_pos
                    break
            
            coords = getattr(player, "coords", None) or {"x": 0, "y": 0}
            players.append({
                "playerId": player.player_id,
                "name": getattr(player, "name", None) or f"{getattr(player, 'first_name', '')} {getattr(player, 'last_name', '')}".strip(),
                "team": team_key,
                "team_id": team_obj.team_id,
                "pos": pos,  # None for bench players
                "jersey": player.jersey,
                "photo": getattr(player, "photo", None),  # Player headshot image
                "primary_color": getattr(team_obj, "primary_color", "#000000"),
                "secondary_color": getattr(team_obj, "secondary_color", "#ffffff"),
                "x": coords.get("x", 0),
                "y": coords.get("y", 0),
                "stats": player.stats.get("game", {}),  # Include game stats for persistence
                "attributes": {
                    "EM": player.attributes.get("EM", 0),
                    "CH": player.attributes.get("CH", 0),
                    "MO": player.attributes.get("MO", 0),
                    "NG": player.attributes.get("NG", 1.0)  # ✅ Real-time energy value from in-memory Player object
                }
            })

    # Only include non-lineup players if we're including animations (full turn data)
    # For turn-by-turn mode, only current lineup is needed (turns are empty or stale)
    # Check both exclude_animations flag AND if there are actual NEW turns to reference
    has_fresh_turns = len(game.turns) > 0 and not exclude_animations
    if has_fresh_turns:
        included_ids = {p["playerId"] for p in players}
        for pid in referenced_ids:
            if pid in included_ids:
                continue
            player_obj = game.home_team.get_player_by_id(pid) or game.away_team.get_player_by_id(pid)
            if player_obj:
                team_key = "home" if game.home_team.get_player_by_id(pid) else "away"
                team_obj = game.home_team if team_key == "home" else game.away_team
                coords = getattr(player_obj, "coords", None) or {"x": 0, "y": 0}
                players.append({
                    "playerId": player_obj.player_id,
                    "name": getattr(player_obj, "name", None) or f"{getattr(player_obj, 'first_name', '')} {getattr(player_obj, 'last_name', '')}".strip(),
                    "team": team_key,
                    "team_id": team_obj.team_id,
                    "pos": getattr(player_obj, "position", None) or getattr(player_obj, "pos", None),
                    "jersey": player_obj.jersey,
                    "photo": getattr(player_obj, "photo", None),  # Player headshot image
                    "primary_color": getattr(team_obj, "primary_color", "#000000"),
                    "secondary_color": getattr(team_obj, "secondary_color", "#ffffff"),
                    "x": coords.get("x", 0),
                    "y": coords.get("y", 0),
                    "stats": player_obj.stats.get("game", {}),  # Include game stats for persistence
                    "attributes": {
                        "EM": player_obj.attributes.get("EM", 0),
                        "CH": player_obj.attributes.get("CH", 0),
                        "MO": player_obj.attributes.get("MO", 0),
                        "NG": player_obj.attributes.get("NG", 1.0)
                    }
                })
            else:
                players.append({
                    "playerId": pid,
                    "name": "",
                    "team": None,
                    "team_id": None,
                    "pos": None,
                    "jersey": None,
                    "primary_color": "#000000",
                    "secondary_color": "#ffffff",
                    "x": 0,
                    "y": 0,
                })
            included_ids.add(pid)

    team_info = {
        "home": {
            "team_id": game.home_team.team_id,
            "player_ids": [p["playerId"] for p in players if p["team"] == "home"],
            "primary_color": game.home_team.primary_color,
            "secondary_color": game.home_team.secondary_color,
        },
        "away": {
            "team_id": game.away_team.team_id,
            "player_ids": [p["playerId"] for p in players if p["team"] == "away"],
            "primary_color": game.away_team.primary_color,
            "secondary_color": game.away_team.secondary_color,
        },
    }
    # print(f"Home team primary color: {game.home_team.primary_color}")
    # print(f"Home team secondary color: {game.home_team.secondary_color}")
    # print(f"Away team primary color: {game.away_team.primary_color}")
    # print(f"Away team secondary color: {game.away_team.secondary_color}")

    home_team_obj = {
        "name": game.home_team.name,
        "team_id": game.home_team.team_id,
        "score": game.score.get(game.home_team.name, 0),
        "colors": {
            "primary_color": game.home_team.primary_color,
            "secondary_color": game.home_team.secondary_color,
        },
    }

    away_team_obj = {
        "name": game.away_team.name,
        "team_id": game.away_team.team_id,
        "score": game.score.get(game.away_team.name, 0),
        "colors": {
            "primary_color": game.away_team.primary_color,
            "secondary_color": game.away_team.secondary_color,
        },
    }

    cumulative_box = game.get_box_score()

    # ✅ FIX: Use in-memory plays from team objects (they have updated game_stats)
    # Instead of creating fresh copies from database, use the plays that were updated during gameplay
    # This preserves game_stats (times_run, successes, player_points) that were tracked during the game
    from copy import deepcopy
    import logging
    
    # Get plays from home team (in-memory, with updated game_stats)
    home_plays = deepcopy(getattr(game.home_team, 'plays', {}))
    # Get plays from away team (in-memory, with updated game_stats)
    away_plays = deepcopy(getattr(game.away_team, 'plays', {}))
    from BackEnd.utils.team_play_utils import iter_team_plays
    
    # 🔍 DEBUG: Log game_stats in plays
    home_plays_with_stats = {
        display_name: play
        for _play_key, play, display_name in iter_team_plays(home_plays)
        if play.get("game_stats", {}).get("times_run", 0) > 0
    }
    away_plays_with_stats = {
        display_name: play
        for _play_key, play, display_name in iter_team_plays(away_plays)
        if play.get("game_stats", {}).get("times_run", 0) > 0
    }
    # if home_plays_with_stats:
    #     logging.warning(f"🔍 [SUMMARIZE_GAME_STATE] Home team plays with game_stats: {list(home_plays_with_stats.keys())}")
    #     for play_name, play_data in list(home_plays_with_stats.items())[:3]:  # Log first 3
    #         game_stats = play_data.get("game_stats", {})
    #         logging.warning(f"🔍 [SUMMARIZE_GAME_STATE] Home play '{play_name}': times_run={game_stats.get('times_run', 0)}, successes={game_stats.get('successes', 0)}, player_points={len(game_stats.get('player_points', {}))} players")
    # if away_plays_with_stats:
    #     logging.warning(f"🔍 [SUMMARIZE_GAME_STATE] Away team plays with game_stats: {list(away_plays_with_stats.keys())}")
    #     for play_name, play_data in list(away_plays_with_stats.items())[:3]:  # Log first 3
    #         game_stats = play_data.get("game_stats", {})
    #         logging.warning(f"🔍 [SUMMARIZE_GAME_STATE] Away play '{play_name}': times_run={game_stats.get('times_run', 0)}, successes={game_stats.get('successes', 0)}, player_points={len(game_stats.get('player_points', {}))} players")
    # If teams don't have plays loaded, fallback to database (shouldn't happen in normal flow)
    if not home_plays and not away_plays:
        try:
            from BackEnd.api.gameplan_routes import populate_team_plays
            populated_plays = populate_team_plays()
            home_plays = populated_plays.copy()
            away_plays = populated_plays.copy()
        except Exception as e:
            print(f"🚨 Error in populate_team_plays: {e}")
            home_plays = {}
            away_plays = {}
    
    # ✅ PRESERVE playbook_settings from database when saving game state
    # This ensures slot_assignments and other playbook settings persist across timeout/quarter saves
    # ✅ SS&S: DB is source of truth - always load from DB for persistence
    # GameManager is just a cache - we preserve what's in DB, not what's in cache
    home_playbook_settings = {}
    away_playbook_settings = {}
    home_canonical_team_id = None
    away_canonical_team_id = None
    
    # 🔍 DEBUG: Check if GameManager has settings (for diagnostic purposes)
    # ✅ REMOVED: Verbose SUMMARIZE DEBUG logs - redundant with trace logs
    
    # ✅ FIX: Always try to load playbook_settings (from GameManager or DB) regardless of exclude_animations
    # For frontend (exclude_animations=False): GameManager has current state
    # For DB save (exclude_animations=True): DB is source of truth, but GameManager is safety net
    # This ensures settings are available in both frontend response AND DB save
    if hasattr(game, 'game_id') and game.game_id:
        try:
            from BackEnd.db import games_collection
            from bson import ObjectId
            from BackEnd.utils.team_id_resolver import resolve_team_id_to_canonical
            
            # Try both UUID string and ObjectId formats for game_id
            saved_game = games_collection.find_one({"_id": game.game_id})
            if not saved_game:
                try:
                    saved_game = games_collection.find_one({"_id": ObjectId(game.game_id)})
                except:
                    pass
            
            if saved_game:
                teams = saved_game.get("teams", {})
                
                # ✅ TRACE: Log available team keys for debugging
                available_team_keys = list(teams.keys())
                # logging.warning(f"🔍 [SUMMARIZE] Available team keys in DB: {available_team_keys}")
                # logging.warning(f"🔍 [SUMMARIZE] Looking for home_team_id={game.home_team.team_id}, away_team_id={game.away_team.team_id}")
                
                # ✅ SS&S: Use unified resolver to get canonical team_id (same logic as extract_team_settings)
                # This ensures we use the same canonical format for both save and extract
                # For single mode, resolve from game document (validates against teams object)
                try:
                    home_canonical_team_id = resolve_team_id_to_canonical(
                        team_identifier=game.home_team.team_id,
                        mode="single",
                        doc=saved_game  # Pass game document for validation
                    )
                    # logging.warning(f"✅ [SUMMARIZE] Resolved home_team_id to canonical: '{game.home_team.team_id}' → '{home_canonical_team_id}'")
                except (ValueError, Exception) as e:
                    # logging.warning(f"⚠️ [SUMMARIZE] Could not resolve home_team_id to canonical: {e}")
                    # Fallback: try direct lookup in teams object
                    if game.home_team.team_id in teams:
                        home_canonical_team_id = game.home_team.team_id
                    elif game.home_team.name in [teams.get(tid, {}).get("name") for tid in teams.keys()]:
                        # Find by name match
                        for tid in teams.keys():
                            if teams.get(tid, {}).get("name") == game.home_team.name:
                                home_canonical_team_id = tid
                                break
                
                try:
                    away_canonical_team_id = resolve_team_id_to_canonical(
                        team_identifier=game.away_team.team_id,
                        mode="single",
                        doc=saved_game  # Pass game document for validation
                    )
                    # logging.warning(f"✅ [SUMMARIZE] Resolved away_team_id to canonical: '{game.away_team.team_id}' → '{away_canonical_team_id}'")
                except (ValueError, Exception) as e:
                    # logging.warning(f"⚠️ [SUMMARIZE] Could not resolve away_team_id to canonical: {e}")
                    # Fallback: try direct lookup in teams object
                    if game.away_team.team_id in teams:
                        away_canonical_team_id = game.away_team.team_id
                    elif game.away_team.name in [teams.get(tid, {}).get("name") for tid in teams.keys()]:
                        # Find by name match
                        for tid in teams.keys():
                            if teams.get(tid, {}).get("name") == game.away_team.name:
                                away_canonical_team_id = tid
                                break
                
                # ✅ CRITICAL FIX: During active gameplay (timeout saves), GameManager is source of truth for playbook_settings
                # GameManager has the current, active settings that are being used during gameplay
                # Database may have stale or empty settings from initial game creation
                # Priority: GameManager (active gameplay) > Database (persistence)
                
                # Home team: Check GameManager first (active gameplay source of truth)
                if hasattr(game.home_team, 'playbook_settings') and game.home_team.playbook_settings:
                    # Check if GameManager has non-empty playbook_settings
                    gm_slots = len(game.home_team.playbook_settings.get("slot_assignments", {}))
                    if gm_slots > 0 or any(game.home_team.playbook_settings.get(key, {}) for key in ["motion", "set_play_inside", "set_play_attack", "set_play_outside"]):
                        home_playbook_settings = game.home_team.playbook_settings
                        # logging.warning(f"✅ [SUMMARIZE] Using GameManager home playbook_settings (active gameplay): slot_assignments={gm_slots}")
                    else:
                        # GameManager has empty settings, try DB
                        if home_canonical_team_id:
                            home_team_data = teams.get(home_canonical_team_id, {})
                            db_settings = home_team_data.get("playbook_settings", {})
                            if db_settings:
                                home_playbook_settings = db_settings
                                slot_count = len(db_settings.get("slot_assignments", {}))
                                # logging.warning(f"✅ [SUMMARIZE] GameManager empty, using DB home playbook_settings: slot_assignments={slot_count}")
                            else:
                                home_playbook_settings = {}  # No settings anywhere
                                # logging.warning(f"⚠️ [SUMMARIZE] No playbook_settings found for home team (GameManager empty, DB empty)")
                        else:
                            home_playbook_settings = {}  # Can't resolve team_id
                            # logging.warning(f"⚠️ [SUMMARIZE] Could not resolve home_canonical_team_id, GameManager empty")
                else:
                    # GameManager doesn't have playbook_settings, try DB
                    if home_canonical_team_id:
                        home_team_data = teams.get(home_canonical_team_id, {})
                        home_playbook_settings = home_team_data.get("playbook_settings", {})
                        if home_playbook_settings:
                            slot_count = len(home_playbook_settings.get("slot_assignments", {}))
                            # logging.warning(f"✅ [SUMMARIZE] GameManager missing, using DB home playbook_settings: slot_assignments={slot_count}")
                        else:
                            # logging.warning(f"⚠️ [SUMMARIZE] No playbook_settings found for home team (GameManager missing, DB empty)")
                            pass
                    else:
                        home_playbook_settings = {}  # Can't resolve team_id
                        # logging.warning(f"⚠️ [SUMMARIZE] Could not resolve home_canonical_team_id, GameManager missing")
                
                # Away team: Check GameManager first (active gameplay source of truth)
                if hasattr(game.away_team, 'playbook_settings') and game.away_team.playbook_settings:
                    # Check if GameManager has non-empty playbook_settings
                    gm_slots = len(game.away_team.playbook_settings.get("slot_assignments", {}))
                    if gm_slots > 0 or any(game.away_team.playbook_settings.get(key, {}) for key in ["motion", "set_play_inside", "set_play_attack", "set_play_outside"]):
                        away_playbook_settings = game.away_team.playbook_settings
                        # logging.warning(f"✅ [SUMMARIZE] Using GameManager away playbook_settings (active gameplay): slot_assignments={gm_slots}")
                    else:
                        # GameManager has empty settings, try DB
                        if away_canonical_team_id:
                            away_team_data = teams.get(away_canonical_team_id, {})
                            db_settings = away_team_data.get("playbook_settings", {})
                            if db_settings:
                                away_playbook_settings = db_settings
                                slot_count = len(db_settings.get("slot_assignments", {}))
                                # logging.warning(f"✅ [SUMMARIZE] GameManager empty, using DB away playbook_settings: slot_assignments={slot_count}")
                            else:
                                away_playbook_settings = {}  # No settings anywhere
                                # logging.warning(f"⚠️ [SUMMARIZE] No playbook_settings found for away team (GameManager empty, DB empty)")
                        else:
                            away_playbook_settings = {}  # Can't resolve team_id
                            # logging.warning(f"⚠️ [SUMMARIZE] Could not resolve away_canonical_team_id, GameManager empty")
                else:
                    # GameManager doesn't have playbook_settings, try DB
                    if away_canonical_team_id:
                        away_team_data = teams.get(away_canonical_team_id, {})
                        away_playbook_settings = away_team_data.get("playbook_settings", {})
                        if away_playbook_settings:
                            slot_count = len(away_playbook_settings.get("slot_assignments", {}))
                            # logging.warning(f"✅ [SUMMARIZE] GameManager missing, using DB away playbook_settings: slot_assignments={slot_count}")
                        else:
                            # logging.warning(f"⚠️ [SUMMARIZE] No playbook_settings found for away team (GameManager missing, DB empty)")
                            pass
                    else:
                        away_playbook_settings = {}  # Can't resolve team_id
                        # logging.warning(f"⚠️ [SUMMARIZE] Could not resolve away_canonical_team_id, GameManager missing")
                
                # ✅ REMOVED: Verbose success/failure logs - only log if settings are missing when expected
        except Exception as e:
            # If we can't load playbook_settings from DB, try GameManager as fallback
            logging.warning(f"⚠️ Could not load playbook_settings from database: {e}, trying GameManager fallback")
            # Fallback to GameManager if DB load failed
            if not home_playbook_settings and hasattr(game.home_team, 'playbook_settings') and game.home_team.playbook_settings:
                home_playbook_settings = game.home_team.playbook_settings
                slot_count = len(home_playbook_settings.get("slot_assignments", {}))
                # logging.warning(f"✅ [SUMMARIZE] DB load failed, using GameManager fallback for home: slot_assignments={slot_count}")
            if not away_playbook_settings and hasattr(game.away_team, 'playbook_settings') and game.away_team.playbook_settings:
                away_playbook_settings = game.away_team.playbook_settings
                slot_count = len(away_playbook_settings.get("slot_assignments", {}))
                # logging.warning(f"✅ [SUMMARIZE] DB load failed, using GameManager fallback for away: slot_assignments={slot_count}")
    
    # ✅ FINAL FALLBACK: If DB loading didn't run (no game_id) or didn't find settings, check GameManager
    # This ensures settings are available even when DB loading fails
    if not home_playbook_settings and hasattr(game.home_team, 'playbook_settings') and game.home_team.playbook_settings:
        home_playbook_settings = game.home_team.playbook_settings
        slot_count = len(home_playbook_settings.get("slot_assignments", {}))
        # logging.warning(f"✅ [SUMMARIZE] Using GameManager for home (no DB load): slot_assignments={slot_count}")
    if not away_playbook_settings and hasattr(game.away_team, 'playbook_settings') and game.away_team.playbook_settings:
        away_playbook_settings = game.away_team.playbook_settings
        slot_count = len(away_playbook_settings.get("slot_assignments", {}))
        # logging.warning(f"✅ [SUMMARIZE] Using GameManager for away (no DB load): slot_assignments={slot_count}")
    
    # ✅ UNIFIED TEAM STRUCTURE: Create single teams object with ALL team data
    # ✅ SS&S: Use canonical team_id keys (same format as extract_team_settings uses)
    # This ensures consistent key matching between save and extract
    # If canonical resolution failed, fallback to game.home_team.team_id (shouldn't happen, but defensive)
    # Note: If home_canonical_team_id/away_canonical_team_id are None, we already tried to resolve them above
    # The fallback here is only for edge cases where resolution completely failed
    home_key = home_canonical_team_id if home_canonical_team_id else game.home_team.team_id
    away_key = away_canonical_team_id if away_canonical_team_id else game.away_team.team_id
    
    # 🔍 DEBUG: Log team_id keys used for saving playbook_settings during timeout
    # logging.warning(f"🔍 [SUMMARIZE-TIMEOUT-SAVE] Team ID keys for playbook_settings save:")
    # logging.warning(f"🔍 [SUMMARIZE-TIMEOUT-SAVE]   game.home_team.team_id = '{game.home_team.team_id}'")
    # logging.warning(f"🔍 [SUMMARIZE-TIMEOUT-SAVE]   game.away_team.team_id = '{game.away_team.team_id}'")
    # logging.warning(f"🔍 [SUMMARIZE-TIMEOUT-SAVE]   home_canonical_team_id = '{home_canonical_team_id}'")
    # logging.warning(f"🔍 [SUMMARIZE-TIMEOUT-SAVE]   away_canonical_team_id = '{away_canonical_team_id}'")
    # logging.warning(f"🔍 [SUMMARIZE-TIMEOUT-SAVE]   FINAL home_key = '{home_key}' (canonical)")
    # logging.warning(f"🔍 [SUMMARIZE-TIMEOUT-SAVE]   FINAL away_key = '{away_key}' (canonical)")
    # logging.warning(f"🔍 [SUMMARIZE-TIMEOUT-SAVE]   home_playbook_settings has slot_assignments: {len(home_playbook_settings.get('slot_assignments', {})) if home_playbook_settings else 0}")
    # logging.warning(f"🔍 [SUMMARIZE-TIMEOUT-SAVE]   away_playbook_settings has slot_assignments: {len(away_playbook_settings.get('slot_assignments', {})) if away_playbook_settings else 0}")
    
    # Process turns: exclude animations for database persistence, keep for real-time frontend
    from copy import deepcopy

    def _turns_to_serializable(turn_list):
        """Recursively replace Player instances with player_to_dict so JSON serialization succeeds."""
        from BackEnd.models.player import Player, player_to_dict

        def _convert(obj):
            if isinstance(obj, Player):
                return player_to_dict(obj)
            if isinstance(obj, list):
                return [_convert(x) for x in obj]
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            return obj

        return [_convert(t) for t in turn_list]

    # For database saves, don't store turns at all (only need game state metadata)
    # Turns are only needed for real-time frontend display, not for persistence
    if exclude_animations:
        turns = []  # Empty array - don't save turns to database (prevents document size issues)
    else:
        turns = _turns_to_serializable(game.turns)  # Serializable copy for JSON response (no Player instances)
    
    # Get cumulative box scores
    cumulative_box = game.get_box_score()
    
    # ✅ Extract strategy_settings before building dictionary (for debugging and clarity)
    home_strategy = getattr(game.home_team, 'strategy_settings', {})
    away_strategy = getattr(game.away_team, 'strategy_settings', {})
    
    # ✅ REMOVED: Verbose PERSIST-SETTINGS logs - redundant with trace logs (keep only warnings)
    # Only log warnings if settings are missing (these indicate problems)
    if not home_strategy or not isinstance(home_strategy, dict) or len(home_strategy) == 0:
        # logging.warning(f"⚠️ [PERSIST-SETTINGS] Home strategy_settings is empty or missing!")
        pass
    if not away_strategy or not isinstance(away_strategy, dict) or len(away_strategy) == 0:
        # logging.warning(f"⚠️ [PERSIST-SETTINGS] Away strategy_settings is empty or missing!")
        pass
    if not home_playbook_settings or not isinstance(home_playbook_settings, dict):
        # logging.warning(f"⚠️ [PERSIST-SETTINGS] Home playbook_settings is empty or missing!")
        pass
    if not away_playbook_settings or not isinstance(away_playbook_settings, dict):
        # logging.warning(f"⚠️ [PERSIST-SETTINGS] Away playbook_settings is empty or missing!")
        pass
    
    # ✅ UNIFIED STRUCTURE: All team data in one place (eliminates home_team/away_team duplication)
    teams_obj = {
        home_key: {
            # Display fields
            "name": game.home_team.name,
            "team_id": game.home_team.team_id,
            "mascot": game.home_team.mascot,
            "colors": {
                "primary_color": game.home_team.primary_color,
                "secondary_color": game.home_team.secondary_color,
            },
            # Game state fields
            "score": game.score.get(game.home_team.name, 0),
            "points_by_quarter": list(
                getattr(game.home_team, "points_by_quarter", [])
                or game.game_state.get("points_by_quarter", {}).get(game.home_team.name, [0, 0, 0, 0])
            ),
            "team_fouls": game.home_team.team_fouls,
            "timeouts": getattr(game.home_team, 'timeouts', 4),  # Default to 4 if not set (backward compatibility)
            # Data fields (single source of truth)
            "attributes": getattr(game.home_team, 'team_attributes', {}),
            # ✅ SS&S: Use team_id to look up box_score (cumulative_box now uses team_id keys)
            "box_score": cumulative_box.get(game.home_team.team_id, cumulative_box.get(game.home_team.name, {})),
            "totals": game.team_totals.get(game.home_team.name, {}),
            # Persistence fields
            "strategy_settings": home_strategy,
            "strategy_calls": getattr(game.home_team, 'strategy_calls', {}),  # ✅ SS&S: Persist playcall overrides
            "plays": home_plays,  # ✅ FIX: Use in-memory plays with updated game_stats
            "scouting": getattr(game.home_team, 'scouting_data', {}),
            "playbook_settings": home_playbook_settings  # ✅ Preserve from database
        },
        away_key: {
            # Display fields
            "name": game.away_team.name,
            "team_id": game.away_team.team_id,
            "mascot": game.away_team.mascot,
            "colors": {
                "primary_color": game.away_team.primary_color,
                "secondary_color": game.away_team.secondary_color,
            },
            # Game state fields
            "score": game.score.get(game.away_team.name, 0),
            "points_by_quarter": list(
                getattr(game.away_team, "points_by_quarter", [])
                or game.game_state.get("points_by_quarter", {}).get(game.away_team.name, [0, 0, 0, 0])
            ),
            "team_fouls": game.away_team.team_fouls,
            "timeouts": getattr(game.away_team, 'timeouts', 4),  # Default to 4 if not set (backward compatibility)
            # Data fields (single source of truth)
            "attributes": getattr(game.away_team, 'team_attributes', {}),
            # ✅ SS&S: Use team_id to look up box_score (cumulative_box now uses team_id keys)
            "box_score": cumulative_box.get(game.away_team.team_id, cumulative_box.get(game.away_team.name, {})),
            "totals": game.team_totals.get(game.away_team.name, {}),
            # Persistence fields
            "strategy_settings": getattr(game.away_team, 'strategy_settings', {}),
            "strategy_calls": getattr(game.away_team, 'strategy_calls', {}),  # ✅ SS&S: Persist playcall overrides
            "plays": away_plays,  # ✅ FIX: Use in-memory plays with updated game_stats
            "scouting": getattr(game.away_team, 'scouting_data', {}),
            "playbook_settings": away_playbook_settings  # ✅ Preserve from database
        }
    }

    # ✅ UNIFIED STRUCTURE: All team data in teams object, referenced by home_team_id/away_team_id
    # ✅ Eliminated home_team/away_team duplication - single source of truth in teams object
    return {
        # Game metadata
        "game_id": str(game.game_id) if hasattr(game, 'game_id') else None,
        "quarter": game.quarter,
        "is_final": game.quarter > 4 and game.score.get(game.home_team.name, 0) != game.score.get(game.away_team.name, 0),
        "opening_tip_winner": game.game_state.get("opening_tip_winner"),
        # Home crowd (rolled once per game; persist so DB load / timeout resume does not re-roll)
        "home_crowd_factor": game.game_state.get("home_crowd_factor"),
        "home_crowd_away_shot_threshold_delta": game.game_state.get("home_crowd_away_shot_threshold_delta"),
        "home_crowd_home_shot_threshold_delta": game.game_state.get("home_crowd_home_shot_threshold_delta"),
        "game_stats_initialized": game.game_state.get("game_stats_initialized", False),  # Preserve stats initialization flag
        "user_team_side": game.game_state.get("user_team_side"),  # ✅ SS&S: Save user_team_side for persistent override checking
        "no_defender_shots": int(game.game_state.get("no_defender_shots", 0) or 0),
        # ✅ TIMEOUT/FOUL_OUT: Only write when truthy so normal saves don't overwrite DB and wipe resume state (we $unset on actual resume in main.py)
        **({"timeout_next_play_type": game.game_state["timeout_next_play_type"]} if game.game_state.get("timeout_next_play_type") else {}),
        **({"timeout_offense_team_id": game.game_state["timeout_offense_team_id"]} if game.game_state.get("timeout_offense_team_id") else {}),
        **({"timeout_trace_id": game.game_state["timeout_trace_id"]} if game.game_state.get("timeout_trace_id") else {}),
        # ✅ FREE_THROW timeout resume: persist FT state so first simulate_turn creates the FT turn
        **(
            {
                "timeout_free_throws_remaining": game.game_state.get("free_throws_remaining"),
                "timeout_free_throws": game.game_state.get("free_throws"),
                "timeout_shooter_id": getattr(game.game_state.get("shooter"), "player_id", None),
                "timeout_one_and_one": game.game_state.get("one_and_one", False),
            }
            if game.game_state.get("timeout_next_play_type") == "FREE_THROW"
            else {}
        ),
        "clock": game.game_state.get("clock", "8:00"),  # ✅ TIMEOUT: Save clock for resume (same as quarter breaks)
        "time_remaining": game.game_state.get("time_remaining", 480),  # ✅ TIMEOUT: Save time_remaining for resume (same as quarter breaks)
        "shot_clock_remaining": game.game_state.get("shot_clock_remaining", min(30, game.game_state.get("time_remaining", 480))),
        "man_defense_matchups": game.game_state.get("man_defense_matchups", {}),  # ✅ MAN DEFENSE MATCHUPS: User team matchups for persistence
        "man_defense_matchups_computer": game.game_state.get("man_defense_matchups_computer", {}),  # Computer team matchups (default if missing)
        "rim_runner_by_team_id": game.game_state.get("rim_runner_by_team_id") or {},
        "computer_timeouts": serialize_computer_timeouts(game.game_state.get("computer_timeouts")),  # ✅ COMPUTER TIMEOUT: Per-quarter count + checked_conditions (enforces max 1 per quarter Q1–Q3 after DB load)
        
        # Top-level team IDs for team lookup (required for accessing teams object)
        "home_team_id": home_key,
        "away_team_id": away_key,
        
        # Top-level score map for backward compatibility (some code expects summary["score"])
        # Build from teams object to ensure consistency
        "score": {
            teams_obj[home_key]["name"]: teams_obj[home_key]["score"],
            teams_obj[away_key]["name"]: teams_obj[away_key]["score"]
        },
        
        # ✅ UNIFIED TEAMS OBJECT: Single source of truth for all team data
        # Access via: teams[home_team_id] or teams[away_team_id]
        # Contains: name, team_id, mascot, colors, score, points_by_quarter, team_fouls, timeouts,
        #           attributes, box_score, totals, strategy_settings, strategy_calls, plays, scouting, playbook_settings
        "teams": teams_obj,
        
        # Game data
        "turns": turns,  # Animations excluded for database saves
        # text_log is only needed for live/front-end viewing (legacy/debug play-by-play).
        # Do not persist it to Mongo for normal saves to avoid DB bloat.
        **({"text_log": game.text_log} if not exclude_animations else {}),
        
        # Players array (for frontend rendering and stats persistence)
        "players": players,
    }

def check_defensive_foul(self, defender, is_three):
    """
    Returns True if a defensive foul is committed during a shot attempt.
    """
    if not defender:
        return False  # No defender, no foul

    attrs = defender.attributes
    discipline = attrs.get("ND", 5)  # ND = "No Dumb Fouls"

    # Base foul rate: higher on 3pt shots, but reduced by discipline
    base_foul_chance = 0.06 if is_three else 0.045
    foul_chance = max(0.01, base_foul_chance - (discipline * 0.0045))

    return random.random() < foul_chance

def calculate_gravity_score(attrs):
    return (
        attrs["SH"] * 0.3 +
        attrs["SC"] * 0.3 +
        attrs["IQ"] * 0.4
    )


def calculate_ball_handling_score(player):
    """
    Calculate ball handling score for an offensive player.
    Used for turnover and steal attempt calculations.
    
    Formula: (BH * 0.5 + AG * 0.2 + IQ * 0.2 + CH * 0.1) * random(1, 6)
    
    Args:
        player: Player object with attributes
    
    Returns:
        int: Ball handling score
    """
    attrs = player.attributes
    return (
        attrs["BH"] * 0.5 +
        attrs["AG"] * 0.2 +
        attrs["IQ"] * 0.2 +
        attrs["CH"] * 0.1
    ) * random.randint(1, 6)


def calculate_defender_pressure_score(defender, defense_call):
    """
    Calculate defensive pressure score for a defender.
    Used for turnover and steal attempt calculations.
    
    Formula: (OD * 0.3 + AG * 0.3 + IQ * 0.2 + CH * 0.2) * random(1, 6)
    Zone defense modifier: pressure *= 0.9
    
    Args:
        defender: Defender player object with attributes
        defense_call: Defense playcall string (e.g., "Man", "2-3 Zone")
    
    Returns:
        int: Defender pressure score
    """
    from BackEnd.utils.defense_utils import is_zone_defense
    
    def_attrs = defender.attributes
    pressure = (
        def_attrs["OD"] * 0.3 +
        def_attrs["AG"] * 0.3 +
        def_attrs["IQ"] * 0.2 +
        def_attrs["CH"] * 0.2
    ) * random.randint(1, 6)
    
    if is_zone_defense(defense_call):
        pressure *= 0.9
    
    return int(pressure)

def get_away_player_coords(playerCoords):
        
        """
        Gets individual player coordinates if the away team has the ball.
        Flips coordinates around the center of the court (x=50).
        """

        ySpot = playerCoords["y"]    
        coordsX = playerCoords["x"]
        # Flip around center: if x=30 (home side), flip to x=70 (away side)
        # Formula: new_x = 100 - old_x
        xSpot = 100 - coordsX
        playerCoords = {"x": xSpot, "y": ySpot}

        return playerCoords

def getAwayTeamCoords(coordsDict):
       for position, coords in coordsDict.items():
           ySpot = coords["y"]
           coordsX = coords["x"]
           # Flip around center: if x=30 (home side), flip to x=70 (away side)
           # Formula: new_x = 100 - old_x
           xSpot = 100 - coordsX
           coordsDict[position] = {"x": xSpot, "y": ySpot}
       return coordsDict


ANIMATION_CLAMP_BOUNDS: Dict[str, float] = {
    "min_x": 5.0,
    "max_x": 95.0,
    "min_y": 2.0,
    "max_y": 49.0,
}

ANIMATION_CLAMP_EXEMPT_RESULT_TYPES = frozenset({
    "SIDE_INBOUND",
    "BASELINE_INBOUND",
    "TIMEOUT",
})


def is_animation_clamp_exempt(result_type: Optional[str], context: Optional[Dict[str, Any]] = None) -> bool:
    """Return True when a turn payload should skip backend animation coordinate clamping."""
    if isinstance(context, dict) and context.get("force_exempt") is True:
        return True
    return result_type in ANIMATION_CLAMP_EXEMPT_RESULT_TYPES


def _clamp_animation_coord_value(value: Any, lower: float, upper: float) -> Any:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return value
    return min(upper, max(lower, float(value)))


def clamp_animation_grid_coords(
    coords: Optional[Dict[str, Any]],
    result_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Clamp one grid coordinate pair to canonical animation bounds."""
    if not isinstance(coords, dict):
        return coords
    if is_animation_clamp_exempt(result_type, context):
        return dict(coords)
    return {
        **coords,
        "x": _clamp_animation_coord_value(coords.get("x"), ANIMATION_CLAMP_BOUNDS["min_x"], ANIMATION_CLAMP_BOUNDS["max_x"]),
        "y": _clamp_animation_coord_value(coords.get("y"), ANIMATION_CLAMP_BOUNDS["min_y"], ANIMATION_CLAMP_BOUNDS["max_y"]),
    }


def _sanitize_animation_rows(rows: Any, result_type: Optional[str]) -> Any:
    if not isinstance(rows, list):
        return rows
    for row in rows:
        if not isinstance(row, dict):
            continue
        end = row.get("end")
        if isinstance(end, dict):
            row["end"] = clamp_animation_grid_coords(end, result_type)
        movement = row.get("movement")
        if isinstance(movement, list):
            for step in movement:
                if not isinstance(step, dict):
                    continue
                coords = step.get("coords")
                if isinstance(coords, dict):
                    step["coords"] = clamp_animation_grid_coords(coords, result_type)
    return rows


def sanitize_turn_animation_payload(turn: Any, context: Optional[Dict[str, Any]] = None) -> Any:
    """
    Return a sanitized copy of a turn payload where animation-facing coordinates are clamped.

    Clamp policy:
      - x: 9..91
      - y: 2..49
    Exempt result types:
      - SIDE_INBOUND
      - BASELINE_INBOUND
      - TIMEOUT
    """
    if not isinstance(turn, dict):
        return turn

    payload = deepcopy(turn)
    result_type = payload.get("result_type")

    if result_type == "BATCH" and isinstance(payload.get("batch_turns"), list):
        payload["batch_turns"] = [
            sanitize_turn_animation_payload(t, context=context) if isinstance(t, dict) else t
            for t in payload["batch_turns"]
        ]
        return payload

    for key in ("oDestinations", "dDestinations", "offense_getback_coords", "defense_release_coords"):
        block = payload.get(key)
        if not isinstance(block, dict):
            continue
        payload[key] = {
            k: clamp_animation_grid_coords(v, result_type, context=context) if isinstance(v, dict) else v
            for k, v in block.items()
        }

    # Player-only clamp policy: leave ball payload coordinates untouched.
    # Ball motion/spot fields are consumed by dedicated ball animation logic.

    payload["animations"] = _sanitize_animation_rows(payload.get("animations"), result_type)

    final_turn_meta = payload.get("final_turn_meta")
    if isinstance(final_turn_meta, dict):
        coords_by_step = final_turn_meta.get("ball_handler_coords_by_step")
        if isinstance(coords_by_step, list):
            final_turn_meta["ball_handler_coords_by_step"] = [
                clamp_animation_grid_coords(c, result_type, context=context) if isinstance(c, dict) else c
                for c in coords_by_step
            ]

    return payload


# Turn payload keys: player_id -> {x, y} in HOME grid. Later keys override earlier for same id.
TURN_COORDS_OVERLAY_KEYS: Tuple[str, ...] = (
    "defense_release_coords",
    "offense_getback_coords",
)


def _norm_player_id(pid: Any) -> Optional[str]:
    if pid is None:
        return None
    return str(pid)


def _final_xy_from_animation_row(anim: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Resolve final grid position from one animation row (matches FE last-step / end usage)."""
    if not isinstance(anim, dict):
        return None
    end = anim.get("end")
    if isinstance(end, dict):
        x, y = end.get("x"), end.get("y")
        if x is not None and y is not None:
            return {"x": float(x), "y": float(y)}
    movement = anim.get("movement") or []
    for step in reversed(movement):
        if not isinstance(step, dict):
            continue
        coords = step.get("coords")
        if isinstance(coords, dict):
            x, y = coords.get("x"), coords.get("y")
            if x is not None and y is not None:
                return {"x": float(x), "y": float(y)}
        x, y = step.get("x"), step.get("y")
        if x is not None and y is not None:
            return {"x": float(x), "y": float(y)}
    return None


def apply_coords_from_animations_list(game: Any, animations: Optional[List[Any]]) -> None:
    """
    Apply final positions from an animation list to matching lineup players only.
    Used mid-resolution (e.g. before resolve_shot) and inside sync_lineup_coords_from_turn.
    """
    if not animations:
        return
    for anim in animations:
        if not isinstance(anim, dict):
            continue
        pid = anim.get("playerId")
        if pid is None:
            continue
        final = _final_xy_from_animation_row(anim)
        if final is None:
            continue
        ns = _norm_player_id(pid)
        if not ns:
            continue
        for team in (game.home_team, game.away_team):
            for player in (team.lineup or {}).values():
                if player is None:
                    continue
                if _norm_player_id(getattr(player, "player_id", None)) == ns:
                    player.coords = dict(final)
                    break


def sync_lineup_coords_from_turn(game: Any, turn_result: Dict[str, Any]) -> None:
    """
    After a turn is finalized, align all ten active players' ``Player.coords`` with the
    same spatial data the frontend uses: carry-forward, then animation finals, then
    explicit overlay maps on the turn (get-back / release).
    """
    if game is None or not isinstance(turn_result, dict):
        return

    positions: Dict[str, Dict[str, float]] = {}
    for team in (game.home_team, game.away_team):
        for player in (team.lineup or {}).values():
            if player is None or getattr(player, "player_id", None) is None:
                continue
            pid = _norm_player_id(player.player_id)
            if not pid:
                continue
            c = getattr(player, "coords", None) or {}
            if isinstance(c, dict) and c.get("x") is not None and c.get("y") is not None:
                positions[pid] = {"x": float(c["x"]), "y": float(c["y"])}
            else:
                positions[pid] = {"x": 50.0, "y": 25.0}

    animations = turn_result.get("animations")
    if isinstance(animations, list):
        for anim in animations:
            if not isinstance(anim, dict):
                continue
            pid = anim.get("playerId")
            if pid is None:
                continue
            final = _final_xy_from_animation_row(anim)
            if final is None:
                continue
            ns = _norm_player_id(pid)
            if ns:
                positions[ns] = dict(final)

    for key in TURN_COORDS_OVERLAY_KEYS:
        block = turn_result.get(key)
        if not isinstance(block, dict):
            continue
        for pid, coords in block.items():
            if not isinstance(coords, dict):
                continue
            if coords.get("x") is None or coords.get("y") is None:
                continue
            ns = _norm_player_id(pid)
            if ns:
                positions[ns] = {"x": float(coords["x"]), "y": float(coords["y"])}

    for team in (game.home_team, game.away_team):
        for player in (team.lineup or {}).values():
            if player is None or getattr(player, "player_id", None) is None:
                continue
            pid = _norm_player_id(player.player_id)
            if pid and pid in positions:
                player.coords = dict(positions[pid])


def serialize_lineup(lineup_dict):
    return {
        pos: player.player_id if hasattr(player, 'player_id') else player
        for pos, player in lineup_dict.items()
    }


def calculate_charge(shooter, defender, off_team, def_team):
    """
    Calculate whether a charge or blocking foul occurs on a drive.

    Uses shooter/defender attributes, team chemistry, and discipline to compute
    offense/defense scores and a reconciliation value; thresholds determine the call.

    Returns:
        str | None: "CHARGE" (foul on offense), "BLOCKING_FOUL" (foul on defense),
            or None (no call, continue with shot).
    """
    if not shooter or not defender:
        return None
    attrs_shooter = getattr(shooter, "attributes", None) or {}
    attrs_defender = getattr(defender, "attributes", None) or {}
    if not attrs_shooter or not attrs_defender:
        return None

    # Offense score = shooter (AG*0.6 + IQ*0.2 + CH*0.2) * random(1, 6)
    off_base = (
        attrs_shooter.get("AG", 0) * 0.6
        + attrs_shooter.get("IQ", 0) * 0.2
        + attrs_shooter.get("CH", 0) * 0.2
    )
    offense_score = off_base * random.randint(1, 6)

    # Defense score = defender (AG*0.5 + OD*0.3 + IQ*0.1 + CH*0.1) * random(1, 6)
    def_base = (
        attrs_defender.get("AG", 0) * 0.5
        + attrs_defender.get("OD", 0) * 0.3
        + attrs_defender.get("IQ", 0) * 0.1
        + attrs_defender.get("CH", 0) * 0.1
    )
    defense_score = def_base * random.randint(1, 6)

    # Chemistry factor per team = int(team_chemistry / 4)
    off_chemistry = int((off_team.team_attributes.get("team_chemistry", 0) or 0) / 4)
    def_chemistry = int((def_team.team_attributes.get("team_chemistry", 0) or 0) / 4)

    def _discipline_factor(team, chemistry_factor):
        discipline = team.team_attributes.get("discipline", 0) or 0
        if discipline >= 0:
            return discipline * random.randint(0, max(0, chemistry_factor))
        # Invert chemistry factor on 1–6 scale: 1->6, 2->5, 3->4, 4->3, 5->2, 6->1
        cf = min(max(chemistry_factor, 1), 6)
        inverted = 7 - cf
        return discipline * random.randint(0, inverted)

    offense_score += _discipline_factor(off_team, off_chemistry)
    defense_score += _discipline_factor(def_team, def_chemistry)

    reconciliation = offense_score - defense_score

    if reconciliation < CHARGE_THRESHOLD:
        return "CHARGE"
    if reconciliation > BLOCKING_FOUL_THRESHOLD:
        return "BLOCKING_FOUL"
    return None
