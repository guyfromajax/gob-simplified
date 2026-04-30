"""
Scoreboard metadata on unified game `teams` objects (franchise mode).

- natl_rank: read from franchise_team_data (FTD) for each team_id.
- wins / losses: derived from franchise.results via calculate_franchise_standings
  (FTD rows do not persist W-L; franchise results are the SS&S source).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def enrich_franchise_teams_scoreboard_meta(
    teams_obj: dict[str, Any],
    franchise_id: str,
    home_team_id: str,
    away_team_id: str,
) -> None:
    """
    Mutate teams_obj[home_team_id] and teams_obj[away_team_id] in place.

    Sets when data is available: natl_rank, wins, losses, team_wins, team_losses
    (team_wins / team_losses mirror wins / losses for older frontend keys).
    """
    if not franchise_id or not isinstance(teams_obj, dict):
        return

    from bson import ObjectId
    from bson.errors import InvalidId

    from BackEnd.db import franchise_team_data_collection, franchises_collection
    from BackEnd.utils.franchise_standings import calculate_franchise_standings

    try:
        fid = ObjectId(franchise_id)
    except (InvalidId, TypeError):
        logger.warning("enrich_franchise_teams_scoreboard_meta: invalid franchise_id=%r", franchise_id)
        return

    oids: list[ObjectId] = []
    id_strs: list[str] = []
    for raw in (home_team_id, away_team_id):
        if not raw:
            continue
        s = str(raw)
        if s in id_strs:
            continue
        try:
            oids.append(ObjectId(s))
            id_strs.append(s)
        except (InvalidId, TypeError):
            logger.warning("enrich_franchise_teams_scoreboard_meta: invalid team_id=%r", raw)

    if not oids:
        return

    ftd_by_tid: dict[str, dict[str, Any]] = {}
    try:
        for doc in franchise_team_data_collection.find(
            {"franchise_id": fid, "team_id": {"$in": oids}},
            {"team_id": 1, "natl_rank": 1},
        ):
            tid = doc.get("team_id")
            if tid is not None:
                ftd_by_tid[str(tid)] = doc
    except Exception as e:
        logger.warning("enrich_franchise_teams_scoreboard_meta: FTD query failed: %s", e)
        return

    standings: dict[str, dict[str, int]] = {}
    try:
        fdoc = franchises_collection.find_one({"_id": fid}, {"results": 1})
        results = (fdoc or {}).get("results") or {}
        standings = calculate_franchise_standings(
            results,
            {tid: {} for tid in id_strs},
        )
    except Exception as e:
        logger.warning("enrich_franchise_teams_scoreboard_meta: standings failed: %s", e)

    def _apply(team_id_str: str) -> None:
        if team_id_str not in teams_obj:
            return
        entry = teams_obj[team_id_str]
        if not isinstance(entry, dict):
            return

        ftd = ftd_by_tid.get(team_id_str)
        if ftd:
            nr = ftd.get("natl_rank")
            if nr is not None:
                try:
                    entry["natl_rank"] = int(nr)
                except (TypeError, ValueError):
                    pass

        st = standings.get(team_id_str) or {}
        try:
            w = int(st.get("W", 0) or 0)
            ell = int(st.get("L", 0) or 0)
        except (TypeError, ValueError):
            w, ell = 0, 0
        entry["wins"] = w
        entry["losses"] = ell
        entry["team_wins"] = w
        entry["team_losses"] = ell

    _apply(str(home_team_id))
    _apply(str(away_team_id))


def coalesce_natl_rank_from_team_row(team_data: dict[str, Any], rank_from_ftd_loader: Any) -> Any:
    """Prefer persisted ``teams`` natl_rank; else use value from FTD loader (e.g. GET /api/game)."""
    if isinstance(team_data, dict):
        tnr = team_data.get("natl_rank")
        if tnr is not None:
            try:
                return int(tnr)
            except (TypeError, ValueError):
                pass
    return rank_from_ftd_loader


def attach_home_away_team_scoreboard_shards(summary: dict[str, Any]) -> None:
    """
    Set ``home_team`` / ``away_team`` on a simulate (or other) summary so the court can read
    rank/record from the same blobs as S3 ``attributes`` — sourced from ``teams`` rows.
    """
    if not isinstance(summary, dict):
        return
    teams = summary.get("teams") or {}
    if not isinstance(teams, dict) or not teams:
        return
    hid = summary.get("home_team_id")
    aid = summary.get("away_team_id")

    def _row(tid: Any) -> dict[str, Any] | None:
        if tid is None or tid == "":
            return None
        row = teams.get(tid)
        if row is None:
            sid = str(tid)
            for k, v in teams.items():
                if str(k) == sid and isinstance(v, dict):
                    return v
        return row if isinstance(row, dict) else None

    def _shard(tid: Any) -> dict[str, Any] | None:
        row = _row(tid)
        if not row:
            return None
        return {
            "name": row.get("name"),
            "team_id": row.get("team_id"),
            "attributes": row.get("attributes") or {},
            "natl_rank": row.get("natl_rank"),
            "wins": row.get("wins"),
            "losses": row.get("losses"),
            "team_wins": row.get("team_wins"),
            "team_losses": row.get("team_losses"),
        }

    hs = _shard(hid)
    if hs:
        summary["home_team"] = hs
    aws = _shard(aid)
    if aws:
        summary["away_team"] = aws
