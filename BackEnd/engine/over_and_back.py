"""
Over-and-back pass geometry and passer awareness (universal primitives).

Used by dynamic FCP/HCT pass branches today; intended for HCO and other pass
paths as they adopt the same pre-pass gate.
"""

from __future__ import annotations

from BackEnd.utils.sim_random import sim_rng as random
from typing import Any, Dict, Optional

OOB_PASS_PS_WEIGHT = 0.8
OOB_PASS_CH_WEIGHT = 0.2

# Half-court line. Once frontcourt is established, an off-ball offender who has
# crossed this line may not drift back over it (his x is ratcheted here).
HALF_COURT_X = 50

# Non-BH offenders still in backcourt after FC is established sprint toward this
# band (home orientation; flipped for away offense in ``cross_half_urgency_target``).
CROSS_HALF_URGENCY_X_MIN = 51
CROSS_HALF_URGENCY_X_MAX = 57
CROSS_HALF_URGENCY_Y_JITTER = 8


def crossed_half_court(x: float, is_away_offense: bool) -> bool:
    return x <= 50 if is_away_offense else x >= 50


def in_backcourt(x: float, is_away_offense: bool) -> bool:
    """True when ``x`` is behind the half-court line for this offense."""
    return not crossed_half_court(x, is_away_offense)


def update_frontcourt_established(
    frontcourt_established: bool,
    xy: Dict[str, Any],
    is_away_offense: bool,
) -> bool:
    """True once the ball has legally established frontcourt this possession.

    Call on the live ball-handler each loop beat and on the pass **catch spot**
    when frontcourt is established by pass receipt (not only by dribble advance).

    "This possession" is a contract on the CALLER, not something this function
    can enforce — it is pure, and returns only what the ``frontcourt_established``
    it was handed and this ``xy`` imply. So the flag has to LIVE for the
    possession: ``dynamic_hct`` carries it on ``game_state`` across turn seams and
    only ``GameManager.reset_frontcourt_state`` clears it. Until 2026-09-06 the
    caller kept it in a ``compute_dynamic_hct_turn`` local that reset every turn,
    and this line over-promised: the 10-second rule re-armed mid-possession, and
    an over-and-back after the establishing turn could not be detected at all.
    """
    if frontcourt_established:
        return True
    return crossed_half_court(float(xy.get("x", 50)), is_away_offense)


def is_over_and_back_pass(
    frontcourt_established: bool,
    receiver_xy: Dict[str, Any],
    is_away_offense: bool,
) -> bool:
    """True when a completed pass to ``receiver_xy`` would be an over-and-back."""
    if not frontcourt_established:
        return False
    return in_backcourt(float(receiver_xy.get("x", 50)), is_away_offense)


def passer_over_and_back_threshold(passer: Any) -> float:
    """Awareness floor: ``0.8 × PS + 0.2 × CH`` (passer attributes, 0–100 scale)."""
    attrs = getattr(passer, "attributes", None) or {}
    ps = float(attrs.get("PS", 50) or 50)
    ch = float(attrs.get("CH", 50) or 50)
    return OOB_PASS_PS_WEIGHT * ps + OOB_PASS_CH_WEIGHT * ch


def passer_commits_over_and_back_pass(passer: Any, rng: Any = random) -> bool:
    """Return True if the passer makes the illegal backcourt pass.

    ``roll = randint(1, 100)``. Pass occurs when ``roll > threshold`` — higher
    PS/CH raises the bar (smarter passer holds); lower attributes → more mistakes.
    """
    roll = int(rng.randint(1, 100))
    return roll > passer_over_and_back_threshold(passer)


def cross_half_urgency_target(
    current_xy: Dict[str, Any],
    is_away_offense: bool,
    *,
    clamp_fn,
    flip_fn,
    rng: Any = random,
) -> Dict[str, int]:
    """Random frontcourt-side target for a backcourt offender clearing half court."""
    start_y = int(current_xy.get("y", 25))
    y = start_y + rng.randint(-CROSS_HALF_URGENCY_Y_JITTER, CROSS_HALF_URGENCY_Y_JITTER)
    y = max(5, min(45, y))
    target = {
        "x": rng.randint(CROSS_HALF_URGENCY_X_MIN, CROSS_HALF_URGENCY_X_MAX),
        "y": y,
    }
    if is_away_offense:
        target = flip_fn(target)
    return clamp_fn(target)


def gate_offense_backcourt_reentry(
    off_coords: Dict[str, Dict[str, Any]],
    ratcheted: set,
    positions: Any,
    is_away_offense: bool,
    frontcourt_established: bool,
    *,
    skip: Optional[set] = None,
) -> None:
    """Ratchet off-ball offenders at the half-court line once FC is established.

    Any offender who has crossed half court (while ``frontcourt_established``) is
    added to ``ratcheted`` and can no longer re-enter the backcourt: on every
    subsequent beat his ``x`` is clamped to :data:`HALF_COURT_X`. Players still in
    the backcourt are left alone (cross-half urgency pulls them forward). ``skip``
    (the live ball handler and any in-flight pass receiver) is never gated —
    gating the receiver would silently suppress over-and-back detection.

    Mutates ``off_coords`` in place. Home offense (``is_away_offense`` False)
    attacks toward x=100, so the gate floors x at 50; away offense attacks toward
    x=0, so the same line caps x at 50.
    """
    if not frontcourt_established:
        return
    skip = skip or set()
    for pos in positions:
        if pos in skip:
            continue
        x = float(off_coords[pos]["x"])
        if not in_backcourt(x, is_away_offense):
            ratcheted.add(pos)
        elif pos in ratcheted:
            off_coords[pos]["x"] = HALF_COURT_X


def clamp_target_to_frontcourt(
    current_xy: Dict[str, Any],
    target_xy: Dict[str, Any],
    is_away_offense: bool,
) -> Dict[str, Any]:
    """Stop a mover who is already at-or-past half court from targeting behind it.

    AVOIDANCE ONLY, and deliberately gated on the mover's CURRENT side rather
    than on ``frontcourt_established``: at target-selection time he has not yet
    crossed back, so his own side is a sound proxy and needs no possession
    bookkeeping. The same proxy is USELESS for detection — once he is behind the
    line it reports "not established", which is inverted from what a violation
    check needs. Detection must read the flag. Mirrors the clamp in
    ``transition_bridge._pick_pg_receive_target``.
    """
    if in_backcourt(float(current_xy.get("x", 50)), is_away_offense):
        return target_xy
    x = float(target_xy.get("x", 50))
    x = min(HALF_COURT_X, x) if is_away_offense else max(HALF_COURT_X, x)
    clamped = dict(target_xy)
    clamped["x"] = round(x, 1)
    return clamped


def should_hold_instead_of_backcourt_pass(
    frontcourt_established: bool,
    receiver_xy: Dict[str, Any],
    is_away_offense: bool,
    passer: Any,
    grace_bh_pos: Optional[str],
    current_bh_pos: str,
    rng: Any = random,
) -> bool:
    """True when an over-and-back outlet should become a hold beat instead.

    During the one-beat grace for the first BH to establish frontcourt, backward
    passes are always held. After grace, the passer may still throw the pass
    when ``passer_commits_over_and_back_pass`` returns True (PS/CH roll).
    """
    if not is_over_and_back_pass(frontcourt_established, receiver_xy, is_away_offense):
        return False
    if grace_bh_pos is not None and current_bh_pos == grace_bh_pos:
        return True
    return not passer_commits_over_and_back_pass(passer, rng=rng)
