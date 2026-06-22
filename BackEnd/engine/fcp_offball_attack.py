"""
FCP off-ball offense movement during BH attack / advance beats.

Incremental press-break (``hct_advance`` after attack wins): backcourt non-BH
release toward x∈[46,53]; PF/C phase targets keyed to ball progress x. Broken
open-floor drives use ABA spot targets until a cutoff RETAIN reverts here.

Home-on-offense coords; away uses ``get_away_player_coords`` flip at boundaries.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Set, Tuple

from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.utils.shared import clamp_animation_grid_coords, get_away_player_coords

POSITIONS = ("PG", "SG", "SF", "PF", "C")
BACKCOURT_POS = frozenset({"PG", "SG", "SF"})
FRONTCOURT_POS = frozenset({"PF", "C"})

# Backcourt release lane (home orientation).
FCP_BACKCOURT_X_MIN = 46
FCP_BACKCOURT_X_MAX = 53
FCP_BACKCOURT_Y_JITTER = 6

# Ball-progress thresholds (see ``_ball_progress_x``).
FCP_PROGRESS_HOLD_PF = 34  # PF stationary while progress < this
FCP_PROGRESS_HOLD_C = 34  # C stationary while progress <= this
FCP_PROGRESS_FRONT = 50  # PF wing band / C front band above this

# Deep key anchor for PF mid-band: backcourt-side of half court (x < 50 home).
FCP_DEEP_KEY_ANCHOR = {"x": 47, "y": 25}
FCP_DEEP_KEY_RADIUS = 6

ABA_X_MIN = 65
ABA_X_MAX = 80
ABA_Y_MIN = 10
ABA_Y_MAX = 40

PF_PHASE3_SPOTS = (
    "key",
    "upper midWing",
    "lower midWing",
    "upper wing",
    "lower wing",
)

C_PHASE2_SPOTS = (
    "topLane",
    "upper apex",
    "lower apex",
    "upper midCorner",
    "lower midCorner",
    "upper wing",
    "lower wing",
)

C_PHASE3_HALF_SPOTS = (
    "upper lowPost",
    "lower lowPost",
    "upper midPost",
    "lower midPost",
    "upper midBaseline",
    "lower midBaseline",
    "upper corner",
    "lower corner",
    "upper midCorner",
    "lower midCorner",
    "upper bird",
    "lower bird",
)


def _clamp_xy(xy: Dict[str, Any]) -> Dict[str, int]:
    c = clamp_animation_grid_coords(float(xy["x"]), float(xy["y"]))
    return {"x": int(c["x"]), "y": int(c["y"])}


def _flip(xy: Dict[str, Any]) -> Dict[str, int]:
    return get_away_player_coords({"x": int(xy["x"]), "y": int(xy["y"])})


def _ball_progress_x(bh_xy: Dict[str, Any], is_away_offense: bool) -> int:
    """Distance-style progress toward the offense basket (34 = backcourt line)."""
    x = int(bh_xy["x"])
    if is_away_offense:
        return 100 - x
    return x


def _bh_vertical_half(bh_y: int) -> str:
    return "upper" if int(bh_y) > 25 else "lower"


def _spot_xy(name: str, is_away_offense: bool) -> Dict[str, int]:
    base = dict(HCO_STRING_SPOTS[name])
    return _flip(base) if is_away_offense else _clamp_xy(base)


def _filter_half_spots(names: Tuple[str, ...], half: str) -> List[str]:
    if half == "upper":
        return [n for n in names if n.startswith("upper") or n == "topLane"]
    return [n for n in names if n.startswith("lower")]


class FcpOffballAttackState:
    """Per-possession off-ball target state for dynamic FCP attack beats."""

    def __init__(self, is_away_offense: bool) -> None:
        self.is_away_offense = is_away_offense
        self._dest: Dict[str, Dict[str, int]] = {}
        self._phase: Dict[str, str] = {}
        self._aba_mode = False
        self._incremental_active = False

    def sync_off_targets(
        self,
        off_targets: Dict[str, Dict[str, int]],
        bh_pos: str,
    ) -> None:
        """Mirror active destinations into ``off_targets`` for the emitter."""
        for pos in POSITIONS:
            if pos == bh_pos:
                continue
            if pos in self._dest:
                off_targets[pos] = dict(self._dest[pos])

    def enter_aba_mode(
        self,
        off_coords: Dict[str, Dict[str, int]],
        bh_pos: str,
    ) -> None:
        self._aba_mode = True
        self._incremental_active = False
        self._phase.clear()
        for pos in POSITIONS:
            if pos == bh_pos:
                continue
            self._dest[pos] = _random_aba_xy(self.is_away_offense)
            self._phase[pos] = "aba"

    def exit_aba_to_incremental(
        self,
        bh_xy: Dict[str, Any],
        off_coords: Dict[str, Dict[str, int]],
        bh_pos: str,
    ) -> None:
        self._aba_mode = False
        self._incremental_active = True
        self._phase.clear()
        self._dest.clear()
        self.refresh_incremental(bh_xy, off_coords, bh_pos, force=True)

    def refresh_incremental(
        self,
        bh_xy: Dict[str, Any],
        off_coords: Dict[str, Dict[str, int]],
        bh_pos: str,
        *,
        force: bool = False,
    ) -> None:
        """Assign / refresh targets when a band condition fires or on first advance."""
        self._incremental_active = True
        self._aba_mode = False
        progress = _ball_progress_x(bh_xy, self.is_away_offense)
        half = _bh_vertical_half(bh_xy["y"])

        for pos in POSITIONS:
            if pos == bh_pos:
                continue
            if pos in BACKCOURT_POS:
                self._refresh_backcourt(pos, off_coords, force=force)
            elif pos == "PF":
                self._refresh_pf(pos, off_coords, progress, force=force)
            elif pos == "C":
                self._refresh_c(pos, off_coords, progress, half, force=force)

    def _refresh_backcourt(
        self,
        pos: str,
        off_coords: Dict[str, Dict[str, int]],
        *,
        force: bool,
    ) -> None:
        phase = "release"
        if not force and self._phase.get(pos) == phase and pos in self._dest:
            return
        start_y = int(off_coords[pos]["y"])
        dest = _clamp_xy(
            {
                "x": random.randint(FCP_BACKCOURT_X_MIN, FCP_BACKCOURT_X_MAX),
                "y": start_y + random.randint(-FCP_BACKCOURT_Y_JITTER, FCP_BACKCOURT_Y_JITTER),
            }
        )
        if self.is_away_offense:
            dest = _flip(dest)
        self._dest[pos] = dest
        self._phase[pos] = phase

    def _should_assign_phase(
        self,
        pos: str,
        phase: str,
        off_coords: Dict[str, Dict[str, int]],
        *,
        force: bool,
    ) -> bool:
        if force or self._phase.get(pos) != phase:
            return True
        if pos not in self._dest:
            return True
        return False

    def _refresh_pf(
        self,
        pos: str,
        off_coords: Dict[str, Dict[str, int]],
        progress: int,
        *,
        force: bool,
    ) -> None:
        if progress < FCP_PROGRESS_HOLD_PF:
            phase = "hold"
            self._dest[pos] = dict(off_coords[pos])
        elif progress < FCP_PROGRESS_FRONT:
            phase = "deep"
            if self._should_assign_phase(pos, phase, off_coords, force=force):
                self._dest[pos] = _random_near_deep_key(self.is_away_offense)
        else:
            phase = "wing"
            if self._should_assign_phase(pos, phase, off_coords, force=force):
                spot = random.choice(PF_PHASE3_SPOTS)
                self._dest[pos] = _spot_xy(spot, self.is_away_offense)
        self._phase[pos] = phase

    def _refresh_c(
        self,
        pos: str,
        off_coords: Dict[str, Dict[str, int]],
        progress: int,
        half: str,
        *,
        force: bool,
    ) -> None:
        if progress <= FCP_PROGRESS_HOLD_C:
            phase = "hold"
            self._dest[pos] = dict(off_coords[pos])
        elif progress <= FCP_PROGRESS_FRONT:
            phase = "mid"
            if self._should_assign_phase(pos, phase, off_coords, force=force):
                pool = _filter_half_spots(C_PHASE2_SPOTS, half)
                spot = random.choice(pool) if pool else "topLane"
                self._dest[pos] = _spot_xy(spot, self.is_away_offense)
        else:
            phase = "front"
            if self._should_assign_phase(pos, phase, off_coords, force=force):
                half_pool = _filter_half_spots(C_PHASE3_HALF_SPOTS, half)
                spot = random.choice(["midLane"] + half_pool)
                self._dest[pos] = _spot_xy(spot, self.is_away_offense)
        self._phase[pos] = phase

    def move_offense(
        self,
        off_coords: Dict[str, Dict[str, int]],
        off_lineup: Dict[str, Any],
        bh_pos: str,
        seconds: float,
        *,
        exclude: Optional[Set[str]] = None,
        ag_grid_fn,
        interrupted_fn,
    ) -> None:
        """Move non-BH offense toward ``self._dest`` at sprint rate."""
        skip = {bh_pos} | (exclude or set())
        for pos in POSITIONS:
            if pos in skip:
                continue
            dest = self._dest.get(pos)
            if dest is None:
                continue
            if _at_destination(off_coords[pos], dest):
                continue
            rate = ag_grid_fn(off_lineup.get(pos), "sprint")
            if rate <= 0:
                continue
            off_coords[pos] = _clamp_xy(
                interrupted_fn(off_coords[pos], dest, rate, seconds)
            )


def _at_destination(current: Dict[str, Any], dest: Dict[str, Any], tol: float = 0.5) -> bool:
    return math.hypot(dest["x"] - current["x"], dest["y"] - current["y"]) <= tol


def _random_near_deep_key(is_away_offense: bool) -> Dict[str, int]:
    anchor = _flip(FCP_DEEP_KEY_ANCHOR) if is_away_offense else dict(FCP_DEEP_KEY_ANCHOR)
    for _ in range(48):
        dx = random.randint(-FCP_DEEP_KEY_RADIUS, FCP_DEEP_KEY_RADIUS)
        dy = random.randint(-FCP_DEEP_KEY_RADIUS, FCP_DEEP_KEY_RADIUS)
        if dx * dx + dy * dy > FCP_DEEP_KEY_RADIUS * FCP_DEEP_KEY_RADIUS:
            continue
        pt = _clamp_xy({"x": anchor["x"] + dx, "y": anchor["y"] + dy})
        prog = _ball_progress_x(pt, is_away_offense)
        if FCP_PROGRESS_HOLD_PF <= prog < FCP_PROGRESS_FRONT:
            return pt
    return _clamp_xy(anchor)


def _random_aba_xy(is_away_offense: bool) -> Dict[str, int]:
    pt = _clamp_xy(
        {
            "x": random.randint(ABA_X_MIN, ABA_X_MAX),
            "y": random.randint(ABA_Y_MIN, ABA_Y_MAX),
        }
    )
    return _flip(pt) if is_away_offense else pt
