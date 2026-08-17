"""Recruiting Report / Results news ranking helpers.

Weekly reports (weeks 1–35 title cadence): team points from lean-list share of
each recruit's current RT. Week-35 Results: points = 100% of signed recruits' RT
for the signing team only.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any, Callable

LEAN_SLOT_WEIGHTS = {"1": 1.0, "2": 0.5, "3": 0.25}
NATIONAL_LIMIT = 25
REGION_LIMIT = 16  # full region (2 conferences × 8 teams)
NATIONAL_COLUMN_SPLIT = (13, 12)
REGION_COLUMN_SPLIT = (8, 8)


def recruit_max_rt(recruit_doc: dict[str, Any]) -> int:
    """Best position rating on a recruit/FRD doc (current RT)."""
    ratings = recruit_doc.get("position_ratings") or {}
    values = [int(v or 0) for v in ratings.values() if isinstance(v, (int, float))]
    return max(values) if values else 0


def team_points_from_lean_lists(
    recruits: list[dict[str, Any]],
    recruit_rt_fn: Callable[[dict[str, Any]], int],
) -> dict[str, int]:
    """Accrue rounded lean-share points per team. Slot 1/2/3 = 100%/50%/25% of RT."""
    scores: dict[str, int] = {}
    for recruit in recruits or []:
        rt = int(recruit_rt_fn(recruit) or 0)
        if rt <= 0:
            continue
        lean = recruit.get("Lean") or {}
        if not isinstance(lean, dict):
            continue
        for slot, weight in LEAN_SLOT_WEIGHTS.items():
            team_id = lean.get(slot)
            if team_id is None or team_id == "" or team_id == "open":
                continue
            tid = str(team_id)
            scores[tid] = scores.get(tid, 0) + int(round(rt * weight))
    return scores


def team_points_from_signings(signed_players: list[dict[str, Any]]) -> dict[str, int]:
    """Signing team receives 100% of each signed recruit's RT; no other team scores."""
    scores: dict[str, int] = {}
    for player in signed_players or []:
        tid = str(player.get("team_id") or "")
        if not tid:
            continue
        rt = int(player.get("rt") or 0)
        if rt <= 0:
            continue
        scores[tid] = scores.get(tid, 0) + rt
    return scores


def rank_teams_by_points(
    scores: dict[str, int],
    team_name_map: dict[str, str],
    *,
    limit: int,
    rng: random.Random | None = None,
    include_team_ids: set[str] | None = None,
    include_zeros: bool = False,
) -> list[dict[str, Any]]:
    """Strict sequential ranks 1..N. Ties broken randomly.

    By default omits zero-point teams. When ``include_team_ids`` is set, ranks that
    fixed roster (missing scores treated as 0); ``include_zeros`` keeps 0-point rows.
    """
    rng = rng or random
    if include_team_ids is not None:
        items = [
            (str(tid), int((scores or {}).get(str(tid), 0) or 0))
            for tid in include_team_ids
        ]
        if not include_zeros:
            items = [(tid, pts) for tid, pts in items if pts > 0]
    else:
        items = [(tid, int(pts)) for tid, pts in (scores or {}).items() if int(pts) > 0]
    items.sort(key=lambda row: (-row[1], rng.random()))
    ranked: list[dict[str, Any]] = []
    for i, (tid, pts) in enumerate(items[: max(0, int(limit))], start=1):
        ranked.append(
            {
                "rank": i,
                "team_id": tid,
                "team": team_name_map.get(tid, tid),
                "score": pts,
            }
        )
    return ranked


def build_recruiting_rankings_story(
    *,
    story_id: str,
    week: int,
    headline: str,
    story_type: str,
    scores: dict[str, int],
    team_name_map: dict[str, str],
    user_region_letter: str | None,
    region_team_ids: set[str] | None,
    national_limit: int = NATIONAL_LIMIT,
    region_limit: int = REGION_LIMIT,
) -> dict[str, Any] | None:
    """National Top 25 + full user-region rankings. None if nobody has national points."""
    national = rank_teams_by_points(
        scores,
        team_name_map,
        limit=national_limit,
    )
    if not national:
        return None

    rich_lines: list[dict[str, Any]] = [
        {"type": "heading", "text": "National Recruit Rankings"},
        {
            "type": "ranking_table",
            "columns": ["Rank", "Team", "Score"],
            "rows": national,
            "column_split": list(NATIONAL_COLUMN_SPLIT),
        },
    ]

    region_letter = (user_region_letter or "").strip().upper()
    if region_letter and region_team_ids:
        regional = rank_teams_by_points(
            scores,
            team_name_map,
            limit=region_limit,
            include_team_ids=set(region_team_ids),
            include_zeros=True,
        )
        if regional:
            rich_lines.append({"type": "gap"})
            rich_lines.append({"type": "heading", "text": f"Region {region_letter}"})
            rich_lines.append(
                {
                    "type": "ranking_table",
                    "columns": ["Rank", "Team", "Score"],
                    "rows": regional,
                    "column_split": list(REGION_COLUMN_SPLIT),
                }
            )

    return {
        "story_id": story_id,
        "week": int(week),
        "type": story_type,
        "headline": headline,
        "rich_lines": rich_lines,
        "created_at": datetime.utcnow(),
    }
