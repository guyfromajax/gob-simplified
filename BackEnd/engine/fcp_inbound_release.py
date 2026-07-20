"""
FCP inbounder (SF) release after BIP: sprint to x=34 on an open vertical tier,
and pass-eligibility gating until he clears a per-possession x threshold.

Home-on-offense coords; away uses ``get_away_player_coords`` at boundaries.
"""

from __future__ import annotations

from BackEnd.utils.sim_random import sim_rng as random
from typing import Any, Dict, Set

from BackEnd.utils.shared import clamp_animation_grid_coords, get_away_player_coords

FCP_INBOUND_BASELINE_X_HOME = 3
FCP_SF_RELEASE_X_HOME = 34
FCP_SF_PASS_CLEAR_X_MIN = 14
FCP_SF_PASS_CLEAR_X_MAX = 20

# Vertical staging tiers at the release line (home orientation).
FCP_SF_TIER_Y = {
    "upper": 35,
    "center": 25,
    "lower": 15,
}

ALL_SF_TIERS = frozenset(FCP_SF_TIER_Y)


def sample_fcp_sf_pass_clear_x() -> int:
    """Per-possession x progress (home-oriented) before SF is a pass target."""
    return random.randint(FCP_SF_PASS_CLEAR_X_MIN, FCP_SF_PASS_CLEAR_X_MAX)


def _clamp_xy(xy: Dict[str, Any]) -> Dict[str, int]:
    clamped = clamp_animation_grid_coords(
        {"x": float(xy["x"]), "y": float(xy["y"])},
    ) or xy
    return {"x": int(round(clamped["x"])), "y": int(round(clamped["y"]))}


def _flip(xy: Dict[str, Any]) -> Dict[str, int]:
    return get_away_player_coords({"x": int(xy["x"]), "y": int(xy["y"])})


def _offense_progress_x(x: float, is_away_offense: bool) -> float:
    return (100.0 - x) if is_away_offense else x


def _y_to_vertical_tier(y: int) -> str:
    if y > 30:
        return "upper"
    if y < 20:
        return "lower"
    return "center"


def _occupied_backcourt_tiers(
    off_coords: Dict[str, Dict[str, int]],
    bh_pos: str,
) -> Set[str]:
    """Tiers taken by PG/SG (excluding the ball handler)."""
    tiers: Set[str] = set()
    for pos in ("PG", "SG"):
        if pos == bh_pos:
            continue
        tiers.add(_y_to_vertical_tier(int(off_coords[pos]["y"])))
    return tiers


def pick_open_sf_tier(
    off_coords: Dict[str, Dict[str, int]],
    bh_pos: str,
) -> str:
    """Random open upper/center/lower tier (always ≥1 open with 3 tiers / 2 players)."""
    occupied = _occupied_backcourt_tiers(off_coords, bh_pos)
    open_tiers = sorted(ALL_SF_TIERS - occupied)
    return random.choice(open_tiers)


def sf_at_fcp_inbound_baseline(
    off_coords: Dict[str, Dict[str, int]],
    is_away_offense: bool,
) -> bool:
    """True while SF is still at the BIP baseline inbound spot."""
    sf = off_coords.get("SF") or {}
    x = float(sf.get("x", 50))
    if is_away_offense:
        return x >= (100 - FCP_INBOUND_BASELINE_X_HOME)
    return x <= FCP_INBOUND_BASELINE_X_HOME


def compute_sf_inbound_release_target(
    off_coords: Dict[str, Dict[str, int]],
    bh_pos: str,
    is_away_offense: bool,
) -> Dict[str, int]:
    """Destination for SF sprint off the baseline: x=34 on an open vertical tier."""
    tier = pick_open_sf_tier(off_coords, bh_pos)
    dest = _clamp_xy({"x": FCP_SF_RELEASE_X_HOME, "y": FCP_SF_TIER_Y[tier]})
    if is_away_offense:
        dest = _flip(dest)
    return dest


def sf_cleared_for_fcp_pass(
    sf_xy: Dict[str, Any],
    is_away_offense: bool,
    clear_x: int,
) -> bool:
    """True when SF has sprinted far enough inbounds to receive a press-break pass."""
    x = float(sf_xy.get("x", 50))
    return _offense_progress_x(x, is_away_offense) >= float(clear_x)
