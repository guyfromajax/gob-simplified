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

#: Phase 1 EXTENDED — separation for all ten players, **default OFF**, and its own flag.
#:
#: It REQUIRES ``GOB_COLLISION_SEPARATION=1``. With this on and the base flag off it logs once
#: and does nothing: the defender-defender pass must stay independently testable and
#: independently rollback-able, so the two are deliberately not folded together.
#:
#: WHY THE SCOPE CHANGED. reports/coincidence-origin-audit.md established that exact-cell
#: coincidence is 2.7% of the visible overlap problem and 1.30x pure chance for the headline
#: stack, with no single cause. The metric that matches what a viewer sees is pairs within
#: 2.0 grid units (156,232) rather than exact cells (28,377). This pass is judged on that.
COLLISION_SEPARATION_ALL_FLAG = "GOB_COLLISION_SEPARATION_ALL"

#: Fraction of full clearance (r_a + r_b) that two defenders are allowed to overlap.
#: 0.5 = half the combined sprite width may overlap before they are pushed apart.
#: NOT tuned here — Jamie tunes once at the end.
COLLISION_OVERLAP_TOLERANCE = 0.5

#: MEASUREMENT OVERRIDE for the tolerance sweep. Read at call time.
#:
#: This exists so a sweep needs no code edit per point. **Absent, empty or unparseable, it
#: resolves to COLLISION_OVERLAP_TOLERANCE exactly**, so the shipped default is untouched and
#: flags-on with the variable unset is byte-identical to flags-on at 0.5 — which is gated, not
#: assumed (reports/collision-tolerance-sweep.md).
#:
#: It is NOT a tuning knob and NOT a shipped behaviour change: it is inert in production, where
#: the variable is never set. The surface it measures is for Jamie's single tuning pass.
COLLISION_TOLERANCE_ENV = "GOB_COLLISION_TOLERANCE"

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


#: Offensive ball actions. A player doing any of these at a step owns the ball at that step, so
#: his coordinate is a pass origin / drive origin / shot spot and is EXEMPT.
BALL_ACTIONS = frozenset({"handle_ball", "receive", "pass", "drive", "shoot"})

#: The action that makes a position the shooter for this skeleton.
SHOOT_ACTION = "shoot"

#: Is an offensive player standing on his AUTHORED ``location`` pinned?
#:
#: True = a player who has arrived at the spot the play sent him to is doing something
#: deliberate, and his partner absorbs the separation — the same argument that pins a defender
#: on his man. Measured both ways in reports/collision-phase1-extended.md.
PIN_OFFENCE_AT_AUTHORED_LOCATION = True

#: How close to his authored spot counts as "at" it, in grid units. NOT a balance constant and
#: not tuned: it is the rounding tolerance of the grid itself, the same 0.5 used to decide
#: whether two players occupy one cell.
AUTHORED_LOCATION_TOLERANCE = 0.5

_WARNED_ALL_WITHOUT_BASE = [False]


def collision_separation_enabled() -> bool:
    """``GOB_COLLISION_SEPARATION`` — **default OFF**. Read at call time so tests can set it."""
    return os.environ.get(COLLISION_SEPARATION_FLAG, "0") == "1"


def collision_separation_all_enabled() -> bool:
    """``GOB_COLLISION_SEPARATION_ALL`` — **default OFF**. Read at call time."""
    return os.environ.get(COLLISION_SEPARATION_ALL_FLAG, "0") == "1"


def warn_if_all_without_base() -> None:
    """ALL on, base off: say so ONCE per process and do nothing. Never half-apply."""
    if _WARNED_ALL_WITHOUT_BASE[0]:
        return
    _WARNED_ALL_WITHOUT_BASE[0] = True
    import logging
    logging.warning(
        "GOB_COLLISION_SEPARATION_ALL=1 but GOB_COLLISION_SEPARATION is off — ten-player "
        "separation is DISABLED. The extended pass builds on the defender-defender pass; "
        "running it alone would separate the offence while leaving the defence untouched."
    )


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


def overlap_tolerance() -> float:
    """The tolerance in force. ``COLLISION_OVERLAP_TOLERANCE`` unless the sweep override says
    otherwise; anything unset, empty, unparseable or non-positive falls back to the constant, so
    the production default cannot be changed by accident."""
    raw = os.environ.get(COLLISION_TOLERANCE_ENV)
    if raw is None or not str(raw).strip():
        return COLLISION_OVERLAP_TOLERANCE
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return COLLISION_OVERLAP_TOLERANCE
    return value if value > 0.0 else COLLISION_OVERLAP_TOLERANCE


def separation_threshold(player_a: Any, player_b: Any) -> float:
    """Centre distance below which this specific pair reads as overlapping."""
    return overlap_tolerance() * (
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
        # how often COLLISION_MAX_DISPLACEMENT is the limiter rather than the tolerance
        "pushes": 0,
        "pushes_cap_bound": 0,
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
                    stats["pushes"] += 1
                    room = COLLISION_MAX_DISPLACEMENT - spent[who]
                    if room <= 0:
                        stats["pushes_cap_bound"] += 1
                        continue
                    mag = abs(amount)
                    if mag > room:
                        stats["pushes_cap_bound"] += 1
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


def apply_separation_to_animations(animations, game, def_lineup, off_lineup=None,
                                   skeleton=None):
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
    import collections as _c
    stats = {"enabled": False, "all_enabled": False, "steps": 0, "pairs_overlapping": 0,
             "pairs_separated": 0, "pairs_one_pinned": 0, "pairs_skipped_both_pinned": 0,
             "pinned": 0, "moves": [], "residual": 0, "residual_worst": 0.0,
             "def_placements": 0, "all_placements": 0, "off_carried_not_writable": 0,
             "pinned_defender": 0, "pinned_shooter": 0, "pinned_ball": 0,
             "pinned_authored": 0, "pinned_not_writable": 0, "pinned_already_written": 0,
             "moved_by_class": _c.Counter(), "residual_by_class": _c.Counter(),
             "pushes": 0, "pushes_cap_bound": 0, "tolerance": overlap_tolerance()}
    if not collision_separation_enabled() or not animations or not def_lineup:
        # ALL on with the base flag off: say so once, change nothing.
        if collision_separation_all_enabled() and not collision_separation_enabled():
            warn_if_all_without_base()
        return stats
    stats["enabled"] = True

    # Phase 1 EXTENDED replaces the defender-only pass; it is NOT an extra pass on top, so a
    # placement can never be pushed twice.
    if collision_separation_all_enabled():
        stats["all_enabled"] = True
        out = apply_separation_all(animations, game, def_lineup, off_lineup, skeleton, stats)
        out["moved_by_class"] = dict(out["moved_by_class"])
        out["residual_by_class"] = dict(out["residual_by_class"])
        return out

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


# ── Phase 1 EXTENDED: all ten players ────────────────────────────────────────────────────


def _authored_by_step(skeleton):
    """``{step_idx: {off_pos: location_name}}`` from the skeleton, for the authored-location pin."""
    out = {}
    for i, st in enumerate((skeleton or {}).get("steps") or []):
        row = {}
        for pos, info in (st.get("pos_actions") or {}).items():
            if not isinstance(info, dict):
                continue
            loc = info.get("location") or info.get("spot")
            if loc:
                row[pos] = loc
        out[i] = row
    return out


def _actions_by_step(skeleton):
    """``{step_idx: {off_pos: action}}`` — the per-step exempt test."""
    out = {}
    for i, st in enumerate((skeleton or {}).get("steps") or []):
        out[i] = {pos: (info or {}).get("action", "")
                  for pos, info in (st.get("pos_actions") or {}).items()}
    return out


def shooter_positions(skeleton):
    """Offensive positions that SHOOT anywhere in this skeleton.

    NOT CLAIRVOYANT: this reads the authored play, which is what the emitter is already
    executing, not the outcome of the shot.

    THE SHOOTER IS EXEMPT AT EVERY STEP, deliberately and not as a convenience.
    ``_documentation_master/projects/bugs.md`` records that **26.8% played / 27.6% wrap of
    shots are decided by ``<=`` against a ZERO MARGIN** on the three-point arc, and that moving
    authored spot coordinates to create margin is "a balance change wearing a tidy-up costume".
    A sub-cell nudge to a shooter reflips that population. So he is never touched, and the
    invariant is asserted at runtime rather than argued.
    """
    out = set()
    for st in (skeleton or {}).get("steps") or []:
        for pos, info in (st.get("pos_actions") or {}).items():
            if isinstance(info, dict) and (info.get("action") or "").lower().strip() == SHOOT_ACTION:
                out.add(pos)
    return out


def _entry_at_timestamp(anim, ts):
    """The player's own movement entry at this timestamp, or None.

    An offensive player's ``movement`` only gains an entry on steps where he HAS a pos_action,
    so ``movement[i]`` is not step ``i`` — the trap ``offense_grid_from_animations`` documents.
    Defenders are step-indexed; the offence is matched on its own timestamp.
    """
    for e in (anim or {}).get("movement") or []:
        if isinstance(e, dict) and e.get("timestamp") == ts:
            c = e.get("coords")
            if isinstance(c, dict) and "x" in c and "y" in c:
                return e
    return None


def _carried_coord(anim, ts):
    """Where the player stands at ``ts``: his last entry at or before it (carry-forward)."""
    best = None
    for e in (anim or {}).get("movement") or []:
        if not isinstance(e, dict):
            continue
        t = e.get("timestamp")
        if t is None or t > ts:
            continue
        c = e.get("coords")
        if isinstance(c, dict) and "x" in c and "y" in c:
            if best is None or t >= best[0]:
                best = (t, c)
    return best[1] if best else None


def _resync_start_end(anim):
    mv = (anim or {}).get("movement") or []
    if mv:
        anim["start"] = mv[0]["coords"]
        anim["end"] = mv[-1]["coords"]


def apply_separation_all(animations, game, def_lineup, off_lineup, skeleton, stats):
    """Ten-player separation. Same machinery as ``separate_defenders`` — nothing retuned.

    Keys are ``"D-<pos>"`` / ``"O-<pos>"`` so one call covers def-def, off-off and def-off in a
    single relaxation, which is what lets a defender and an offensive player share the push
    instead of one of them absorbing it twice.

    THE EXEMPT SET (offence moves are far more consequential than defender moves):
      * the SHOOTER, at every step — see ``shooter_positions``;
      * any offensive player whose action at this step is a BALL action — his coordinate is a
        pass origin, a drive origin or a shot spot;
      * a defender within ``pinned_coverage_distance()`` of his man — the existing Phase 1 pin;
      * optionally an offensive player standing on his authored ``location``
        (``PIN_OFFENCE_AT_AUTHORED_LOCATION``).
    """
    from BackEnd.constants import HCO_STRING_SPOTS

    by_pid = {a.get("playerId"): a for a in animations if a.get("playerId") is not None}

    def_pid, def_player = {}, {}
    for pos, pl in (def_lineup or {}).items():
        pid = getattr(pl, "player_id", None)
        if pid is not None and pid in by_pid:
            def_pid["D-" + str(pos)] = pid
            def_player["D-" + str(pos)] = pl
    off_pid, off_player = {}, {}
    for pos, pl in (off_lineup or {}).items():
        pid = getattr(pl, "player_id", None)
        if pid is not None and pid in by_pid:
            off_pid["O-" + str(pos)] = pid
            off_player["O-" + str(pos)] = pl
    if len(def_pid) + len(off_pid) < 2:
        return stats
    players = dict(def_player)
    players.update(off_player)

    matchups = {}
    try:
        from BackEnd.utils.man_defense_matchups import get_matchups_for_defending_team
        matchups = get_matchups_for_defending_team(
            getattr(game, "game_state", None) or {},
            bool(getattr(getattr(game, "defense_team", None), "is_user_team", False)),
        ) or {}
    except Exception:
        matchups = {}

    shooters = {"O-" + p for p in shooter_positions(skeleton)}
    actions = _actions_by_step(skeleton)
    authored = _authored_by_step(skeleton)
    is_away = False
    try:
        is_away = game.offense_team.team_id == game.away_team.team_id
    except Exception:
        is_away = False
    if is_away:
        from BackEnd.utils.shared import get_away_player_coords
    pin_at = pinned_coverage_distance()

    # The timeline is the DEFENDERS' movement, which is one entry per step and complete.
    ref = next(iter(def_pid.values()), None)
    ref_mv = (by_pid.get(ref) or {}).get("movement") or [] if ref else []
    stats["all_steps"] = 0

    # ONE WRITE PER OFFENSIVE ENTRY PER PASS.
    # Defenders are step-indexed, so index i is a distinct entry every time. The offence is
    # matched on its own TIMESTAMP, and 26.8% of defender movement lists repeat a timestamp
    # (sub-steps), so the same offensive entry can be selected at more than one index. Writing
    # it twice would apply COLLISION_MAX_DISPLACEMENT twice — measured as a 4.0 displacement
    # against a 2.0 cap before this guard existed. After the first write he still takes part in
    # the separation as an obstacle, but he is pinned so nothing moves him again.
    written_off = set()

    for i, ref_entry in enumerate(ref_mv):
        ts = (ref_entry or {}).get("timestamp")
        if ts is None:
            continue
        coords, entries = {}, {}
        for key, pid in def_pid.items():
            mv = (by_pid.get(pid) or {}).get("movement") or []
            if i < len(mv) and isinstance(mv[i], dict):
                c = mv[i].get("coords")
                if isinstance(c, dict) and "x" in c and "y" in c:
                    coords[key] = {"x": float(c["x"]), "y": float(c["y"])}
                    entries[key] = mv[i]
        for key, pid in off_pid.items():
            anim = by_pid.get(pid)
            own = _entry_at_timestamp(anim, ts)
            c = own["coords"] if own else _carried_coord(anim, ts)
            if isinstance(c, dict) and "x" in c and "y" in c:
                coords[key] = {"x": float(c["x"]), "y": float(c["y"])}
                if own is not None:
                    entries[key] = own          # writable only where he has his OWN entry
                else:
                    stats["off_carried_not_writable"] += 1
        if len(coords) < 2:
            continue
        stats["all_steps"] += 1
        stats["all_placements"] += len(coords)

        pinned = set()
        # existing Phase 1 pin: a defender doing deliberate coverage
        for key in coords:
            if not key.startswith("D-"):
                continue
            dpos = key[2:]
            opos = matchups.get(dpos, dpos)
            man = coords.get("O-" + str(opos))
            if man is not None and _dist(coords[key], man) <= pin_at:
                pinned.add(key)
                stats["pinned_defender"] += 1
        step_actions = actions.get(i, {})
        step_authored = authored.get(i, {})
        for key in coords:
            if not key.startswith("O-"):
                continue
            opos = key[2:]
            if key in shooters:
                pinned.add(key); stats["pinned_shooter"] += 1; continue
            act = (step_actions.get(opos) or "").lower().strip()
            if act in BALL_ACTIONS:
                pinned.add(key); stats["pinned_ball"] += 1; continue
            if key not in entries:
                pinned.add(key); stats["pinned_not_writable"] += 1; continue
            if id(entries[key]) in written_off:
                pinned.add(key); stats["pinned_already_written"] += 1; continue
            if PIN_OFFENCE_AT_AUTHORED_LOCATION:
                loc = step_authored.get(opos)
                spot = HCO_STRING_SPOTS.get(loc) if loc else None
                if spot is not None:
                    if is_away:
                        spot = get_away_player_coords(spot)
                    if _dist(coords[key], spot) <= AUTHORED_LOCATION_TOLERANCE:
                        pinned.add(key); stats["pinned_authored"] += 1

        new, s = separate_defenders(coords, players, pinned=pinned)
        for k in ("pairs_overlapping", "pairs_separated", "pairs_one_pinned",
                  "pairs_skipped_both_pinned", "pushes", "pushes_cap_bound"):
            stats[k] += s[k]
        for _who, moved in s["moved"].items():
            stats["moves"].append(round(moved, 4))
            stats["moved_by_class"]["off" if _who.startswith("O-") else "def"] += 1
        stats["residual"] += len(s["residual"])
        for a, b, gap in s["residual"]:
            stats["residual_worst"] = max(stats["residual_worst"], gap)
            cls = "def-def" if a.startswith("D-") and b.startswith("D-") else (
                "off-off" if a.startswith("O-") and b.startswith("O-") else "def-off")
            stats["residual_by_class"][cls] += 1

        for key, entry in entries.items():
            if key not in new or key in pinned:
                continue
            entry["coords"] = {"x": new[key]["x"], "y": new[key]["y"]}
            if key.startswith("O-"):
                written_off.add(id(entry))
        for key in entries:
            if key.startswith("O-"):
                _resync_start_end(by_pid.get(off_pid[key]))
    return stats
