"""Shape-movement decomposition for development validation.

Raw cosine retention conflates two different coaching intents:

- **Along-shape (sharpening)** — movement parallel to the player's starting
  deviation from flat. "More of the same" / reinforce strengths.
- **Across-shape (conversion)** — the orthogonal residual. "Change who he is."

A coach who specialises a player's top three moves shape just as surely as a
converter; cosine alone cannot tell them apart. Report both.
"""
from __future__ import annotations

import math
from typing import Sequence


def _norm(v: Sequence[float]) -> float:
    return math.sqrt(sum(x * x for x in v)) or 0.0


def decompose_shape_delta(
    s0: Sequence[float], s1: Sequence[float]
) -> dict[str, float]:
    """Decompose s1 − s0 into along-shape (signed) and across-shape (L2).

    Identity axis = starting shape's deviation from flat (``s0 − 1`` on a
    unit-mean vector). Positive along = further specialization in the same
    pattern; across = magnitude of the orthogonal component.
    """
    if len(s0) != len(s1):
        raise ValueError("shape vectors must match length")
    d = [a - b for a, b in zip(s1, s0)]
    # Unit-mean shapes: flat = all ones. Deviation from flat is the identity axis.
    u = [x - 1.0 for x in s0]
    nu = _norm(u)
    nd = _norm(d)
    if nu < 1e-12:
        return {
            "along": 0.0,
            "across": nd,
            "delta_l2": nd,
            "along_share": 0.0,
            "across_share": 1.0 if nd > 1e-12 else 0.0,
        }
    u_hat = [x / nu for x in u]
    along = sum(di * ui for di, ui in zip(d, u_hat))
    across_vec = [di - along * ui for di, ui in zip(d, u_hat)]
    across = _norm(across_vec)
    denom = abs(along) + across
    return {
        "along": along,
        "across": across,
        "delta_l2": nd,
        "along_share": (abs(along) / denom) if denom > 1e-12 else 0.0,
        "across_share": (across / denom) if denom > 1e-12 else 0.0,
    }
