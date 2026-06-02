"""
Rim Runner fast break — DREB outlet → burst → PG read → pass / HCO / shot / intercept / bat OOB.

See docs discussion + Fast_Break_System. Covert Release path remains in resolve_fast_break_logic.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import (
    AWAY_RIM_COORDS,
    HCO_STRING_SPOTS,
    HOME_RIM_COORDS,
    USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR,
)
from BackEnd.constants.fast_break_play_types import RIM_RUNNER, TRIANGLE
from BackEnd.models.animator import Animator
from BackEnd.utils.shared import (
    apply_coords_from_animations_list,
    calc_ag_segment_seconds,
    calculate_outlet_pass_score,
    get_away_player_coords,
    unpack_game_context,
)
from BackEnd.utils.shared_defense import calculate_defender_coords
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

TRIANGLE_LANE_TARGETS = (
    "lower lowPost",
    "upper lowPost",
    "lower midPost",
    "upper midPost",
    "lower highPost",
    "upper highPost",
    "basketSpot",
    "midLane",
    "topLane",
    "lower bird",
    "upper bird",
    "lower apex",
    "upper apex",
)


def _spot_coords(spot: str, is_away_offense: bool) -> Dict[str, float]:
    coords = dict(HCO_STRING_SPOTS.get(spot, {"x": 50, "y": 25}))
    if is_away_offense:
        coords = get_away_player_coords(coords)
    return {"x": float(coords["x"]), "y": float(coords["y"])}


def _triangle_half_from_y(y: float) -> str:
    return "upper" if float(y) > 25.0 else "lower"


def _rr_half_from_y(y: float) -> str:
    return "upper" if float(y) > 24.0 else "lower"


def _triangle_same_half_spot(prefix: str, half: str) -> str:
    return f"{half} {prefix}"


def _triangle_other_half(half: str) -> str:
    return "lower" if half == "upper" else "upper"


def _player_dict_coords(player: Any) -> Dict[str, float]:
    return {"x": _player_x(player), "y": _player_y(player)}


def _resolve_triangle_offense_roles(
    off_lineup: Dict[str, Any],
    *,
    rim_runner: Any,
    ball_handler: Any,
    rebounder: Any,
    is_away_offense: bool,
) -> Dict[str, Any]:
    rr_id = str(getattr(rim_runner, "player_id", None)) if rim_runner else None
    bh_id = str(getattr(ball_handler, "player_id", None)) if ball_handler else None
    reb_id = str(getattr(rebounder, "player_id", None)) if rebounder else None
    offense_players = [p for p in off_lineup.values() if p is not None]

    corner_candidates = []
    for player in offense_players:
        pid = str(getattr(player, "player_id", None))
        if pid in {rr_id, bh_id, reb_id}:
            continue
        corner_candidates.append(player)

    basket_x = _basket_x_for_offense(is_away_offense)
    if len(corner_candidates) < 2:
        pool = [p for p in offense_players if str(getattr(p, "player_id", None)) not in {rr_id, bh_id}]
        pool.sort(key=lambda p: abs(_player_x(p) - basket_x))
        corner_candidates = pool[:2]

    corner_candidates = corner_candidates[:2]
    trailer = rebounder
    if trailer is None or str(getattr(trailer, "player_id", None)) == bh_id:
        trailer_pool = [
            p for p in offense_players
            if str(getattr(p, "player_id", None)) not in {rr_id, bh_id}
            and all(str(getattr(p, "player_id", None)) != str(getattr(cp, "player_id", None)) for cp in corner_candidates)
        ]
        trailer = trailer_pool[0] if trailer_pool else rebounder

    if len(corner_candidates) == 2:
        c0, c1 = corner_candidates
        y0, y1 = _player_y(c0), _player_y(c1)
        if y0 < y1:
            lower_corner, upper_corner = c0, c1
        elif y1 < y0:
            lower_corner, upper_corner = c1, c0
        else:
            lower_corner, upper_corner = random.sample(corner_candidates, 2)
    else:
        lower_corner = upper_corner = corner_candidates[0] if corner_candidates else None

    return {
        "lower_corner": lower_corner,
        "upper_corner": upper_corner,
        "trailer": trailer,
    }


def _resolve_triangle_setup_payload(
    *,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    ball_handler: Any,
    rim_runner: Any,
    rebounder: Any,
    is_away_offense: bool,
    fb_opp: int,
) -> Dict[str, Any]:
    offense_roles = _resolve_triangle_offense_roles(
        off_lineup,
        rim_runner=rim_runner,
        ball_handler=ball_handler,
        rebounder=rebounder,
        is_away_offense=is_away_offense,
    )
    bh_half = _triangle_half_from_y(_player_y(ball_handler))
    other_half = _triangle_other_half(bh_half)
    bh_spot = _triangle_same_half_spot("wing", bh_half)
    rr_spot = _triangle_same_half_spot("lowPost", bh_half)
    trailer_spot = _triangle_same_half_spot("wing", other_half)
    lower_corner_spot = "lower corner"
    upper_corner_spot = "upper corner"

    corners = []
    if offense_roles["lower_corner"] is not None:
        corners.append(
            {
                "player_id": getattr(offense_roles["lower_corner"], "player_id", None),
                "spot": lower_corner_spot,
                "to": _spot_coords(lower_corner_spot, is_away_offense),
                "burst": False,
            }
        )
    if offense_roles["upper_corner"] is not None:
        corners.append(
            {
                "player_id": getattr(offense_roles["upper_corner"], "player_id", None),
                "spot": upper_corner_spot,
                "to": _spot_coords(upper_corner_spot, is_away_offense),
                "burst": False,
            }
        )

    bh_to = _spot_coords(bh_spot, is_away_offense)
    rr_to = _spot_coords(rr_spot, is_away_offense)
    trailer = offense_roles["trailer"]
    trailer_to = _spot_coords(trailer_spot, is_away_offense) if trailer is not None else None

    defense_players = [p for p in def_lineup.values() if p is not None]
    basket_x = _basket_x_for_offense(is_away_offense)
    defense_sorted = sorted(defense_players, key=lambda d: abs(_player_x(d) - basket_x))
    rr_defender = defense_sorted[0] if defense_sorted else None
    bh_defender = defense_sorted[1] if len(defense_sorted) > 1 else None
    helper_defenders = defense_sorted[2:]
    target_basket = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    rr_def_to = None
    bh_def_to = None
    if rr_defender is not None:
        rr_def_to = calculate_defender_coords(
            rr_to,
            target_basket,
            "normal",
            spot=rr_spot,
            ball_handler_coords=bh_to,
            is_ball_handler=False,
            ball_spot=bh_spot,
        )
    if bh_defender is not None:
        bh_def_to = calculate_defender_coords(
            bh_to,
            target_basket,
            "normal",
            spot=bh_spot,
            ball_handler_coords=bh_to,
            is_ball_handler=True,
            ball_spot=bh_spot,
        )

    helper_moves = []
    helper_burst = fb_opp > 5
    for defender in helper_defenders:
        lane_spot = random.choice(TRIANGLE_LANE_TARGETS)
        helper_moves.append(
            {
                "player_id": getattr(defender, "player_id", None),
                "spot": lane_spot,
                "to": _spot_coords(lane_spot, is_away_offense),
                "burst": helper_burst,
            }
        )

    same_side_corner = next((c for c in corners if c["spot"].startswith(bh_half)), None)
    opposite_side_corner = next((c for c in corners if not c["spot"].startswith(bh_half)), None)

    return {
        "is_away_offense": is_away_offense,
        "same_side": bh_half,
        "ball_handler_id": getattr(ball_handler, "player_id", None),
        "ball_handler_spot": bh_spot,
        "ball_handler_to": bh_to,
        "rim_runner_id": getattr(rim_runner, "player_id", None),
        "rim_runner_spot": rr_spot,
        "rim_runner_to": rr_to,
        "trailer_id": getattr(trailer, "player_id", None) if trailer is not None else None,
        "trailer_spot": trailer_spot,
        "trailer_to": trailer_to,
        "corner_players": corners,
        "same_side_corner_id": same_side_corner["player_id"] if same_side_corner else None,
        "same_side_corner_spot": same_side_corner["spot"] if same_side_corner else None,
        "same_side_corner_to": same_side_corner["to"] if same_side_corner else None,
        "opposite_side_corner_id": opposite_side_corner["player_id"] if opposite_side_corner else None,
        "opposite_side_corner_spot": opposite_side_corner["spot"] if opposite_side_corner else None,
        "opposite_side_corner_to": opposite_side_corner["to"] if opposite_side_corner else None,
        "rr_defender_id": getattr(rr_defender, "player_id", None) if rr_defender else None,
        "rr_defender_to": rr_def_to,
        "bh_defender_id": getattr(bh_defender, "player_id", None) if bh_defender else None,
        "bh_defender_to": bh_def_to,
        "helper_defenders": helper_moves,
    }


def _triangle_find_player(lineup: Dict[str, Any], player_id: Any) -> Optional[Any]:
    pid_s = str(player_id) if player_id is not None else None
    for player in lineup.values():
        if player is not None and str(getattr(player, "player_id", None)) == pid_s:
            return player
    return None


def _triangle_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    return ((float(a["x"]) - float(b["x"])) ** 2 + (float(a["y"]) - float(b["y"])) ** 2) ** 0.5


def _triangle_corner_shot_defender(def_lineup: Dict[str, Any], shooter_coords: Dict[str, float]) -> Optional[Any]:
    best = None
    best_dist = float("inf")
    for defender in def_lineup.values():
        if defender is None:
            continue
        dist = _triangle_distance(_player_dict_coords(defender), shooter_coords)
        if dist <= 6.0 and dist < best_dist:
            best = defender
            best_dist = dist
    return best


def _triangle_build_turn_result(
    *,
    game: Any,
    game_state: dict,
    off_team: Any,
    def_team: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    fb_roles: Dict[str, Any],
    ball_handler: Any,
    rim_runner: Any,
    setup_payload: Dict[str, Any],
    branch: str,
    fb_open: bool,
    custom_corner_override: bool = False,
) -> Dict[str, Any]:
    animator = Animator(game)
    fb_roles["triangle_sequence"] = True
    fb_roles["triangle_branch"] = branch
    fb_roles["triangle_setup_phase"] = setup_payload

    same_side_corner_id = setup_payload.get("same_side_corner_id")
    same_side_corner = _triangle_find_player(off_lineup, same_side_corner_id)
    ball_handler_spot = setup_payload.get("ball_handler_spot")
    rim_runner_spot = setup_payload.get("rim_runner_spot")
    same_side_corner_spot = setup_payload.get("same_side_corner_spot")
    shot_roles: Dict[str, Any]

    if branch == "triangle_rr_post":
        shooter = rim_runner
        passer = ball_handler
        shot_type = "inside"
        shooter_spot = rim_runner_spot
        defender = _triangle_find_player(def_lineup, setup_payload.get("rr_defender_id"))
        shot_spot = setup_payload.get("rim_runner_to")
    elif branch == "triangle_corner_three":
        shooter = same_side_corner
        passer = ball_handler
        shot_type = "outside"
        shooter_spot = same_side_corner_spot
        shot_spot = setup_payload.get("same_side_corner_to")
        defender = _triangle_corner_shot_defender(def_lineup, shot_spot)
    elif branch == "triangle_bh_wing_three":
        shooter = ball_handler
        passer = None
        shot_type = "outside"
        shooter_spot = ball_handler_spot
        shot_spot = setup_payload.get("ball_handler_to")
        defender = _triangle_find_player(def_lineup, setup_payload.get("bh_defender_id"))
    elif branch == "triangle_bh_drive":
        drive_to = _spot_coords(_triangle_same_half_spot("lowPost", setup_payload["same_side"]), setup_payload["is_away_offense"])
        mid_lane = _spot_coords("midLane", setup_payload["is_away_offense"])
        setup_payload["triangle_drive_to"] = drive_to
        setup_payload["triangle_rr_drive_to"] = mid_lane
        shooter = ball_handler
        passer = None
        shot_type = "attack"
        shooter_spot = _triangle_same_half_spot("lowPost", setup_payload["same_side"])
        shot_spot = drive_to
        defender = _triangle_find_player(def_lineup, setup_payload.get("bh_defender_id"))
    elif branch == "triangle_drive_rr_feed":
        drive_to = _spot_coords(_triangle_same_half_spot("lowPost", setup_payload["same_side"]), setup_payload["is_away_offense"])
        mid_lane = _spot_coords("midLane", setup_payload["is_away_offense"])
        setup_payload["triangle_drive_to"] = drive_to
        setup_payload["triangle_rr_drive_to"] = mid_lane
        shooter = rim_runner
        passer = ball_handler
        shot_type = "inside"
        shooter_spot = "midLane"
        shot_spot = mid_lane
        defender = _triangle_find_player(def_lineup, setup_payload.get("rr_defender_id"))
    elif branch == "triangle_drive_corner_kick":
        drive_to = _spot_coords(_triangle_same_half_spot("lowPost", setup_payload["same_side"]), setup_payload["is_away_offense"])
        mid_lane = _spot_coords("midLane", setup_payload["is_away_offense"])
        setup_payload["triangle_drive_to"] = drive_to
        setup_payload["triangle_rr_drive_to"] = mid_lane
        shooter = same_side_corner
        passer = ball_handler
        shot_type = "outside"
        shooter_spot = same_side_corner_spot
        shot_spot = setup_payload.get("same_side_corner_to")
        defender = _triangle_corner_shot_defender(def_lineup, shot_spot)
    else:
        raise ValueError(f"Unsupported triangle branch: {branch}")

    if shooter is None:
        raise ValueError(f"Triangle branch missing shooter: {branch}")

    defender_count = 1 if defender is not None else 0
    fb_roles["ball_handler"] = ball_handler
    fb_roles["ball_handler_id"] = getattr(ball_handler, "player_id", None)
    fb_roles["passer"] = passer
    fb_roles["shooter"] = shooter
    fb_roles["defender"] = defender
    fb_roles["defender_count"] = defender_count

    shot_roles = {
        "shooter": shooter,
        "passer": passer,
        "screener": None,
        "defender": defender,
        "shot_type": shot_type,
        "is_fast_break": True,
        "motion_playcall": "Outside" if shot_type == "outside" else "Attack",
        "defender_count": defender_count,
        "shot_spot": {"x": float(shot_spot["x"]), "y": float(shot_spot["y"])},
        "triangle_branch": branch,
    }

    if custom_corner_override:
        game_state["fast_break_shot_threshold_override"] = 190 - int(
            off_team.team_attributes.get("fb_efficiency", 0) or 0
        )
        game_state["fast_break_force_threshold_no_three_bonus"] = True
    elif branch in {"triangle_rr_post", "triangle_drive_rr_feed"} and defender_count == 0:
        game_state["fast_break_shot_threshold_override"] = 1

    rr_snap_roles = {**shot_roles, "ball_handler": ball_handler}
    rr_snap = build_fast_break_pre_shot_snapshot(
        game, off_lineup, def_lineup, rr_snap_roles, "fb_triangle_pre_shot"
    )
    fb_animations = animator.capture_fast_break_animation(fb_roles, False, None)
    turn_result = game.shot_manager.resolve_shot(shot_roles)
    game_state.pop("fast_break_shot_threshold_override", None)
    game_state.pop("fast_break_force_threshold_no_three_bonus", None)
    attach_position_snapshots(turn_result, [rr_snap])
    turn_result["animations"] = fb_animations
    turn_result["roles"] = fb_roles
    turn_result["fast_break"] = True
    turn_result["fast_break_play"] = TRIANGLE
    turn_result["text"] = "Fast Break! " + turn_result.get("text", "")
    turn_result["triangle_branch"] = branch
    turn_result["triangle_sequence"] = True
    _apply_rr_decision_metadata(turn_result, pass_attempted=False, fb_open=fb_open)
    if turn_result.get("result_type") == "MAKE":
        off_team.scouting_data["offense"]["Fast_Break_Success"] = (
            off_team.scouting_data["offense"].get("Fast_Break_Success", 0) + 1
        )
        from BackEnd.constants.fast_break_play_types import ensure_fast_break_plays

        ensure_fast_break_plays(off_team.scouting_data["offense"])[TRIANGLE]["S"] += 1
    elif turn_result.get("result_type") == "MISS":
        def_team.scouting_data["defense"]["vs_Fast_Break"]["success"] = (
            def_team.scouting_data["defense"]["vs_Fast_Break"].get("success", 0) + 1
        )
    _record_fast_break_stats(fb_roles, turn_result, game)
    apply_fast_break_cg_time(turn_result, shot_attempted=True)
    return turn_result


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


def _resolve_rr_burst_destination(
    *,
    rr_x0: float,
    rr_y0: float,
    outlet_receiver_target_x: float,
    dx_burst: int,
    is_away_offense: bool,
    most_recent_shot_turn: Optional[dict],
) -> Tuple[Dict[str, float], Optional[float]]:
    rr_half = _rr_half_from_y(rr_y0)
    rr_wing_to = _spot_coords(f"{rr_half} wing", is_away_offense)
    x_dir = -1 if is_away_offense else 1

    dynamic_base_x = None
    try:
        bounce_x = float((most_recent_shot_turn or {}).get("ball_bounce_x"))
    except (TypeError, ValueError):
        bounce_x = None
    if bounce_x is not None:
        if (not is_away_offense and 25 < bounce_x < 50) or (is_away_offense and 50 < bounce_x < 75):
            dynamic_base_x = float(outlet_receiver_target_x)

    base_x = dynamic_base_x if dynamic_base_x is not None else float(rr_x0)
    raw_x = float(base_x) + x_dir * dx_burst
    wing_x = float(rr_wing_to["x"])
    if is_away_offense:
        clamped_x = max(raw_x, wing_x)
    else:
        clamped_x = min(raw_x, wing_x)

    return (
        {
            "x": float(max(4, min(97, int(round(clamped_x))))),
            "y": float(rr_wing_to["y"]),
        },
        dynamic_base_x,
    )


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


def _apply_universal_geometry_for_rr_shot(
    *,
    shooter: Any,
    roles: Dict[str, Any],
    fb_roles: Dict[str, Any],
    fb_animations: List[Dict[str, Any]],
    game: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    is_away_offense: bool,
    stopper_id: Optional[str],
    outlet_defender_id: Optional[str],
) -> None:
    """Apply the universal FB shot geometry helper to an RR shot in-flight.

    Mutates ``roles``, ``fb_roles``, ``fb_animations``, and
    ``game.game_state`` in place:

    - Sets ``roles["shot_spot"]`` to the helper's shooter_target.
    - Sets ``roles["defender"]`` to the first arriver (or None if uncontested).
    - Sets ``fast_break_shot_threshold_override`` = 1 when uncontested
      (matches the existing "no defender → threshold 1 = always make"
      pattern at line 1128; same effect as Steal-FB's auto-make rule).
    - Updates ``fb_animations`` end coords for the shooter and racing
      defenders so the schema emitter renders the new positions. The
      stopper and outlet defender are NOT updated (they stay at their
      end-of-preceding-step positions per spec).

    Race pool per spec: all defenders EXCEPT the stopper AND the outlet
    defender. See docs/projects/Fast_Break_System.md (universal helper
    section) and Step_By_Step_System.md (RR resolution stages).

    No-op (caller does nothing different) if the helper returns no
    geometry — caller falls back to whatever was on ``roles`` already.
    """
    from BackEnd.utils.fast_break_shot_geometry import compute_fb_shot_geometry

    if shooter is None:
        return

    shooter_id = getattr(shooter, "player_id", None)
    if shooter_id is None:
        return
    shooter_id = str(shooter_id)

    # Race pool: all defenders EXCEPT stopper + outlet defender.
    excluded: set = set()
    if stopper_id is not None:
        excluded.add(str(stopper_id))
    if outlet_defender_id is not None:
        excluded.add(str(outlet_defender_id))

    available_defenders: List[Any] = []
    defender_starts: Dict[str, Dict[str, float]] = {}
    for d in def_lineup.values():
        if d is None:
            continue
        d_id = getattr(d, "player_id", None)
        if d_id is None:
            continue
        d_id_str = str(d_id)
        if d_id_str in excluded:
            continue
        available_defenders.append(d)
        # Start coord = end of preceding step. The animator captured
        # animations represent the FB trajectory up to this point; their
        # "end" field is each player's position at end of the prior step.
        anim_end = None
        for entry in fb_animations:
            if entry.get("playerId") == d_id_str or entry.get("playerId") == d_id:
                anim_end = entry.get("end") or entry.get("end_coords")
                if isinstance(anim_end, dict):
                    break
        if isinstance(anim_end, dict) and "x" in anim_end and "y" in anim_end:
            defender_starts[d_id_str] = {
                "x": float(anim_end["x"]),
                "y": float(anim_end["y"]),
            }
        else:
            # Fallback: live coords on the player object.
            raw = getattr(d, "coords", None) or {}
            defender_starts[d_id_str] = {
                "x": float(raw.get("x", 50.0)),
                "y": float(raw.get("y", 25.0)),
            }

    # Shooter start: prefer animation end; fall back to live coords.
    shooter_start: Dict[str, float] = {"x": 50.0, "y": 25.0}
    for entry in fb_animations:
        if entry.get("playerId") == shooter_id or entry.get("playerId") == getattr(shooter, "player_id", None):
            anim_end = entry.get("end") or entry.get("end_coords")
            if isinstance(anim_end, dict) and "x" in anim_end and "y" in anim_end:
                shooter_start = {"x": float(anim_end["x"]), "y": float(anim_end["y"])}
                break
    else:
        raw = getattr(shooter, "coords", None) or {}
        if isinstance(raw, dict) and "x" in raw and "y" in raw:
            shooter_start = {"x": float(raw["x"]), "y": float(raw["y"])}

    geometry = compute_fb_shot_geometry(
        shooter=shooter,
        shooter_start=shooter_start,
        available_defenders=available_defenders,
        defender_starts=defender_starts,
        is_away_offense=is_away_offense,
    )

    # Override shot_spot + defender on roles.
    roles["shot_spot"] = dict(geometry["shooter_target"])
    if geometry["contested"] and geometry["shot_defender_id"]:
        # Look up player object by id.
        for d in def_lineup.values():
            if d is None:
                continue
            if str(getattr(d, "player_id", "")) == geometry["shot_defender_id"]:
                roles["defender"] = d
                fb_roles["defender"] = d
                fb_roles["defender_count"] = 1
                break
    else:
        # Uncontested → no defender; threshold=1 means auto-make.
        roles["defender"] = None
        fb_roles["defender"] = None
        fb_roles["defender_count"] = 0
        game.game_state["fast_break_shot_threshold_override"] = 1

    # Update fb_animations end coords for shooter + racing defenders so
    # the schema emitter renders the new positions. Stopper and outlet
    # defender are intentionally left alone (no movement on shot step).
    # Must write BOTH `entry["end"]` (downstream BE wiring + FE legacy
    # paths) AND `entry["movement"][-1]["coords"]` (UESS emitter reads
    # via `_movement_end_coord`). Writing only `entry["end"]` silently
    # drops the override at the emitter — shooter renders at the legacy
    # animator's spot.
    end_coords_override: Dict[str, Dict[str, float]] = {
        shooter_id: geometry["shooter_target"],
        **geometry["defender_end_coords"],
    }
    overrides_applied = 0
    for entry in fb_animations:
        pid = entry.get("playerId")
        pid_str = str(pid) if pid is not None else None
        if pid_str and pid_str in end_coords_override:
            new_coords = dict(end_coords_override[pid_str])
            entry["end"] = new_coords
            mv = entry.get("movement") or []
            if mv and isinstance(mv[-1], dict):
                mv[-1]["coords"] = dict(new_coords)
            overrides_applied += 1

    logging.warning(
        "🔍 [FB UNIVERSAL RR] shot_spot=%s contested=%s shot_def=%s applied_overrides=%d",
        geometry["shooter_target"],
        geometry["contested"],
        geometry["shot_defender_id"],
        overrides_applied,
    )


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
    rr_movement_archetype = "burst" if burst_anim_success else "sprint"
    dx_burst = random.randint(20, 25) if burst_anim_success else random.randint(9, 14)

    rr_half = _rr_half_from_y(rr_y0)
    rr_new_y = float(_spot_coords(f"{rr_half} wing", is_away_offense)["y"])

    receive_ty = 15.0 if rr_half == "upper" else 35.0

    most_recent = _find_most_recent_shot_turn(game)

    # Outlet receive spot: fixed at x=40 (home offense) or x=60 (away offense),
    # opposite-wing y from RR's burst destination.
    # Outlet receiver: offense player whose starting coords are closest to the
    # outlet spot. Rebounder is eligible; only RR is excluded.
    best_tx = 45.0 if not is_away_offense else 55.0

    offense_players = [p for p in off_lineup.values() if p is not None]
    best_p: Any = None
    best_d2 = float("inf")
    for p in offense_players:
        pid = getattr(p, "player_id", None)
        if rr_id is not None and pid is not None and str(pid) == str(rr_id):
            continue
        px = _player_x(p)
        py = _player_y(p)
        d2 = (best_tx - px) ** 2 + (receive_ty - py) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_p = p
    if best_p is None:
        best_p = pg or rebounder
        if best_p is None:
            best_p = next(p for p in offense_players if p)

    rr_destination, dynamic_base_x = _resolve_rr_burst_destination(
        rr_x0=rr_x0,
        rr_y0=rr_y0,
        outlet_receiver_target_x=best_tx,
        dx_burst=dx_burst,
        is_away_offense=is_away_offense,
        most_recent_shot_turn=most_recent,
    )
    rr_new_x = float(rr_destination["x"])

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
        # Phase 4b: per-segment game_seconds for the outlet defender's contest tween.
        od_start = {"x": float(_player_x(outlet_defender)), "y": float(_player_y(outlet_defender))}
        od_to["game_seconds"] = calc_ag_segment_seconds(
            od_start, od_to, outlet_defender, archetype="standard"
        )

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
            # Other defenders (non-getback, non-outlet-defender): same short
            # drift as other offense — 1–4 grid toward basket, y unchanged.
            nx = max(4, min(97, int(round(px + x_dir * random.randint(1, 4)))))
            ny = float(py)
        # Phase 4b: per-segment game_seconds for the secondary movers' burst tweens.
        # AG-driven via Movement Rate Refactor helper (default archetype).
        # Frontend reads `other_players[i].game_seconds × clockSecondMs`.
        other_gs = calc_ag_segment_seconds(
            {"x": float(px), "y": float(py)},
            {"x": float(nx), "y": float(ny)},
            pl,
            archetype="standard",
        )
        other_moves.append(
            {
                "player_id": getattr(pl, "player_id", None),
                "to_x": float(nx),
                "to_y": float(ny),
                "game_seconds": other_gs,
            }
        )

    recv_id_val = getattr(ball_handler, "player_id", None)
    # Phase 4b: per-segment game_seconds for RR burst/sprint and outlet receiver settle.
    rr_from = {"x": float(rr_x0), "y": float(rr_y0)}
    rr_to = {
        "x": float(rr_new_x),
        "y": float(rr_new_y),
        "game_seconds": calc_ag_segment_seconds(
            rr_from,
            {"x": float(rr_new_x), "y": float(rr_new_y)},
            rr,
            archetype=rr_movement_archetype,
        ),
        "movement_archetype": rr_movement_archetype,
    }
    recv_start = {
        "x": float(_player_x(ball_handler)),
        "y": float(_player_y(ball_handler)),
    } if ball_handler else None
    recv_end = {"x": float(best_tx), "y": float(receive_ty)}
    if ball_handler and recv_start is not None:
        recv_end["game_seconds"] = calc_ag_segment_seconds(
            recv_start, {"x": float(best_tx), "y": float(receive_ty)}, ball_handler, archetype="standard",
        )

    fb_roles["rim_runner_burst_phase"] = {
        "rr_id": rr_id,
        "rr_from": rr_from,
        "rr_to": rr_to,
        "burst_success": burst_anim_success,
        "burst_delta": dx_burst,
        "movement_factor": movement_factor,
        "burst_threshold": burst_threshold_anim,
        "dynamic_rr_x_base": dynamic_base_x,
        "skip_outlet_pass": skip_outlet_pass,
        "outlet_passer_id": None if skip_outlet_pass else rid,
        "outlet_receiver_id": recv_id_val,
        "receiver_to": recv_end,
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
    # Distance gate: outlet defender must be within 10 grid Euclidean of the
    # outlet passer (rebounder) to meaningfully contest the pass. Beyond
    # that, denial is geometrically implausible — auto-success regardless of
    # attribute rolls. See Animation_System_Updated.md / Advance_Triggers.md.
    outlet_within_range = True
    if outlet_defender and rebounder:
        rc = getattr(rebounder, "coords", None) or {}
        dc = getattr(outlet_defender, "coords", None) or {}
        if (
            isinstance(rc, dict) and "x" in rc and "y" in rc
            and isinstance(dc, dict) and "x" in dc and "y" in dc
        ):
            dx = float(dc["x"]) - float(rc["x"])
            dy = float(dc["y"]) - float(rc["y"])
            if (dx * dx + dy * dy) ** 0.5 > 10.0:
                outlet_within_range = False

    off_attrs = getattr(rebounder, "attributes", {}) if rebounder else {}
    outlet_off_base = (
        off_attrs.get("PS", 0) * 0.5 + off_attrs.get("ST", 0) * 0.3 + off_attrs.get("IQ", 0) * 0.2
    )
    outlet_offense_score = outlet_off_base * random.randint(1, 6)

    if outlet_defender and outlet_within_range:
        da = outlet_defender.attributes
        outlet_def_base = da.get("IQ", 0) * 0.5 + da.get("OD", 0) * 0.3 + da.get("ST", 0) * 0.2
        outlet_defense_score = outlet_def_base * random.randint(1, 6)
    else:
        outlet_defense_score = 0.0

    if not outlet_within_range:
        # Auto-success when defender is out of range — bypass the inequality
        # entirely so a zero-zero attribute roll edge case can't trip denial.
        outlet_ok = True
    else:
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

    # --- Burst ---
    getback_ids = (most_recent or {}).get("offense_getback") or []
    primary_def, in_getback = _primary_burst_defender(
        def_lineup, list(getback_ids), is_away_offense, rr
    )

    # Stage B — burst scores. Both sides now include their team-level FB
    # attribute (offense: fb_efficiency; defense: fb_opp_modifier). Pattern
    # matches the CR DEFENSIVE_STOP skill-check formula (sum × die).
    # In-getback IQ weight lowered from 1.0 → 0.6 (per RR spec update).
    rr_attrs = getattr(rr, "attributes", {}) if rr else {}
    burst_offense_score = (
        rr_attrs.get("AG", 0) * 0.7
        + rr_attrs.get("IQ", 0) * 0.3
        + fb_eff
    ) * random.randint(1, 6)

    if primary_def:
        da = primary_def.attributes
        if in_getback:
            burst_def_base = da.get("IQ", 0) * 0.6 + da.get("AG", 0) * 0.5
        else:
            burst_def_base = da.get("IQ", 0) * 0.5 + da.get("AG", 0) * 0.5
        burst_defense_score = (burst_def_base + fb_opp) * random.randint(1, 6)
    else:
        burst_defense_score = 0.0

    # Stage C — fb_open decision. Triangle gets a stricter offense
    # multiplier than RR (loosened 0.6 → 0.8 per RR spec update — still
    # stricter than RR's plain comparison).
    if fb_play_key == TRIANGLE:
        fb_open = (burst_offense_score * 0.8) > burst_defense_score
    else:
        fb_open = burst_offense_score > burst_defense_score

    # Stage D — PG read. read_score now adds offense team fb_efficiency
    # (per RR spec update). read_threshold still uses the same fb_eff
    # adjustment as before (200 − 5×fb_eff), so fb_eff now influences
    # both sides of the comparison.
    bh_attrs = getattr(ball_handler, "attributes", {})
    read_score = (bh_attrs.get("IQ", 0) + fb_eff) * random.randint(1, 6)
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

    if not pass_attempted and fb_play_key == TRIANGLE:
        setup_payload = _resolve_triangle_setup_payload(
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            ball_handler=ball_handler,
            rim_runner=rr,
            rebounder=rebounder,
            is_away_offense=is_away_offense,
            fb_opp=fb_opp,
        )
        fb_roles["triangle_sequence"] = True
        fb_roles["triangle_setup_phase"] = setup_payload

        decision = random.randint(1, 8)
        branch = None
        custom_corner_override = False
        if decision in (1, 2):
            branch = "triangle_rr_post"
        elif decision == 3:
            branch = "triangle_corner_three"
            custom_corner_override = True
        elif decision == 4:
            branch = "triangle_bh_wing_three"
        elif decision in (5, 6):
            drive_decision = random.randint(1, 5)
            setup_payload["triangle_drive_decision"] = drive_decision
            if drive_decision in (1, 2):
                branch = "triangle_bh_drive"
            elif drive_decision in (3, 4):
                branch = "triangle_drive_rr_feed"
            else:
                branch = "triangle_drive_corner_kick"
                custom_corner_override = True
        else:
            game_state["offensive_state"] = "HCO"
            animator = Animator(game)
            animations = animator.capture_fast_break_animation(fb_roles, False, None)
            result = {
                "result_type": "DEFENSIVE_STOP",
                "ball_handler": ball_handler,
                "defender": primary_def,
                "text": "Fast Break! Triangle — flowing into half court.",
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
                "triangle_enter_hco": True,
                "triangle_sequence": True,
                "triangle_branch": "triangle_enter_hco",
                "rim_runner_fb_open": fb_open,
                "rim_runner_correct_read": correct_read,
                "rim_runner_no_lane_pass": True,
            }
            _apply_rr_decision_metadata(result, pass_attempted=False, fb_open=fb_open)
            _record_fast_break_stats(fb_roles, result, game)
            apply_fast_break_cg_time(result, shot_attempted=False)
            return result

        setup_payload["triangle_branch"] = branch
        setup_payload["triangle_decision_roll"] = decision
        return _triangle_build_turn_result(
            game=game,
            game_state=game_state,
            off_team=off_team,
            def_team=def_team,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            fb_roles=fb_roles,
            ball_handler=ball_handler,
            rim_runner=rr,
            setup_payload=setup_payload,
            branch=branch,
            fb_open=fb_open,
            custom_corner_override=custom_corner_override,
        )

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
        # UESS Phase 1a/1b: RR's and Triangle's schema emitters read
        # `player.coords` as the FB step 0 START state (= end of DREB).
        # The legacy animator's pre-staged FB-END positions are flipped via
        # `get_away_player_coords` for AWAY offense, so writing them to
        # `player.coords` here causes a horizontal mirror-flip teleport at
        # the DREB→FB step 0 boundary. Skip for RR + Triangle (mirrors the
        # existing CR skip in phase_resolution.py).
        if fb_play_key not in (RIM_RUNNER, TRIANGLE):
            apply_coords_from_animations_list(game, fb_animations)
        if fb_roles.get("_bh_final_x") is not None and fb_roles.get("_bh_final_y") is not None:
            roles["shot_spot"] = {"x": fb_roles["_bh_final_x"], "y": fb_roles["_bh_final_y"]}
        rr_snap_roles = {**roles, "ball_handler": ball_handler}
        rr_snap = build_fast_break_pre_shot_snapshot(
            game, off_lineup, def_lineup, rr_snap_roles, "fb_rr_pre_shot"
        )
        # Universal geometry: replace shot_spot + defender + contested
        # decision per spec. Gated by feature flag for revert. Race pool
        # excludes Stopper and Outlet defender.
        if USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR and fb_play_key == RIM_RUNNER:
            _apply_universal_geometry_for_rr_shot(
                shooter=rr,
                roles=roles,
                fb_roles=fb_roles,
                fb_animations=fb_animations,
                game=game,
                off_lineup=off_lineup,
                def_lineup=def_lineup,
                is_away_offense=is_away_offense,
                stopper_id=getattr(primary_def, "player_id", None),
                outlet_defender_id=getattr(outlet_defender, "player_id", None) if outlet_defender else None,
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
        # UESS Phase 1a/1b: skip for RR + Triangle (see DREB→FB teleport
        # rationale above).
        if fb_play_key not in (RIM_RUNNER, TRIANGLE):
            apply_coords_from_animations_list(game, fb_animations)
        if fb_roles.get("_bh_final_x") is not None:
            roles["shot_spot"] = {"x": fb_roles["_bh_final_x"], "y": fb_roles["_bh_final_y"]}
        rr_snap_roles = {**roles, "ball_handler": ball_handler}
        rr_snap = build_fast_break_pre_shot_snapshot(
            game, off_lineup, def_lineup, rr_snap_roles, "fb_rr_pre_shot"
        )
        # Universal geometry: catch-and-shoot path (no primary_def). No
        # stopper to exclude; still exclude outlet defender.
        if USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR and fb_play_key == RIM_RUNNER:
            _apply_universal_geometry_for_rr_shot(
                shooter=rr,
                roles=roles,
                fb_roles=fb_roles,
                fb_animations=fb_animations,
                game=game,
                off_lineup=off_lineup,
                def_lineup=def_lineup,
                is_away_offense=is_away_offense,
                stopper_id=None,
                outlet_defender_id=getattr(outlet_defender, "player_id", None) if outlet_defender else None,
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

    # Positional gate: defender must be (a) within 8 grid Euclidean of the
    # pass lane (BH → RR line segment) AND (b) at-or-past RR's x in the
    # attacking direction. If either fails, no intercept attempt — fall
    # through to completion (shot). Prevents far-away defenders from
    # "stealing" the lane pass on attribute roll alone.
    _bh_x = _player_x(ball_handler)
    _bh_y = _player_y(ball_handler)
    _rr_x = _player_x(rr)
    _rr_y = _player_y(rr)
    _def_x = _player_x(primary_def)
    _def_y = _player_y(primary_def)

    _dx_lane = _rr_x - _bh_x
    _dy_lane = _rr_y - _bh_y
    _lane_len_sq = _dx_lane * _dx_lane + _dy_lane * _dy_lane
    if _lane_len_sq < 1e-9:
        _lane_dist = ((_def_x - _bh_x) ** 2 + (_def_y - _bh_y) ** 2) ** 0.5
    else:
        _t = max(
            0.0,
            min(
                1.0,
                ((_def_x - _bh_x) * _dx_lane + (_def_y - _bh_y) * _dy_lane) / _lane_len_sq,
            ),
        )
        _proj_x = _bh_x + _t * _dx_lane
        _proj_y = _bh_y + _t * _dy_lane
        _lane_dist = ((_def_x - _proj_x) ** 2 + (_def_y - _proj_y) ** 2) ** 0.5

    _past_rr = (_def_x >= _rr_x) if not is_away_offense else (_def_x <= _rr_x)
    _can_intercept = _lane_dist <= 8.0 and _past_rr

    da = primary_def.attributes
    intercept_score = (
        (da.get("OD", 0) * 0.6 + da.get("AG", 0) * 0.2 + da.get("IQ", 0) * 0.2)
        * random.randint(1, 6)
        if _can_intercept
        else 0
    )

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
        # UESS Phase 1a/1b: skip for RR + Triangle (see DREB→FB teleport
        # rationale above).
        if rr_anims and fb_play_key not in (RIM_RUNNER, TRIANGLE):
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
        # UESS Phase 1a/1b: skip for RR + Triangle (see DREB→FB teleport
        # rationale above).
        if bat_anims and fb_play_key not in (RIM_RUNNER, TRIANGLE):
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
    # UESS Phase 1a/1b: skip for RR + Triangle (see DREB→FB teleport
    # rationale above).
    if fb_play_key not in (RIM_RUNNER, TRIANGLE):
        apply_coords_from_animations_list(game, fb_animations)
    if fb_roles.get("_bh_final_x") is not None:
        roles["shot_spot"] = {"x": fb_roles["_bh_final_x"], "y": fb_roles["_bh_final_y"]}
    rr_snap_roles = {**roles, "ball_handler": ball_handler}
    rr_snap = build_fast_break_pre_shot_snapshot(
        game, off_lineup, def_lineup, rr_snap_roles, "fb_rr_pre_shot"
    )
    # Universal geometry: completion-shot path after intercept fall-through.
    if USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR and fb_play_key == RIM_RUNNER:
        _apply_universal_geometry_for_rr_shot(
            shooter=rr,
            roles=roles,
            fb_roles=fb_roles,
            fb_animations=fb_animations,
            game=game,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            is_away_offense=is_away_offense,
            stopper_id=getattr(primary_def, "player_id", None) if primary_def else None,
            outlet_defender_id=getattr(outlet_defender, "player_id", None) if outlet_defender else None,
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
