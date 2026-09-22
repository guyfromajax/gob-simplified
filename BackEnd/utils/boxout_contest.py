"""Box-out contest (Model C): strength decides who ends up in front for the rebound.

Crash destinations already decide who is best placed for a rebound, but nobody
contests that placement. A box-out is the contest: a defender near an offensive
crasher puts a body on him, and the loser gets pushed back off the line to the rim.

**NOT CLAIRVOYANT.** This resolves at destination-authoring time, from the two
players' shot-moment positions, their crash destinations and their ST - and nothing
else. It never sees the bounce, the shot result, the rebounder, or the free-throw
transition, exactly as ``crash_destination`` never does. Everything it needs is known
at the moment the ball leaves the shooter's hand, which is when players actually start
boxing out. ``tests/test_boxout_contest.py`` enforces the signature, and
``crash_destination``'s own allowlist and poison tests are untouched.

SHAPE COPIED FROM ``engine/pass_contest.py``, the house's other two-stage contest:
``find_pass_contester`` does pure geometry to pick who is eligible, then
``resolve_pass_contest`` scores it as ``(weighted attributes) x rand(1,6)``. The same
split is used here - ``find_boxout_pairs`` is pure geometry with no RNG at all, and
``resolve_boxout`` is one weighted-composite ``x rand(1,6)`` roll each. That idiom is everywhere in
this engine (``calculate_rebound_score``, ``calculate_outlet_pass_score``,
``calculate_defender_pressure_score``, the D8 cutoff in ``dynamic_hct._resolve_moment``)
and it is what keeps a big attribute edge a strong tilt rather than a certainty.

``GOB_BOXOUT_CONTEST`` gates it, default OFF.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

from BackEnd.utils.sim_random import sim_rng as _default_rng

#: Pair radius, grid units. DERIVED, not chosen: the pooled median shot-moment distance
#: from a defensive crasher to his nearest offensive crasher is 8.00 (n=8,860, sim,
#: SEED_DEFENSES=1; 7.67 mean at SEED_DEFENSES=0), so half of defensive crashers have a
#: man within it. It also equals ``pass_contest.PASS_LANE_DIST`` (8.0), the engine's
#: existing "close enough to contest" spatial gate - the geometry and the house agree.
#: See reports/boxout-stage1-2026-09-20.md.
BOXOUT_PAIR_RADIUS = 8.0

#: Push-back as a fraction of the loser's REMAINING travel to his destination. DERIVED:
#: paired crashers travel a mean 10.90 units from the shot moment to their destination,
#: and the mean gap between a pair's two destinations is 5.06. Half the remaining travel
#: is 5.45 - so on average the push-back is the size of the gap between the two men,
#: which moves the loser from level with the winner to behind him. That is what losing a
#: box-out means, and it is why the fraction is 0.5 rather than a number picked to hit an
#: OREB target. NOT TUNED.
BOXOUT_PUSHBACK_FRACTION = 0.5

#: The box-out contest's attribute weights. **This is the one place to edit for tuning.**
#: Stage 2 (Jamie's call) replaced pure ST with this composite: boxing out is rebounding
#: instinct as much as strength, so RB carries equal weight to ST, with IQ and CH as the
#: small awareness/competitiveness terms - the same four attributes and the same shape as
#: ``shared.calculate_rebound_score``, at different weights. Weights sum to 1.0, which is
#: the house contract for a composite that gets multiplied by ``rand(1, 6)``
#: (see ``shared.scale_score_to_100``).
BOXOUT_SCORE_WEIGHTS = {"RB": 0.4, "ST": 0.4, "IQ": 0.1, "CH": 0.1}

#: Court clamp, identical to ``crash_destination``'s, so a push-back cannot put a player
#: out of bounds or on the baseline.
COURT_X_MIN, COURT_X_MAX = 3.0, 97.0
COURT_Y_MIN, COURT_Y_MAX = 3.0, 47.0

RIM_Y = 25.0


def enabled() -> bool:
    """``GOB_BOXOUT_CONTEST`` - **default OFF**. Stage 1 is measurement only."""
    return os.environ.get("GOB_BOXOUT_CONTEST", "0") == "1"


def _xy(player: Any) -> Optional[Tuple[float, float]]:
    coords = getattr(player, "coords", None) or {}
    try:
        return float(coords["x"]), float(coords["y"])
    except (KeyError, TypeError, ValueError):
        return None


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def find_boxout_pairs(
    def_players: Iterable[Any],
    off_players: Iterable[Any],
    *,
    radius: float = BOXOUT_PAIR_RADIUS,
) -> List[Tuple[Any, Any, float]]:
    """Stage 1 - pure geometry, NO RNG. ``[(defender, offensive_crasher, distance)]``.

    Each defender takes the nearest unpaired offensive crasher within ``radius``, so a
    player is in at most one pair and there is exactly one contest per pair.

    DETERMINISTIC, including the tiebreak. Defenders are walked in the order the caller
    supplies (the lineup-slot order PG/SG/SF/PF/C), and when two offensive crashers are
    exactly equidistant the one earlier in ``off_players`` wins - also lineup-slot order.
    Both are stable orderings that do not depend on dict iteration or on a draw.
    """
    offs = [(o, _xy(o)) for o in (off_players or []) if o is not None]
    offs = [(o, p) for o, p in offs if p is not None]
    taken = set()
    pairs: List[Tuple[Any, Any, float]] = []
    for d in (def_players or []):
        if d is None:
            continue
        dp = _xy(d)
        if dp is None:
            continue
        best = None
        for idx, (o, op) in enumerate(offs):
            if idx in taken:
                continue
            gap = _dist(dp, op)
            if gap > radius:
                continue
            # strict < keeps the FIRST of two equidistant candidates, i.e. the one
            # earlier in lineup-slot order
            if best is None or gap < best[1]:
                best = (idx, gap)
        if best is None:
            continue
        taken.add(best[0])
        pairs.append((d, offs[best[0]][0], best[1]))
    return pairs


def boxout_score(player: Any, rng: Any = None) -> float:
    """``(0.4*RB + 0.4*ST + 0.1*IQ + 0.1*CH) x rand(1,6)`` - see ``BOXOUT_SCORE_WEIGHTS``.

    Same idiom as ``shared.calculate_rebound_score``, ``calculate_outlet_pass_score`` and
    the D8 cutoff in ``dynamic_hct._resolve_moment``: a weighted attribute composite
    multiplied by one d6. The d6 is what keeps an attribute edge a tilt rather than a
    certainty. Jamie's ``randint(1, 6)`` is untouched - same roll, new multiplicand.

    Stage 1 used pure ST. Stage 2 swapped in the composite above; nothing else about the
    model changed. Measured in reports/boxout-stage2-2026-09-20.md.
    """
    r = _default_rng if rng is None else rng
    attrs = getattr(player, "attributes", None) or {}
    composite = sum(float(attrs.get(k, 0) or 0) * w for k, w in BOXOUT_SCORE_WEIGHTS.items())
    return composite * r.randint(1, 6)


def resolve_boxout(defender: Any, offensive_crasher: Any, *, rng: Any = None) -> Dict[str, Any]:
    """Stage 2 - one roll each. Returns ``{"winner", "loser", "def_score", "off_score"}``.

    **A tie goes to the defender.** That is the stable non-RNG tiebreak: the defender is
    the man initiating the box-out and is by construction between his opponent and the
    rim at that moment, so "nobody wins the leverage" means the position does not change
    hands. It gives the defence a 58.3% floor at equal ST, which is the only place this
    model asserts a structural edge - reported rather than buried.
    """
    d_score = boxout_score(defender, rng=rng)
    o_score = boxout_score(offensive_crasher, rng=rng)
    defender_wins = d_score >= o_score
    return {
        "winner": defender if defender_wins else offensive_crasher,
        "loser": offensive_crasher if defender_wins else defender,
        "defender_wins": defender_wins,
        "def_score": d_score,
        "off_score": o_score,
    }


def push_back(
    destination: Dict[str, float],
    origin: Tuple[float, float],
    rim_x: float,
    *,
    fraction: float = BOXOUT_PUSHBACK_FRACTION,
) -> Dict[str, float]:
    """Move ``destination`` directly AWAY from the rim, along the rim-to-destination line.

    The magnitude is ``fraction`` x the loser's remaining travel (``origin`` to
    ``destination``), so a man who was going a long way loses proportionally more ground
    and a man already in place barely moves. Clamped to the court exactly as
    ``crash_destination`` clamps its own output.

    Returns a NEW dict; the winner's destination is never touched.
    """
    try:
        dx, dy = float(destination["x"]), float(destination["y"])
    except (KeyError, TypeError, ValueError):
        return dict(destination or {})

    travel = _dist(origin, (dx, dy))
    if travel <= 0.0:
        return {"x": dx, "y": dy}

    vx, vy = dx - float(rim_x), dy - RIM_Y
    norm = (vx * vx + vy * vy) ** 0.5
    if norm <= 0.0:
        # standing on the rim: push straight down the floor, away from it
        vx, vy, norm = (1.0 if float(rim_x) < 50.0 else -1.0), 0.0, 1.0

    magnitude = fraction * travel
    nx = dx + (vx / norm) * magnitude
    ny = dy + (vy / norm) * magnitude
    return {
        "x": round(max(COURT_X_MIN, min(COURT_X_MAX, nx)), 2),
        "y": round(max(COURT_Y_MIN, min(COURT_Y_MAX, ny)), 2),
    }
