"""Team Builder attribute budget / online-eligibility constants (§9).

Soft enforcement only — never block. Values are intentionally easy to tune.

Principle (post–§2.3): no custom program may exceed what already exists in the
league on any dimension.
  - Ceiling  = league max player (1,034 → 1,035)
  - Top-5    = league max top-5 (3,954 → 3,950)
  - Floor    = league min player (24) — sanity guard only
  - Team     ≈ P90 of per-team totals (6,400)

§2.3 measured (2026-07-27, all_players_with_team_names.txt):
  Top-5: min 2282 · median 3148 · P90 3640 · max 3954
  Per-team min player: min 24 · P10 61 · median 151.5
  Per-team totals: median ~5566.5 · max 7027
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

# Single source of truth (§9.2, revised after §2.3)
TEAM_ATTR_BUDGET = 6400
TOP5_ATTR_CAP = 3950
PLAYER_ATTR_CEILING = 1035
PLAYER_ATTR_FLOOR = 24
FLOOR_APPLIES_TO_TOP_N = 12

# League context for meter markers (measured, not caps)
LEAGUE_TEAM_MEDIAN = 5567
LEAGUE_TEAM_BEST = 7027
LEAGUE_TOP5_MEDIAN = 3148
LEAGUE_TOP5_BEST = 3954

CORE_12_ATTRS = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT")


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


def evaluate_roster_budget(
    player_attrs: Sequence[Mapping[str, Any] | None],
) -> dict[str, Any]:
    """
    Evaluate soft eligibility for a roster (four conditions).

    Floor applies to the top FLOOR_APPLIES_TO_TOP_N players by core-12 sum;
    the bottom (len - 12) are unconstrained (walk-on band).
    """
    totals = [core12_total(a) for a in player_attrs]
    totals_sorted = sorted(totals, reverse=True)
    team_total = sum(totals)
    max_player = max(totals) if totals else 0
    top5 = sum(totals_sorted[:5])

    over_budget = max(0, team_total - TEAM_ATTR_BUDGET)
    over_top5 = max(0, top5 - TOP5_ATTR_CAP)
    ceiling_violations = sum(1 for t in totals if t > PLAYER_ATTR_CEILING)
    floor_pool = totals_sorted[:FLOOR_APPLIES_TO_TOP_N]
    floor_violations = sum(1 for t in floor_pool if t < PLAYER_ATTR_FLOOR)

    eligible = (
        over_budget == 0
        and over_top5 == 0
        and ceiling_violations == 0
        and floor_violations == 0
    )

    return {
        "team_total": team_total,
        "team_budget": TEAM_ATTR_BUDGET,
        "over_budget_by": over_budget,
        "top5_total": top5,
        "top5_cap": TOP5_ATTR_CAP,
        "over_top5_by": over_top5,
        "max_player": max_player,
        "player_ceiling": PLAYER_ATTR_CEILING,
        "ceiling_violations": ceiling_violations,
        "floor": PLAYER_ATTR_FLOOR,
        "floor_violations": floor_violations,
        "eligible_for_online": eligible,
        "has_ever_exceeded_budget": not eligible,
        "roster_shape": {
            "team_total": team_total,
            "top5_total": top5,
            "max_player": max_player,
        },
        "league_context": {
            "team_median": LEAGUE_TEAM_MEDIAN,
            "team_best": LEAGUE_TEAM_BEST,
            "top5_median": LEAGUE_TOP5_MEDIAN,
            "top5_best": LEAGUE_TOP5_BEST,
        },
    }
