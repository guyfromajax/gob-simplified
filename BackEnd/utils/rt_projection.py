"""Projected potential — the single home for the Player Potential Rating display value.

Three responsibilities, each in ONE place, so nothing drifts across the surfaces:
  • the FORMULA lives here:   raw = JH_ANCHOR_BY_TIER[entry_tier] × 2.0 × potential_factor
  • the RATCHET lives here:    emitted = max(raw, current_RT)
  • the LETTERS live in the views (rtBucket.js / rt_display.rt_letter_grade)

`ratcheted_potential_rt` emits the value the views display: it is ALREADY RATCHETED
against the player's current RT, so a consumer must NOT re-apply max(projection, current)
— doing so in three views is exactly the duplication this module exists to prevent. The
views format two integers (current RT and this value) through the letter mapping; they add
no arithmetic. The payload field carrying this value is named `potential_rt_ratcheted`
(see POTENTIAL_RT_FIELD) precisely so it can't be mistaken for the raw projection.

Why ×2.0 reads true: it lifts the JH anchor to the SENIOR ladder anchor (40/50/60/70/80/100),
where a median-peak career now lands after the 2026-08 attractor-level fix — so the emitted
value matches achieved RT rather than sitting ~9% high. The ratchet is computed at RENDER,
needs no history, and cannot desynchronise from live RT, so it works for any class year.

Returns None when tier/factor give no basis — the caller then shows the current rating ALONE
(a single letter), which is the correct display for a player with no projectable ceiling.
"""
from __future__ import annotations

from typing import Any, Optional

from BackEnd.utils.rt_display import rt_letter_grade

# JH anchor → senior ladder anchor. The tier's senior ceiling before the ±15% factor.
POTENTIAL_PROJECTION_MULTIPLE = 2.0

# Canonical payload field name. The value under this key is ALREADY RATCHETED — the
# "_ratcheted" suffix is load-bearing: it tells every consumer not to re-apply the max().
POTENTIAL_RT_FIELD = "potential_rt_ratcheted"


def _coerce_rt(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ratcheted_potential_rt(
    entry_tier: Any,
    potential_factor: Any,
    current_rt: Any = None,
) -> Optional[float]:
    """The ALREADY-RATCHETED projected-ceiling RT to display, or ``None`` when tier/
    factor give no basis (caller shows the current rating alone).

    This is ``max(anchor × 2.0 × potential_factor, current_rt)`` — the ratchet is
    applied HERE so no view repeats it. ``potential_factor`` should already be resolved
    by the caller (it holds the player_id needed for the legacy fallback); this function
    stays pure and never re-derives it.
    """
    from BackEnd.utils.player_generation import JH_ANCHOR_BY_TIER

    cur = _coerce_rt(current_rt)
    pf = _coerce_rt(potential_factor)
    if not entry_tier or entry_tier not in JH_ANCHOR_BY_TIER or pf is None or pf <= 0:
        return None  # no basis → caller shows the current rating ALONE (single letter)
    raw = JH_ANCHOR_BY_TIER[entry_tier] * POTENTIAL_PROJECTION_MULTIPLE * pf
    if cur is not None:
        raw = max(raw, cur)  # RATCHET — never emit a ceiling below the actual rating
    return raw


def potential_rt_for_player(
    player_id: Any,
    entry_tier: Any,
    stored_potential_factor: Any,
    position_ratings: Any,
) -> Optional[int]:
    """Payload-ready ``potential_rt_ratcheted`` for one player, from RAW stored fields.

    The single call the display endpoints use: it resolves ``potential_factor`` (stored value,
    else the deterministic player_id hash), takes best-position RT as the current rating,
    applies the ratchet, and rounds to an int for display. Returns ``None`` when there is no
    basis, so the caller shows the current rating alone.

    Alarm RE-ARMED (Phase 5 complete, 2026-08): the pool now carries potential_factor, so a
    fallback on a read is no longer an expected legacy row — it means a genuinely dropped field
    on some write path, and it warns (as entry_tier's does). The blanket warn=False suppression
    that pre-Phase-5 reads needed (the un-backfilled pool would have logged per player per page
    load) is gone. DEPLOY ORDER: run scripts/backfill_pool_potential_factor.py --commit in an
    environment BEFORE this code ships there, or that env's pool reads will warn until it does.
    A transient legacy *franchise* save may still warn on display until it lazy-backfills at
    rollover — expected, low volume.
    """
    from BackEnd.utils.player_generation import resolve_potential_factor

    ratings = position_ratings if isinstance(position_ratings, dict) else {}
    current = max(ratings.values()) if ratings else None
    pf = resolve_potential_factor(player_id, stored_potential_factor)
    value = ratcheted_potential_rt(entry_tier, pf, current)
    return int(round(value)) if value is not None else None


def rt_current_potential(
    current_rt: Any,
    entry_tier: Any,
    potential_factor: Any,
) -> str:
    """`current/potential` letter pair for server-rendered surfaces, e.g. ``"C/B"`` /
    ``"A/A++"``. Falls back to the current grade alone when there is no projection basis.
    Uses the already-ratcheted value, so a met-ceiling player reads ``"A++/A++"``.
    """
    cur_letter = rt_letter_grade(current_rt)
    ceiling = ratcheted_potential_rt(entry_tier, potential_factor, current_rt)
    if ceiling is None:
        return cur_letter
    return f"{cur_letter}/{rt_letter_grade(ceiling)}"


__all__ = [
    "POTENTIAL_PROJECTION_MULTIPLE",
    "POTENTIAL_RT_FIELD",
    "ratcheted_potential_rt",
    "potential_rt_for_player",
    "rt_current_potential",
]
