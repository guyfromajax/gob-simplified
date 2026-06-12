"""Coaching archetype classifier — backend source of truth.

Given a team's 5 active starters, pick the one Coaching Archetype that describes
the lineup, per `_documentation_master/00_General_Systems/Coaching_Archetype_System.md`:

  1. Total each of the 11 attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ)
     across the 5 starters.
  2. Determine the "top-3" attribute set: sort totals descending, take the value
     at the 3rd rank as the cutoff, and include every attribute whose total is
     >= that cutoff (this captures ties at the 3rd rank, and ties at #1/#2 that
     spill past it).
  3. Each archetype qualifies if its attribute combination is present in that
     top-3 set. If more than one qualifies, pick one at random; if exactly one,
     use it; if none, fall back to `mr_unconventional`.

This mirrors the mechanism in FrontEnd/static/js/shared/tutorialLineupModals.js
(`computeTopThreeAttributes`), but the QUALIFIER set here matches the 18-archetype
spec, not the tutorial's feedback messages. Attribute reads prefer `anchor_<ATTR>`
(the un-fatigued base rating) exactly like the JS.
"""

from __future__ import annotations

import random as _random

# The 11 attributes that feed archetype classification.
ATTRS_IN_PLAY: tuple[str, ...] = (
    "SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ",
)

# Ordered (archetype_key, predicate-over-top3-set) for the 17 qualifying
# archetypes. `mr_unconventional` is the fallback when none of these match.
# Combinations are taken verbatim from the spec doc — note the deliberate
# asymmetry: offensive_athleticism allows ST/AG/ND, defensive_athleticism only
# AG/ND.
ARCHETYPE_QUALIFIERS: tuple[tuple[str, object], ...] = (
    ("pure_offense", lambda t: "SC" in t and "SH" in t),
    ("pure_defense", lambda t: "ID" in t and "OD" in t),
    ("od_balance", lambda t: ("SC" in t or "SH" in t) and ("ID" in t or "OD" in t)),
    ("rebounding_king", lambda t: "RB" in t and "ST" in t),
    ("the_intimidator", lambda t: ("ID" in t or "OD" in t) and "ST" in t),
    ("mr_fundamentals", lambda t: sum(k in t for k in ("PS", "BH", "RB")) >= 2),
    ("outrun_the_competition", lambda t: "ND" in t and "AG" in t),
    ("cerebral_offense", lambda t: ("SC" in t or "SH" in t) and "IQ" in t),
    ("cerebral_defense", lambda t: ("ID" in t or "OD" in t) and "IQ" in t),
    ("pure_athleticism", lambda t: sum(k in t for k in ("ST", "AG", "ND")) >= 2),
    ("pure_discipline", lambda t: ("PS" in t or "BH" in t) and "IQ" in t),
    ("offensive_athleticism", lambda t: ("SC" in t or "SH" in t) and ("ST" in t or "AG" in t or "ND" in t)),
    ("defensive_athleticism", lambda t: ("ID" in t or "OD" in t) and ("AG" in t or "ND" in t)),
    ("offensive_fundamentals", lambda t: ("SC" in t or "SH" in t) and ("BH" in t or "PS" in t)),
    ("defensive_fundamentals", lambda t: ("ID" in t or "OD" in t) and ("BH" in t or "PS" in t)),
    ("offensive_rebounding", lambda t: ("SC" in t or "SH" in t) and "RB" in t),
    ("defensive_rebounding", lambda t: ("ID" in t or "OD" in t) and "RB" in t),
)

UNCONVENTIONAL = "mr_unconventional"


def attr_value(attrs: dict, attr: str) -> float:
    """Read one attribute from a player's attributes dict.

    Mirrors the JS `a['anchor_'+attr] ?? a[attr] ?? 0`: prefer the `anchor_`
    (un-fatigued) value, fall back to the live key, else 0. A present `anchor_`
    of 0 is used as-is (only a missing key falls through).
    """
    raw = attrs.get(f"anchor_{attr}")
    if raw is None:
        raw = attrs.get(attr, 0)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def compute_top_attributes(starters: list[dict]) -> set[str]:
    """Return the top-3 attribute set (with tie spill) across the 5 starters.

    `starters` is a list of player attribute dicts (each may carry `anchor_<ATTR>`
    and/or `<ATTR>` keys).
    """
    totals = {attr: sum(attr_value(p, attr) for p in starters) for attr in ATTRS_IN_PLAY}
    sorted_attrs = sorted(ATTRS_IN_PLAY, key=lambda a: totals[a], reverse=True)
    cutoff = totals[sorted_attrs[2]]  # ATTRS_IN_PLAY has 11 entries; index 2 always exists
    return {attr for attr in ATTRS_IN_PLAY if totals[attr] >= cutoff}


def qualifying_archetypes(top: set[str]) -> list[str]:
    """All archetype keys whose combination is satisfied by the top-3 set."""
    return [key for key, test in ARCHETYPE_QUALIFIERS if test(top)]


def classify_archetype(starters: list[dict], *, rng: _random.Random | None = None) -> str:
    """Pick one archetype key for the given 5 starters.

    Returns one of the 18 archetype keys. When multiple qualify, picks at random
    (pass `rng` for deterministic selection in tests); when none qualify, returns
    `mr_unconventional`.
    """
    top = compute_top_attributes(starters)
    pool = qualifying_archetypes(top)
    if not pool:
        return UNCONVENTIONAL
    if len(pool) == 1:
        return pool[0]
    return (rng or _random).choice(pool)
