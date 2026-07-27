"""Universal pass-contest primitive (Dynamic_HCT_Turns.md §14).

Resolves whether an in-flight pass is contested by a defender — completed cleanly,
intercepted (STEAL), or batted out of bounds. Geometry-first and **pure**: it takes
plain coord dicts + lightweight defender descriptors (no ``Player`` / ``game``
dependency), so it is reusable from any pass path (HCT first, then HCO / inbounds /
Rim Runner) and trivially unit-testable.

Model (true to the sim — see §14.0):
  Stage 1 — hybrid geometry gate (per defender): he must be *in the lane*
    (perpendicular distance to the passer→receiver segment ≤ ``PASS_LANE_DIST``)
    AND *reachable in time* (the D21 arrival-time walk: the first segment point he
    can reach no later than the ball, minus an IQ anticipation head-start).
  Stage 2 — passer safety gate (offense counter): ``pass_score = (PS·0.6 + CH·0.2 +
    IQ·0.2)×rand(1,6)``; if it clears ``PASS_SAFETY_BASE − offense_modifier`` the pass
    is safe (no interception in play). ``offense_modifier`` is turn-type based (see
    ``resolve_offense_pass_modifier``).
  Stage 3 — interception band: ``intercept_score = (OD·0.6 + CH·0.2 + IQ·0.2)×rand(1,6)``
    vs the fixed tiers → COMPLETE / INTERCEPT / BAT_OOB.

The contester (when several are eligible) is the one whose contact occurs **earliest
along the flight** (first hand on the ball).
"""

from __future__ import annotations

import math
from BackEnd.utils.sim_random import sim_rng as random
from typing import Any, Dict, Iterable, List, Optional, Tuple

from BackEnd.utils.team_attr_scale import core8_gameplay

# --- Tunable knobs (§14.6) ---------------------------------------------------
# Spatial lane width: a defender farther than this (perpendicular) from the pass
# line is not "in the lane" and cannot contest, however fast he is.
PASS_LANE_DIST = 8.0
# Anticipation: IQ buys up to this many game-seconds of reaction head-start in the
# arrival-time race (scaled linearly from IQ/100).
PASS_IQ_ANTICIPATION_MAX_SEC = 0.15
# Interception composite weights (defender — hands/awareness, not foot-speed).
PASS_INTERCEPT_OD_WEIGHT = 0.6
PASS_INTERCEPT_CH_WEIGHT = 0.2
PASS_INTERCEPT_IQ_WEIGHT = 0.2
# Passer "safe pass" composite weights (offense — passing skill).
PASS_SAFETY_PS_WEIGHT = 0.6
PASS_SAFETY_CH_WEIGHT = 0.2
PASS_SAFETY_IQ_WEIGHT = 0.2
# Random multiplier band on the composites (inclusive).
PASS_INTERCEPT_ROLL_MIN = 1
PASS_INTERCEPT_ROLL_MAX = 6
# Passer safety gate base: if the passer's pass_score > (BASE − offense_modifier),
# no interception is in play (a good passer evades the lurking defender).
PASS_SAFETY_BASE = 200.0
# Deflection threshold: intercept_score > tier_mid → the pass is deflected (then the split roll below
# decides INTERCEPT vs BAT_OOB). TIER_HI is retained for back-compat callers but no longer used.
PASS_INTERCEPT_TIER_HI = 250.0
PASS_INTERCEPT_TIER_MID = 200.0
# INTERCEPT-vs-BAT_OOB split (shared HCO/HCT/FCP). On a deflection the defender's ball skill decides
# the KIND: roll rand(1, PASS_DEFLECT_KIND_D); under (CH + IQ) → clean INTERCEPT (steal), else BAT_OOB
# (knocked out, offense retains). This is the dial for the INTERCEPT/BAT_OOB RATIO, independent of how
# OFTEN passes are deflected (that's the safety base + tier_mid). ↑ D = a smaller CH+IQ share clears
# the roll = MORE BAT_OOB; ↓ D = MORE clean INTERCEPTs. Good defenders (high CH+IQ) skew toward INTERCEPT.
PASS_DEFLECT_KIND_D = 200

# Turn-type → offense team_attributes key feeding the passer safety gate's
# ``offense_modifier`` (a higher offense rating lowers the bar the passer must clear,
# so good offenses complete more passes). Unlisted turn types fall back to offense
# efficiency.
OFFENSE_PASS_MODIFIER_KEYS = {
    "HCO": "offensive_efficiency",
    "HCT": "pt_opp_modifier",
    "FAST_BREAK": "fb_efficiency",
}
DEFAULT_OFFENSE_PASS_MODIFIER_KEY = "offensive_efficiency"

COMPLETE = "COMPLETE"
INTERCEPT = "INTERCEPT"
BAT_OOB = "BAT_OOB"

# Court boundaries (grid space): sidelines y=0/50, baselines x=0/100.
COURT_X_MIN, COURT_X_MAX = 0.0, 100.0
COURT_Y_MIN, COURT_Y_MAX = 0.0, 50.0


def nearest_oob_point(xy):
    """Universal (HCO/HCT/FCP): the nearest court boundary point — sideline OR baseline — to ``xy``,
    where a batted-out-of-bounds ball exits. Returns ``{"x", "y"}`` on the closest of the four edges
    (keeps the other coordinate, so the ball flies straight out the near edge)."""
    x = float(xy.get("x", 0.0)); y = float(xy.get("y", 0.0))
    d_left, d_right = x - COURT_X_MIN, COURT_X_MAX - x
    d_bottom, d_top = y - COURT_Y_MIN, COURT_Y_MAX - y
    m = min(d_left, d_right, d_bottom, d_top)
    if m == d_top:
        return {"x": x, "y": COURT_Y_MAX}
    if m == d_bottom:
        return {"x": x, "y": COURT_Y_MIN}
    if m == d_right:
        return {"x": COURT_X_MAX, "y": y}
    return {"x": COURT_X_MIN, "y": y}


def _euclid(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    return math.hypot(float(b["x"]) - float(a["x"]), float(b["y"]) - float(a["y"]))


def _project_onto_segment(
    p: Dict[str, Any], a: Dict[str, Any], b: Dict[str, Any]
) -> Tuple[float, Dict[str, float], float]:
    """Project ``p`` onto segment a→b. Returns ``(t, proj_point, perp_dist)`` where
    ``t`` is the clamped [0,1] position along the segment."""
    ax, ay = float(a["x"]), float(a["y"])
    bx, by = float(b["x"]), float(b["y"])
    px, py = float(p["x"]), float(p["y"])
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-9:
        return 0.0, {"x": ax, "y": ay}, math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    proj = {"x": ax + t * dx, "y": ay + t * dy}
    perp = math.hypot(px - proj["x"], py - proj["y"])
    return t, proj, perp


def defenders_in_lane(passer_xy, receiver_xy, def_coords, lane_dist,
                      exclude=None, t_min=0.1, t_max=0.9):
    """Defender ids sitting in the passer→receiver passing lane: perpendicular distance to the
    segment <= ``lane_dist`` AND projection in the middle band (``t_min``..``t_max``). The band
    excludes endpoint defenders — the passer's on-ball man (t≈0) and the receiver's man (t≈1) —
    so only a true lane-sitting help defender counts. ``exclude``: ids to skip outright.

    Pure geometry; used for the HCO hot-read "truly open" decision gate (and reusable for any
    lane-clearance check). ``def_coords`` maps id → {x, y}."""
    exclude = exclude or set()
    out = set()
    for did, xy in (def_coords or {}).items():
        if did in exclude or not xy:
            continue
        t, _proj, perp = _project_onto_segment(xy, passer_xy, receiver_xy)
        if t_min <= t <= t_max and perp <= lane_dist:
            out.add(did)
    return out


def min_perp_in_lane(passer_xy, receiver_xy, def_coords, t_min=0.1, t_max=1.0, exclude=None):
    """Smallest perpendicular distance to the passer→receiver segment among defenders whose
    projection falls in the band [t_min, t_max]. Returns None if none qualify. Pure geometry, no
    distance cap — for diagnostics (how close is the nearest potential interceptor?)."""
    exclude = exclude or set()
    best = None
    for did, xy in (def_coords or {}).items():
        if did in exclude or not xy:
            continue
        t, _proj, perp = _project_onto_segment(xy, passer_xy, receiver_xy)
        if t_min <= t <= t_max and (best is None or perp < best):
            best = perp
    return best


def _iq_headstart(iq: float) -> float:
    return max(0.0, min(1.0, float(iq) / 100.0)) * PASS_IQ_ANTICIPATION_MAX_SEC


def _earliest_contact(
    defender_xy: Dict[str, Any],
    rate: float,
    passer_xy: Dict[str, Any],
    receiver_xy: Dict[str, Any],
    seg_len: float,
    ball_speed: float,
    iq_headstart: float,
) -> Optional[Tuple[float, Dict[str, float]]]:
    """D21 arrival-time walk. Returns ``(s, contact_point)`` for the first sampled
    point the defender reaches no later than the ball (within his head-start), or
    ``None`` if he can never beat the ball to the line."""
    if rate <= 0 or ball_speed <= 0 or seg_len <= 0:
        return None
    ax, ay = float(passer_xy["x"]), float(passer_xy["y"])
    bx, by = float(receiver_xy["x"]), float(receiver_xy["y"])
    steps = max(1, int(round(seg_len)))
    for i in range(steps + 1):
        s = i / steps
        point = {"x": ax + (bx - ax) * s, "y": ay + (by - ay) * s}
        t_ball = (seg_len * s) / ball_speed
        t_def = _euclid(defender_xy, point) / rate - iq_headstart
        if t_def <= t_ball:
            return s, point
    return None


def _intercept_score(defender: Dict[str, Any], rng: Any, add: float = 0.0) -> float:
    od = float(defender.get("OD", 0) or 0)
    ch = float(defender.get("CH", 0) or 0)
    iq = float(defender.get("IQ", 0) or 0)
    composite = (
        od * PASS_INTERCEPT_OD_WEIGHT
        + ch * PASS_INTERCEPT_CH_WEIGHT
        + iq * PASS_INTERCEPT_IQ_WEIGHT
        + add  # team-level modifier (e.g. defensive_efficiency) added before the roll
    )
    return composite * rng.randint(PASS_INTERCEPT_ROLL_MIN, PASS_INTERCEPT_ROLL_MAX)


def _pass_score(passer: Dict[str, Any], rng: Any, add: float = 0.0) -> float:
    """The passer's 'safe pass' score (offense counter to the contest)."""
    ps = float(passer.get("PS", 0) or 0)
    ch = float(passer.get("CH", 0) or 0)
    iq = float(passer.get("IQ", 0) or 0)
    composite = (
        ps * PASS_SAFETY_PS_WEIGHT
        + ch * PASS_SAFETY_CH_WEIGHT
        + iq * PASS_SAFETY_IQ_WEIGHT
        + add  # team-level modifier (e.g. offensive_efficiency) added before the roll
    )
    return composite * rng.randint(PASS_INTERCEPT_ROLL_MIN, PASS_INTERCEPT_ROLL_MAX)


def resolve_offense_pass_modifier(turn_type: Any, off_team_attributes: Any) -> float:
    """Resolve the passer-safety-gate ``offense_modifier`` from the turn type and the
    offense's ``team_attributes`` (HCO→offensive_efficiency, HCT→pt_opp_modifier,
    FAST_BREAK→fb_efficiency, else→offensive_efficiency)."""
    key = OFFENSE_PASS_MODIFIER_KEYS.get(turn_type, DEFAULT_OFFENSE_PASS_MODIFIER_KEY)
    try:
        return core8_gameplay((off_team_attributes or {}).get(key, 0))
    except (TypeError, ValueError, AttributeError):
        return 0.0


def find_pass_contester(
    passer_xy: Dict[str, Any],
    receiver_xy: Dict[str, Any],
    ball_speed: float,
    defenders: Iterable[Dict[str, Any]],
    lane_dist: float = PASS_LANE_DIST,
) -> Optional[Dict[str, Any]]:
    """Stage 1 (pure geometry). Return the eligible defender whose contact is earliest
    along the flight, as ``{"defender", "contact_point", "s"}``, or ``None``.

    Each defender descriptor is a dict: ``{"id", "xy", "rate", "OD", "AG", "IQ"}``.
    ``lane_dist`` (perpendicular spatial gate) defaults to ``PASS_LANE_DIST`` (8.0, HCT/FCP);
    HCO passes a tighter value.
    """
    seg_len = _euclid(passer_xy, receiver_xy)
    if seg_len <= 0 or ball_speed <= 0:
        return None

    best: Optional[Dict[str, Any]] = None
    for d in defenders:
        xy = d.get("xy")
        if not isinstance(xy, dict):
            continue
        _t, _proj, perp = _project_onto_segment(xy, passer_xy, receiver_xy)
        if perp > lane_dist:  # spatial gate
            continue
        hit = _earliest_contact(
            xy, float(d.get("rate", 0) or 0), passer_xy, receiver_xy,
            seg_len, ball_speed, _iq_headstart(d.get("IQ", 0)),
        )
        if hit is None:  # temporal gate
            continue
        s, contact = hit
        if best is None or s < best["s"]:
            best = {"defender": d, "contact_point": contact, "s": s}
    return best


def resolve_pass_contest(
    passer: Dict[str, Any],
    receiver_xy: Dict[str, Any],
    ball_speed: float,
    defenders: Iterable[Dict[str, Any]],
    *,
    offense_modifier_g: float = 0.0,   # CONTRACT: already core8_gameplay()-normalized (±10 scale)
    defense_modifier_g: float = 0.0,   # CONTRACT: already core8_gameplay()-normalized (±10 scale)
    lane_dist: float = PASS_LANE_DIST,
    rng: Any = random,
    safety_base: float = None,
    tier_hi: float = None,
    tier_mid: float = None,
    efficiency_in_composite: bool = False,
) -> Dict[str, Any]:
    """Resolve a pass contest (§14). Returns
    ``{"outcome", "deflector", "contact_point"}`` where ``outcome`` is one of
    ``COMPLETE`` / ``INTERCEPT`` / ``BAT_OOB``. ``deflector`` is the contesting
    defender's id (``None`` on a clean completion).

    ``passer`` is a descriptor ``{"xy", "PS", "CH", "IQ"}``. Resolution order:
      1. Geometry — if no defender is eligible (in the lane + reachable), COMPLETE.
      2. Passer safety gate — ``pass_score = (PS·0.6 + CH·0.2 + IQ·0.2)×rand(1,6)``;
         if it exceeds ``PASS_SAFETY_BASE − offense_modifier_g`` the pass is safe
         (COMPLETE, no interception in play). A higher ``offense_modifier_g`` (the
         turn-type offense rating — see ``resolve_offense_pass_modifier``) lowers the
         bar, so good offenses complete more passes.

    ⚠️ CONTRACT: ``offense_modifier_g`` / ``defense_modifier_g`` MUST arrive already
    ``core8_gameplay()``-normalized (±10 scale). Callers resolve them via
    ``resolve_offense_pass_modifier`` (which wraps) and the ``_hco_def_efficiency``
    stash (wrapped at stash time). Do NOT pass a raw ±20 team attribute here — the
    ``_g`` suffix marks the normalized contract.
      3. Interception band — ``intercept_score = (OD·0.6 + CH·0.2 + IQ·0.2)×rand(1,6)``.
         ``score ≤ tier_mid`` → COMPLETE. Over it → the pass is DEFLECTED, and the defender's
         ball skill splits the kind: ``rand(1, PASS_DEFLECT_KIND_D) < (CH + IQ)`` → INTERCEPT, else BAT_OOB.
         (Replaced the old hi/mid two-tier split, whose narrow band the quantized score skipped →
         BAT_OOB was unreachable. ``tier_hi`` is now unused.)

    ``rng`` is injectable for tests (gate roll, then the band roll, then the split roll on a deflect).
    """
    passer_xy = passer.get("xy") if isinstance(passer, dict) else None
    if not isinstance(passer_xy, dict):
        return {"outcome": COMPLETE, "deflector": None, "contact_point": None, "stage": "no_passer_xy"}

    contester = find_pass_contester(passer_xy, receiver_xy, ball_speed, defenders, lane_dist=lane_dist)
    if contester is None:
        return {"outcome": COMPLETE, "deflector": None, "contact_point": None, "stage": "no_contester"}

    # Per-call tier overrides (HCO passes a tighter mid; HCT/FCP use the shared default). Only
    # tier_mid is the deflection threshold now; tier_hi is accepted for back-compat but unused.
    _base = PASS_SAFETY_BASE if safety_base is None else safety_base
    _mid = PASS_INTERCEPT_TIER_MID if tier_mid is None else tier_mid
    # When efficiency_in_composite (HCO): team efficiency is added to the composite AND subtracted
    # from the bar/tiers (doubly favors the stronger team). HCT/FCP leave it off → old behavior.
    _pass_add = offense_modifier_g if efficiency_in_composite else 0.0
    _int_add = defense_modifier_g if efficiency_in_composite else 0.0

    # Passer safety gate (3a) — a good passer evades the lurking defender entirely.
    if _pass_score(passer, rng, add=_pass_add) > (_base - offense_modifier_g):
        return {"outcome": COMPLETE, "deflector": None, "contact_point": None, "stage": "passer_safe"}

    # Interceptor skill band (3b). A SINGLE deflection threshold (tier_mid, efficiency-adjusted):
    # score at/under it → COMPLETE. Over it → the pass is DEFLECTED, and the defender's ball skill
    # decides the kind: roll d200 vs (CH + IQ) — under → clean INTERCEPT, else BAT_OOB. This replaces
    # the old hi/mid two-tier split: the (mid, hi] BAT_OOB band was narrower than the score's
    # quantization step (composite × randint(1,6), step ≈ composite ≈ 50-100+), so consecutive scores
    # straddled it → BAT_OOB was effectively unreachable. tier_hi is no longer used.
    defender = contester["defender"]
    score = _intercept_score(defender, rng, add=_int_add)
    if score <= (_mid - _int_add):
        return {"outcome": COMPLETE, "deflector": None, "contact_point": None, "stage": "band_complete"}
    ch = float(defender.get("CH", 0) or 0)
    iq = float(defender.get("IQ", 0) or 0)
    if rng.randint(1, PASS_DEFLECT_KIND_D) < (ch + iq):
        outcome, stage = INTERCEPT, "intercept"
    else:
        outcome, stage = BAT_OOB, "bat_oob"

    return {
        "outcome": outcome,
        "deflector": defender.get("id"),
        "contact_point": contester["contact_point"],
        "stage": stage,
    }
