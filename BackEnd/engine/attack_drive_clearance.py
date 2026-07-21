"""Motion offense attack-drive: lane clearance, perimeter reads, drive contest, dish/shoot."""

from __future__ import annotations

import logging
import math
from BackEnd.utils.sim_random import sim_rng as random
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


def _drive_stop_coord(
    start: Dict[str, float], end: Dict[str, float], fraction: float
) -> Dict[str, int]:
    """S2d: the BH's stop point = `fraction` of the way from the drive start toward the destination
    (0 = didn't move, 1 = reached the rim). Used to halt a contested/stopped drive short of the rim."""
    f = max(0.0, min(1.0, float(fraction)))
    return {
        "x": int(round(float(start["x"]) + (float(end["x"]) - float(start["x"])) * f)),
        "y": int(round(float(start["y"]) + (float(end["y"]) - float(start["y"])) * f)),
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
) -> Tuple[float, float, bool]:
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
    offense_wins = off_score > def_score + def_bonus
    return off_score, def_score, offense_wins


# Dynamic HCO Defense — S2 spine (Dynamic_MM_Brief §S2). The HCO primary drive contest routes through
# the SHARED `_resolve_moment` (the FB/HCT drive-contact model) instead of a bespoke margin band — ONE
# roll yields the tier + stop point + contact outcome, tuned via the shared HCT_D8_* levels. This
# retires S2a's `_classify_drive_tier` + the `DRIVE_TIER_*` band/lean constants (never consumed).
DRIVE_NEUTRAL_STOP_FRACTION = 0.5   # Tier B (contested NEUTRAL): BH pulls up ~midway to the rim
DRIVE_STOPPED_MAX_GRID = 2.0        # Tier C (defense WINS): BH advances AT MOST this many grid before the wall
# Win/lose gate width for the HCO drive contest (± each way, in o_score/d_score points). The shared
# default (chem+eff, a few pts) makes the neutral tier vanishingly rare; ~100 gives B real presence.
# Tunable (S2f). Passed to `_resolve_moment(neutral_band=...)`; FB/HCT keep the chem+eff default.
DRIVE_NEUTRAL_BAND = 100.0

# S2c help-cutoff tuning. On a Tier-A blow-by a HELP defender may rotate to cut off the drive. HCO
# drives are half-court (standard AG rate, like HCT — not FB's outlet sprint), so the corridor + slack
# stay tight. Aggression gates whether a given help defender even attempts the rotation (mirrors FB's
# stop_attempt_prob → loose/aggressive defenses sit deeper in help lanes and cut off more). Tunable (S2f).
HCO_CUTOFF_PATH_CORRIDOR = 11.0          # help defender must be within 11 grid of the drive line to rotate
HCO_CUTOFF_DEFENDER_TIME_SLACK = 1.0     # no arrival-time credit (a clean blow-by outruns late help)
HCO_CUTOFF_STOP_ATTEMPT_PROB = {"passive": 0.0, "normal": 0.5, "aggressive": 1.0}


def _resolve_hco_help_cutoff(
    bh_start, drive_end, driver, primary_def_pos, def_coords, def_lineup,
    off_team, def_team, aggression,
):
    """S2c: on a Tier-A blow-by, a HELP defender (NOT the beaten primary) may rotate to cut off the
    drive. Reuses the shared FB/HCT cutoff geometry (`best_cutoff_on_drive` → meet point) + contest
    (`resolve_cutoff_contest` → `_resolve_moment`). Returns ``(cutoff_pos, tier, stop_fraction, contact,
    meet)``; ``cutoff_pos`` is None when no help defender reaches the path (or the BH beats the help
    too → stays a blow-by). The outcome maps to the SAME tier vocabulary as the primary contest, so
    S2d/S2b/S2e consume the demotion unchanged. See Dynamic_MM_Brief §S2c."""
    from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec
    from BackEnd.engine.cutoff_resolution import best_cutoff_on_drive

    # Race only the OTHER defenders — the beaten primary is behind the play.
    race_coords = {p: c for p, c in def_coords.items() if p != primary_def_pos and c}
    if not race_coords:
        return None, "A", 1.0, None, None
    bh_rate = _ag_grid_per_game_sec(driver, "standard")
    stop_prob = HCO_CUTOFF_STOP_ATTEMPT_PROB.get(aggression, 0.5)
    cutoff_pos, meet = best_cutoff_on_drive(
        bh_start, drive_end, bh_rate, race_coords, def_lineup,
        get_defender_rate=lambda d: _ag_grid_per_game_sec(d, "standard"),
        path_corridor=HCO_CUTOFF_PATH_CORRIDOR,
        defender_time_slack=HCO_CUTOFF_DEFENDER_TIME_SLACK,
        stop_attempt_prob=stop_prob,
        rng=random,
    )
    cutoff_def = def_lineup.get(cutoff_pos) if cutoff_pos else None
    if not cutoff_pos or meet is None or cutoff_def is None:
        return None, "A", 1.0, None, None

    # Resolve the help collision through the SAME HCO drive contest as the primary (`clean_stop` + tuned
    # `neutral_band` + team-eff mods) — a help cutoff IS just another BH-vs-defender drive collision, so it
    # yields the identical tier vocabulary (incl. a `C` clean stop → great-stop SFX), not the narrower
    # FB/HCT default. `best_cutoff_on_drive` stays the shared geometric reuse; only WHERE (the meet) is HCO.
    tier, ratio, contact = _resolve_hco_drive_contest(driver, cutoff_def, off_team, def_team)
    if tier == "A" and not contact:
        # BH beats the help defender too → stays a clean blow-by (no demotion; primary stays the beaten man).
        return None, "A", 1.0, None, None
    # Meet progress along driver_start→drive_end = the stop fraction for a demotion (S2d re-derives the
    # stop coord from it, landing back on the meet point since best_cutoff walks that exact segment).
    _path = _euclid(bh_start, drive_end)
    frac = (_euclid(bh_start, meet) / _path) if _path > 0 else float(ratio)
    if tier == "A":
        # D_FOUL on the help defender → blow-by that draws a shooting foul (and-1 / FTs via S2b), to the rim.
        return cutoff_pos, "A", 1.0, contact, meet
    # B (contested pull-up) / C (clean stop, or O_FOUL/DEAD BALL contact) → stop at the meet point.
    return cutoff_pos, tier, frac, contact, meet


def _resolve_hco_drive_contest(driver, primary_def, off_team, def_team):
    """S2 spine: the HCO primary drive contest via the shared `_resolve_moment` (FB/HCT model). ONE
    roll → ``(tier, stop_fraction, contact)``. tier ∈ {'A','B','C'}; stop_fraction = drive progress at
    the stop (1.0 = reaches the rim); contact ∈ {None, 'D_FOUL', 'O_FOUL', 'DEAD BALL'} (routed by S2b).
    `def_mod`/`off_mod` feed HCO team efficiency; `exclude_steal=True` (a drive collision is a
    charge/block/lost-handle, not a pickpocket) + `clean_stop=True` (distinguish the C clean stop from
    a contested B). See Dynamic_MM_Brief §S2 + projects/attack_contest_unification.md."""
    from BackEnd.engine.dynamic_hct import _resolve_moment
    off_attrs = getattr(off_team, "team_attributes", {}) or {}
    def_attrs = getattr(def_team, "team_attributes", {}) or {}
    off_eff = int(off_attrs.get("offensive_efficiency") or 0)
    def_eff = int(def_attrs.get("defensive_efficiency") or 0)
    outcome, ratio, _credited = _resolve_moment(
        off_team, def_team, driver, primary_def,
        exclude_steal=True, clean_stop=True, def_mod=def_eff, off_mod=off_eff,
        neutral_band=DRIVE_NEUTRAL_BAND)
    if outcome == "POS_O":
        return "A", 1.0, None
    if outcome == "D_FOUL":
        # Blow-by that drew a shooting foul on the beaten defender → A + foul (and-1 / FTs via S2b).
        return "A", 1.0, "D_FOUL"
    if outcome == "NEUTRAL":
        return "B", DRIVE_NEUTRAL_STOP_FRACTION, None
    if outcome == "D_STOP":
        return "C", float(ratio), None
    # O_FOUL (charge) / DEAD BALL (lost handle) — defense-wins terminal contact at the ratio point.
    return "C", float(ratio), outcome


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
    drive_contact = None  # None | 'D_FOUL' | 'O_FOUL' | 'DEAD BALL' — routed by S2b
    bh_defender_pos: Optional[str] = None
    off_to_def: Dict[str, str] = {}
    def_positions: Dict[str, Dict[str, float]] = {}
    zone_boundaries: Dict[str, Any] = {}
    _help_race_coords: Dict[str, Dict[str, float]] = {}  # pre-drive defender coords → S2c help-cutoff race

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
            if _three_tier:
                # S2 spine: the SHARED contest (`_resolve_moment`, FB/HCT model) — one roll →
                # tier + stop + contact. `drive_offense_wins` (today's defender override) is derived
                # from the tier so the existing override still renders until S2d/S2b consume the rest.
                drive_tier, drive_stop_fraction, drive_contact = _resolve_hco_drive_contest(
                    driver, primary_def, off_team, def_team)
                drive_offense_wins = drive_tier == "A"
            else:
                # Flag-off: today's binary contest, unchanged (byte-identical).
                _, _, drive_offense_wins = _compute_drive_scores(
                    driver, primary_def, off_team, def_team, defense_playcall)
                drive_tier = "A" if drive_offense_wins else "C"
                drive_stop_fraction = 1.0 if drive_offense_wins else 0.0

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

        # S2c: race the zone help defenders to the drive path. The matched-only `zone_def_positions`
        # OMITS any zone defender whose area holds no offensive player — notably the rim protector on a
        # cleared-paint drive (basketSpot is uncovered in the 2-3 shell), i.e. the exact help defender a
        # rim blow-by should meet. Under the flag, fill those gaps with a rim-help coord so the race sees
        # every defender. Flag-off + the legacy `help_def` path keep the original matched-only map
        # (byte-identical); precise zone-anchor placement is S4 zone posture.
        _help_race_coords = dict(zone_def_positions)
        if _three_tier:
            for _zpos in _OFFENSE_POSITIONS:
                if def_lineup.get(_zpos) and _zpos not in _help_race_coords:
                    _help_race_coords[_zpos] = get_defender_coords(
                        drive_end, is_away_offense, aggression, destination_location, drive_end,
                        is_ball_handler=False, ball_spot=destination_location,
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
        _help_race_coords = def_positions  # S2c: race the man help defenders to the drive path

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
            if _three_tier:
                # S2 spine: the SHARED contest (`_resolve_moment`, FB/HCT model) — one roll →
                # tier + stop + contact. `drive_offense_wins` (today's defender override) is derived
                # from the tier so the existing override still renders until S2d/S2b consume the rest.
                drive_tier, drive_stop_fraction, drive_contact = _resolve_hco_drive_contest(
                    driver, primary_def, off_team, def_team)
                drive_offense_wins = drive_tier == "A"
            else:
                # Flag-off: today's binary contest, unchanged (byte-identical).
                _, _, drive_offense_wins = _compute_drive_scores(
                    driver, primary_def, off_team, def_team, defense_playcall)
                drive_tier = "A" if drive_offense_wins else "C"
                drive_stop_fraction = 1.0 if drive_offense_wins else 0.0

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

    # S2c — help cutoff on a Tier-A blow-by. The BH beat his primary; now a HELP defender may rotate to
    # cut off the drive path. Reuses the shared FB/HCT cutoff geometry + contest (`_resolve_hco_help_cutoff`
    # → `best_cutoff_on_drive` + `resolve_cutoff_contest`). A successful cutoff DEMOTES the blow-by: the
    # cutoff defender becomes the contact/guard defender (`bh_defender_pos`) and the drive re-resolves to
    # B/C (or a foul/charge/TO) — the downstream S2d/S2b/S2e machinery then consumes the demoted tier with
    # NO special-casing. Loose/aggressive postures sit deeper in help lanes → more cutoffs, organically.
    # Tier B/C (primary already stopped him) and flag-off skip this. See Dynamic_MM_Brief §S2c.
    if _three_tier and drive_tier == "A" and driver and bh_defender_pos and _help_race_coords:
        _cut_pos, _cut_tier, _cut_frac, _cut_contact, _cut_meet = _resolve_hco_help_cutoff(
            driver_start, drive_end, driver, bh_defender_pos,
            _help_race_coords, def_lineup, off_team, def_team, aggression)
        if _cut_pos:
            drive_tier, drive_stop_fraction, drive_contact = _cut_tier, _cut_frac, _cut_contact
            bh_defender_pos = _cut_pos  # cutoff defender now walls the ball (S2d) / credits contact (S2b)
            drive_offense_wins = drive_tier == "A"
            logging.debug(
                "🚧 [HELP CUTOFF] %s cuts off blow-by → tier %s stop=%.2f contact=%s meet=%s",
                _cut_pos, drive_tier, drive_stop_fraction, _cut_contact, _cut_meet)

    # S2d — path-stop: on a contested (B) or defense-win (C) drive, the BH is halted SHORT of the rim
    # at the contest's stop point instead of driving all the way in. Move his drive-end + shoot coord
    # to the stop, reclassify the shot from the stop distance (pull-up vs layup — the coord-based shot
    # math then makes a stopped shot organically harder), and wall the primary defender just beyond the
    # stop (between the BH and the basket). Tier A (blow-by) + flag-off are untouched. S2b routes the
    # foul/charge/TO contact; S2e the pull-up/dish/reset options. See Dynamic_MM_Brief §S2.
    _stop_shot_type = None
    _stop_shot_playcall = None
    if _three_tier and drive_tier in ("B", "C") and drive_stop_fraction < 1.0:
        if drive_tier == "C":
            # Defense WON — the BH is walled almost at once: cap his advance to an ABSOLUTE 0–2 grid
            # (scaled by how narrowly he was stopped), NOT a fraction of the full drive (which let a
            # narrow stop carry him most of the way in). Fixes "Nice Stop but the driver kept going".
            _full = math.hypot(drive_end["x"] - driver_start["x"], drive_end["y"] - driver_start["y"])
            _cap_frac = min(1.0, (drive_stop_fraction * DRIVE_STOPPED_MAX_GRID) / _full) if _full > 1e-6 else 0.0
            _bh_stop = _drive_stop_coord(driver_start, drive_end, _cap_frac)
        else:
            _bh_stop = _drive_stop_coord(driver_start, drive_end, drive_stop_fraction)  # B: contested pull-up midway
        _stop_shot_type, _stop_shot_playcall = _shot_type_for_coords(_bh_stop, is_away_offense)
        drive_end_by_pos[ball_handler_pos] = {"location": destination_location, "coords": _bh_stop}
        drive_pos_actions[ball_handler_pos] = _pos_action_for_target(
            drive_end_by_pos[ball_handler_pos], "drive")
        final_off_for_defense[ball_handler_pos] = {
            "location": destination_location, "coords": _bh_stop}
        if bh_defender_pos and def_lineup.get(bh_defender_pos):
            # The defender who stopped him guards the ball AT the stop (standard on-ball cushion →
            # the pull-up is contested), between the BH and the basket. Mirrors the "defense wins →
            # guard_ball" path, but at the stop instead of the rim.
            defender_overrides[bh_defender_pos] = {
                "coords": get_defender_coords(
                    _bh_stop, is_away_offense, aggression, destination_location, None,
                    is_ball_handler=True),
                "action": "guard_ball",
            }
        logging.debug(
            "🛑 [DRIVE STOP] tier %s → BH stopped at %.0f%% (%s) shot=%s",
            drive_tier, drive_stop_fraction * 100, _bh_stop, _stop_shot_type)

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
        elif is_zone_defense(defense_playcall) and _three_tier:
            # Flag-on zone: an unmatched zone defender (rim protector on a cleared-paint drive) guards his
            # AREA at the rim — count him as a rim guardian via the S2c-completed map, not center court.
            # Flag-off keeps the legacy center-court default below (pre-existing; parity → S4 zone posture).
            defender_end_coords[def_pos] = _help_race_coords.get(
                def_pos, {"x": 50.0, "y": 25.0},
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

    # S2e — a STOPPED BH (Tier B/C) re-decides dish-vs-pull-up as an OPENNESS read (reuse the walk's
    # native `should_shoot` dish read), not the blind `shoot_prob` coin flip: dish to a teammate whose
    # look beats the contested pull-up, else take the pull-up. HCO-native (the stopped BH re-enters the
    # half-court read). Wrapped so a read error can never break the drive. (Full reset/freelance = a
    # follow-up.) See Dynamic_MM_Brief §S2 / attack_contest_unification.md.
    _s2e_dish_pos = None
    if _three_tier and drive_tier in ("B", "C"):
        try:
            from BackEnd.engine.motion_read_map import build_motion_read_map
            from BackEnd.engine.motion_step_decision import should_shoot
            _s2e_read = build_motion_read_map(game, off_lineup, def_lineup)
            _s2e_locs = {p: (drive_end_by_pos.get(p) or {}).get("location", "key") for p in off_lineup}
            _s2e_gs = getattr(game, "game_state", {}) or {}
            _s2e_sc = float(_s2e_gs.get("_hco_shot_clock_est",
                                        _s2e_gs.get("shot_clock_remaining", 30)) or 30)
            _s2e_tempo = (getattr(off_team, "strategy_calls", {}) or {}).get("tempo_call", "normal")
            _s2e_dec = should_shoot(ball_handler_pos, off_lineup, _s2e_locs, _s2e_read, off_team,
                                    _s2e_sc, _s2e_tempo, random, openness=0.0, allow_dish=True)
            if _s2e_dec and _s2e_dec.get("shooter_pos") and _s2e_dec["shooter_pos"] != ball_handler_pos:
                _s2e_dish_pos = _s2e_dec["shooter_pos"]
        except Exception:
            _s2e_dish_pos = None

    driver_shoots = random.random() < shoot_prob
    if _three_tier and drive_tier in ("B", "C"):
        # Stopped BH: dish if should_shoot found an open teammate, else the contested pull-up.
        driver_shoots = _s2e_dish_pos is None
        logging.debug(
            "🧭 [DRIVE STOP READ] tier %s bh=%s → %s",
            drive_tier, ball_handler_pos,
            ("DISH→" + _s2e_dish_pos) if _s2e_dish_pos else "PULL-UP",
        )
    dish_target_pos: Optional[str] = None
    # S2d: a stopped drive (B/C) is a pull-up from the stop, not a layup — reclassify the driver's shot
    # from the stop coord (falls back to "attack" for a full drive / Tier A / flag-off).
    resolved_shot_type = _stop_shot_type or "attack"
    resolved_playcall = _stop_shot_playcall or "Attack"
    uncontested = defender_count == 0
    defense_bonus = 100 if is_double_team and driver_shoots else 0

    shooter_pos = ball_handler_pos
    shooter = off_lineup.get(ball_handler_pos)
    shooter_location = destination_location
    passer_pos: Optional[str] = None

    if not driver_shoots:
        # S2e: on a B/C stop, dish to should_shoot's chosen open teammate; otherwise fall back to the
        # legacy interior/random dish selection (full drive, double-team kick-out, flag-off).
        prefer_interior = random.random() < 0.75
        dish_target_pos = _s2e_dish_pos or _resolve_dish_target(
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
        # S2 — 3-tier drive contest from the shared `_resolve_moment` (consumed by S2d path-stop /
        # S2b contact / S2c help-cutoff / S2e return-to-walk). 'A' blow-by (1.0) · 'B' neutral (~0.5,
        # pull-up/dish) · 'C' clean stop / contact (ratio). `drive_contact` routes the foul/charge/TO;
        # `drive_contact_defender_id` credits the foul / draws the charge (S2b).
        "drive_tier": drive_tier,
        "drive_stop_fraction": drive_stop_fraction,
        "drive_contact": drive_contact,
        "drive_contact_defender_id": (
            getattr(def_lineup.get(bh_defender_pos), "player_id", None)
            if (drive_contact and bh_defender_pos) else None),
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
    # S2 observability — the 3-tier outcome from the shared contest (only when 3-tier is on).
    if _three_tier:
        logging.debug(
            "🚗 [DRIVE TIER] %s stop_fraction=%.2f contact=%s (shared _resolve_moment) win=%s dest=%s",
            drive_tier, drive_stop_fraction, drive_contact, drive_offense_wins, destination_location)

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
