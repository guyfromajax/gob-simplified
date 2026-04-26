"""Lazy season totals: coaching archetype picks on user-team FTD (`coaching_focus.*` counters)."""

from __future__ import annotations

import random
from typing import Any

from BackEnd.models.training_execution_v2 import parse_coaching_focus

# FTD `coaching_focus` subkeys (all four archetypes).
COACHING_FOCUS_FTD_COUNT_KEYS = (
    "authoritarian",
    "systems_coach",
    "player_maximizer",
    "culture_builder",
)

# User-team FTD only; incremented on each training submit (no backfill).
_COACHING_FOCUS_ARCHETYPE_TO_FTD_SUBKEY = {
    "authoritarian": "authoritarian",
    "systems-coach": "systems_coach",
    "player-maximizer": "player_maximizer",
    "culture-builder": "culture_builder",
}

# Season rollover: retain this fraction of each counter (i.e. 75% reduction).
_COACHING_FOCUS_SEASON_CARRYOVER_RATIO = 0.25


def carryover_coaching_focus_counts_for_new_season(existing: Any) -> dict[str, int]:
    """
    New season within the same franchise: each archetype count becomes
    round(prior * 0.25) — a 75% reduction, integer-rounded.
    """
    out = {k: 0 for k in COACHING_FOCUS_FTD_COUNT_KEYS}
    if not isinstance(existing, dict):
        return out
    for k in COACHING_FOCUS_FTD_COUNT_KEYS:
        raw = existing.get(k, 0)
        try:
            n = float(raw)
        except (TypeError, ValueError):
            n = 0.0
        out[k] = int(round(n * _COACHING_FOCUS_SEASON_CARRYOVER_RATIO))
    return out


def user_ftd_coaching_focus_increment(
    coaching_focus_raw: Any,
    *,
    training_camp_first_week: bool = False,
) -> dict[str, int] | None:
    """
    Return a single-key dict suitable for MongoDB $inc under coaching_focus.<subkey>, or None.

    Subkeys: authoritarian, systems_coach, player_maximizer, culture_builder.

    Week 1 training camp (before first game): weight is random.randint(2, 4) instead of 1.
    """
    if coaching_focus_raw is None:
        arch, _ = parse_coaching_focus(None)
    else:
        arch, _ = parse_coaching_focus(str(coaching_focus_raw).strip() or None)
    subkey = _COACHING_FOCUS_ARCHETYPE_TO_FTD_SUBKEY.get(arch or "")
    if not subkey:
        return None
    weight = random.randint(2, 4) if training_camp_first_week else 1
    return {f"coaching_focus.{subkey}": weight}
