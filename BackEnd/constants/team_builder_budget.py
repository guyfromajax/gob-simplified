"""Team Builder attribute model (v2 §4).

Mode determines online eligibility. Top-5 / 6400 four-condition soft budget retired.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence

# Per-attribute clamps (§4.1)
ATTR_MIN = 5
ATTR_MAX = 99

# §4.3: 5 × 12 floor; inherited totals below this are topped up in capped mode
# (not on path 1 keep).
TOPUP_FLOOR = 60

# Capped belt-and-braces ceiling (§4.4); highest inherited is 1,034
CAPPED_PLAYER_CEILING = 1035

# Uncapped team pool = league best program total (§4.1 / §2.3)
UNCAPPED_TEAM_POOL = 7027

# League context markers for uncapped meter (measured, not caps)
LEAGUE_TEAM_MEDIAN = 5567
LEAGUE_TEAM_BEST = 7027

CORE_12_ATTRS = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT")

ATTRIBUTE_MODES = frozenset({"capped", "uncapped"})


def core12_total(attrs: Mapping[str, Any] | None) -> int:
    if not attrs:
        return 0
    total = 0
    for key in CORE_12_ATTRS:
        try:
            total += int(attrs.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def clamp_attr(value: Any) -> int:
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        n = ATTR_MIN
    return max(ATTR_MIN, min(ATTR_MAX, n))


def normalize_attribute_mode(mode: Any) -> str:
    text = str(mode or "capped").strip().lower()
    return text if text in ATTRIBUTE_MODES else "capped"


def online_eligible_for_mode(mode: Any) -> bool:
    return normalize_attribute_mode(mode) == "capped"


def capped_budget_for_inherited(raw_total: int) -> int:
    """Per-player capped budget: inherited total, or 60 after top-up."""
    return TOPUP_FLOOR if raw_total < TOPUP_FLOOR else max(0, int(raw_total))


def apply_capped_topup(
    raw_attrs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """
    Raise a below-floor player to exactly TOPUP_FLOOR with each attr in [5, 99].

    Returns:
      attrs: core-12 (+ anchors) after adjustment
      raw_total: pre-top-up core-12 sum
      budget: capped budget (max(raw_total, 60))
      topped_up: whether top-up applied
    """
    raw = dict(raw_attrs or {})
    raw_total = core12_total(raw)
    topped_up = raw_total < TOPUP_FLOOR
    budget = capped_budget_for_inherited(raw_total)

    attrs: dict[str, int] = {key: clamp_attr(raw.get(key, ATTR_MIN)) for key in CORE_12_ATTRS}
    total = sum(attrs.values())

    # Distribute up to budget
    guard = 0
    while total < budget and guard < 2000:
        guard += 1
        # Prefer attrs that were raised from below-min / still low
        key = min(CORE_12_ATTRS, key=lambda k: (attrs[k], k))
        if attrs[key] >= ATTR_MAX:
            # All maxed — stop
            break
        attrs[key] += 1
        total += 1

    # Trim down to budget when floor push overshot (still never below ATTR_MIN)
    guard = 0
    while total > budget and guard < 2000:
        guard += 1
        key = max(CORE_12_ATTRS, key=lambda k: (attrs[k], k))
        if attrs[key] <= ATTR_MIN:
            break
        attrs[key] -= 1
        total -= 1

    out: dict[str, Any] = {}
    for key in CORE_12_ATTRS:
        out[key] = attrs[key]
        out[f"anchor_{key}"] = attrs[key]
    return {
        "attrs": out,
        "raw_total": raw_total,
        "budget": budget,
        "topped_up": topped_up,
    }


def roster_shape_from_attrs(
    player_attrs: Sequence[Mapping[str, Any] | None],
) -> dict[str, int]:
    totals = [core12_total(a) for a in player_attrs]
    totals_sorted = sorted(totals, reverse=True)
    return {
        "team_total": sum(totals),
        "top5_total": sum(totals_sorted[:5]),
        "max_player": max(totals) if totals else 0,
    }


def evaluate_mode_roster(
    *,
    attribute_mode: Any,
    player_attrs: Sequence[Mapping[str, Any] | None],
    per_player_budgets: Sequence[int] | None = None,
) -> dict[str, Any]:
    """
    Mode-based evaluation for Apply metadata.

    Eligibility is determined by mode alone. Pool / per-player overages are
    reported for UI but do not flip online_eligible.
    """
    mode = normalize_attribute_mode(attribute_mode)
    eligible = online_eligible_for_mode(mode)
    shape = roster_shape_from_attrs(player_attrs)
    team_total = shape["team_total"]

    over_pool = 0
    if mode == "uncapped":
        over_pool = max(0, team_total - UNCAPPED_TEAM_POOL)

    per_player_over = 0
    if mode == "capped" and per_player_budgets is not None:
        for attrs, budget in zip(player_attrs, per_player_budgets):
            spent = core12_total(attrs)
            if spent > int(budget or 0):
                per_player_over += spent - int(budget or 0)

    return {
        "attribute_mode": mode,
        "online_eligible": eligible,
        # Retained unread field: true when uncapped (ineligible by mode) or over pool.
        "has_ever_exceeded_budget": (not eligible) or over_pool > 0 or per_player_over > 0,
        "roster_shape": shape,
        "team_total": team_total,
        "team_pool": UNCAPPED_TEAM_POOL,
        "over_pool_by": over_pool,
        "per_player_over_by": per_player_over,
        "league_context": {
            "team_median": LEAGUE_TEAM_MEDIAN,
            "team_best": LEAGUE_TEAM_BEST,
        },
    }
