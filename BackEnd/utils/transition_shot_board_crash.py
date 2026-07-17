"""Stamp rebounder-board crash overlays for FB / HCT / FCP shot attempts.

HCO already authors ``offense_rebounder_coords`` / ``defense_rebounder_coords``
in ``shot_manager``. Live Fast Break, dynamic HCT, and dynamic FCP often reach
``_build_post_shot_sub_steps`` with those maps empty, so off-ball players freeze
through ball flight.

This helper fills (or extends) those overlay maps from the terminal shoot /
finish step so ``_apply_overlay_motion_to_shoot_step`` +
``_build_ball_motion_sub_step`` continue motion through flight and bounce.

Rules (aligned Jul 2026):
- Scope: ``current_turn`` in {FAST_BREAK, HCT, FCP} and MAKE/MISS/BLOCK.
- Offense and defense are both eligible.
- Shot defender and shooter always hold (not added to rebounder overlays).
- Players already within ``CONTEST_EUCLIDEAN_RADIUS`` (11) of the attacked
  basket and not moving keep their spot.
- Players already moving on the shoot step keep that destination in overlays
  so flight continues it.
- Idle players outside 11 of the basket get a random destination within 11 of
  the basket.
- Fast Break NEUTRAL: keep coordinated matchup/help defensive holds and lead
  offense holds (trailers may crash). All five defenders hold on NEUTRAL.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, Optional, Set

from BackEnd.constants import (
    AWAY_RIM_COORDS,
    CONTEST_EUCLIDEAN_RADIUS,
    HOME_RIM_COORDS,
)

_BOARD_CRASH_TURNS = frozenset({"FAST_BREAK", "HCT", "FCP"})
_MOVING_EPS = 0.75


def _euclid(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    return math.hypot(
        float(a.get("x", 0)) - float(b.get("x", 0)),
        float(a.get("y", 0)) - float(b.get("y", 0)),
    )


def _safe_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "player_id"):
        pid = getattr(value, "player_id", None)
        return str(pid) if pid is not None else None
    text = str(value).strip()
    return text or None


def _clamp_coord(coord: Dict[str, float]) -> Dict[str, float]:
    return {
        "x": float(max(4.0, min(97.0, coord["x"]))),
        "y": float(max(1.0, min(49.0, coord["y"]))),
    }


def sample_coord_within_basket_radius(
    basket: Dict[str, Any],
    radius: float = float(CONTEST_EUCLIDEAN_RADIUS),
    rng: Any = None,
) -> Dict[str, float]:
    """Uniform-ish sample in the disk of ``radius`` around ``basket``."""
    rng = rng or random
    bx = float(basket["x"])
    by = float(basket["y"])
    r = float(radius)
    for _ in range(64):
        dx = rng.uniform(-r, r)
        dy = rng.uniform(-r, r)
        if (dx * dx) + (dy * dy) <= (r * r):
            return _clamp_coord({"x": bx + dx, "y": by + dy})
    return _clamp_coord({"x": bx, "y": by})


def _lineup_player_ids(lineup: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    for player in (lineup or {}).values():
        pid = _safe_id(player)
        if pid:
            out.add(pid)
    return out


def _overlay_has_pid(overlay: Dict[str, Any], pid: str) -> bool:
    if not isinstance(overlay, dict):
        return False
    if pid in overlay:
        return True
    if pid.isdigit() and int(pid) in overlay:
        return True
    return False


def _shoot_step_destination(
    shoot_step: Dict[str, Any],
    pid: str,
    start_coord: Dict[str, Any],
) -> Optional[Dict[str, float]]:
    """Return the shoot-step destination when the player is already moving."""
    start = shoot_step.get("start") or {}
    destinations = start.get("destination") or {}
    dest = destinations.get(pid)
    if dest is None and pid.isdigit():
        dest = destinations.get(int(pid))
    if not isinstance(dest, dict):
        return None
    if dest.get("x") is None or dest.get("y") is None:
        return None
    target = {"x": float(dest["x"]), "y": float(dest["y"])}
    if _euclid(start_coord, target) <= _MOVING_EPS:
        return None
    return target


def resolve_shot_defender_hold_id(turn_result: Dict[str, Any]) -> Optional[str]:
    for key in ("shot_defender_id", "defender_id"):
        pid = _safe_id(turn_result.get(key))
        if pid:
            return pid
    pid = _safe_id(turn_result.get("defender"))
    if pid:
        return pid
    fb_drive = turn_result.get("fb_drive_resolution") or {}
    if isinstance(fb_drive, dict):
        for key in ("shot_defender_id", "stopper_id", "d8_credited_player_id"):
            pid = _safe_id(fb_drive.get(key))
            if pid:
                return pid
    return None


def compute_fb_neutral_board_crash_hold_ids(
    *,
    stealer_id: Optional[str],
    off_start_coords: Dict[str, Dict[str, Any]],
    def_start_coords: Dict[str, Dict[str, Any]],
    is_away_offense: bool,
) -> Set[str]:
    """NEUTRAL hold set: all defenders + lead offenders (+ ball-handler).

    Trailers are intentionally omitted so they can crash to the boards.
    """
    from BackEnd.engine.after_steal_transition_positioning import classify_offense_roles

    hold: Set[str] = set(str(pid) for pid in (def_start_coords or {}))
    if not stealer_id:
        return hold
    leads, _trailers = classify_offense_roles(
        stealer_id=str(stealer_id),
        off_start_coords=off_start_coords,
        is_away_offense=is_away_offense,
    )
    hold.update(str(pid) for pid in leads)
    hold.add(str(stealer_id))
    return hold


def maybe_stamp_transition_shot_board_crash_overlays(
    turn_result: Dict[str, Any],
    shoot_step: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    away_offense: bool,
    rng: Any = None,
) -> None:
    """Stamp/extend rebounder overlay maps for transition shot attempts.

    No-op for HCO / OREB / FT and for non-MAKE/MISS/BLOCK results. Mutates
    ``turn_result`` in place. Safe when overlays already exist (skips those
    player ids so HCO-style stamps from ``shot_manager`` win).
    """
    if not isinstance(turn_result, dict) or not isinstance(shoot_step, dict):
        return

    current_turn = (turn_result.get("current_turn") or "").upper()
    if current_turn not in _BOARD_CRASH_TURNS:
        return

    result_type = (turn_result.get("result_type") or "").upper()
    if result_type not in ("MAKE", "MISS", "BLOCK"):
        return

    rng = rng or random
    basket = dict(AWAY_RIM_COORDS if away_offense else HOME_RIM_COORDS)
    radius = float(CONTEST_EUCLIDEAN_RADIUS)

    start_coords = (shoot_step.get("start") or {}).get("coords") or {}
    if not isinstance(start_coords, dict) or not start_coords:
        return

    off_ids = _lineup_player_ids(off_lineup)
    def_ids = _lineup_player_ids(def_lineup)

    hold: Set[str] = set()
    shooter_id = _safe_id(turn_result.get("shooter")) or _safe_id(
        turn_result.get("shooter_id")
    )
    if shooter_id:
        hold.add(shooter_id)

    shot_def_id = resolve_shot_defender_hold_id(turn_result)
    if shot_def_id:
        hold.add(shot_def_id)

    fb_drive = turn_result.get("fb_drive_resolution") or {}
    is_neutral = (
        current_turn == "FAST_BREAK"
        and isinstance(fb_drive, dict)
        and fb_drive.get("outcome") == "NEUTRAL"
    )
    if is_neutral:
        off_starts = {
            pid: dict(sc)
            for pid, sc in start_coords.items()
            if pid in off_ids and isinstance(sc, dict)
        }
        def_starts = {
            pid: dict(sc)
            for pid, sc in start_coords.items()
            if pid in def_ids and isinstance(sc, dict)
        }
        stealer_id = (
            shooter_id
            or _safe_id(turn_result.get("stealer_id"))
            or _safe_id(turn_result.get("ball_handler_id"))
        )
        hold |= compute_fb_neutral_board_crash_hold_ids(
            stealer_id=stealer_id,
            off_start_coords=off_starts,
            def_start_coords=def_starts,
            is_away_offense=away_offense,
        )

    offense_map = turn_result.setdefault("offense_rebounder_coords", {})
    defense_map = turn_result.setdefault("defense_rebounder_coords", {})
    if not isinstance(offense_map, dict):
        offense_map = {}
        turn_result["offense_rebounder_coords"] = offense_map
    if not isinstance(defense_map, dict):
        defense_map = {}
        turn_result["defense_rebounder_coords"] = defense_map

    for pid, sc in start_coords.items():
        pid_s = str(pid)
        if pid_s in hold:
            continue
        if pid_s not in off_ids and pid_s not in def_ids:
            continue
        if _overlay_has_pid(offense_map, pid_s) or _overlay_has_pid(defense_map, pid_s):
            continue
        if not isinstance(sc, dict) or sc.get("x") is None or sc.get("y") is None:
            continue

        start_coord = {"x": float(sc["x"]), "y": float(sc["y"])}
        moving_dest = _shoot_step_destination(shoot_step, pid_s, start_coord)
        if moving_dest is not None:
            target = _clamp_coord(moving_dest)
        elif _euclid(start_coord, basket) <= radius:
            continue
        else:
            target = sample_coord_within_basket_radius(basket, radius=radius, rng=rng)

        if pid_s in off_ids:
            offense_map[pid_s] = target
        else:
            defense_map[pid_s] = target

    from BackEnd.utils.shared import canonicalize_post_shot_overlays

    canonicalize_post_shot_overlays(turn_result)
