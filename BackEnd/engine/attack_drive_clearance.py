"""Motion offense attack-drive clearance: offensive spacing + defensive reactions.

When a motion play resolves to an attack shot, teammates in the drive lane
clear on the drive step; defenders react (man double/help or zone collapse).
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.utils.defense_identity import defense_zone_shell_variant
from BackEnd.utils.defense_utils import is_zone_defense
from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team
from BackEnd.utils.shared import get_away_player_coords, player_read
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
    # Opposite vertical half from the drive destination.
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
    # Deterministic fallback: nudge y until separated.
    base_x = (x_min + x_max) / 2.0
    base_y = (y_min + y_max) / 2.0
    for n in range(20):
        candidate = {"x": round(base_x + n * 0.5, 2), "y": round(base_y + n * 0.4, 2)}
        if all(_euclid(candidate, e) >= 3.0 for e in existing):
            return candidate
    return {"x": round(base_x, 2), "y": round(base_y, 2)}


def _select_dish_receiver(
    candidates: List[Dict[str, Any]],
    is_away_offense: bool,
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    basket_x = 10.0 if is_away_offense else 90.0

    def dist(c: Dict[str, Any]) -> float:
        return abs(float(c["x"]) - basket_x)

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


def _defender_help_threshold(def_team: Any) -> int:
    attrs = getattr(def_team, "team_attributes", {}) or {}
    chem = int(attrs.get("team_chemistry") or 0)
    return 150 - 2 * chem


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
    """Build drive/shoot pos_actions and ``_attack_drive`` metadata."""
    dest_half = _drive_destination_half(destination_location)
    drive_end_home = _home_spot_coords(destination_location)
    drive_end = _display_coords(drive_end_home, is_away_offense)
    midlane_end = _display_coords(_home_spot_coords("midLane"), is_away_offense)

    off_positions = _offensive_positions_from_step(selected_step, is_away_offense)

    in_way: List[Dict[str, Any]] = []
    for pos in _OFFENSE_POSITIONS:
        if pos == ball_handler_pos:
            continue
        loc = off_positions[pos]["location"]
        if _is_in_blast_radius(loc, destination_location, dest_half):
            entry = dict(off_positions[pos])
            entry["position"] = pos
            in_way.append(entry)

    dish_receiver_pos: Optional[str] = None
    evac_targets: List[Dict[str, Any]] = []
    placed_coords: List[Dict[str, float]] = [dict(drive_end)]

    if destination_location != "midLane" and in_way:
        dish = _select_dish_receiver(in_way, is_away_offense)
        if dish:
            dish_receiver_pos = dish["position"]
            evac_targets = [c for c in in_way if c["position"] != dish_receiver_pos]
    else:
        evac_targets = list(in_way)

    drive_end_by_pos: Dict[str, Dict[str, Any]] = {}
    for pos in _OFFENSE_POSITIONS:
        if pos == ball_handler_pos:
            drive_end_by_pos[pos] = {
                "location": destination_location,
                "coords": dict(drive_end),
            }
            continue
        if pos == dish_receiver_pos:
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

    drive_pos_actions: Dict[str, Dict[str, Any]] = {}
    for pos in _OFFENSE_POSITIONS:
        target = drive_end_by_pos[pos]
        if pos == ball_handler_pos:
            drive_pos_actions[pos] = _pos_action_for_target(target, "drive")
        elif pos == dish_receiver_pos or any(c["position"] == pos for c in evac_targets):
            drive_pos_actions[pos] = _pos_action_for_target(target, "cut")
        else:
            drive_pos_actions[pos] = _pos_action_for_target(target, "stationary")

    shoot_pos_actions: Dict[str, Dict[str, Any]] = {}
    for pos in _OFFENSE_POSITIONS:
        target = drive_end_by_pos[pos]
        if pos == ball_handler_pos:
            shoot_pos_actions[pos] = _pos_action_for_target(target, "shoot")
        else:
            shoot_pos_actions[pos] = _pos_action_for_target(target, "stationary")

    def_team = getattr(game, "defense_team", None)
    aggression = "normal"
    if def_team is not None:
        aggression = (getattr(def_team, "strategy_calls", {}) or {}).get(
            "aggression_call", "normal"
        )
    defense_playcall = (getattr(game, "game_state", {}) or {}).get(
        "defense_playcall", "man"
    )

    defender_overrides: Dict[str, Dict[str, Any]] = {}
    double_team = False
    help_read_success = False

    if is_zone_defense(defense_playcall):
        zone_boundaries = _zone_boundaries_for_spot(
            defense_playcall, destination_location, is_away_offense
        )
        bh_coord = off_positions[ball_handler_pos]["coords"]
        bh_zone_def = _defender_for_zone_point(zone_boundaries, bh_coord, is_away_offense)
        drive_zone_def = _defender_for_zone_point(zone_boundaries, drive_end, is_away_offense)

        for def_pos in _OFFENSE_POSITIONS:
            if not def_lineup.get(def_pos):
                continue
            if def_pos == bh_zone_def or def_pos == drive_zone_def:
                defender_overrides[def_pos] = {
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

        if dish_receiver_pos:
            midlane_zone_def = _defender_for_zone_point(
                zone_boundaries, midlane_end, is_away_offense
            )
            if midlane_zone_def and midlane_zone_def not in {
                bh_zone_def,
                drive_zone_def,
            }:
                help_player = def_lineup.get(midlane_zone_def)
                read_score = player_read(help_player) if help_player else 0
                help_read_success = read_score > _defender_help_threshold(def_team)
                if help_read_success:
                    dish_coord = drive_end_by_pos[dish_receiver_pos]["coords"]
                    dish_spot = drive_end_by_pos[dish_receiver_pos].get("location") or "midLane"
                    defender_overrides[midlane_zone_def] = {
                        "coords": get_defender_coords(
                            dish_coord,
                            is_away_offense,
                            aggression,
                            dish_spot,
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

        if bh_defender_pos in def_lineup:
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

        if dish_receiver_pos:
            double_team = random.random() < 0.5
            dish_defender_pos = off_to_def.get(dish_receiver_pos)
            if double_team and dish_defender_pos:
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
                    midlane_end,
                    exclude={bh_defender_pos, dish_defender_pos},
                )
                if help_def:
                    help_player = def_lineup.get(help_def)
                    read_score = player_read(help_player) if help_player else 0
                    help_read_success = read_score > _defender_help_threshold(def_team)
                    if help_read_success:
                        dish_coord = drive_end_by_pos[dish_receiver_pos]["coords"]
                        defender_overrides[help_def] = {
                            "coords": get_defender_coords(
                                dish_coord,
                                is_away_offense,
                                aggression,
                                "midLane",
                                drive_end,
                                is_ball_handler=False,
                                ball_spot=destination_location,
                            ),
                            "action": "guard_offball",
                        }

    attack_drive_meta = {
        "driver_gate": True,
        "gate_driver_pos": ball_handler_pos,
        "destination_location": destination_location,
        "dish_receiver_pos": dish_receiver_pos,
        "double_team": double_team,
        "help_read_success": help_read_success,
        "defender_overrides": defender_overrides,
    }

    logging.debug(
        "🏀 [ATTACK DRIVE CLEARANCE] dest=%s in_way=%s dish=%s double=%s help_read=%s",
        destination_location,
        [c["position"] for c in in_way],
        dish_receiver_pos,
        double_team,
        help_read_success,
    )

    return {
        "drive_pos_actions": drive_pos_actions,
        "shoot_pos_actions": shoot_pos_actions,
        "attack_drive_meta": attack_drive_meta,
    }
