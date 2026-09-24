"""Defender-defender partial-overlap separation — ``GOB_COLLISION_SEPARATION``, default OFF.

WHY
    reports/overlap-and-screens-audit-2026-09-24.md measured the overlap Jamie sees at rest and
    found it is a SCALE MISMATCH, not a positioning bug: the shipped player marker is ~5.25 grid
    units wide at the league median height, while every distance in the defensive vocabulary
    (deny 2.0, on-ball tight 2.5 / normal 3.5 / loose 4.5) is smaller than one sprite. 74.78% of
    steps carry at least one pair inside 3.0 units; 14.50% carry an exactly coincident pair.

SCOPE — DEFENDER-DEFENDER ONLY
    This never moves an offensive player, and it never separates a defender from the man he is
    guarding: that overlap is COVERAGE. Deny sits at 2.0 on purpose. The audit showed a naive
    flat-3.0 rule would move 25.32% of placements with 28.6% of the separated pairs being
    deliberate deny/help work, which is what the pinning rule below exists to avoid.

THE THRESHOLD IS PER PAIR, DERIVED FROM HEIGHT
    The frontend sizes each marker from the player's height
    (``createHeadshotMarkerV2.js:headRadiusForHeight``). Two players clear each other completely
    at ``r_a + r_b``; this tolerates half of that overlapping::

        threshold(a, b) = COLLISION_OVERLAP_TOLERANCE * (r_a + r_b)

    ~2.62 grid units for two median (75") players, ~2.08 for two at the short clamp, ~3.17 for
    two at the tall clamp. The radii are computed here from height — the four widths in the
    audit are illustrations, not inputs.

DETERMINISM
    Fixed iteration order by player id, a capped number of relaxation passes (residual overlap is
    accepted, not iterated away), a per-defender displacement cap, and **no RNG at all**. Ties
    break on player id. This runs inside the placement path, before the freeze stamp, so the
    frozen row records the post-separation coordinate and screen still equals game.
"""

import math
import os
from typing import Any, Dict, Iterable, Optional, Tuple

#: The flag. Unset or anything other than "1" means OFF.
COLLISION_SEPARATION_FLAG = "GOB_COLLISION_SEPARATION"

#: Fraction of full clearance (r_a + r_b) that two defenders are allowed to overlap.
#: 0.5 = half the combined sprite width may overlap before they are pushed apart.
#: NOT tuned here — Jamie tunes once at the end.
COLLISION_OVERLAP_TOLERANCE = 0.5

#: Relaxation passes. Pushing A off B can push A into C; this is capped rather than iterated to
#: convergence so the pass is O(1) and cannot oscillate. Residual overlap is accepted and
#: measured, not chased.
COLLISION_MAX_PASSES = 3

#: Hard cap on how far one defender may be displaced in one step, in grid units, summed across
#: all passes. Nothing teleports: this is under half a sprite width.
COLLISION_MAX_DISPLACEMENT = 2.0

#: A defender sitting this close to the man he is assigned to is doing deliberate coverage work
#: — deny (``POSTURE_DENY_DISTANCE`` 2.0) or on-ball tight (``ONBALL_POSTURE_DIST["tight"]``
#: 2.5). He is PINNED: he is never pushed, and his partner in a colliding pair absorbs the whole
#: separation. Resolved from the shared_defense constants at call time, never inlined.
_PINNED_FALLBACK_DISTANCE = 2.5

#: Canvas is a fixed 1229x768 logical space for a 100x50 grid (gridToPixels.js, bootGame.js),
#: with Phaser.Scale.FIT, so px-per-grid is scale-invariant. 1229 / 100.
PX_PER_GRID_X = 12.29

#: Mirror of ``headRadiusForHeight`` in createHeadshotMarkerV2.js. Kept as separate named parts
#: so a frontend change is a visible diff here rather than a silent divergence.
_HEAD_RADIUS_BASE_PX = 30.0        # at 72 inches
_HEAD_RADIUS_PER_INCH = 0.75
_HEAD_RADIUS_ANCHOR_IN = 72.0
_HEAD_RADIUS_MIN_PX = 25.5         # <= 5'6"
_HEAD_RADIUS_MAX_PX = 39.0         # >= 7'0"
_HEAD_RADIUS_DEFAULT_PX = 28.5     # height unknown — the frontend's own default


def collision_separation_enabled() -> bool:
    """``GOB_COLLISION_SEPARATION`` — **default OFF**. Read at call time so tests can set it."""
    return os.environ.get(COLLISION_SEPARATION_FLAG, "0") == "1"


def _head_radius_px(height_inches: Any) -> float:
    """The rendered marker radius in pixels, exactly as the frontend computes it."""
    if height_inches is None:
        return _HEAD_RADIUS_DEFAULT_PX
    try:
        h = float(height_inches)
    except (TypeError, ValueError):
        return _HEAD_RADIUS_DEFAULT_PX
    r = _HEAD_RADIUS_BASE_PX + (h - _HEAD_RADIUS_ANCHOR_IN) * _HEAD_RADIUS_PER_INCH
    return max(_HEAD_RADIUS_MIN_PX, min(_HEAD_RADIUS_MAX_PX, r))


def defender_radius_grid(player: Any) -> float:
    """Half a player's rendered width, in GRID units. Derived from height, never hardcoded."""
    height = None
    if player is not None:
        height = getattr(player, "height", None)
        if height is None:
            attrs = getattr(player, "attributes", None)
            if isinstance(attrs, dict):
                height = attrs.get("height")
    return _head_radius_px(height) / PX_PER_GRID_X


def separation_threshold(player_a: Any, player_b: Any) -> float:
    """Centre distance below which this specific pair reads as overlapping."""
    return COLLISION_OVERLAP_TOLERANCE * (
        defender_radius_grid(player_a) + defender_radius_grid(player_b)
    )


def pinned_coverage_distance() -> float:
    """The distance to his own man inside which a defender is doing deliberate coverage work.

    Read from ``shared_defense`` so a retune of deny / tight moves this with it. Falls back to
    the larger of the two shipped values if the import is unavailable.
    """
    try:
        from BackEnd.utils.shared_defense import (
            ONBALL_POSTURE_DIST,
            POSTURE_DENY_DISTANCE,
        )
    except Exception:
        return _PINNED_FALLBACK_DISTANCE
    try:
        return max(float(POSTURE_DENY_DISTANCE), float(ONBALL_POSTURE_DIST["tight"]))
    except Exception:
        return _PINNED_FALLBACK_DISTANCE


def _dist(a: Dict[str, float], b: Dict[str, float]) -> float:
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))


def separate_defenders(
    coords: Dict[str, Dict[str, float]],
    players: Dict[str, Any],
    pinned: Optional[Iterable[str]] = None,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Any]]:
    """Push overlapping DEFENDER pairs apart. Returns ``(new_coords, stats)``.

    ``coords`` and ``players`` are keyed by the same ids (defender position or player id); every
    key present is treated as a defender, so the caller is responsible for never passing an
    offensive player in. ``pinned`` ids are never moved.

    Deterministic: ids are sorted, passes are capped, displacement is capped, and nothing here
    draws randomness.
    """
    stats = {
        "pairs_considered": 0,
        "pairs_overlapping": 0,
        "pairs_separated": 0,
        "pairs_skipped_both_pinned": 0,
        "pairs_one_pinned": 0,
        "moved": {},
        "residual": [],
    }
    if not coords:
        return coords, stats

    pinned_set = set(pinned or ())
    ids = sorted(coords)                      # FIXED ORDER — never dict or set order
    out = {i: {"x": float(coords[i]["x"]), "y": float(coords[i]["y"])} for i in ids}
    spent = {i: 0.0 for i in ids}

    for _pass in range(COLLISION_MAX_PASSES):
        moved_any = False
        for ai in range(len(ids)):
            a = ids[ai]
            for bi in range(ai + 1, len(ids)):
                b = ids[bi]
                if _pass == 0:
                    stats["pairs_considered"] += 1
                thr = separation_threshold(players.get(a), players.get(b))
                d = _dist(out[a], out[b])
                if d >= thr:
                    continue
                if _pass == 0:
                    stats["pairs_overlapping"] += 1
                a_pinned, b_pinned = a in pinned_set, b in pinned_set
                if a_pinned and b_pinned:
                    if _pass == 0:
                        stats["pairs_skipped_both_pinned"] += 1
                    continue
                need = thr - d
                if d < 1e-9:
                    # Exactly coincident: no direction to push along. Separate on the x axis,
                    # lower id to -x, so the result is a function of the ids alone. NO RNG.
                    ux, uy = (-1.0, 0.0) if a < b else (1.0, 0.0)
                else:
                    ux = (out[a]["x"] - out[b]["x"]) / d
                    uy = (out[a]["y"] - out[b]["y"]) / d
                if a_pinned or b_pinned:
                    if _pass == 0:
                        stats["pairs_one_pinned"] += 1
                    shares = ((b, -need) if a_pinned else (a, need),)
                else:
                    # Midpoint preserved: each takes half.
                    shares = ((a, need / 2.0), (b, -need / 2.0))
                for who, amount in shares:
                    room = COLLISION_MAX_DISPLACEMENT - spent[who]
                    if room <= 0:
                        continue
                    mag = abs(amount)
                    if mag > room:
                        amount = room if amount > 0 else -room
                        mag = room
                    out[who]["x"] += ux * amount
                    out[who]["y"] += uy * amount
                    spent[who] += mag
                    stats["moved"][who] = spent[who]
                    moved_any = True
                if _pass == 0:
                    stats["pairs_separated"] += 1
        if not moved_any:
            break

    for ai in range(len(ids)):
        for bi in range(ai + 1, len(ids)):
            a, b = ids[ai], ids[bi]
            thr = separation_threshold(players.get(a), players.get(b))
            d = _dist(out[a], out[b])
            if d < thr:
                stats["residual"].append((a, b, round(thr - d, 4)))
    return out, stats


def apply_separation_to_animations(animations, game, def_lineup, off_lineup=None):
    """Apply defender-defender separation to a built ``animations`` list, in place.

    THIS IS THE ONLY ENTRY POINT THE ENGINE USES, and it is called from
    ``defender_placement.build_all_animations`` immediately before it returns — i.e. INSIDE the
    placement path and BEFORE the freeze stamp, which reads these same coords back out through
    ``defender_grid_from_animations``. The frozen row therefore records the post-separation
    coordinate; nothing writes to a frozen row afterwards.

    Only entries whose ``playerId`` is on the DEFENDING lineup are touched. Offensive entries are
    read (to locate each defender's man) and never written — that is what keeps this in scope.

    Returns a stats dict; returns immediately with the flag off.
    """
    stats = {"enabled": False, "steps": 0, "pairs_overlapping": 0, "pairs_separated": 0,
             "pairs_one_pinned": 0, "pairs_skipped_both_pinned": 0, "pinned": 0,
             "moves": [], "residual": 0, "residual_worst": 0.0, "def_placements": 0}
    if not collision_separation_enabled() or not animations or not def_lineup:
        return stats
    stats["enabled"] = True

    by_pid = {}
    for a in animations:
        pid = a.get("playerId")
        if pid is not None:
            by_pid[pid] = a

    def_pid_by_pos, def_player_by_pos = {}, {}
    for dpos, pl in (def_lineup or {}).items():
        pid = getattr(pl, "player_id", None)
        if pid is not None and pid in by_pid:
            def_pid_by_pos[dpos] = pid
            def_player_by_pos[dpos] = pl
    if len(def_pid_by_pos) < 2:
        return stats

    off_pid_by_pos = {}
    for opos, pl in (off_lineup or {}).items():
        pid = getattr(pl, "player_id", None)
        if pid is not None and pid in by_pid:
            off_pid_by_pos[opos] = pid

    # def_pos -> off_pos, so a defender doing deliberate coverage can be pinned off his own man.
    matchups = {}
    try:
        from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team
        matchups = get_matchups_for_defending_team(
            getattr(game, "game_state", None) or {},
            bool(getattr(getattr(game, "defense_team", None), "is_user_team", False)),
        ) or {}
    except Exception:
        matchups = {}

    def _coords_at(pid, i):
        mv = (by_pid.get(pid) or {}).get("movement") or []
        if i >= len(mv):
            return None
        c = (mv[i] or {}).get("coords")
        return c if isinstance(c, dict) and "x" in c and "y" in c else None

    n_steps = 0
    for pid in def_pid_by_pos.values():
        n_steps = max(n_steps, len((by_pid.get(pid) or {}).get("movement") or []))

    pin_at = pinned_coverage_distance()
    for i in range(n_steps):
        coords = {}
        for dpos, pid in def_pid_by_pos.items():
            c = _coords_at(pid, i)
            if c is not None:
                coords[dpos] = {"x": float(c["x"]), "y": float(c["y"])}
        if len(coords) < 2:
            continue
        stats["def_placements"] += len(coords)

        pinned = set()
        for dpos in coords:
            opos = matchups.get(dpos, dpos)          # default man-on-man is position-on-position
            opid = off_pid_by_pos.get(opos)
            man = _coords_at(opid, i) if opid else None
            if man is not None and _dist(coords[dpos], man) <= pin_at:
                pinned.add(dpos)
        stats["pinned"] += len(pinned)

        new, s = separate_defenders(coords, def_player_by_pos, pinned=pinned)
        stats["steps"] += 1
        for k in ("pairs_overlapping", "pairs_separated", "pairs_one_pinned",
                  "pairs_skipped_both_pinned"):
            stats[k] += s[k]
        for _who, moved in s["moved"].items():
            stats["moves"].append(round(moved, 4))
        stats["residual"] += len(s["residual"])
        for _a, _b, gap in s["residual"]:
            stats["residual_worst"] = max(stats["residual_worst"], gap)

        for dpos, pid in def_pid_by_pos.items():
            if dpos not in new:
                continue
            mv = (by_pid.get(pid) or {}).get("movement") or []
            if i < len(mv) and isinstance(mv[i], dict):
                mv[i]["coords"] = {"x": new[dpos]["x"], "y": new[dpos]["y"]}
    return stats
