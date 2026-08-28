"""Loose-ball resolution — a deflected pass that stays in play.

WHAT THIS IS
------------
A defender who deflects a pass (``BAT_OOB`` from ``pass_contest``) used to have
exactly one outcome: the ball went out of bounds and the offense kept it on a side
inbound. That made every successful deflection a dead ball, which is neither how
basketball looks nor a meaningful reward for gambling in the passing lane.

Half of those deflections now stay in play as a LOOSE BALL: the ball caroms to a
random spot near the contact point and both teams scramble for it.

    deflection (BAT_OOB)
      ├─ 50% → out of bounds, offense retains  (unchanged, `_finalize_hco_pass_bat_oob`)
      └─ 50% → loose ball
                ├─ bounce spot lands off the court → treated as out of bounds (above)
                └─ bounce spot is in play → scramble
                      ├─ offense recovers → possession continues, shot clock NOT reset
                      └─ defense recovers → turnover (passer) + steal (recoverer)

HOW THE WINNER IS PICKED
------------------------
Deliberately modelled on rebounding (``select_rebounder_by_score``) — same shape,
different inputs, because scrambling for a loose ball rewards different qualities
than boxing out for a carom:

    score = ((0.3·AG + 0.3·IQ + 0.4·CH) + fight) × rand(1, 6)
    score × 1 / (1 + distance / LOOSE_BALL_DISTANCE_SCALE)

Two deliberate departures from the rebound formula:

* **fight is added BEFORE the die**, not after. As a flat addend on a composite
  averaging ~175 it would be a ±5.7% nudge — smaller than one pip of the die, i.e.
  inert. Inside the parenthesis it scales with the roll and becomes a real lever.
  ``fight`` is core-8, so it reads through ``core8_gameplay()`` per THE RULE in
  ``team_attr_scale`` (stored ±20 → gameplay ±10).
* **the distance discount is twice as steep as rebounding's**
  (``LOOSE_BALL_DISTANCE_SCALE`` 4.0 vs ``REBOUND_DISTANCE_SCALE`` 8.0), so the
  random bounce spot — not the die — is the main driver of who ends up with it.

Measured over 150k simulated scrambles, the closest eligible player wins 49.6% of
loose balls at rebound scale and 54.2% at 4.0. The ``rand(1, 6)`` die is a 6× swing
and dominates either way; if geo needs to be more decisive than that, NARROW THE DIE
(``LOOSE_BALL_ROLL_MIN``/``MAX``) — it is a far stronger knob than the scale.

WHAT LIVES ELSEWHERE
--------------------
This module is pure: coords in, winner out, no game mutation and no step building.

* the 50/50 split and the deflection itself — ``pass_contest.py``
* turn results (steal vs. possession-continues) — ``phase_resolution.py``
* the scramble animation — ``skeleton_step_emitter.append_hco_loose_ball_trajectory``
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import PASS_GRID_SPOTS_PER_GAME_SECOND
from BackEnd.utils.sim_random import announcement_rng, sim_rng as random
from BackEnd.utils.team_attr_scale import core8_gameplay
from BackEnd.engine.pass_contest import (
    COURT_X_MAX,
    COURT_X_MIN,
    COURT_Y_MAX,
    COURT_Y_MIN,
)

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Share of deflections (`BAT_OOB`) that stay in play instead of going out of bounds.
# ↑ = more scrambles, fewer dead balls. The realised loose-ball rate is LOWER than
# this, because a bounce spot that lands off the court reverts to out of bounds.
LOOSE_BALL_FROM_DEFLECTION_PCT = 50

# The carom: a uniformly random direction, and a uniformly random distance in this
# band, measured from the deflection contact point. Widen for wilder scrambles.
LOOSE_BALL_BOUNCE_MIN_DIST = 4.0
LOOSE_BALL_BOUNCE_MAX_DIST = 12.0

# Only players within this Euclidean distance of the bounce spot may recover it.
# Everyone else is too far to be part of the play. If NOBODY is inside it, the
# radius expands (see `select_loose_ball_recoverer`) rather than failing.
LOOSE_BALL_CANDIDATE_RADIUS = 12.0

# Distance discount: score × 1 / (1 + d / SCALE). LOWER = distance matters MORE.
# 4.0 is deliberately half of REBOUND_DISTANCE_SCALE (8.0) — see the module docstring.
LOOSE_BALL_DISTANCE_SCALE = 4.0

# Ability composite. Agility to get there, IQ to read the carom, and chemistry —
# the heaviest term — for coming up with it in a crowd.
LOOSE_BALL_AG_WEIGHT = 0.3
LOOSE_BALL_IQ_WEIGHT = 0.3
LOOSE_BALL_CH_WEIGHT = 0.4

# The die. Matches rebounding's rand(1, 6). This is the DOMINANT source of variance
# (a 6× swing); narrowing it is the strongest way to make position and ability
# decide loose balls. See the module docstring for measured effects.
LOOSE_BALL_ROLL_MIN = 1
LOOSE_BALL_ROLL_MAX = 6

# Offense recovers with less than this on the shot clock → no time to run anything,
# so route to the forced-shot scenario instead of a fresh HCO possession.
LOOSE_BALL_FORCED_SHOT_CLOCK = 6.0

# How fast the ball caroms from contact to its resting spot, in grid spots per game
# second. Seeded from the pass-in-air rate so a deflected ball reads at pass speed —
# derived rather than a copied literal, so the two can never silently diverge. Still
# independently tunable: a carom is not a pass, and may want its own pace later.
LOOSE_BALL_BOUNCE_GRID_PER_GAME_SEC = float(PASS_GRID_SPOTS_PER_GAME_SECOND)

# Announcer call fired the instant the ball is knocked loose. One is chosen at random
# per loose ball. Both must be listed in the frontend's `GAMEPLAY_SFX_FILES` manifest
# or `playGameSfx` finds no preloaded pool and silently warns instead of playing.
LOOSE_BALL_SFX_FILES = ("braddock-loose-ball-v2.mp3", "sammy-loose-ball-v3.mp3")
LOOSE_BALL_SFX_VOLUME = 0.7

# Pace the scrambling players converge at. `sprint` — everyone is going full tilt.
LOOSE_BALL_CONVERGE_ARCHETYPE = "sprint"


def _euclid(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    return math.hypot(float(b["x"]) - float(a["x"]), float(b["y"]) - float(a["y"]))


def deflection_stays_in_play(rng=None) -> bool:
    """Does this deflection stay in play (loose ball) or go out of bounds?

    One draw, taken for EVERY deflection so the gameplay stream advances
    identically whichever way it lands.
    """
    _rng = rng or random
    return _rng.randint(1, 100) <= LOOSE_BALL_FROM_DEFLECTION_PCT


def is_in_bounds(xy: Dict[str, Any]) -> bool:
    """Is this point on the court? Boundary-inclusive — `nearest_oob_point` puts an
    out-of-bounds ball exactly ON an edge, so a point on the line is still in play."""
    try:
        x, y = float(xy["x"]), float(xy["y"])
    except (TypeError, ValueError, KeyError):
        return False
    return COURT_X_MIN <= x <= COURT_X_MAX and COURT_Y_MIN <= y <= COURT_Y_MAX


def roll_bounce_spot(contact: Dict[str, Any], rng=None) -> Dict[str, float]:
    """Where the deflected ball comes to rest: a uniformly random direction and a
    uniformly random distance in [MIN, MAX] from the contact point.

    Uniform in (angle, radius) rather than uniform over the annulus by area — that
    concentrates slightly toward the inner edge, which is the intended reading of
    "any direction and any distance in that range".

    MAY RETURN AN OUT-OF-BOUNDS POINT. That is deliberate: a deflection near the
    sideline SHOULD often sail out. Callers check `is_in_bounds` and fall back to
    the batted-out-of-bounds path.
    """
    _rng = rng or random
    angle = _rng.uniform(0.0, 2.0 * math.pi)
    dist = _rng.uniform(LOOSE_BALL_BOUNCE_MIN_DIST, LOOSE_BALL_BOUNCE_MAX_DIST)
    return {
        "x": float(contact["x"]) + dist * math.cos(angle),
        "y": float(contact["y"]) + dist * math.sin(angle),
    }


def loose_ball_ability(player: Any) -> float:
    """The attribute half of the score: 0.3·AG + 0.3·IQ + 0.4·CH. No die, no team."""
    attrs = getattr(player, "attributes", None) or {}

    def _a(key: str) -> float:
        try:
            return float(attrs.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    return (
        LOOSE_BALL_AG_WEIGHT * _a("AG")
        + LOOSE_BALL_IQ_WEIGHT * _a("IQ")
        + LOOSE_BALL_CH_WEIGHT * _a("CH")
    )


def _team_fight(team: Any) -> float:
    """Team fight as a GAMEPLAY value. Core-8 → `core8_gameplay` (stored ±20 → ±10)."""
    try:
        raw = (getattr(team, "team_attributes", None) or {}).get("fight", 0)
    except (AttributeError, TypeError):
        return 0.0
    return float(core8_gameplay(raw))


def loose_ball_score(player: Any, team: Any, distance: float, rng=None) -> float:
    """One player's contest score. Fight is added INSIDE the die (see the docstring),
    then the whole thing is discounted by distance to the ball."""
    _rng = rng or random
    raw = (loose_ball_ability(player) + _team_fight(team)) * _rng.randint(
        LOOSE_BALL_ROLL_MIN, LOOSE_BALL_ROLL_MAX
    )
    scale = float(LOOSE_BALL_DISTANCE_SCALE) or 1.0
    return raw * (1.0 / (1.0 + max(0.0, float(distance)) / scale))


def select_loose_ball_recoverer(
    *,
    bounce_spot: Dict[str, Any],
    off_entries: List[Tuple[str, Any, Dict[str, Any]]],
    def_entries: List[Tuple[str, Any, Dict[str, Any]]],
    off_team: Any,
    def_team: Any,
    rng=None,
) -> Optional[Dict[str, Any]]:
    """Pick who comes up with the loose ball.

    ``off_entries`` / ``def_entries`` are ``(position, player, coords)`` triples —
    the caller owns eligibility and supplies RENDERED coords (what the animator
    draws), so the scramble is judged on the same geometry the viewer sees.

    Every player inside ``LOOSE_BALL_CANDIDATE_RADIUS`` of the bounce spot competes.
    If that leaves nobody, the radius grows until someone qualifies — a loose ball
    on the floor must always be recovered by SOMEONE, so an empty pool can never be
    a valid answer. Ties break at random, as specified: no rebound-style
    modifier/MO/chemistry ladder.

    Returns ``{position, player, team, is_offense, distance, score}`` or None when
    there are no players at all.
    """
    _rng = rng or random

    scored: List[Dict[str, Any]] = []
    for is_off, entries, team in (
        (True, off_entries, off_team),
        (False, def_entries, def_team),
    ):
        for pos, player, coords in entries or []:
            if player is None or not coords:
                continue
            try:
                xy = {"x": float(coords["x"]), "y": float(coords["y"])}
            except (TypeError, ValueError, KeyError):
                continue
            scored.append({
                "position": pos,
                "player": player,
                "team": team,
                "is_offense": is_off,
                "distance": _euclid(xy, bounce_spot),
            })

    if not scored:
        return None

    # Widen until somebody is in range. A loose ball always gets picked up.
    radius = float(LOOSE_BALL_CANDIDATE_RADIUS)
    pool = [e for e in scored if e["distance"] <= radius]
    while not pool:
        radius += 5.0
        pool = [e for e in scored if e["distance"] <= radius]

    for entry in pool:
        entry["score"] = loose_ball_score(
            entry["player"], entry["team"], entry["distance"], rng=_rng)

    best = max(e["score"] for e in pool)
    tied = [e for e in pool if e["score"] == best]
    return tied[0] if len(tied) == 1 else _rng.choice(tied)


def scramble_timing(
    *,
    contact: Dict[str, Any],
    bounce_spot: Dict[str, Any],
    winner_coords: Dict[str, Any],
    winner_rate_grid_per_game_sec: float,
) -> Tuple[float, float]:
    """``(bounce_t, recover_t)`` in game seconds for the two scramble steps.

    ``bounce_t`` is the ball's carom from contact to its resting spot.
    ``recover_t`` is whatever is LEFT of the winner's run once the ball has landed —
    the scramble is over when the ball has come to rest AND the winner has reached
    it, so the total is ``max(bounce_t, winner_travel)``. A winner already standing
    on the spot gets ``recover_t`` 0.0 and the play resolves the moment it lands.
    """
    bounce_dist = _euclid(contact, bounce_spot)
    bounce_t = bounce_dist / max(1e-6, float(LOOSE_BALL_BOUNCE_GRID_PER_GAME_SEC))
    travel = _euclid(winner_coords, bounce_spot) / max(
        1e-6, float(winner_rate_grid_per_game_sec))
    return float(bounce_t), float(max(0.0, travel - bounce_t))


def pick_loose_ball_sfx() -> str:
    """Which announcer calls the loose ball. Backend-chosen (UESS: the frontend
    renders, it does not decide).

    Drawn from ``announcement_rng``, NOT the gameplay stream. This is presentation:
    adding or removing a clip must never shift a basketball outcome. (The older
    hot-read coach VO draws from ``sim_rng`` — that predates the split and is
    currently disabled; do not copy it.)
    """
    return announcement_rng.choice(LOOSE_BALL_SFX_FILES)
