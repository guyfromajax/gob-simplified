"""Recruiting Report / Results news ranking helpers.

Weekly reports (weeks 1–35 title cadence): team points from lean-list share of
each recruit's current RT. Week-35 Results: points = 100% of signed recruits' RT
for the signing team only.

Durable ranks (FTD ``recruiting_rank`` / ``recruiting_region_rank`` /
``recruiting_score``) are recomputed from the same scores at those moments so
Roster and other surfaces can read without rescanning FRDs.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Any, Callable, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

LEAN_SLOT_WEIGHTS = {"1": 1.0, "2": 0.5, "3": 0.25}
NATIONAL_LIMIT = 25
REGION_LIMIT = 16  # full region (2 conferences × 8 teams)
NATIONAL_COLUMN_SPLIT = (13, 12)
REGION_COLUMN_SPLIT = (8, 8)

# The quiet line under "National Recruit Rankings". It says what Score is for, not how
# it is built: the formula (lean slots, signings) is hidden from the player, so no news
# copy explains it.
WEEKLY_SCORE_CAPTION = "Class strength so far"
RESULTS_SCORE_CAPTION = "Class strength"

FTD_RECRUITING_RANK = "recruiting_rank"
FTD_RECRUITING_REGION_RANK = "recruiting_region_rank"
FTD_RECRUITING_SCORE = "recruiting_score"


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


def compute_recruiting_rank_fields(
    scores: Mapping[str, int] | None,
    team_ids: Sequence[str],
    region_by_team_id: Mapping[str, str],
    *,
    rng: Optional[random.Random] = None,
) -> dict[str, dict[str, int]]:
    """Full-league recruiting ranks for FTD persistence.

    Every team in ``team_ids`` gets a national ``recruiting_rank`` (1..N, zeros included)
    and a ``recruiting_region_rank`` within its region letter (1..region size). Ties break
    randomly once at compute time; persisted values stay stable until the next recompute.
    """
    chooser = rng if rng is not None else random.Random()
    score_map = {str(k): int(v or 0) for k, v in (scores or {}).items()}
    ids = [str(tid) for tid in team_ids if tid]
    if not ids:
        return {}

    national = [(tid, score_map.get(tid, 0)) for tid in ids]
    national.sort(key=lambda row: (-row[1], chooser.random()))
    out: dict[str, dict[str, int]] = {}
    for place, (tid, pts) in enumerate(national, start=1):
        out[tid] = {
            FTD_RECRUITING_RANK: place,
            FTD_RECRUITING_SCORE: pts,
            FTD_RECRUITING_REGION_RANK: 0,
        }

    by_region: dict[str, list[str]] = {}
    for tid in ids:
        letter = str(region_by_team_id.get(tid) or "").strip().upper() or "?"
        by_region.setdefault(letter, []).append(tid)

    for tids in by_region.values():
        region_rows = [(tid, score_map.get(tid, 0)) for tid in tids]
        region_rows.sort(key=lambda row: (-row[1], chooser.random()))
        for place, (tid, _) in enumerate(region_rows, start=1):
            out[tid][FTD_RECRUITING_REGION_RANK] = place

    return out


def persist_recruiting_ranks_to_ftd(
    *,
    franchise_id: Any,
    ranked_by_team_id: Mapping[str, Mapping[str, int]],
    franchise_team_data_collection: Any,
) -> int:
    """Write recruiting rank fields onto each FTD doc. Returns update count."""
    if not ranked_by_team_id:
        return 0
    try:
        from bson import ObjectId
        from pymongo import UpdateOne
    except Exception:
        logger.exception("[RECRUITING-RANK] imports failed")
        return 0

    ops = []
    now = datetime.utcnow()
    for tid, fields in ranked_by_team_id.items():
        try:
            team_oid = ObjectId(str(tid))
        except Exception:
            continue
        ops.append(
            UpdateOne(
                {"franchise_id": franchise_id, "team_id": team_oid},
                {
                    "$set": {
                        FTD_RECRUITING_RANK: int(fields.get(FTD_RECRUITING_RANK) or 0),
                        FTD_RECRUITING_REGION_RANK: int(
                            fields.get(FTD_RECRUITING_REGION_RANK) or 0
                        ),
                        FTD_RECRUITING_SCORE: int(fields.get(FTD_RECRUITING_SCORE) or 0),
                        "updated_at": now,
                    }
                },
            )
        )
    if not ops:
        return 0
    try:
        result = franchise_team_data_collection.bulk_write(ops, ordered=False)
        return int(getattr(result, "modified_count", 0) or 0) + int(
            getattr(result, "upserted_count", 0) or 0
        )
    except Exception:
        logger.exception(
            "[RECRUITING-RANK] FTD bulk write failed franchise=%s",
            str(franchise_id),
        )
        return 0


def previous_table_ranks(previous_story: Mapping[str, Any] | None) -> dict[str, dict[str, int]]:
    """``{"national": {team_id: rank}, "region": {team_id: rank}}`` from a stored report.

    A table is named by its ``table`` key. A story stored before that key existed has
    the national table first and the region table second. The national map includes the
    user's foot row when the story has one.
    """
    out: dict[str, dict[str, int]] = {}
    if not isinstance(previous_story, Mapping):
        return out
    tables = [
        line for line in (previous_story.get("rich_lines") or [])
        if isinstance(line, Mapping) and line.get("type") == "ranking_table"
    ]
    for index, line in enumerate(tables):
        name = str(line.get("table") or ("national" if index == 0 else "region" if index == 1 else ""))
        if name not in ("national", "region") or name in out:
            continue
        ranks: dict[str, int] = {}
        rows = list(line.get("rows") or [])
        if isinstance(line.get("user_row"), Mapping):
            rows.append(line["user_row"])
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            team_id = str(row.get("team_id") or "")
            try:
                rank = int(row.get("rank"))
            except (TypeError, ValueError):
                continue
            if team_id and rank > 0:
                ranks[team_id] = rank
        out[name] = ranks
    return out


def stamp_rank_movement(
    rows: list[dict[str, Any]],
    previous: Mapping[str, int] | None,
    *,
    mark_new: bool = True,
) -> None:
    """Write each row's movement against last week's same table, in place.

    ``move`` is places gained (positive = rose, 0 = unchanged). A team that was not in
    last week's table gets ``new: True``. No previous table: nothing is written, so the
    page shows no marks.
    """
    if not previous:
        return
    for row in rows:
        before = previous.get(str(row.get("team_id") or ""))
        if before is None:
            if mark_new:
                row["new"] = True
            continue
        row["move"] = int(before) - int(row["rank"])


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
    user_team_id: str | None = None,
    user_zero_rank: int | None = None,
    previous_story: Mapping[str, Any] | None = None,
    score_caption: str | None = None,
) -> dict[str, Any] | None:
    """National Top 25 + full user-region rankings. None if nobody has national points.

    ``user_team_id``: when that team is outside the national top 25 its row is stored
    as the table's ``user_row``, with its real rank (its place among every team with
    points; ``user_zero_rank``, the durable full-league rank, when it has none).
    ``previous_story``: last week's stored report. Each row then carries its movement
    against the same table (``stamp_rank_movement``), stored with the story so an old
    story keeps its own week's movement.
    """
    # Every team with points, ranked once: the top 25 is the table, and a user team
    # further down reads its rank from the same order.
    everyone = rank_teams_by_points(
        scores,
        team_name_map,
        limit=len(scores or {}) + 1,
    )
    national = everyone[: max(0, int(national_limit))]
    if not national:
        return None

    user_tid = str(user_team_id or "")
    user_row: dict[str, Any] | None = None
    if user_tid and not any(row["team_id"] == user_tid for row in national):
        user_row = next((dict(row) for row in everyone if row["team_id"] == user_tid), None)
        if user_row is None and user_zero_rank:
            user_row = {
                "rank": int(user_zero_rank),
                "team_id": user_tid,
                "team": team_name_map.get(user_tid, user_tid),
                "score": 0,
            }

    previous = previous_table_ranks(previous_story)
    stamp_rank_movement(national, previous.get("national"))
    if user_row is not None:
        # Outside the table both weeks is not "new": only a known earlier rank is a move.
        stamp_rank_movement([user_row], previous.get("national"), mark_new=False)

    national_table: dict[str, Any] = {
        "type": "ranking_table",
        "table": "national",
        "columns": ["Rank", "Team", "Score"],
        "rows": national,
        "column_split": list(NATIONAL_COLUMN_SPLIT),
    }
    if score_caption:
        national_table["caption"] = str(score_caption)
    if user_row is not None:
        national_table["user_row"] = user_row
    rich_lines: list[dict[str, Any]] = [
        {"type": "heading", "text": "National Recruit Rankings"},
        national_table,
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
            stamp_rank_movement(regional, previous.get("region"))
            rich_lines.append({"type": "gap"})
            rich_lines.append({"type": "heading", "text": f"Region {region_letter}"})
            rich_lines.append(
                {
                    "type": "ranking_table",
                    "table": "region",
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
