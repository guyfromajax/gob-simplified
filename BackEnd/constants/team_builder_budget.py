"""Team Builder attribute model (v2 §4).

Mode determines online eligibility. Top-5 / four-condition soft budget retired.
League pool and median are computed at runtime — never hardcoded here.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

# Per-attribute clamps (§4.1)
ATTR_MIN = 5
ATTR_MAX = 99

# §4.3: 5 × 12 floor; inherited totals below this are topped up in capped mode
# (not on path 1 keep). Structurally correct regardless of how many players it touches.
TOPUP_FLOOR = 60

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


def resolve_online_eligible(doc: Mapping[str, Any] | None) -> bool:
    """
    Single source of truth for online eligibility on a franchise document.

    Spec field is `online_eligible`. Legacy `online_eligibility` is read only when
    the spec field is absent (v1 franchises). Callers must never assign the two
    independently — derive the alias from this helper at the response edge.
    """
    if not doc:
        return True
    if "online_eligible" in doc:
        return bool(doc.get("online_eligible"))
    if "online_eligibility" in doc:
        return bool(doc.get("online_eligibility"))
    return True


def capped_budget_for_inherited(raw_total: int) -> int:
    """Per-player capped budget: inherited total, or 60 after top-up."""
    return TOPUP_FLOOR if raw_total < TOPUP_FLOOR else max(0, int(raw_total))


def force_core12_to_budget(
    raw_attrs: Mapping[str, Any] | None,
    budget: int,
) -> dict[str, int]:
    """Clamp to [5, 99] then redistribute so core-12 sum equals budget exactly."""
    target = max(0, int(budget))
    attrs: dict[str, int] = {key: clamp_attr((raw_attrs or {}).get(key, ATTR_MIN)) for key in CORE_12_ATTRS}
    total = sum(attrs.values())
    guard = 0
    while total < target and guard < 2000:
        guard += 1
        key = min(CORE_12_ATTRS, key=lambda k: (attrs[k], k))
        if attrs[key] >= ATTR_MAX:
            break
        attrs[key] += 1
        total += 1
    guard = 0
    while total > target and guard < 2000:
        guard += 1
        key = max(CORE_12_ATTRS, key=lambda k: (attrs[k], k))
        if attrs[key] <= ATTR_MIN:
            break
        attrs[key] -= 1
        total -= 1
    return attrs


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

    guard = 0
    while total < budget and guard < 2000:
        guard += 1
        key = min(CORE_12_ATTRS, key=lambda k: (attrs[k], k))
        if attrs[key] >= ATTR_MAX:
            break
        attrs[key] += 1
        total += 1

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
    team_pool: int | None = None,
    team_median: int | None = None,
) -> dict[str, Any]:
    """
    Mode-based evaluation for Apply metadata / UI.

    Eligibility is determined by mode alone. `team_pool` / `team_median` must be
    supplied from runtime league context (Decision #5) — never from constants.
    """
    mode = normalize_attribute_mode(attribute_mode)
    eligible = online_eligible_for_mode(mode)
    shape = roster_shape_from_attrs(player_attrs)
    team_total = shape["team_total"]
    pool = max(0, int(team_pool or 0))
    median = max(0, int(team_median or 0))

    over_pool = 0
    if mode == "uncapped" and pool > 0:
        over_pool = max(0, team_total - pool)

    per_player_over = 0
    per_player_under = 0
    if mode == "capped" and per_player_budgets is not None:
        for attrs, budget in zip(player_attrs, per_player_budgets):
            spent = core12_total(attrs)
            cap = int(budget or 0)
            if spent > cap:
                per_player_over += spent - cap
            elif spent < cap:
                per_player_under += cap - spent

    return {
        "attribute_mode": mode,
        "online_eligible": eligible,
        # Retained unread field: true when uncapped (ineligible by mode) or over pool.
        "has_ever_exceeded_budget": (not eligible) or over_pool > 0 or per_player_over > 0,
        "roster_shape": shape,
        "team_total": team_total,
        "team_pool": pool,
        "over_pool_by": over_pool,
        "per_player_over_by": per_player_over,
        "per_player_under_by": per_player_under,
        "league_context": {
            "team_median": median,
            "team_best": pool,
        },
    }
