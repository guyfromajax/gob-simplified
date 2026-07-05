"""
FCP defensive PF/C front-court zone (Straight Pressure only).

Dynamic x/y band compresses as the BH advances; offender help/denial uses
offenders inside the zone (not the HCT ABA pool). See Z-Completed/Dynamic_FCP_Brief §2.3.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

POSITIONS = ("PG", "SG", "SF", "PF", "C")

# Zone geometry (home orientation — mirror x for away at boundaries).
FCP_ZONE_COMPRESS_START = 36
FCP_ZONE_COMPRESS_STOP = 50
FCP_ZONE_REAR = 50
FCP_ZONE_FRONT_CAP = 64
FCP_ZONE_SLIDE_WIDTH = 14
FCP_ZONE_PRE_Y_MIN, FCP_ZONE_PRE_Y_MAX = 1, 50
FCP_ZONE_COMPRESS_Y_MIN, FCP_ZONE_COMPRESS_Y_MAX = 10, 40

FCP_PRESS_BREAK_PROGRESS = 64


def fcp_ball_progress(bh_xy: Dict[str, Any], is_away_offense: bool) -> int:
    x = int(bh_xy["x"])
    return (100 - x) if is_away_offense else x


def fcp_bh_past_press_break(bh_xy: Dict[str, Any], is_away_offense: bool) -> bool:
    """True when BH progress x ≥ 64 (FCP Straight Pressure man release)."""
    return fcp_ball_progress(bh_xy, is_away_offense) >= FCP_PRESS_BREAK_PROGRESS


def fcp_zone_bounds_home(progress: int) -> Optional[Tuple[int, int, int, int]]:
    """Press zone in home orientation; ``None`` when progress ≥ 64."""
    if progress >= FCP_PRESS_BREAK_PROGRESS:
        return None
    if progress < FCP_ZONE_COMPRESS_START:
        return (
            FCP_ZONE_REAR,
            FCP_ZONE_FRONT_CAP,
            FCP_ZONE_PRE_Y_MIN,
            FCP_ZONE_PRE_Y_MAX,
        )
    if progress <= FCP_ZONE_COMPRESS_STOP:
        return (
            progress,
            min(progress + FCP_ZONE_SLIDE_WIDTH, FCP_ZONE_FRONT_CAP),
            FCP_ZONE_COMPRESS_Y_MIN,
            FCP_ZONE_COMPRESS_Y_MAX,
        )
    return (
        FCP_ZONE_REAR,
        FCP_ZONE_FRONT_CAP,
        FCP_ZONE_COMPRESS_Y_MIN,
        FCP_ZONE_COMPRESS_Y_MAX,
    )


def fcp_zone_bounds(
    bh_xy: Dict[str, Any], is_away_offense: bool
) -> Optional[Tuple[int, int, int, int]]:
    home = fcp_zone_bounds_home(fcp_ball_progress(bh_xy, is_away_offense))
    if home is None:
        return None
    x_lo, x_hi, y_lo, y_hi = home
    if is_away_offense:
        x_lo, x_hi = 100 - x_hi, 100 - x_lo
    return (x_lo, x_hi, y_lo, y_hi)


def offender_in_fcp_zone(
    off_xy: Dict[str, Any], bounds: Tuple[int, int, int, int]
) -> bool:
    x_lo, x_hi, y_lo, y_hi = bounds
    return x_lo <= int(off_xy["x"]) <= x_hi and y_lo <= int(off_xy["y"]) <= y_hi


def fcp_anchor_names(progress: int) -> Tuple[str, str]:
    """Ladder pair (rear anchor, front anchor) by BH progress."""
    if progress < FCP_ZONE_COMPRESS_START:
        return ("midcourt", "key")
    if progress <= FCP_ZONE_COMPRESS_STOP:
        return ("midcourt", "key")
    if progress < FCP_PRESS_BREAK_PROGRESS:
        return ("key", "midLane")
    return ("midLane", "basketSpot")


def fcp_pf_c_targets(
    bh_xy: Dict[str, Any],
    off_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    *,
    spot_fn,
    ball_band_fn,
    converge_fn,
    clamp_fn,
    interpolate_fn,
    euclid_fn,
    in_aba_fn,
    aba_half_fn,
    rim_coords,
    flip_fn,
) -> Dict[str, Dict[str, int]]:
    """FCP Straight Pressure PF/C targets (dynamic zone + anchor ladder)."""
    progress = fcp_ball_progress(bh_xy, is_away_offense)
    band = ball_band_fn(bh_xy["y"])
    defend_bh = converge_fn(bh_xy, is_away_offense)

    def _anchor(name: str) -> Dict[str, int]:
        if name == "midcourt":
            base = {"x": 50, "y": 25}
            return clamp_fn(flip_fn(base) if is_away_offense else base)
        return spot_fn(name)

    if in_aba_fn(bh_xy, is_away_offense):
        basket_spot = spot_fn("basketSpot")
        mid_lane = spot_fn("midLane")
        if band == "center":
            return {"C": basket_spot, "PF": defend_bh}
        if band == "upper":
            return {"C": defend_bh, "PF": mid_lane}
        return {"PF": defend_bh, "C": mid_lane}

    bounds = fcp_zone_bounds(bh_xy, is_away_offense)
    rear_name, front_name = fcp_anchor_names(progress)
    rear = _anchor(rear_name)
    front = _anchor(front_name)

    if bounds is None or progress >= FCP_PRESS_BREAK_PROGRESS:
        if band == "center":
            return {"PF": rear, "C": front}
        if band == "upper":
            return {"PF": rear, "C": front}
        return {"C": rear, "PF": front}

    if band == "center":
        mid = clamp_fn(
            {"x": int(round((rear["x"] + front["x"]) / 2)), "y": rear["y"]}
        )
        return {"PF": mid, "C": front}

    if band == "upper":
        return {
            "PF": rear,
            "C": _fcp_help_denial(
                bh_xy,
                off_coords,
                is_away_offense,
                "upper",
                bounds,
                front,
                spot_fn=spot_fn,
                clamp_fn=clamp_fn,
                interpolate_fn=interpolate_fn,
                euclid_fn=euclid_fn,
                aba_half_fn=aba_half_fn,
                rim_coords=rim_coords,
            ),
        }
    return {
        "C": rear,
        "PF": _fcp_help_denial(
            bh_xy,
            off_coords,
            is_away_offense,
            "lower",
            bounds,
            front,
            spot_fn=spot_fn,
            clamp_fn=clamp_fn,
            interpolate_fn=interpolate_fn,
            euclid_fn=euclid_fn,
            aba_half_fn=aba_half_fn,
            rim_coords=rim_coords,
        ),
    }


def _fcp_help_denial(
    bh_xy: Dict[str, Any],
    off_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
    half: str,
    bounds: Tuple[int, int, int, int],
    front_anchor: Dict[str, int],
    *,
    spot_fn,
    clamp_fn,
    interpolate_fn,
    euclid_fn,
    aba_half_fn,
    rim_coords,
) -> Dict[str, int]:
    wing = spot_fn("upper wing" if half == "upper" else "lower wing")
    occupants: List[str] = [
        p
        for p in POSITIONS
        if offender_in_fcp_zone(off_coords[p], bounds)
        and aba_half_fn(off_coords[p]) == half
    ]
    if not occupants:
        return wing
    rim_xy = {"x": float(rim_coords["x"]), "y": float(rim_coords["y"])}
    best = sorted(
        occupants,
        key=lambda p: (euclid_fn(off_coords[p], rim_xy), -off_coords[p]["x"]),
    )[0]
    off_xy = off_coords[best]
    deeper = (
        off_xy["x"] < front_anchor["x"]
        if is_away_offense
        else off_xy["x"] > front_anchor["x"]
    )
    if deeper:
        return clamp_fn(interpolate_fn(bh_xy, off_xy, 0.6))
    return front_anchor
