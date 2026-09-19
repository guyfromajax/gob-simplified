"""Where a player crashes the boards on a shot attempt.

A crash destination is a function of the **shot**, never of the **outcome**. At the
moment of release nobody on the floor knows whether it goes in, where it bounces, or
whether a whistle is coming, so one model serves every shot attempt - make, miss,
foul, no foul - because those are indistinguishable when players start crashing.

Model A: sample the destination from the rebound distribution *for that shot*
(``_bounce_variance_for_shot_distance``, keyed on shooter-to-rim distance), drawn
**independently of the ball's own draw**. Two independent draws from one distribution
land in different places, which is exactly the point: crashers go where a miss from
that shot is *likely* to go, and are individually wrong about as often as they are
right.

WHY THIS FUNCTION TAKES WHAT IT TAKES - read before changing the signature.
    ``bounce_spot`` is computed at ``shot_manager.py:2465``, eighty-five lines before
    the HCO crash destinations are authored at ``:2550``, and ``result["ball_bounce_x"]``
    is already populated by then. It is sitting in scope. **It must not be read.**
    A crasher who knows where the ball will land is clairvoyant: everyone converges on
    one point and rebounding collapses into a deterministic race to a known spot.

    So this function is deliberately given ONLY the shot: the shooter's position and
    which rim he is attacking. It does not receive ``result``, ``bounce_spot``, the
    make/miss flag, the calling frame, or anything else that could carry the outcome.
    That is enforced by ``tests/test_crash_destination.py``, which fails if the
    signature grows an outcome-bearing parameter. Do not "improve" this by passing the
    bounce in - the divergence between the two draws IS the model.

``GOB_CRASH_SHOT_AWARE`` gates it, default OFF.
"""

from __future__ import annotations

import os
from typing import Dict

from BackEnd.utils.sim_random import sim_rng as random
from BackEnd.utils.shared import _bounce_variance_for_shot_distance

# How far in from each edge a crasher may be placed. The court is 0-100 by 0-50;
# these keep a crasher off the baseline and out of bounds without pulling him so far
# in that a genuine long rebound position becomes unreachable.
COURT_X_MIN, COURT_X_MAX = 3.0, 97.0
COURT_Y_MIN, COURT_Y_MAX = 3.0, 47.0

#: Fraction of the ball's own spread that crashers cover. 1.0 = crashers are drawn
#: from exactly the distribution the ball is drawn from. Below 1.0 they hedge toward
#: the rim - covering the likely area rather than the full range the ball can reach,
#: which is what real crashers do.
#:
#: 0.7 chosen by Jamie from reports/crash-model-a-visual-2026-09-19.md: crashers go
#: where a miss from that shot PROBABLY goes rather than covering its full range.
#: Static sampling had it beating 1.0 on every distance band and on both axes
#: (euclidean median to the bounce 4.0 / 4.0 / 7.3 / 9.8 / 11.0 across the bands,
#: against 4.2 / 4.2 / 8.2 / 11.0 / 12.1). Note that scoring crashers on distance to
#: where the ball ENDED UP always favours a tighter model - it is a coverage-versus-
#: accuracy trade, not an optimisation, and 0.7 is the judgement, not the optimum.
#: ``GOB_CRASH_TIGHTNESS=1.0`` keeps the full-spread variant selectable.
DEFAULT_TIGHTNESS = 0.7

RIM_Y = 25.0

# Set by the caller for observability only; never read by the model.
CLAMP_COUNTER: Dict[str, int] = {"calls": 0, "clamped": 0}


def enabled() -> bool:
    """``GOB_CRASH_SHOT_AWARE`` - default OFF."""
    return os.environ.get("GOB_CRASH_SHOT_AWARE", "0") == "1"


def active_tightness() -> float:
    try:
        return float(os.environ.get("GOB_CRASH_TIGHTNESS", DEFAULT_TIGHTNESS))
    except (TypeError, ValueError):
        return DEFAULT_TIGHTNESS


def shot_distance_to_rim(shooter_x: float, shooter_y: float, rim_x: float) -> float:
    return ((float(shooter_x) - float(rim_x)) ** 2 + (float(shooter_y) - RIM_Y) ** 2) ** 0.5


def crash_destination(
    *,
    shooter_x: float,
    shooter_y: float,
    rim_x: float,
    tightness: float = None,
) -> Dict[str, float]:
    """A crasher's destination for a shot taken from ``(shooter_x, shooter_y)``.

    ONLY the shot is an input. See the module docstring for why; the test suite
    enforces it.

    Consumes exactly two ``randint`` draws, the same count as the flat box it
    replaces, so turning the model on is draw-neutral.
    """
    t = active_tightness() if tightness is None else float(tightness)
    t = max(0.0, min(1.0, t))

    distance = shot_distance_to_rim(shooter_x, shooter_y, rim_x)
    x_min, x_max, y_variance = _bounce_variance_for_shot_distance(distance)

    # Narrow the spread toward the rim end. The minimum offset is kept so crashers
    # never stand on top of the rim; only the reach is pulled in.
    x_max_t = int(round(x_min + (x_max - x_min) * t))
    if x_max_t < x_min:
        x_max_t = x_min
    y_var_t = int(round(y_variance * t))
    if y_var_t < 1:
        y_var_t = 1

    # Draw 1 of 2: offset from the rim, along the length of the floor.
    x_offset = random.randint(x_min, x_max_t)
    raw_x = float(rim_x) - x_offset if float(rim_x) > 50.0 else float(rim_x) + x_offset
    # Draw 2 of 2: spread across the floor.
    raw_y = RIM_Y + random.randint(-y_var_t, y_var_t)

    x = max(COURT_X_MIN, min(COURT_X_MAX, raw_x))
    y = max(COURT_Y_MIN, min(COURT_Y_MAX, raw_y))

    CLAMP_COUNTER["calls"] += 1
    if x != raw_x or y != raw_y:
        CLAMP_COUNTER["clamped"] += 1

    return {"x": x, "y": y}
