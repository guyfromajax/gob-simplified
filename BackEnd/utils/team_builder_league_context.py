"""Runtime league attribute context for Team Builder (v2 Decision #5 / §4.5a).

Uncapped pool and markers are computed on **week-1 as-initialized 15-player
rosters**: each team's universal-pool scholarship 12 plus three Poor-tier
walk-ons drawn with a seed derived only from that team's ObjectId.

That basis is identical for every user and does not move with season, week,
training, or which franchise save happens to exist. Live franchise FPD is
never the pool source.

Never hardcode pool/median literals — recalibration of the universal pool
changes the scholarship side; the walk-on side stays formulaically seeded.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

from BackEnd.constants.team_builder_budget import CORE_12_ATTRS, core12_total


def _median_int(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) // 2


def _team_core12_total_from_docs(player_docs: list[dict[str, Any]]) -> int:
    return sum(core12_total(doc.get("attributes") or {}) for doc in player_docs)


def _context_from_totals(team_totals: list[int], max_player: int) -> dict[str, Any]:
    team_pool = max(team_totals) if team_totals else 0
    return {
        "team_pool": team_pool,
        "team_best": team_pool,
        "team_median": _median_int(team_totals),
        "team_count": len(team_totals),
        "max_player_total": max_player,
        "max_player_ceiling": (max_player + 1) if max_player else 0,
    }


def _seed_for_team(team_id: Any) -> int:
    digest = hashlib.sha256(f"tb-league-wo-v1:{team_id}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _seeded_walk_on_core12_total(team_id: Any) -> tuple[int, int]:
    """
    Three as-initialized walk-on core-12 totals for one team.

    Uses generate_walk_on_profile() under a team-scoped seed so every caller
    gets the same pad for the same team_id.
    """
    from BackEnd.models.franchise_manager import generate_walk_on_profile

    rng_state = random.getstate()
    random.seed(_seed_for_team(team_id))
    try:
        totals = [
            core12_total(generate_walk_on_profile().get("attributes") or {})
            for _ in range(3)
        ]
    finally:
        random.setstate(rng_state)
    return sum(totals), max(totals) if totals else 0


def compute_league_attr_context(db: Any) -> dict[str, Any]:
    """
    Week-1 as-initialized 15-player league pool / median (§4.5a pin).

    scholarship = sum(core-12) over each team's universal `players` docs
    walk-ons    = 3× generate_walk_on_profile() under seed(team_id)
    team total  = scholarship + walk-ons

    `source` is always `week1_as_initialized`.
    """
    team_totals: list[int] = []
    max_player = 0
    scholarship_totals: list[int] = []
    walk_on_pads: list[int] = []

    teams = list(db.teams.find({}, {"_id": 1, "player_ids": 1, "total_player_attrs": 1}))
    for team in teams:
        player_ids_raw = team.get("player_ids") or []
        id_variants: list[Any] = []
        for pid in player_ids_raw:
            id_variants.append(pid)
            try:
                from bson import ObjectId

                id_variants.append(ObjectId(str(pid)))
            except Exception:
                pass
            id_variants.append(str(pid))

        player_docs: list[dict[str, Any]] = []
        if id_variants:
            # Universal pool _ids may be ObjectId or string depending on migration.
            seen: set[str] = set()
            for doc in db.players.find(
                {"_id": {"$in": id_variants}},
                {"attributes": 1},
            ):
                key = str(doc.get("_id"))
                if key in seen:
                    continue
                seen.add(key)
                player_docs.append(doc)

        if player_docs:
            scholarship = _team_core12_total_from_docs(player_docs)
            for doc in player_docs:
                max_player = max(max_player, core12_total(doc.get("attributes") or {}))
        else:
            try:
                scholarship = int(team.get("total_player_attrs") or 0)
            except (TypeError, ValueError):
                scholarship = 0

        walk_pad, walk_max = _seeded_walk_on_core12_total(team.get("_id"))
        max_player = max(max_player, walk_max)
        team_total = scholarship + walk_pad
        if team_total > 0:
            team_totals.append(team_total)
            scholarship_totals.append(scholarship)
            walk_on_pads.append(walk_pad)

    ctx = _context_from_totals(team_totals, max_player)
    ctx["source"] = "week1_as_initialized"
    # Diagnostic fields for operators — not consumed by the FE meter.
    if scholarship_totals:
        ctx["scholarship_pool"] = max(scholarship_totals)
        ctx["scholarship_median"] = _median_int(scholarship_totals)
    if walk_on_pads:
        ctx["walk_on_pad_at_pool_team"] = walk_on_pads[
            team_totals.index(ctx["team_pool"])
        ] if ctx["team_pool"] in team_totals else max(walk_on_pads)
        ctx["walk_on_pad_median"] = _median_int(walk_on_pads)
    return ctx


def compute_franchise_roster_context(db: Any, franchise_id: Any) -> dict[str, Any] | None:
    """Diagnostic: live FTD/FPD totals for one franchise (not the pool basis)."""
    ftds = list(
        db.franchise_team_data.find(
            {"franchise_id": franchise_id},
            {"players": 1},
        )
    )
    if not ftds:
        return None

    all_pids: list[str] = []
    for ftd in ftds:
        all_pids.extend(str(pid) for pid in (ftd.get("players") or []) if pid)
    if not all_pids:
        return None

    fpd_docs = list(
        db.franchise_players_data.find(
            {"franchise_id": str(franchise_id), "player_id": {"$in": all_pids}},
            {"player_id": 1, "attributes": 1},
        )
    )
    by_id = {str(d.get("player_id")): d for d in fpd_docs}

    team_totals: list[int] = []
    max_player = 0
    for ftd in ftds:
        docs = [
            by_id[str(pid)]
            for pid in (ftd.get("players") or [])
            if str(pid) in by_id
        ]
        if len(docs) < 12:
            continue
        team_total = _team_core12_total_from_docs(docs)
        if team_total <= 0:
            continue
        team_totals.append(team_total)
        for doc in docs:
            max_player = max(max_player, core12_total(doc.get("attributes") or {}))

    if not team_totals:
        return None
    ctx = _context_from_totals(team_totals, max_player)
    ctx["source"] = "live_franchise"
    ctx["franchise_id"] = str(franchise_id)
    return ctx


__all__ = [
    "compute_league_attr_context",
    "compute_franchise_roster_context",
    "CORE_12_ATTRS",
]
