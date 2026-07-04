"""Shot micro-movements — backend-authored footwork + contest reactions.

See implementation brief: movement registry, contest resolver, bucket behavior,
and ``build_shot_micro_steps`` consumed by skeleton / HCT / FB / OREB emitters.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Literal, Optional, Tuple

from BackEnd.constants import (
    AWAY_RIM_COORDS,
    HCO_STRING_SPOTS,
    HOME_RIM_COORDS,
    MADE_SHOT_SWEET_SPOT_AWAY_RIM,
    MADE_SHOT_SWEET_SPOT_HOME_RIM,
)
from BackEnd.constants.shot_micro_movements_constants import (
    ARC_SPOT_OCCUPIED_RADIUS,
    CONTEST_DEFENSE_WIN_THRESHOLD,
    CONTEST_OFFENSE_WIN_THRESHOLD,
    DEFENDER_GLUE_CLAMP_MIN,
    DEFENDER_GLUE_GAP,
    DEFENDER_STICK_GAP,
    DEFENDER_TRACK_GAP,
    DEFENDER_WALL_GAP,
    DUNK_APPROACH_AWAY,
    DUNK_APPROACH_HOME,
    DUNK_BALL_RAISE,
    DUNK_CLOCK_MS_PER_GAME_SEC,
    DUNK_DRIVE_MAX_DIST,
    DUNK_FAMILIES,
    DUNK_HEIGHT_SCALE_BY_INCH,
    DUNK_LOCATION_MAX_GRID,
    DUNK_MARGIN_THRESHOLD,
    DUNK_MOVE_SPOTS_DRIVE,
    DUNK_MOVE_SPOTS_STRONG,
    DUNK_AG_THRESHOLD_DIST_9,
    DUNK_AG_THRESHOLD_DIST_10,
    DUNK_RATTLE_MAG_PX,
    DUNK_RATTLE_MS,
    DUNK_RISE_PX,
    DUNK_WALL_CLOCK_MIN_MS,
    DUNK_WALL_CLOCK_RISE_SLAM_MS,
    JAB_COUNTER_MULTIPLIER,
    JAB_STEP_GRID,
    MICRO_FLOURISH_BEAT_T,
    MICRO_MOVE_STEP_T_FLOOR,
    MICRO_STEP_GRID,
    MOVEMENT_POOL_BY_SHOT_TYPE,
    MUSCLE_LOSS_COMPLETION,
    OUTSIDE_ARC_SPOT_ORDER,
    OUTSIDE_MOVING_FAMILIES,
    OUTSIDE_STATIC_FALLBACK_FAMILIES,
    PUMP_FAKE_FLOURISH_BEAT_T,
    TRAVEL_SHOOT_MIN_GRID,
)
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _euclid,
    _motion_end_toward_dest,
    _player_lookup_by_id,
    shot_result_sfx,
    stamp_tween_durations,
)
from BackEnd.utils.shared import get_away_player_coords
from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    ClockState,
    GridCoord,
    NextStep,
    PlayerAction,
    PlayerArchetype,
)

ContestResult = Literal["offense_win", "neutral", "defense_win"]

# family_id → bucket (A muscle, B separation, C quick/set, D pump)
FAMILY_BUCKET: Dict[str, str] = {
    "strong_inside": "A",
    "strong_attack": "A",
    "fade_away": "B",
    "jab_step": "B",
    "under_and_up": "D+B",
    "dribble_shoot": "B",
    "straight_inside": "C",
    "pullup_attack": "C",
    "set": "C",
    "set_pump": "D",
    "dribble_pump_shoot": "D+B",
    "pump_dribble_shoot": "D+B",
    "dunk": "A",
    "drive_dunk": "A",
}

BUCKET_OVERRIDE: Dict[Tuple[str, ContestResult], str] = {
    ("pullup_attack", "offense_win"): "seal",
}

# bucket × contest → defender behavior token
BUCKET_BEHAVIOR: Dict[str, Dict[ContestResult, str]] = {
    "A": {
        "offense_win": "seal",
        "neutral": "stick",
        "defense_win": "wall",
    },
    "B": {
        "offense_win": "stranded",
        "neutral": "stick",
        "defense_win": "glue",
    },
    "C": {
        "offense_win": "stationary",
        "neutral": "lean",
        "defense_win": "pushoff",
    },
    "D": {
        "offense_win": "bite",
        "neutral": "pause",
        "defense_win": "glue",
    },
}


def resolve_contest(
    shot_score_pre_defense: float,
    shot_defense_score_raw: float,
) -> Tuple[ContestResult, float]:
    margin = float(shot_score_pre_defense) - float(shot_defense_score_raw)
    if margin > CONTEST_OFFENSE_WIN_THRESHOLD:
        return "offense_win", margin
    if margin < CONTEST_DEFENSE_WIN_THRESHOLD:
        return "defense_win", margin
    return "neutral", margin


def _attacking_rim(away_offense: bool) -> GridCoord:
    return dict(AWAY_RIM_COORDS if away_offense else HOME_RIM_COORDS)


def _unit_toward_rim(from_coord: GridCoord, away_offense: bool) -> Tuple[float, float]:
    rim = _attacking_rim(away_offense)
    dx = float(rim["x"]) - float(from_coord["x"])
    dy = float(rim["y"]) - float(from_coord["y"])
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-6:
        return (1.0 if not away_offense else -1.0), 0.0
    return dx / length, dy / length


def _perp_jab_direction(shooter_y: float) -> float:
    """+1 = jab toward upper side (increase y); -1 = toward lower."""
    if shooter_y > 25.0 + 1e-6:
        return -1.0
    if shooter_y < 25.0 - 1e-6:
        return 1.0
    return 1.0


def _offset_coord(base: GridCoord, dx: float, dy: float) -> GridCoord:
    return {"x": float(base["x"]) + dx, "y": float(base["y"]) + dy}


def _dunk_approach_coord(away_offense: bool) -> GridCoord:
    return dict(DUNK_APPROACH_AWAY if away_offense else DUNK_APPROACH_HOME)


def _dunk_resolve_coord(away_offense: bool) -> GridCoord:
    return dict(
        MADE_SHOT_SWEET_SPOT_AWAY_RIM if away_offense else MADE_SHOT_SWEET_SPOT_HOME_RIM
    )


def _dunk_wall_clock_ms(dist_grid: float, shooter_player: Any) -> float:
    sprint_rate = max(1e-6, _ag_grid_per_game_sec(shooter_player, "sprint"))
    return max(
        DUNK_WALL_CLOCK_MIN_MS,
        (float(dist_grid) / sprint_rate) * DUNK_CLOCK_MS_PER_GAME_SEC
        + DUNK_WALL_CLOCK_RISE_SLAM_MS,
    )


def is_dunk_micro_family(family_id: Optional[str]) -> bool:
    return str(family_id or "") in DUNK_FAMILIES


def _basket_spot_coord(away_offense: bool) -> GridCoord:
    raw = HCO_STRING_SPOTS["basketSpot"]
    if away_offense:
        return get_away_player_coords(raw)
    return {"x": float(raw["x"]), "y": float(raw["y"])}


def dunk_height_scale(height_inches: Any) -> int:
    try:
        h = int(height_inches if height_inches is not None else 72)
    except (TypeError, ValueError):
        h = 72
    if h in DUNK_HEIGHT_SCALE_BY_INCH:
        return int(DUNK_HEIGHT_SCALE_BY_INCH[h])
    if h >= 83:
        return 30
    if h <= 68:
        return 0
    return 0


def dunk_location_eligible(dist_grid: float, agility: float) -> bool:
    if dist_grid > DUNK_LOCATION_MAX_GRID:
        return False
    if dist_grid <= DUNK_DRIVE_MAX_DIST:
        return True
    ag = float(agility or 0)
    if dist_grid <= 9.0:
        return ag > DUNK_AG_THRESHOLD_DIST_9
    return ag > DUNK_AG_THRESHOLD_DIST_10


def dunk_in_play_margin(
    shot_score_pre_defense: float,
    shot_defense_score_raw: float,
    *,
    off_fight: float = 0.0,
    def_fight: float = 0.0,
) -> float:
    return (
        float(shot_score_pre_defense)
        - float(shot_defense_score_raw)
        + float(off_fight)
        - float(def_fight)
    )


def resolve_dunk_micro_stamp(
    *,
    shot_type: str,
    shooter_coord: GridCoord,
    shooter_player: Any,
    off_team: Any,
    def_team: Any,
    shot_score_pre_defense: float,
    shot_defense_score_raw: float,
    result_type: str,
    away_offense: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """Return dunk stamp dict or None (caller falls back to normal micro pool).

    See Shot_System.md § Dunk Selection & Block Interaction.
    """
    st = str(shot_type or "").lower()
    if st not in ("inside", "attack"):
        return None
    if away_offense is None:
        away_offense = _infer_away_offense_from_display_coord(shooter_coord)

    basket = _basket_spot_coord(away_offense)
    dist = _euclid(shooter_coord, basket)
    attrs = getattr(shooter_player, "attributes", None) or {}
    ag = float(attrs.get("AG", 0) or 0)
    if not dunk_location_eligible(dist, ag):
        return None

    off_fight = float(getattr(off_team, "team_attributes", {}).get("fight", 0) or 0)
    def_fight = float(getattr(def_team, "team_attributes", {}).get("fight", 0) or 0)
    if dunk_in_play_margin(
        shot_score_pre_defense,
        shot_defense_score_raw,
        off_fight=off_fight,
        def_fight=def_fight,
    ) <= DUNK_MARGIN_THRESHOLD:
        return None

    height = getattr(shooter_player, "height", None) or attrs.get("height")
    scale = dunk_height_scale(height)
    roll = random.randint(1, 100)
    family_id = "dunk" if dist <= DUNK_DRIVE_MAX_DIST else "drive_dunk"
    rt = (result_type or "").upper()

    if roll == scale + 1:
        return {
            "family_id": family_id,
            "dunk_miss": True,
            "force_miss": True,
        }
    if roll <= scale and rt in ("MAKE", "BLOCK"):
        return {
            "family_id": family_id,
            "dunk_miss": False,
            "force_miss": False,
        }
    return None


def prepare_dunk_stamp(
    *,
    shot_type: str,
    shooter_coord: GridCoord,
    shooter_player: Any,
    off_team: Any,
    def_team: Any,
    shot_score_pre_defense: float,
    shot_defense_score_raw: float,
    made: bool,
    is_block: bool = False,
    away_offense: Optional[bool] = None,
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Resolve dunk stamp once; apply missed-dunk override to ``made``."""
    st = str(shot_type or "").lower()
    if st not in ("inside", "attack"):
        return None, made
    pre_rt = "MAKE" if made else ("BLOCK" if is_block else "MISS")
    stamp = resolve_dunk_micro_stamp(
        shot_type=shot_type,
        shooter_coord=shooter_coord,
        shooter_player=shooter_player,
        off_team=off_team,
        def_team=def_team,
        shot_score_pre_defense=float(shot_score_pre_defense),
        shot_defense_score_raw=float(shot_defense_score_raw or 0),
        result_type=pre_rt,
        away_offense=away_offense,
    )
    if stamp and stamp.get("force_miss"):
        return stamp, False
    return stamp, made


def _defender_rim_side_coord(
    shooter: GridCoord,
    away_offense: bool,
    gap: float,
) -> GridCoord:
    ux, uy = _unit_toward_rim(shooter, away_offense)
    return _offset_coord(shooter, ux * gap, uy * gap)


def _resolve_defender_behavior(
    family_id: str,
    bucket: str,
    contest_result: ContestResult,
    beat_bucket: Optional[str] = None,
) -> str:
    key_bucket = beat_bucket or bucket
    override = BUCKET_OVERRIDE.get((family_id, contest_result))
    if override:
        return override
    return BUCKET_BEHAVIOR.get(key_bucket, BUCKET_BEHAVIOR["C"])[contest_result]


def _teammate_coords_at_shot(
    shooter_id: str,
    coords: Dict[str, GridCoord],
    off_lineup: Dict[str, Any],
) -> List[GridCoord]:
    out: List[GridCoord] = []
    for pos, player in (off_lineup or {}).items():
        if player is None:
            continue
        pid = getattr(player, "player_id", None)
        if pid is None or str(pid) == str(shooter_id):
            continue
        c = coords.get(str(pid))
        if c:
            out.append(c)
    return out


def _spot_occupied(spot: GridCoord, teammates: List[GridCoord]) -> bool:
    for tc in teammates:
        if _euclid(spot, tc) <= ARC_SPOT_OCCUPIED_RADIUS:
            return True
    return False


def _infer_away_offense_from_display_coord(coord: GridCoord) -> bool:
    """True when ``coord`` is on the away-attacking half (display frame)."""
    d_away = _euclid(coord, AWAY_RIM_COORDS)
    d_home = _euclid(coord, HOME_RIM_COORDS)
    if abs(d_away - d_home) < 0.5:
        return float(coord["x"]) < 50.0
    return d_away < d_home


def _arc_spot_display_coord(spot_name: str, away_offense: bool) -> Optional[GridCoord]:
    """Named HCO arc spot in display orientation (mirrors x for away offense)."""
    home = HCO_STRING_SPOTS.get(spot_name)
    if not home:
        return None
    coord = {"x": float(home["x"]), "y": float(home["y"])}
    if away_offense:
        coord = get_away_player_coords(coord)
    return coord


def _nearest_arc_spot_name(shooter_coord: GridCoord, away_offense: bool) -> Optional[str]:
    best_name = None
    best_dist = float("inf")
    for name in OUTSIDE_ARC_SPOT_ORDER:
        spot = _arc_spot_display_coord(name, away_offense)
        if not spot:
            continue
        d = _euclid(shooter_coord, spot)
        if d < best_dist:
            best_dist = d
            best_name = name
    return best_name


def _adjacent_arc_spots(spot_name: str) -> List[str]:
    order = OUTSIDE_ARC_SPOT_ORDER
    if spot_name not in order:
        return []
    idx = order.index(spot_name)
    neighbors: List[str] = []
    if idx > 0:
        neighbors.append(order[idx - 1])
    if idx < len(order) - 1:
        neighbors.append(order[idx + 1])
    return neighbors


def _pick_outside_dribble_target(
    shooter_coord: GridCoord,
    teammates: List[GridCoord],
    away_offense: bool,
) -> Optional[GridCoord]:
    spot_name = _nearest_arc_spot_name(shooter_coord, away_offense)
    if not spot_name:
        return None
    candidates: List[GridCoord] = []
    for neighbor in _adjacent_arc_spots(spot_name):
        spot = _arc_spot_display_coord(neighbor, away_offense)
        if spot and not _spot_occupied(spot, teammates):
            candidates.append(dict(spot))
    if not candidates:
        return None
    return random.choice(candidates)


# Families with no pre-shoot beats — safe when clock budget is exhausted (Final Turn).
INSTANT_RELEASE_MICRO_FAMILIES = frozenset({"set", "straight_inside", "pullup_attack"})


def _estimate_beat_game_seconds(
    beat: Dict[str, Any],
    *,
    shooter_player: Any,
    shooter_coord: GridCoord,
) -> float:
    """Game-clock burn for one micro beat (mirrors ``build_shot_micro_steps``)."""
    kind = beat.get("kind")
    if kind == "move":
        dx, dy = float(beat["dx"]), float(beat["dy"])
        dest = _offset_coord(shooter_coord, dx, dy)
        arch = beat.get("archetype", "standard")
        rate = _ag_grid_per_game_sec(shooter_player, arch)
        return max(MICRO_MOVE_STEP_T_FLOOR, _euclid(shooter_coord, dest) / max(1e-6, rate))
    if kind == "move_to":
        dest = dict(beat["coord"])
        arch = beat.get("archetype", "cruise")
        rate = _ag_grid_per_game_sec(shooter_player, arch)
        return max(MICRO_MOVE_STEP_T_FLOOR, _euclid(shooter_coord, dest) / max(1e-6, rate))
    if kind == "flourish":
        flourish_kind = beat.get("flourish", "pump_fake")
        return (
            PUMP_FAKE_FLOURISH_BEAT_T
            if flourish_kind == "pump_fake"
            else MICRO_FLOURISH_BEAT_T
        )
    if kind == "dunk":
        approach = beat.get("approach_coord") or DUNK_APPROACH_HOME
        dist = _euclid(shooter_coord, approach)
        wall_ms = _dunk_wall_clock_ms(dist, shooter_player)
        return max(MICRO_MOVE_STEP_T_FLOOR, wall_ms / DUNK_CLOCK_MS_PER_GAME_SEC)
    return MICRO_FLOURISH_BEAT_T


def estimate_micro_pre_release_seconds(
    family_id: str,
    *,
    shooter_player: Any,
    shooter_coord: GridCoord,
    off_lineup: Dict[str, Any],
    all_coords: Dict[str, GridCoord],
    shooter_id: str,
    away_offense: Optional[bool] = None,
) -> float:
    """Seconds of game clock burned on micro beats before the terminal release."""
    if away_offense is None:
        away_offense = _infer_away_offense_from_display_coord(shooter_coord)
    beats = _build_family_beats(
        family_id,
        shooter_coord,
        away_offense,
        off_lineup,
        all_coords,
        shooter_id,
    )
    if not beats or (len(beats) == 1 and beats[0].get("kind") == "shot"):
        return 0.0
    total = 0.0
    current = dict(shooter_coord)
    for beat in beats[:-1]:
        total += _estimate_beat_game_seconds(
            beat, shooter_player=shooter_player, shooter_coord=current,
        )
        kind = beat.get("kind")
        if kind == "move":
            dx, dy = float(beat["dx"]), float(beat["dy"])
            current = _offset_coord(current, dx, dy)
        elif kind == "move_to":
            current = dict(beat["coord"])
    return total


def _instant_release_fallback(shot_type: str) -> str:
    st = str(shot_type).lower()
    if st == "attack":
        return "pullup_attack"
    if st == "inside":
        return "straight_inside"
    return "set"


def worst_case_final_turn_micro_reserve(
    shot_type: str,
    *,
    is_away_offense: bool = False,
) -> float:
    """Conservative pre-release micro reserve for Final Turn preflight pacing."""
    st = str(shot_type).lower()
    pool_key = st if st in MOVEMENT_POOL_BY_SHOT_TYPE else "outside"
    pool = MOVEMENT_POOL_BY_SHOT_TYPE[pool_key]

    class _SlowShooter:
        attributes = {"AG": 1}

    slow = _SlowShooter()
    shooter_id = "__preflight__"
    if st == "outside":
        raw = HCO_STRING_SPOTS.get("upper wing", {"x": 83, "y": 18})
        coord = get_away_player_coords(raw) if is_away_offense else {"x": float(raw["x"]), "y": float(raw["y"])}
    elif st == "attack":
        raw = HCO_STRING_SPOTS.get("basketSpot", {"x": 91, "y": 25})
        coord = get_away_player_coords(raw) if is_away_offense else {"x": float(raw["x"]), "y": float(raw["y"])}
    else:
        raw = HCO_STRING_SPOTS.get("key", {"x": 64, "y": 25})
        coord = get_away_player_coords(raw) if is_away_offense else {"x": float(raw["x"]), "y": float(raw["y"])}
    all_coords = {shooter_id: coord}

    worst = 0.0
    for family_id in pool:
        pre = estimate_micro_pre_release_seconds(
            family_id,
            shooter_player=slow,
            shooter_coord=coord,
            off_lineup={},
            all_coords=all_coords,
            shooter_id=shooter_id,
            away_offense=is_away_offense,
        )
        worst = max(worst, pre)
    return worst


def select_micro_movement(
    shot_type: str,
    *,
    shooter_coord: GridCoord,
    shooter_id: str,
    off_lineup: Dict[str, Any],
    all_coords: Dict[str, GridCoord],
    away_offense: Optional[bool] = None,
    max_pre_release_seconds: Optional[float] = None,
    shooter_player: Optional[Any] = None,
) -> str:
    if away_offense is None:
        away_offense = _infer_away_offense_from_display_coord(shooter_coord)
    pool = list(MOVEMENT_POOL_BY_SHOT_TYPE.get(shot_type, MOVEMENT_POOL_BY_SHOT_TYPE["outside"]))
    if max_pre_release_seconds is not None:
        player = shooter_player or _player_lookup_by_id(off_lineup, {}, shooter_id)
        eligible = [
            family_id
            for family_id in pool
            if estimate_micro_pre_release_seconds(
                family_id,
                shooter_player=player,
                shooter_coord=shooter_coord,
                off_lineup=off_lineup,
                all_coords=all_coords,
                shooter_id=shooter_id,
                away_offense=away_offense,
            )
            <= float(max_pre_release_seconds) + 1e-6
        ]
        if eligible:
            pool = eligible
        else:
            return _instant_release_fallback(shot_type)
    choice = random.choice(pool)
    if choice not in OUTSIDE_MOVING_FAMILIES:
        return choice
    teammates = _teammate_coords_at_shot(shooter_id, all_coords, off_lineup)
    if _pick_outside_dribble_target(shooter_coord, teammates, away_offense) is None:
        fallback = random.choice(OUTSIDE_STATIC_FALLBACK_FAMILIES)
        if max_pre_release_seconds is not None:
            player = shooter_player or _player_lookup_by_id(off_lineup, {}, shooter_id)
            if estimate_micro_pre_release_seconds(
                fallback,
                shooter_player=player,
                shooter_coord=shooter_coord,
                off_lineup=off_lineup,
                all_coords=all_coords,
                shooter_id=shooter_id,
                away_offense=away_offense,
            ) > float(max_pre_release_seconds) + 1e-6:
                return "set"
        return fallback
    return choice


def stamp_micro_telemetry(
    turn_result: Dict[str, Any],
    *,
    family_id: str,
    contest_result: Optional[ContestResult],
    contest_margin: Optional[float],
    shot_defense_score_raw: Optional[float] = None,
    has_contest: Optional[bool] = None,
) -> None:
    turn_result["micro_movement_family"] = family_id
    if contest_result is not None:
        turn_result["contest_result"] = contest_result
    if contest_margin is not None:
        turn_result["contest_margin"] = float(contest_margin)
    if shot_defense_score_raw is not None:
        turn_result["shot_defense_score_raw"] = float(shot_defense_score_raw)
    if has_contest is not None:
        turn_result["has_contest"] = bool(has_contest)


def build_micro_coords_snapshot(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    shooter_id: str,
    shooter_x: float,
    shooter_y: float,
) -> Dict[str, GridCoord]:
    coords: Dict[str, GridCoord] = {}
    for player in list((off_lineup or {}).values()) + list((def_lineup or {}).values()):
        if player is None:
            continue
        pid = str(getattr(player, "player_id", ""))
        if not pid:
            continue
        pc = getattr(player, "coords", None) or {}
        coords[pid] = {"x": float(pc.get("x", 50)), "y": float(pc.get("y", 25))}
    coords[str(shooter_id)] = {"x": float(shooter_x), "y": float(shooter_y)}
    return coords


def select_and_stamp_shot_micro(
    turn_result: Dict[str, Any],
    *,
    shot_type: str,
    shooter_id: str,
    shooter_x: float,
    shooter_y: float,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    has_contest: bool,
    contest_result: Optional[ContestResult],
    contest_margin: Optional[float],
    shot_defense_score_raw: float,
    away_offense: Optional[bool] = None,
    max_pre_release_seconds: Optional[float] = None,
    shooter_player: Optional[Any] = None,
    shot_score_pre_defense: Optional[float] = None,
    off_team: Optional[Any] = None,
    def_team: Optional[Any] = None,
    result_type: Optional[str] = None,
    dunk_stamp: Optional[Dict[str, Any]] = None,
) -> str:
    shooter_coord = {"x": float(shooter_x), "y": float(shooter_y)}
    if away_offense is None:
        away_offense = _infer_away_offense_from_display_coord(shooter_coord)

    family_id: Optional[str] = None
    if dunk_stamp is None and (
        shooter_player is not None
        and shot_score_pre_defense is not None
        and result_type is not None
        and off_team is not None
        and def_team is not None
    ):
        dunk_stamp = resolve_dunk_micro_stamp(
            shot_type=shot_type,
            shooter_coord=shooter_coord,
            shooter_player=shooter_player,
            off_team=off_team,
            def_team=def_team,
            shot_score_pre_defense=float(shot_score_pre_defense),
            shot_defense_score_raw=float(shot_defense_score_raw or 0),
            result_type=str(result_type),
            away_offense=away_offense,
        )
    if dunk_stamp:
        family_id = str(dunk_stamp["family_id"])
        turn_result["dunk_miss"] = bool(dunk_stamp.get("dunk_miss"))
        if dunk_stamp.get("force_miss"):
            turn_result["_dunk_force_miss"] = True

    if family_id is None:
        all_coords = build_micro_coords_snapshot(
            off_lineup, def_lineup, shooter_id, shooter_x, shooter_y,
        )
        family_id = select_micro_movement(
            shot_type,
            shooter_coord=shooter_coord,
            shooter_id=str(shooter_id),
            off_lineup=off_lineup,
            all_coords=all_coords,
            away_offense=away_offense,
            max_pre_release_seconds=max_pre_release_seconds,
            shooter_player=shooter_player,
        )
        turn_result.pop("dunk_miss", None)
        turn_result.pop("_dunk_force_miss", None)

    stamp_micro_telemetry(
        turn_result,
        family_id=family_id,
        contest_result=contest_result if has_contest else None,
        contest_margin=contest_margin if has_contest else None,
        shot_defense_score_raw=shot_defense_score_raw if has_contest else None,
        has_contest=has_contest,
    )
    from BackEnd.utils.shot_ball_arc import roll_shot_arc

    turn_result["uses_shot_arc"] = False if is_dunk_micro_family(family_id) else roll_shot_arc(family_id)
    return family_id


def _stationary_maps(
    coords: Dict[str, GridCoord],
) -> Tuple[
    Dict[str, PlayerAction],
    Dict[str, PlayerArchetype],
    Dict[str, Optional[GridCoord]],
]:
    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in coords}
    archetypes: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in coords}
    destinations: Dict[str, Optional[GridCoord]] = {pid: None for pid in coords}
    return actions, archetypes, destinations


def _advance_player_reaches(player_id: str, coord: GridCoord, t: float) -> AdvanceTrigger:
    return {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": str(player_id),
            "target_coords": dict(coord),
        },
    }


def _compute_step_t(
    start: GridCoord,
    end: GridCoord,
    player: Any,
    archetype: PlayerArchetype,
    gate_id: Optional[str],
    gate_player_id: Optional[str],
) -> Tuple[float, Dict[str, GridCoord]]:
    rate = _ag_grid_per_game_sec(player, archetype)
    dist = _euclid(start, end)
    if dist < 1e-6:
        return max(MICRO_FLOURISH_BEAT_T, MICRO_MOVE_STEP_T_FLOOR), {**start}
    natural_t = max(MICRO_MOVE_STEP_T_FLOOR, dist / rate)
    end_coords = {k: dict(v) for k, v in start.items()} if isinstance(start, dict) else {}
    return natural_t, end_coords


def _apply_defender_behavior_coord(
    behavior: str,
    shooter_start: GridCoord,
    shooter_end: GridCoord,
    defender_start: GridCoord,
    away_offense: bool,
    *,
    pump_direction: Optional[Tuple[float, float]] = None,
) -> GridCoord:
    toward_ux, toward_uy = _unit_toward_rim(shooter_end, away_offense)
    if behavior == "seal":
        return _defender_rim_side_coord(shooter_end, away_offense, -DEFENDER_TRACK_GAP * 1.3)
    if behavior == "stick":
        return _defender_rim_side_coord(shooter_end, away_offense, DEFENDER_STICK_GAP)
    if behavior == "wall":
        return _defender_rim_side_coord(shooter_end, away_offense, DEFENDER_WALL_GAP)
    if behavior == "stranded":
        return dict(defender_start)
    if behavior == "glue":
        target = _defender_rim_side_coord(shooter_end, away_offense, DEFENDER_GLUE_GAP)
        if _euclid(target, shooter_end) < DEFENDER_GLUE_CLAMP_MIN:
            return _defender_rim_side_coord(shooter_end, away_offense, DEFENDER_GLUE_CLAMP_MIN)
        return target
    if behavior == "stationary":
        return dict(defender_start)
    if behavior == "lean":
        return _defender_rim_side_coord(shooter_end, away_offense, DEFENDER_STICK_GAP)
    if behavior == "pushoff":
        return _offset_coord(shooter_end, -toward_ux * 1.3, -toward_uy * 1.3)
    if behavior == "bite" and pump_direction:
        px, py = pump_direction
        return _offset_coord(defender_start, px * 1.8, py * 1.8)
    if behavior == "pause":
        return dict(defender_start)
    return dict(defender_start)


def _disruption_flourish_targets(
    contest_result: ContestResult,
    shot_type: str,
    shooter_id: str,
    defender_id: Optional[str],
    family_id: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Map player_id → flourish stamp for shot-beat disruption."""
    out: Dict[str, Dict[str, Any]] = {}
    if contest_result == "defense_win":
        out[str(shooter_id)] = {"kind": "rattle", "cycles": 3}
    elif contest_result == "offense_win" and defender_id:
        out[str(defender_id)] = {"kind": "rattle", "cycles": 3}
    elif contest_result == "neutral" and (
        shot_type in ("inside", "attack") or is_dunk_micro_family(family_id)
    ):
        out[str(shooter_id)] = {"kind": "rattle", "cycles": 2}
        if defender_id:
            out[str(defender_id)] = {"kind": "rattle", "cycles": 2}
    return out


def _build_family_beats(
    family_id: str,
    shooter_coord: GridCoord,
    away_offense: bool,
    off_lineup: Dict[str, Any],
    all_coords: Dict[str, GridCoord],
    shooter_id: str,
) -> List[Dict[str, Any]]:
    """Declarative beat list for a movement family."""
    ux, uy = _unit_toward_rim(shooter_coord, away_offense)
    perp_x, perp_y = -uy, ux
    jab_sign = _perp_jab_direction(float(shooter_coord["y"]))

    if family_id == "strong_inside" or family_id == "strong_attack":
        return [
            {"kind": "move", "dx": ux * MICRO_STEP_GRID, "dy": uy * MICRO_STEP_GRID, "archetype": "shot_motion"},
            {"kind": "shot"},
        ]
    if family_id == "fade_away":
        return [
            {"kind": "move", "dx": -ux * MICRO_STEP_GRID, "dy": -uy * MICRO_STEP_GRID, "archetype": "cruise"},
            {"kind": "shot"},
        ]
    if family_id == "jab_step":
        return [
            {"kind": "move", "dx": perp_x * JAB_STEP_GRID * jab_sign, "dy": perp_y * JAB_STEP_GRID * jab_sign, "archetype": "standard"},
            {"kind": "shot"},
        ]
    if family_id == "under_and_up":
        counter = JAB_STEP_GRID * JAB_COUNTER_MULTIPLIER
        return [
            {"kind": "move", "dx": perp_x * JAB_STEP_GRID * jab_sign, "dy": perp_y * JAB_STEP_GRID * jab_sign, "archetype": "standard", "beat_bucket": "D"},
            {"kind": "move", "dx": -perp_x * counter * jab_sign, "dy": -perp_y * counter * jab_sign, "archetype": "standard", "beat_bucket": "B"},
            {"kind": "shot"},
        ]
    if family_id in ("straight_inside", "pullup_attack", "set"):
        return [{"kind": "shot"}]
    if family_id == "set_pump":
        return [{"kind": "flourish", "who": "shooter", "flourish": "pump_fake"}, {"kind": "shot"}]
    if family_id == "dribble_shoot":
        teammates = _teammate_coords_at_shot(shooter_id, all_coords, off_lineup)
        target = _pick_outside_dribble_target(shooter_coord, teammates, away_offense)
        if target:
            return [
                {"kind": "move_to", "coord": target, "archetype": "cruise"},
                {"kind": "flourish", "who": "shooter", "flourish": "gather"},
                {"kind": "shot"},
            ]
        return [{"kind": "shot"}]
    if family_id == "dribble_pump_shoot":
        teammates = _teammate_coords_at_shot(shooter_id, all_coords, off_lineup)
        target = _pick_outside_dribble_target(shooter_coord, teammates, away_offense)
        if target:
            return [
                {"kind": "move_to", "coord": target, "archetype": "cruise", "beat_bucket": "B"},
                {"kind": "flourish", "who": "shooter", "flourish": "pump_fake", "beat_bucket": "D"},
                {"kind": "shot", "beat_bucket": "B"},
            ]
        return [{"kind": "flourish", "who": "shooter", "flourish": "pump_fake"}, {"kind": "shot"}]
    if family_id == "pump_dribble_shoot":
        teammates = _teammate_coords_at_shot(shooter_id, all_coords, off_lineup)
        target = _pick_outside_dribble_target(shooter_coord, teammates, away_offense)
        beats: List[Dict[str, Any]] = [
            {"kind": "flourish", "who": "shooter", "flourish": "pump_fake", "beat_bucket": "D"},
        ]
        if target:
            beats.append({"kind": "move_to", "coord": target, "archetype": "cruise", "beat_bucket": "B"})
            beats.append({"kind": "flourish", "who": "shooter", "flourish": "gather", "beat_bucket": "B"})
        beats.append({"kind": "shot", "beat_bucket": "B"})
        return beats
    if family_id == "dunk":
        return [
            {
                "kind": "move",
                "dx": ux * MICRO_STEP_GRID * DUNK_MOVE_SPOTS_STRONG,
                "dy": uy * MICRO_STEP_GRID * DUNK_MOVE_SPOTS_STRONG,
                "archetype": "burst",
            },
            {"kind": "dunk"},
        ]
    if family_id == "drive_dunk":
        return [
            {
                "kind": "move",
                "dx": ux * MICRO_STEP_GRID * DUNK_MOVE_SPOTS_DRIVE,
                "dy": uy * MICRO_STEP_GRID * DUNK_MOVE_SPOTS_DRIVE,
                "archetype": "sprint",
            },
            {"kind": "dunk"},
        ]
    return [{"kind": "shot"}]


def build_shot_micro_steps(
    *,
    family_id: str,
    contest_result: Optional[ContestResult],
    start_coords: Dict[str, GridCoord],
    shooter_id: str,
    defender_id: Optional[str],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    away_offense: bool,
    clock_start: ClockState,
    shot_type: str,
    next_step: NextStep,
    apply_contest_layer: bool,
    result_type: Optional[str] = None,
    dunk_miss: bool = False,
) -> List[AnimationStep]:
    """Build micro-movement AnimationSteps replacing the terminal [shoot] beat."""
    if shooter_id not in start_coords:
        return []

    shooter_coord = dict(start_coords[shooter_id])
    bucket = FAMILY_BUCKET.get(family_id, "C")
    beats = _build_family_beats(
        family_id, shooter_coord, away_offense, off_lineup, start_coords, shooter_id,
    )

    steps: List[AnimationStep] = []
    current_coords = {pid: dict(c) for pid, c in start_coords.items()}
    clock_remaining = float(clock_start["clock_remaining"])
    shot_clock_remaining = float(clock_start["shot_clock_remaining"])
    elapsed_total = 0.0

    shooter_player = _player_lookup_by_id(off_lineup, def_lineup, shooter_id)
    defender_player = (
        _player_lookup_by_id(off_lineup, def_lineup, defender_id) if defender_id else None
    )

    for beat_idx, beat in enumerate(beats):
        is_last = beat_idx == len(beats) - 1
        beat_bucket = beat.get("beat_bucket") or bucket
        contest = contest_result if apply_contest_layer else None
        defender_behavior = None
        if contest and defender_id:
            defender_behavior = _resolve_defender_behavior(
                family_id, bucket, contest, beat_bucket=beat.get("beat_bucket"),
            )

        actions, archetypes, destinations = _stationary_maps(current_coords)
        end_coords = {pid: dict(c) for pid, c in current_coords.items()}
        flourish_map: Dict[str, Any] = {}
        gate_id = shooter_id
        step_t = MICRO_FLOURISH_BEAT_T
        dunk_meta: Optional[Dict[str, Any]] = None
        dunk_ball_end: Any = None
        dunk_arrival_sfx: Optional[Dict[str, Any]] = None

        kind = beat.get("kind")
        if kind == "move":
            dx, dy = float(beat["dx"]), float(beat["dy"])
            if contest == "defense_win" and beat_bucket == "A":
                dx *= MUSCLE_LOSS_COMPLETION
                dy *= MUSCLE_LOSS_COMPLETION
            dest = _offset_coord(current_coords[shooter_id], dx, dy)
            end_coords[shooter_id] = dest
            actions[shooter_id] = "cut"
            arch: PlayerArchetype = beat.get("archetype", "standard")
            archetypes[shooter_id] = arch
            destinations[shooter_id] = dest
            rate = _ag_grid_per_game_sec(shooter_player, arch)
            step_t = max(MICRO_MOVE_STEP_T_FLOOR, _euclid(current_coords[shooter_id], dest) / rate)
        elif kind == "move_to":
            dest = dict(beat["coord"])
            end_coords[shooter_id] = dest
            actions[shooter_id] = "cut"
            arch = beat.get("archetype", "cruise")
            archetypes[shooter_id] = arch
            destinations[shooter_id] = dest
            rate = _ag_grid_per_game_sec(shooter_player, arch)
            step_t = max(MICRO_MOVE_STEP_T_FLOOR, _euclid(current_coords[shooter_id], dest) / rate)
        elif kind == "flourish":
            who = beat.get("who", "shooter")
            pid = shooter_id if who == "shooter" else defender_id
            flourish_kind = beat.get("flourish", "pump_fake")
            if pid:
                flourish_map[str(pid)] = {"kind": flourish_kind, "target": "ball"}
            step_t = (
                PUMP_FAKE_FLOURISH_BEAT_T
                if flourish_kind == "pump_fake"
                else MICRO_FLOURISH_BEAT_T
            )
        elif kind == "shot":
            actions[shooter_id] = "shoot"
            archetypes[shooter_id] = "shot_motion"
            destinations[shooter_id] = None
            if contest:
                for pid, fl in _disruption_flourish_targets(
                    contest, shot_type, shooter_id, defender_id, family_id=family_id,
                ).items():
                    flourish_map.setdefault(pid, fl)
            step_t = max(MICRO_MOVE_STEP_T_FLOOR, MICRO_FLOURISH_BEAT_T)
        elif kind == "dunk":
            approach = _dunk_approach_coord(away_offense)
            resolve = _dunk_resolve_coord(away_offense)
            end_coords[shooter_id] = dict(approach)
            actions[shooter_id] = "shoot"
            archetypes[shooter_id] = "shot_motion"
            destinations[shooter_id] = dict(approach)
            dist = _euclid(current_coords[shooter_id], approach)
            wall_ms = _dunk_wall_clock_ms(dist, shooter_player)
            step_t = max(MICRO_MOVE_STEP_T_FLOOR, wall_ms / DUNK_CLOCK_MS_PER_GAME_SEC)
            result_upper = (result_type or "").upper()
            yield_before_slam = result_upper == "BLOCK" and not dunk_miss
            if contest:
                for pid, fl in _disruption_flourish_targets(
                    contest, shot_type, shooter_id, defender_id, family_id=family_id,
                ).items():
                    flourish_map.setdefault(pid, fl)
            dunk_meta = {
                "micro_beat_kind": "dunk",
                "approach_coord": dict(approach),
                "resolve_coord": dict(resolve),
                "dunk_rise_px": float(DUNK_RISE_PX),
                "dunk_rattle_mag_px": float(DUNK_RATTLE_MAG_PX),
                "dunk_rattle_ms": float(DUNK_RATTLE_MS),
                "dunk_ball_raise": float(DUNK_BALL_RAISE),
                "wall_clock_hold_ms": float(wall_ms),
                "yield_before_slam": yield_before_slam,
                "dunk_miss": bool(dunk_miss),
            }
            if result_upper == "MAKE" and not yield_before_slam and not dunk_miss:
                dunk_ball_end = {"coords": dict(resolve)}
                dunk_arrival_sfx = shot_result_sfx(None, "MAKE")
            else:
                dunk_ball_end = {"owner_player_id": str(shooter_id)}

        if defender_id and defender_behavior and defender_id in current_coords:
            pump_dir = None
            if defender_behavior == "bite":
                ux, uy = _unit_toward_rim(current_coords[shooter_id], away_offense)
                perp_x, perp_y = -uy, ux
                jab_sign = _perp_jab_direction(float(current_coords[shooter_id]["y"]))
                pump_dir = (perp_x * jab_sign, perp_y * jab_sign)
                flourish_map[str(defender_id)] = {"kind": "bite", "target": "ball"}
            def_end = _apply_defender_behavior_coord(
                defender_behavior,
                current_coords[shooter_id],
                end_coords.get(shooter_id, current_coords[shooter_id]),
                current_coords[defender_id],
                away_offense,
                pump_direction=pump_dir,
            )
            actions[defender_id] = "guard_ball" if kind in ("shot", "dunk") else "stationary"
            archetypes[defender_id] = "standard"
            destinations[defender_id] = def_end
            # Clamp the contest to what the defender can actually cover in this
            # (short) micro beat. def_end is the semantic target next to the
            # shooter; if the defender is far away, rendering the full target
            # over a ~140ms beat teleports him across the court (jet). Interrupt
            # his motion at his standard rate × step_t so he closes what he can.
            if defender_player is not None:
                rate = _ag_grid_per_game_sec(defender_player, "standard")
                clamped, _ = _motion_end_toward_dest(
                    current_coords[defender_id], def_end, rate, step_t,
                )
                end_coords[defender_id] = clamped
            else:
                end_coords[defender_id] = def_end

        clock_step_start: ClockState = {
            "clock_remaining": clock_remaining - elapsed_total,
            "shot_clock_remaining": shot_clock_remaining - elapsed_total,
        }
        clock_step_end: ClockState = {
            "clock_remaining": clock_remaining - elapsed_total - step_t,
            "shot_clock_remaining": shot_clock_remaining - elapsed_total - step_t,
        }

        shooter_gate_coord = end_coords.get(shooter_id, current_coords[shooter_id])
        trigger = _advance_player_reaches(shooter_id, shooter_gate_coord, step_t)
        if dunk_meta:
            trigger["metadata"] = {**(trigger.get("metadata") or {}), **dunk_meta}

        end_ball_state: Any = (
            dunk_ball_end if dunk_ball_end is not None else {"owner_player_id": str(shooter_id)}
        )
        step: AnimationStep = {
            "start": {
                "coords": {pid: dict(c) for pid, c in current_coords.items()},
                "destination": destinations,
                "action": actions,
                "archetype": archetypes,
                "ball": {"owner_player_id": str(shooter_id)},
                "clock": clock_step_start,
                "advance_trigger": trigger,
            },
            "end": {
                "coords": end_coords,
                "ball": end_ball_state,
                "time_elapsed": float(step_t),
                "clock": clock_step_end,
                "next": next_step if is_last else {"kind": "next_step", "index": len(steps) + 1},
            },
        }
        if dunk_arrival_sfx:
            step["start"]["sfx_on_ball_arrival"] = dunk_arrival_sfx
        if flourish_map:
            step["start"]["flourish"] = flourish_map
        stamp_tween_durations(
            step["start"], end_coords, float(step_t), off_lineup, def_lineup,
        )
        steps.append(step)
        current_coords = end_coords
        elapsed_total += step_t

    return steps


def _find_terminal_shoot_index(steps: List[AnimationStep]) -> Optional[int]:
    for i in range(len(steps) - 1, -1, -1):
        actions = (steps[i].get("start") or {}).get("action") or {}
        if any(v == "shoot" for v in actions.values()):
            return i
    return None


def _resolve_shooter_id_from_step(
    shoot_step: AnimationStep,
    turn_result: Dict[str, Any],
) -> Optional[str]:
    shooter_id = str(
        turn_result.get("shooter_id")
        or turn_result.get("shooter")
        or ""
    )
    if hasattr(turn_result.get("shooter"), "player_id"):
        shooter_id = str(turn_result["shooter"].player_id)
    start_coords = (shoot_step.get("start") or {}).get("coords") or {}
    if not shooter_id or shooter_id not in start_coords:
        for pid, act in ((shoot_step.get("start") or {}).get("action") or {}).items():
            if act == "shoot":
                shooter_id = str(pid)
                break
    if not shooter_id or shooter_id not in start_coords:
        return None
    return shooter_id


def _shooter_travel_grid_distance(
    shoot_step: AnimationStep,
    shooter_id: str,
) -> float:
    start_coords = (shoot_step.get("start") or {}).get("coords") or {}
    end_coords = (shoot_step.get("end") or {}).get("coords") or {}
    sc = start_coords.get(shooter_id)
    ec = end_coords.get(shooter_id)
    if not sc or not ec:
        return 0.0
    return _euclid(sc, ec)


def _is_travel_shoot_step(shoot_step: AnimationStep, shooter_id: str) -> bool:
    """True when the terminal [shoot] step includes meaningful sprint-to-spot."""
    return _shooter_travel_grid_distance(shoot_step, shooter_id) >= TRAVEL_SHOOT_MIN_GRID


def _demote_travel_shoot_step(shoot_step: AnimationStep, shooter_id: str) -> None:
    """Keep the travel tween; drop ``shoot`` until the micro chain release beat."""
    start = shoot_step.get("start") or {}
    actions = start.get("action") or {}
    if actions.get(shooter_id) != "shoot":
        return
    archetypes = start.get("archetype") or {}
    arch = archetypes.get(shooter_id, "standard")
    actions[shooter_id] = "sprint" if arch == "sprint" else "cut"


def _bump_next_step_indices(
    steps: List[AnimationStep],
    from_index: int,
    delta: int,
) -> None:
    """Shift ``next_step`` indices strictly above ``from_index``."""
    if delta <= 0:
        return
    for step in steps:
        nxt = step.get("end", {}).get("next")
        if not isinstance(nxt, dict) or nxt.get("kind") != "next_step":
            continue
        idx = nxt.get("index")
        if isinstance(idx, int) and idx > from_index:
            nxt["index"] = idx + delta


def _wire_micro_chain(
    micro_steps: List[AnimationStep],
    base_index: int,
    next_step: NextStep,
) -> None:
    for i, step in enumerate(micro_steps[:-1]):
        step["end"]["next"] = {"kind": "next_step", "index": base_index + i + 1}
    micro_steps[-1]["end"]["next"] = next_step


def inject_shot_micro_before_post_shot(
    steps: List[AnimationStep],
    turn_result: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    away_offense: bool,
) -> None:
    """Shared hook: in-place terminal [shoot] → micro chain; travel+shoot → insert after."""
    if turn_result.get("flss"):
        return
    apply_shot_micro_steps_to_chain(
        steps, turn_result, off_lineup, def_lineup, away_offense,
    )


def apply_shot_micro_steps_to_chain(
    steps: List[AnimationStep],
    turn_result: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    away_offense: bool,
) -> None:
    """Replace terminal [shoot] step with micro chain when turn carries telemetry."""
    result_type = (turn_result.get("result_type") or "").upper()
    if result_type not in ("MAKE", "MISS", "BLOCK"):
        return

    family_id = turn_result.get("micro_movement_family")
    if not family_id:
        return

    shoot_idx = _find_terminal_shoot_index(steps)
    if shoot_idx is None:
        return

    shoot_step = steps[shoot_idx]
    start_coords = (shoot_step.get("start") or {}).get("coords") or {}
    if not start_coords:
        return

    shooter_id = _resolve_shooter_id_from_step(shoot_step, turn_result)
    if not shooter_id:
        logging.warning("[MICRO] no shooter_id for micro steps")
        return

    travel_shoot = _is_travel_shoot_step(shoot_step, shooter_id)
    end_coords = (shoot_step.get("end") or {}).get("coords") or {}
    micro_start_coords = (
        {pid: dict(c) for pid, c in end_coords.items()}
        if travel_shoot and end_coords
        else start_coords
    )

    defender_id = None
    defender = turn_result.get("defender")
    if defender is not None:
        defender_id = str(getattr(defender, "player_id", defender))
    elif turn_result.get("defender_id"):
        defender_id = str(turn_result["defender_id"])

    if travel_shoot:
        clock_start = (shoot_step.get("end") or {}).get("clock") or {
            "clock_remaining": 0.0,
            "shot_clock_remaining": 0.0,
        }
    else:
        clock_start = (shoot_step.get("start") or {}).get("clock") or {
            "clock_remaining": 0.0,
            "shot_clock_remaining": 0.0,
        }
    next_step = (shoot_step.get("end") or {}).get("next") or {
        "kind": "next_step",
        "index": shoot_idx + 1,
    }

    contest_result = turn_result.get("contest_result")
    apply_contest = bool(turn_result.get("has_contest")) and contest_result is not None

    micro_steps = build_shot_micro_steps(
        family_id=str(family_id),
        contest_result=contest_result,
        start_coords=micro_start_coords,
        shooter_id=shooter_id,
        defender_id=defender_id,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        away_offense=away_offense,
        clock_start=clock_start,
        shot_type=str(turn_result.get("shot_type") or "outside"),
        next_step=next_step,
        apply_contest_layer=apply_contest,
        result_type=str(result_type),
        dunk_miss=bool(turn_result.get("dunk_miss")),
    )
    if not micro_steps:
        return

    if travel_shoot:
        _demote_travel_shoot_step(shoot_step, shooter_id)
        insert_at = shoot_idx + 1
        delta = len(micro_steps)
        steps[insert_at:insert_at] = micro_steps
        shoot_step["end"]["next"] = {"kind": "next_step", "index": insert_at}
        _bump_next_step_indices(steps, insert_at, delta)
        _wire_micro_chain(micro_steps, insert_at, next_step)
        logging.debug(
            "[MICRO] insert after travel idx=%d family=%s contest=%s "
            "travel=%.1f n_beats=%d",
            shoot_idx, family_id, contest_result,
            _shooter_travel_grid_distance(shoot_step, shooter_id),
            len(micro_steps),
        )
        return

    base_index = shoot_idx
    delta = len(micro_steps) - 1
    steps[shoot_idx : shoot_idx + 1] = micro_steps
    if delta:
        _bump_next_step_indices(steps, base_index, delta)
    _wire_micro_chain(micro_steps, base_index, next_step)

    logging.debug(
        "[MICRO] replaced shoot step idx=%d family=%s contest=%s n_beats=%d",
        shoot_idx, family_id, contest_result, len(micro_steps),
    )
