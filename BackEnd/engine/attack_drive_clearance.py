"""Motion offense attack-drive: lane clearance, perimeter reads, drive contest, dish/shoot."""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional, Set, Tuple

from BackEnd.constants import HCO_STRING_SPOTS, HOME_RIM_COORDS, AWAY_RIM_COORDS, CONTEST_EUCLIDEAN_RADIUS
from BackEnd.utils.defense_identity import defense_zone_shell_variant
from BackEnd.utils.defense_utils import is_zone_defense
from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team
from BackEnd.utils.shared import (
    calculate_ball_handling_score,
    calculate_defender_pressure_score,
    get_away_player_coords,
    player_read,
)
from BackEnd.utils.shared_defense import (
    _get_131_zone_boundaries,
    _get_23_zone_boundaries,
    _get_32_zone_boundaries,
    _point_in_zone,
    get_defender_coords,
)

_OFFENSE_POSITIONS = ["PG", "SG", "SF", "PF", "C"]
_BLAST_RADIUS_SPOTS = frozenset(
    {
        "upper lowPost",
        "upper midPost",
        "upper bird",
        "lower lowPost",
        "lower midPost",
        "lower bird",
    }
)
_CENTRAL_DRIVE_DESTINATIONS = frozenset({"midLane", "basketSpot"})
ATTACK_DRIVE_CONTEST_RADIUS = float(CONTEST_EUCLIDEAN_RADIUS)
ATTACK_DRIVE_INSIDE_RADIUS = 15.0
PERIMETER_OFFENSE_READ_BASE = 150
PERIMETER_DEFENSE_READ_BASE = 125
HELP_READ_BASE = 100
READ_THRESHOLD_FLOOR = -3
DRIVE_CONTEST_DEF_BONUS_MULTIPLIER = 2

_PERIMETER_SPOTS = frozenset(
    {
        "key",
        "deep key",
        "upper midWing",
        "lower midWing",
        "upper wing",
        "lower wing",
        "upper midCorner",
        "lower midCorner",
        "upper corner",
        "lower corner",
        "deep upper wing",
        "deep lower wing",
        "deep upper baseline",
        "deep lower baseline",
    }
)
def _norm_loc(location: str) -> str:
    return (location or "key").strip().lower()


def _euclid(a: Dict[str, float], b: Dict[str, float]) -> float:
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))


def _home_spot_coords(location: str) -> Dict[str, float]:
    raw = HCO_STRING_SPOTS.get(location, {"x": 50, "y": 25})
    return {"x": float(raw["x"]), "y": float(raw["y"])}


def _display_coords(home_coords: Dict[str, float], is_away_offense: bool) -> Dict[str, float]:
    c = {"x": float(home_coords["x"]), "y": float(home_coords["y"])}
    if is_away_offense:
        return get_away_player_coords(c)
    return c


def _spot_display_coords(location: str, is_away_offense: bool) -> Dict[str, float]:
    return _display_coords(_home_spot_coords(location), is_away_offense)


def _basket_display_coords(is_away_offense: bool) -> Dict[str, float]:
    if is_away_offense:
        return {"x": float(AWAY_RIM_COORDS["x"]), "y": float(AWAY_RIM_COORDS["y"])}
    return {"x": float(HOME_RIM_COORDS["x"]), "y": float(HOME_RIM_COORDS["y"])}


def _vertical_half(location: str) -> Optional[str]:
    loc = _norm_loc(location)
    if "upper" in loc:
        return "upper"
    if "lower" in loc:
        return "lower"
    return None


def _is_perimeter_spot(location: str) -> bool:
    return _norm_loc(location) in {s.lower() for s in _PERIMETER_SPOTS}


def _tangential_targets(location: str) -> List[str]:
    loc = _norm_loc(location)
    half = _vertical_half(location)

    if loc == "key":
        return ["upper midWing", "lower midWing"]
    if loc == "deep key":
        return ["key", "upper midWing", "lower midWing"]
    if "midwing" in loc.replace(" ", ""):
        if half == "upper":
            return ["key", "upper wing"]
        if half == "lower":
            return ["key", "lower wing"]
        return ["key", "upper wing", "lower wing"]
    if "midcorner" in loc.replace(" ", ""):
        if half == "upper":
            return ["upper wing", "upper corner"]
        if half == "lower":
            return ["lower wing", "lower corner"]
        return ["upper wing", "upper corner", "lower wing", "lower corner"]
    if "corner" in loc and "midcorner" not in loc.replace(" ", ""):
        if half == "upper":
            return ["upper midCorner"]
        if half == "lower":
            return ["lower midCorner"]
        return ["upper midCorner", "lower midCorner"]
    if "wing" in loc and "midwing" not in loc.replace(" ", ""):
        if loc == "deep upper wing":
            return ["key", "upper wing", "upper midWing"]
        if loc == "deep lower wing":
            return ["key", "lower wing", "lower midWing"]
        if half == "upper":
            return ["upper midWing", "upper midCorner"]
        if half == "lower":
            return ["lower midWing", "lower midCorner"]
        return ["upper midWing", "upper midCorner", "lower midWing", "lower midCorner"]
    if "baseline" in loc:
        if half == "upper" or "upper" in loc:
            return ["upper corner", "upper midCorner", "upper wing"]
        if half == "lower" or "lower" in loc:
            return ["lower corner", "lower midCorner", "lower wing"]
    return []


def _drive_destination_half(destination: str) -> str:
    if destination in _CENTRAL_DRIVE_DESTINATIONS:
        return "central"
    if "upper" in destination.lower():
        return "upper"
    if "lower" in destination.lower():
        return "lower"
    return "central"


def _is_in_blast_radius(location: str, destination: str, dest_half: str) -> bool:
    if location == destination:
        return True
    if destination in _CENTRAL_DRIVE_DESTINATIONS:
        return False
    if location not in _BLAST_RADIUS_SPOTS:
        return False
    if dest_half == "upper":
        return "upper" in location.lower()
    if dest_half == "lower":
        return "lower" in location.lower()
    return False


def _evac_y_range(drive_half: str) -> Tuple[float, float]:
    if drive_half == "upper":
        return (19.0, 25.0)
    if drive_half == "lower":
        return (26.0, 32.0)
    return (19.0, 25.0)


def _evac_x_range(is_away_offense: bool) -> Tuple[float, float]:
    if is_away_offense:
        return (13.0, 23.0)
    return (77.0, 87.0)


def _evac_half_for_player(y: float, destination_half: str) -> str:
    if destination_half in ("upper", "lower"):
        return destination_half
    return "upper" if y > 25.0 else "lower"


def _generate_evac_coord(
    existing: List[Dict[str, float]],
    is_away_offense: bool,
    drive_half: str,
    player_y: float,
    max_attempts: int = 60,
) -> Dict[str, float]:
    half = _evac_half_for_player(player_y, drive_half)
    y_min, y_max = _evac_y_range(half)
    x_min, x_max = _evac_x_range(is_away_offense)
    for _ in range(max_attempts):
        x = round(random.uniform(x_min, x_max), 2)
        y = round(random.uniform(y_min, y_max), 2)
        candidate = {"x": x, "y": y}
        if all(_euclid(candidate, e) >= 3.0 for e in existing):
            return candidate
    base_x = (x_min + x_max) / 2.0
    base_y = (y_min + y_max) / 2.0
    for n in range(20):
        candidate = {"x": round(base_x + n * 0.5, 2), "y": round(base_y + n * 0.4, 2)}
        if all(_euclid(candidate, e) >= 3.0 for e in existing):
            return candidate
    return {"x": round(base_x, 2), "y": round(base_y, 2)}


def _select_clearance_dish_candidate(
    candidates: List[Dict[str, Any]],
    is_away_offense: bool,
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    basket_x = 10.0 if is_away_offense else 90.0

    def coords(c: Dict[str, Any]) -> Dict[str, Any]:
        nested = c.get("coords")
        return nested if isinstance(nested, dict) else c

    def dist(c: Dict[str, Any]) -> float:
        return abs(float(coords(c)["x"]) - basket_x)

    best = min(dist(c) for c in candidates)
    tied = [c for c in candidates if dist(c) == best]
    return random.choice(tied)


def _offensive_positions_from_step(
    selected_step: Dict[str, Any],
    is_away_offense: bool,
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    pos_actions = selected_step.get("pos_actions") or {}
    for pos in _OFFENSE_POSITIONS:
        info = pos_actions.get(pos) or {}
        location = info.get("location") or info.get("spot") or "key"
        if "coords" in info:
            coords = {
                "x": float(info["coords"]["x"]),
                "y": float(info["coords"]["y"]),
            }
        else:
            coords = _display_coords(_home_spot_coords(location), is_away_offense)
        out[pos] = {"location": location, "coords": coords}
    return out


def _perimeter_offense_threshold(off_team: Any) -> int:
    attrs = getattr(off_team, "team_attributes", {}) or {}
    chem = int(attrs.get("team_chemistry") or 0)
    off_eff = int(attrs.get("offensive_efficiency") or 0)
    raw = PERIMETER_OFFENSE_READ_BASE - (chem + off_eff)
    return max(READ_THRESHOLD_FLOOR, raw)


def _perimeter_defense_threshold(def_team: Any) -> int:
    attrs = getattr(def_team, "team_attributes", {}) or {}
    chem = int(attrs.get("team_chemistry") or 0)
    def_eff = int(attrs.get("defensive_efficiency") or 0)
    raw = PERIMETER_DEFENSE_READ_BASE - (chem + def_eff)
    return max(READ_THRESHOLD_FLOOR, raw)


def _defender_help_threshold(def_team: Any) -> int:
    attrs = getattr(def_team, "team_attributes", {}) or {}
    chem = int(attrs.get("team_chemistry") or 0)
    execution = int(attrs.get("defensive_efficiency") or 0)
    raw = HELP_READ_BASE - (chem + execution)
    return max(READ_THRESHOLD_FLOOR, raw)


def _reverse_matchups(matchups: Dict[str, str]) -> Dict[str, str]:
    return {off_pos: def_pos for def_pos, off_pos in matchups.items()}


def _defender_display_positions(
    off_positions: Dict[str, Dict[str, Any]],
    matchups: Dict[str, str],
    ball_handler_pos: str,
    is_away_offense: bool,
    aggression: str,
) -> Dict[str, Dict[str, float]]:
    positions: Dict[str, Dict[str, float]] = {}
    for def_pos, off_pos in matchups.items():
        off = off_positions.get(off_pos) or off_positions.get(def_pos) or {}
        off_coord = off.get("coords") or {"x": 50.0, "y": 25.0}
        spot = off.get("location") or "key"
        bh_coord = (off_positions.get(ball_handler_pos) or {}).get("coords")
        positions[def_pos] = get_defender_coords(
            off_coord,
            is_away_offense,
            aggression,
            spot,
            bh_coord if off_pos != ball_handler_pos else None,
            is_ball_handler=(off_pos == ball_handler_pos),
            ball_spot=(off_positions.get(ball_handler_pos) or {}).get("location") or "key",
        )
    return positions


def _closest_defender_to_point(
    def_positions: Dict[str, Dict[str, float]],
    point: Dict[str, float],
    exclude: Optional[set] = None,
) -> Optional[str]:
    exclude = exclude or set()
    best_pos = None
    best_dist = float("inf")
    for def_pos, coord in def_positions.items():
        if def_pos in exclude:
            continue
        d = _euclid(coord, point)
        if d < best_dist:
            best_dist = d
            best_pos = def_pos
    return best_pos


def _zone_boundaries_for_spot(
    defense_playcall: str,
    ball_spot: str,
    is_away_offense: bool,
) -> Dict[str, Any]:
    zv = defense_zone_shell_variant(defense_playcall) or "23"
    if zv == "32":
        return _get_32_zone_boundaries(ball_spot, is_away_offense)
    if zv == "131":
        return _get_131_zone_boundaries(ball_spot, is_away_offense)
    return _get_23_zone_boundaries(ball_spot, is_away_offense)


def _defender_for_zone_point(
    zone_boundaries: Dict[str, Any],
    point: Dict[str, float],
    is_away_offense: bool,
) -> Optional[str]:
    for def_pos, zone_poly in zone_boundaries.items():
        if zone_poly and _point_in_zone(point, zone_poly, is_away_offense):
            return def_pos
    return None


def _pos_action_for_target(target: Dict[str, Any], action: str) -> Dict[str, Any]:
    if target.get("location"):
        return {"location": target["location"], "action": action}
    return {"coords": dict(target["coords"]), "action": action}


def _target_from_location(location: str, is_away_offense: bool) -> Dict[str, Any]:
    return {
        "location": location,
        "coords": _spot_display_coords(location, is_away_offense),
    }


def _compute_halfway(
    start: Dict[str, float],
    end: Dict[str, float],
) -> Dict[str, float]:
    return {
        "x": round((float(start["x"]) + float(end["x"])) / 2.0, 2),
        "y": round((float(start["y"]) + float(end["y"])) / 2.0, 2),
    }


def _occupied_locations(drive_end_by_pos: Dict[str, Dict[str, Any]]) -> Set[str]:
    occupied: Set[str] = set()
    for target in drive_end_by_pos.values():
        loc = target.get("location")
        if loc:
            occupied.add(_norm_loc(loc))
    return occupied


def _apply_perimeter_relocations(
    *,
    off_positions: Dict[str, Dict[str, Any]],
    drive_end_by_pos: Dict[str, Dict[str, Any]],
    clearance_movers: Set[str],
    ball_handler_pos: str,
    off_lineup: Dict[str, Any],
    off_team: Any,
    is_away_offense: bool,
) -> Set[str]:
    """Single-pass random-order perimeter reads. Returns positions that relocated."""
    threshold = _perimeter_offense_threshold(off_team)
    eligible = [
        pos
        for pos in _OFFENSE_POSITIONS
        if pos != ball_handler_pos
        and pos not in clearance_movers
        and _is_perimeter_spot(off_positions[pos]["location"])
    ]
    random.shuffle(eligible)
    occupied = _occupied_locations(drive_end_by_pos)
    relocated: Set[str] = set()

    for pos in eligible:
        player = off_lineup.get(pos)
        if not player:
            continue
        if player_read(player) <= threshold:
            continue
        start_loc = off_positions[pos]["location"]
        open_targets = [
            t
            for t in _tangential_targets(start_loc)
            if _norm_loc(t) not in occupied
        ]
        if not open_targets:
            continue
        chosen = random.choice(open_targets)
        old_loc = _norm_loc((drive_end_by_pos.get(pos) or {}).get("location") or start_loc)
        drive_end_by_pos[pos] = _target_from_location(chosen, is_away_offense)
        if old_loc in occupied:
            occupied.discard(old_loc)
        occupied.add(_norm_loc(chosen))
        relocated.add(pos)

    return relocated


def _compute_drive_scores(
    driver: Any,
    defender: Any,
    off_team: Any,
    def_team: Any,
    defense_playcall: str,
) -> Tuple[float, float, bool, float]:
    off_attrs = getattr(off_team, "team_attributes", {}) or {}
    def_attrs = getattr(def_team, "team_attributes", {}) or {}
    off_eff = int(off_attrs.get("offensive_efficiency") or 0)
    def_eff = int(def_attrs.get("defensive_efficiency") or 0)
    def_chem = int(def_attrs.get("team_chemistry") or 0)

    off_score = float(calculate_ball_handling_score(driver))
    off_score += off_eff * random.randint(1, 3)
    def_score = float(calculate_defender_pressure_score(defender, defense_playcall))
    def_score += def_eff * random.randint(1, 3)
    def_bonus = DRIVE_CONTEST_DEF_BONUS_MULTIPLIER * (def_chem + def_eff)
    margin = off_score - (def_score + def_bonus)
    offense_wins = margin > 0
    return off_score, def_score, offense_wins, margin


# Dynamic HCO Defense — S2a: 3-tier primary drive contest (Dynamic_MM_Brief §7). The on-ball contest
# margin (off_score − (def_score + def_bonus)) is banded into 3 outcomes instead of a binary win,
# mirroring resolve_contest's ±band structure:
#   A blow-by : margin >  +BAND   → BH beats his man, drives on (help cutoff may still apply, S2c)
#   B neutral : |margin| <= BAND  → stopped 35–65% to the rim by lean, then pull-up / dish (S2d/e)
#   C stopped : margin <  −BAND   → walled off 0–5 grid short (S2d), returns to the walk (S2e)
# `stop_fraction` = drive progress [0,1] at the stop (1.0 = reaches the rim). Flag-gated; flag-off
# keeps today's binary. Band + fractions are first-cut — MC-tuned in S2f.
DRIVE_TIER_NEUTRAL_BAND = 75.0        # ± margin band for the neutral tier
DRIVE_NEUTRAL_STOP_MIN = 0.35         # Tier B: defense-lean stop (fraction to the rim)
DRIVE_NEUTRAL_STOP_MAX = 0.65         # Tier B: offense-lean stop
DRIVE_STOPPED_MAX_FRACTION = 0.15     # Tier C: BH advances at most this fraction (S2d clamps to ≤5 grid)


def _classify_drive_tier(margin: float, band: float = DRIVE_TIER_NEUTRAL_BAND) -> Tuple[str, float]:
    """S2a: map the drive contest margin → (tier, stop_fraction). tier ∈ {'A','B','C'}; stop_fraction
    is the drive progress [0,1] at which the BH is stopped (1.0 = reaches the rim). See §7."""
    if margin > band:
        return "A", 1.0
    if margin < -band:
        # Tier C: walled off early; advance scales mildly with how close it was (0 by margin ≈ −2·band).
        frac = DRIVE_STOPPED_MAX_FRACTION * max(0.0, 1.0 + margin / (2.0 * band))
        return "C", max(0.0, min(DRIVE_STOPPED_MAX_FRACTION, frac))
    # Tier B: neutral — lean from margin within [−band, +band] → [MIN, MAX].
    lean = 0.5 + 0.5 * (margin / band)  # 0 at −band, 1 at +band
    frac = DRIVE_NEUTRAL_STOP_MIN + (DRIVE_NEUTRAL_STOP_MAX - DRIVE_NEUTRAL_STOP_MIN) * lean
    return "B", max(DRIVE_NEUTRAL_STOP_MIN, min(DRIVE_NEUTRAL_STOP_MAX, frac))


def _guardians_within_radius(
    point: Dict[str, float],
    defender_coords: Dict[str, Dict[str, float]],
    radius: float = ATTACK_DRIVE_CONTEST_RADIUS,
) -> List[str]:
    guardians: List[Tuple[str, float]] = []
    for def_pos, coord in defender_coords.items():
        d = _euclid(point, coord)
        if d <= radius:
            guardians.append((def_pos, d))
    guardians.sort(key=lambda t: t[1])
    return [g[0] for g in guardians]


def _select_interior_dish_target(
    drive_end_by_pos: Dict[str, Dict[str, Any]],
    ball_handler_pos: str,
) -> Optional[str]:
    for pos in _OFFENSE_POSITIONS:
        if pos == ball_handler_pos:
            continue
        loc = _norm_loc((drive_end_by_pos.get(pos) or {}).get("location", ""))
        if loc == "midlane":
            return pos

    low_posts = [
        pos
        for pos in _OFFENSE_POSITIONS
        if pos != ball_handler_pos
        and _norm_loc((drive_end_by_pos.get(pos) or {}).get("location", ""))
        in {"upper lowpost", "lower lowpost"}
    ]
    if low_posts:
        return random.choice(low_posts)

    mid_posts = [
        pos
        for pos in _OFFENSE_POSITIONS
        if pos != ball_handler_pos
        and _norm_loc((drive_end_by_pos.get(pos) or {}).get("location", ""))
        in {"upper midpost", "lower midpost"}
    ]
    if mid_posts:
        return random.choice(mid_posts)
    return None


def _select_random_dish_target(
    drive_end_by_pos: Dict[str, Dict[str, Any]],
    ball_handler_pos: str,
) -> Optional[str]:
    candidates = [p for p in _OFFENSE_POSITIONS if p != ball_handler_pos]
    if not candidates:
        return None
    return random.choice(candidates)


def _resolve_dish_target(
    drive_end_by_pos: Dict[str, Dict[str, Any]],
    ball_handler_pos: str,
    prefer_interior: bool,
) -> Optional[str]:
    if prefer_interior:
        interior = _select_interior_dish_target(drive_end_by_pos, ball_handler_pos)
        if interior:
            return interior
    return _select_random_dish_target(drive_end_by_pos, ball_handler_pos)


def _shot_type_for_coords(
    coords: Dict[str, float],
    is_away_offense: bool,
) -> Tuple[str, str]:
    basket = _basket_display_coords(is_away_offense)
    if _euclid(coords, basket) <= ATTACK_DRIVE_INSIDE_RADIUS:
        return "inside", "Inside"
    return "outside", "Outside"


def _stationary_pos_actions(
    drive_end_by_pos: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    return {
        pos: _pos_action_for_target(drive_end_by_pos[pos], "stationary")
        for pos in _OFFENSE_POSITIONS
    }


def build_attack_drive_clearance(
    *,
    selected_step: Dict[str, Any],
    ball_handler_pos: str,
    destination_location: str,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    game: Any,
    is_away_offense: bool,
) -> Dict[str, Any]:
    """Build drive/shoot pos_actions and ``_attack_drive`` metadata (legacy wrapper)."""
    return build_attack_drive_sequence(
        selected_step=selected_step,
        ball_handler_pos=ball_handler_pos,
        start_location=(selected_step.get("pos_actions") or {})
        .get(ball_handler_pos, {})
        .get("location", "key"),
        destination_location=destination_location,
        timestamp=0,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        game=game,
        is_away_offense=is_away_offense,
        legacy_pos_actions_only=True,
    )


def build_attack_drive_sequence(
    *,
    selected_step: Dict[str, Any],
    ball_handler_pos: str,
    start_location: str,
    destination_location: str,
    timestamp: int,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    game: Any,
    is_away_offense: bool,
    legacy_pos_actions_only: bool = False,
) -> Dict[str, Any]:
    """Full motion attack drive: clearance, perimeter reads, contest, dish/shoot steps."""
    dest_half = _drive_destination_half(destination_location)
    drive_end = _spot_display_coords(destination_location, is_away_offense)
    driver_start = _spot_display_coords(start_location, is_away_offense)
    midlane_end = _spot_display_coords("midLane", is_away_offense)

    off_positions = _offensive_positions_from_step(selected_step, is_away_offense)
    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    aggression = "normal"
    if def_team is not None:
        aggression = (getattr(def_team, "strategy_calls", {}) or {}).get(
            "aggression_call", "normal"
        )
    defense_playcall = (getattr(game, "game_state", {}) or {}).get(
        "defense_playcall", "man"
    )

    # --- Lane clearance -------------------------------------------------------
    in_way: List[Dict[str, Any]] = []
    for pos in _OFFENSE_POSITIONS:
        if pos == ball_handler_pos:
            continue
        loc = off_positions[pos]["location"]
        if _is_in_blast_radius(loc, destination_location, dest_half):
            entry = dict(off_positions[pos])
            entry["position"] = pos
            in_way.append(entry)

    clearance_dish_pos: Optional[str] = None
    evac_targets: List[Dict[str, Any]] = []
    placed_coords: List[Dict[str, float]] = [dict(drive_end)]

    if destination_location != "midLane" and in_way:
        dish = _select_clearance_dish_candidate(in_way, is_away_offense)
        if dish:
            clearance_dish_pos = dish["position"]
            evac_targets = [c for c in in_way if c["position"] != clearance_dish_pos]
    else:
        evac_targets = list(in_way)

    clearance_movers: Set[str] = set()
    if clearance_dish_pos:
        clearance_movers.add(clearance_dish_pos)
    clearance_movers.update(c["position"] for c in evac_targets)

    drive_end_by_pos: Dict[str, Dict[str, Any]] = {}
    for pos in _OFFENSE_POSITIONS:
        if pos == ball_handler_pos:
            drive_end_by_pos[pos] = {
                "location": destination_location,
                "coords": dict(drive_end),
            }
            continue
        if pos == clearance_dish_pos:
            drive_end_by_pos[pos] = {"location": "midLane", "coords": dict(midlane_end)}
            continue
        if any(c["position"] == pos for c in evac_targets):
            player_y = float(off_positions[pos]["coords"]["y"])
            evac = _generate_evac_coord(
                placed_coords,
                is_away_offense,
                dest_half,
                player_y,
            )
            placed_coords.append(evac)
            drive_end_by_pos[pos] = {"coords": evac}
            continue
        drive_end_by_pos[pos] = {
            "location": off_positions[pos]["location"],
            "coords": dict(off_positions[pos]["coords"]),
        }

    # --- Perimeter relocation reads -------------------------------------------
    perimeter_moved = _apply_perimeter_relocations(
        off_positions=off_positions,
        drive_end_by_pos=drive_end_by_pos,
        clearance_movers=clearance_movers,
        ball_handler_pos=ball_handler_pos,
        off_lineup=off_lineup,
        off_team=off_team,
        is_away_offense=is_away_offense,
    )

    # --- Drive pos actions ----------------------------------------------------
    drive_pos_actions: Dict[str, Dict[str, Any]] = {}
    for pos in _OFFENSE_POSITIONS:
        target = drive_end_by_pos[pos]
        if pos == ball_handler_pos:
            drive_pos_actions[pos] = _pos_action_for_target(target, "drive")
        elif (
            pos == clearance_dish_pos
            or any(c["position"] == pos for c in evac_targets)
            or pos in perimeter_moved
        ):
            drive_pos_actions[pos] = _pos_action_for_target(target, "cut")
        else:
            drive_pos_actions[pos] = _pos_action_for_target(target, "stationary")

    # --- Defensive reactions --------------------------------------------------
    defender_overrides: Dict[str, Dict[str, Any]] = {}
    double_team = False
    help_read_success = False
    drive_offense_wins = False
    # S2a — 3-tier drive contest (Dynamic_MM_Brief §7). Flag-gated on the turn's defense posture;
    # flag-off keeps the binary win/lose. `drive_tier` / `drive_stop_fraction` ride on the meta for
    # S2b (contact), S2c (help cutoff), S2d (path-stop), S2e (return-to-walk).
    _game_state = getattr(game, "game_state", {}) or {}
    _three_tier = bool(_game_state.get("_hco_defense_posture"))
    drive_tier = "A"
    drive_stop_fraction = 1.0
    bh_defender_pos: Optional[str] = None
    off_to_def: Dict[str, str] = {}
    def_positions: Dict[str, Dict[str, float]] = {}
    zone_boundaries: Dict[str, Any] = {}

    final_off_for_defense = {
        pos: {
            "location": drive_end_by_pos[pos].get("location") or off_positions[pos]["location"],
            "coords": drive_end_by_pos[pos].get("coords") or off_positions[pos]["coords"],
        }
        for pos in _OFFENSE_POSITIONS
    }

    if is_zone_defense(defense_playcall):
        zone_boundaries = _zone_boundaries_for_spot(
            defense_playcall, destination_location, is_away_offense
        )
        bh_coord = off_positions[ball_handler_pos]["coords"]
        bh_zone_def = _defender_for_zone_point(zone_boundaries, bh_coord, is_away_offense)
        drive_zone_def = _defender_for_zone_point(zone_boundaries, drive_end, is_away_offense)
        bh_defender_pos = bh_zone_def or drive_zone_def

        for def_pos in _OFFENSE_POSITIONS:
            if not def_lineup.get(def_pos):
                continue
            off_pos = None
            for pos in _OFFENSE_POSITIONS:
                start = off_positions[pos]
                start_coord = start["coords"]
                if _defender_for_zone_point(zone_boundaries, start_coord, is_away_offense) == def_pos:
                    off_pos = pos
                    break
            if off_pos and off_pos in perimeter_moved:
                help_player = def_lineup.get(def_pos)
                if help_player and player_read(help_player) > _perimeter_defense_threshold(def_team):
                    end_off = final_off_for_defense[off_pos]
                    spot = end_off.get("location") or "key"
                    defender_overrides[def_pos] = {
                        "coords": get_defender_coords(
                            end_off["coords"],
                            is_away_offense,
                            aggression,
                            spot,
                            drive_end,
                            is_ball_handler=False,
                            ball_spot=destination_location,
                        ),
                        "action": "cut",
                    }

        driver = off_lineup.get(ball_handler_pos)
        primary_def = def_lineup.get(bh_defender_pos) if bh_defender_pos else None
        if driver and primary_def:
            _, _, drive_offense_wins, _margin = _compute_drive_scores(
                driver, primary_def, off_team, def_team, defense_playcall,
            )
            # S2a is ADDITIVE: classify the tier + stop_fraction for downstream phases, but leave the
            # binary `drive_offense_wins` (and today's defender override) UNTOUCHED until S2b–e/S2d
            # consume the tier. So flag-on and flag-off behavior are both unchanged at this stage.
            if _three_tier:
                drive_tier, drive_stop_fraction = _classify_drive_tier(_margin)
            else:
                drive_tier = "A" if drive_offense_wins else "C"
                drive_stop_fraction = 1.0 if drive_offense_wins else DRIVE_STOPPED_MAX_FRACTION

        if bh_defender_pos and bh_defender_pos in def_lineup:
            if drive_offense_wins:
                halfway = _compute_halfway(driver_start, drive_end)
                defender_overrides[bh_defender_pos] = {
                    "coords": halfway,
                    "action": "cut",
                }
            else:
                defender_overrides[bh_defender_pos] = {
                    "coords": get_defender_coords(
                        drive_end,
                        is_away_offense,
                        aggression,
                        destination_location,
                        None,
                        is_ball_handler=True,
                    ),
                    "action": "guard_ball",
                }

        if clearance_dish_pos:
            dish_def = _defender_for_zone_point(
                zone_boundaries,
                drive_end_by_pos[clearance_dish_pos]["coords"],
                is_away_offense,
            )
            if dish_def and dish_def not in {bh_defender_pos}:
                dish_player = def_lineup.get(dish_def)
                if dish_player and player_read(dish_player) > _defender_help_threshold(def_team):
                    double_team = True
                    defender_overrides[dish_def] = {
                        "coords": get_defender_coords(
                            drive_end,
                            is_away_offense,
                            aggression,
                            destination_location,
                            None,
                            is_ball_handler=True,
                        ),
                        "action": "guard_ball",
                    }

        zone_def_positions: Dict[str, Dict[str, float]] = {}
        for def_pos in _OFFENSE_POSITIONS:
            if not def_lineup.get(def_pos):
                continue
            guarded_off = None
            for op in _OFFENSE_POSITIONS:
                if _defender_for_zone_point(
                    zone_boundaries, final_off_for_defense[op]["coords"], is_away_offense,
                ) == def_pos:
                    guarded_off = op
                    break
            if guarded_off is None:
                continue
            end_off = final_off_for_defense[guarded_off]
            zone_def_positions[def_pos] = get_defender_coords(
                end_off["coords"],
                is_away_offense,
                aggression,
                end_off.get("location") or "key",
                drive_end,
                is_ball_handler=(guarded_off == ball_handler_pos),
                ball_spot=destination_location,
            )

        help_def = _closest_defender_to_point(
            zone_def_positions,
            midlane_end if clearance_dish_pos else drive_end,
            exclude={bh_defender_pos} if bh_defender_pos else set(),
        )
        if help_def and help_def not in defender_overrides:
            help_player = def_lineup.get(help_def)
            if help_player and player_read(help_player) > _defender_help_threshold(def_team):
                help_read_success = True
                help_target_pos = clearance_dish_pos or ball_handler_pos
                help_off = final_off_for_defense[help_target_pos]
                help_spot = help_off.get("location") or "midLane"
                defender_overrides[help_def] = {
                    "coords": get_defender_coords(
                        help_off["coords"],
                        is_away_offense,
                        aggression,
                        help_spot,
                        drive_end,
                        is_ball_handler=False,
                        ball_spot=destination_location,
                    ),
                    "action": "guard_offball",
                }
    else:
        defending_is_user = getattr(def_team, "is_user_team", False)
        matchups = get_matchups_for_defending_team(
            getattr(game, "game_state", {}) or {},
            defending_is_user,
        )
        off_to_def = _reverse_matchups(matchups)
        def_positions = _defender_display_positions(
            off_positions,
            matchups,
            ball_handler_pos,
            is_away_offense,
            aggression,
        )
        bh_defender_pos = off_to_def.get(ball_handler_pos, ball_handler_pos)

        for off_pos in perimeter_moved:
            def_pos = off_to_def.get(off_pos)
            if not def_pos or def_pos not in def_lineup:
                continue
            def_player = def_lineup.get(def_pos)
            if not def_player or player_read(def_player) <= _perimeter_defense_threshold(def_team):
                continue
            end_off = final_off_for_defense[off_pos]
            spot = end_off.get("location") or "key"
            defender_overrides[def_pos] = {
                "coords": get_defender_coords(
                    end_off["coords"],
                    is_away_offense,
                    aggression,
                    spot,
                    drive_end,
                    is_ball_handler=False,
                    ball_spot=destination_location,
                ),
                "action": "cut",
            }

        driver = off_lineup.get(ball_handler_pos)
        primary_def = def_lineup.get(bh_defender_pos) if bh_defender_pos else None
        if driver and primary_def:
            _, _, drive_offense_wins, _margin = _compute_drive_scores(
                driver, primary_def, off_team, def_team, defense_playcall,
            )
            # S2a is ADDITIVE: classify the tier + stop_fraction for downstream phases, but leave the
            # binary `drive_offense_wins` (and today's defender override) UNTOUCHED until S2b–e/S2d
            # consume the tier. So flag-on and flag-off behavior are both unchanged at this stage.
            if _three_tier:
                drive_tier, drive_stop_fraction = _classify_drive_tier(_margin)
            else:
                drive_tier = "A" if drive_offense_wins else "C"
                drive_stop_fraction = 1.0 if drive_offense_wins else DRIVE_STOPPED_MAX_FRACTION

        if bh_defender_pos and bh_defender_pos in def_lineup:
            if drive_offense_wins:
                halfway = _compute_halfway(driver_start, drive_end)
                defender_overrides[bh_defender_pos] = {
                    "coords": halfway,
                    "action": "cut",
                }
            else:
                defender_overrides[bh_defender_pos] = {
                    "coords": get_defender_coords(
                        drive_end,
                        is_away_offense,
                        aggression,
                        destination_location,
                        None,
                        is_ball_handler=True,
                    ),
                    "action": "guard_ball",
                }

        if clearance_dish_pos:
            dish_defender_pos = off_to_def.get(clearance_dish_pos)
            dish_player = def_lineup.get(dish_defender_pos) if dish_defender_pos else None
            if dish_player and player_read(dish_player) > _defender_help_threshold(def_team):
                double_team = True
                if dish_defender_pos:
                    defender_overrides[dish_defender_pos] = {
                        "coords": get_defender_coords(
                            drive_end,
                            is_away_offense,
                            aggression,
                            destination_location,
                            None,
                            is_ball_handler=True,
                        ),
                        "action": "guard_ball",
                    }

        help_def = _closest_defender_to_point(
            def_positions,
            midlane_end if clearance_dish_pos else drive_end,
            exclude={bh_defender_pos},
        )
        if help_def and help_def not in defender_overrides:
            help_player = def_lineup.get(help_def)
            if help_player and player_read(help_player) > _defender_help_threshold(def_team):
                help_read_success = True
                help_target_pos = clearance_dish_pos or ball_handler_pos
                help_off = final_off_for_defense[help_target_pos]
                help_spot = help_off.get("location") or "midLane"
                defender_overrides[help_def] = {
                    "coords": get_defender_coords(
                        help_off["coords"],
                        is_away_offense,
                        aggression,
                        help_spot,
                        drive_end,
                        is_ball_handler=False,
                        ball_spot=destination_location,
                    ),
                    "action": "guard_offball",
                }

    # Build full defender end coords for contest geometry
    defender_end_coords: Dict[str, Dict[str, float]] = {}
    for def_pos in _OFFENSE_POSITIONS:
        if def_pos in defender_overrides:
            defender_end_coords[def_pos] = dict(defender_overrides[def_pos]["coords"])
            continue
        if not def_lineup.get(def_pos):
            continue
        matched_off: Optional[str] = None
        if is_zone_defense(defense_playcall):
            for op in _OFFENSE_POSITIONS:
                if _defender_for_zone_point(
                    zone_boundaries, final_off_for_defense[op]["coords"], is_away_offense,
                ) == def_pos:
                    matched_off = op
                    break
        else:
            for off_pos, d_pos in off_to_def.items():
                if d_pos == def_pos:
                    matched_off = off_pos
                    break
        if matched_off:
            end_off = final_off_for_defense[matched_off]
            spot = end_off.get("location") or "key"
            defender_end_coords[def_pos] = get_defender_coords(
                end_off["coords"],
                is_away_offense,
                aggression,
                spot,
                drive_end,
                is_ball_handler=(matched_off == ball_handler_pos),
                ball_spot=destination_location,
            )
        else:
            defender_end_coords[def_pos] = def_positions.get(
                def_pos, {"x": 50.0, "y": 25.0},
            )

    guardians = _guardians_within_radius(drive_end, defender_end_coords)
    defender_count = len(guardians)
    is_double_team = defender_count >= 2 or double_team

    if is_double_team:
        shoot_prob = 0.25
    elif defender_count == 0:
        shoot_prob = 1.0
    else:
        shoot_prob = 0.75

    driver_shoots = random.random() < shoot_prob
    dish_target_pos: Optional[str] = None
    resolved_shot_type = "attack"
    resolved_playcall = "Attack"
    uncontested = defender_count == 0
    defense_bonus = 100 if is_double_team and driver_shoots else 0

    shooter_pos = ball_handler_pos
    shooter = off_lineup.get(ball_handler_pos)
    shooter_location = destination_location
    passer_pos: Optional[str] = None

    if not driver_shoots:
        prefer_interior = random.random() < 0.75
        dish_target_pos = _resolve_dish_target(
            drive_end_by_pos, ball_handler_pos, prefer_interior,
        )
        if dish_target_pos:
            shooter_pos = dish_target_pos
            shooter = off_lineup.get(dish_target_pos)
            target = drive_end_by_pos[dish_target_pos]
            shooter_location = target.get("location") or destination_location
            coords = target.get("coords") or drive_end
            resolved_shot_type, resolved_playcall = _shot_type_for_coords(
                coords, is_away_offense,
            )
            passer_pos = ball_handler_pos
            receiver_coords = coords
            uncontested = (
                len(_guardians_within_radius(receiver_coords, defender_end_coords)) == 0
            )
            defense_bonus = 0
        else:
            driver_shoots = True

    attack_drive_meta = {
        "driver_gate": True,
        "gate_driver_pos": ball_handler_pos,
        "destination_location": destination_location,
        "dish_receiver_pos": clearance_dish_pos,
        "double_team": is_double_team,
        "help_read_success": help_read_success,
        "drive_offense_wins": drive_offense_wins,
        "defender_overrides": defender_overrides,
        "defender_count": defender_count,
        "driver_shoots": driver_shoots,
        "dish_target_pos": dish_target_pos,
        # S2a — 3-tier drive contest (consumed by S2b contact / S2c help-cutoff / S2d path-stop /
        # S2e return-to-walk). 'A' blow-by (stop 1.0) · 'B' neutral (0.35–0.65) · 'C' stopped (≤0.15).
        "drive_tier": drive_tier,
        "drive_stop_fraction": drive_stop_fraction,
    }

    logging.debug(
        "🏀 [ATTACK DRIVE] dest=%s clearance_dish=%s perimeter=%s "
        "drive_win=%s guardians=%s shoot=%s dish=%s",
        destination_location,
        clearance_dish_pos,
        sorted(perimeter_moved),
        drive_offense_wins,
        guardians,
        driver_shoots,
        dish_target_pos,
    )
    # S2a observability — the 3-tier outcome (only meaningful when 3-tier is on).
    if _three_tier:
        logging.warning(
            "🚗 [DRIVE TIER] %s stop_fraction=%.2f (margin-banded, BAND=%.0f) drive_win=%s dest=%s",
            drive_tier, drive_stop_fraction, DRIVE_TIER_NEUTRAL_BAND, drive_offense_wins,
            destination_location)

    if legacy_pos_actions_only:
        shoot_pos_actions = _stationary_pos_actions(drive_end_by_pos)
        shoot_pos_actions[ball_handler_pos] = _pos_action_for_target(
            drive_end_by_pos[ball_handler_pos], "shoot",
        )
        return {
            "drive_pos_actions": drive_pos_actions,
            "shoot_pos_actions": shoot_pos_actions,
            "attack_drive_meta": attack_drive_meta,
        }

    drive_step = {
        "timestamp": timestamp,
        "pos_actions": drive_pos_actions,
        "events": [],
        "_attack_drive": dict(attack_drive_meta),
    }

    steps: List[Dict[str, Any]] = [drive_step]

    if driver_shoots and dish_target_pos is None:
        shoot_pos_actions = _stationary_pos_actions(drive_end_by_pos)
        shoot_pos_actions[ball_handler_pos] = _pos_action_for_target(
            drive_end_by_pos[ball_handler_pos], "shoot",
        )
        steps.append({
            "timestamp": timestamp + 300,
            "pos_actions": shoot_pos_actions,
            "events": [{"type": "shot"}],
            "_attack_drive": {
                "start_location": start_location,
                "intended_destination": destination_location,
                "final_location": destination_location,
                "stopped_short": False,
            },
        })
    elif dish_target_pos:
        receiver_target = drive_end_by_pos[dish_target_pos]
        receiver_loc = receiver_target.get("location") or shooter_location
        steps.append({
            "timestamp": timestamp + 300,
            "pos_actions": {
                ball_handler_pos: {
                    "location": destination_location,
                    "action": "pass",
                },
                dish_target_pos: {
                    "location": receiver_loc,
                    "action": "receive",
                },
            },
            "events": [],
        })
        shoot_pos_actions = _stationary_pos_actions(drive_end_by_pos)
        shoot_pos_actions[dish_target_pos] = _pos_action_for_target(receiver_target, "shoot")
        steps.append({
            "timestamp": timestamp + 600,
            "pos_actions": shoot_pos_actions,
            "events": [{"type": "shot"}],
            "_attack_drive": {
                "start_location": start_location,
                "intended_destination": destination_location,
                "final_location": shooter_location,
                "stopped_short": False,
            },
        })

    return {
        "steps": steps,
        "shooter": shooter,
        "shooter_pos": shooter_pos,
        "shooter_location": shooter_location,
        "resolved_shot_type": resolved_shot_type,
        "playcall": resolved_playcall,
        "motion_attack_uncontested": uncontested,
        "motion_attack_geometry_contest": True,
        "motion_attack_defense_bonus": defense_bonus,
        "motion_attack_driver_shoots": bool(driver_shoots),
        "attack_drive_meta": attack_drive_meta,
        "drive_pos_actions": drive_pos_actions,
        "attack_drive_meta_legacy": attack_drive_meta,
    }
