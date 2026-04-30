"""
Scoreboard metadata on unified game `teams` objects (franchise mode).

- natl_rank: read from franchise_team_data (FTD) for each team_id (top-level
  ``natl_rank`` is canonical; optional fallbacks for legacy/nested shapes).
- wins / losses: derived from ``franchise.results`` via calculate_franchise_standings
  (authoritative W-L for the season). The weekly rank job also denormalizes
  ``season_wins`` / ``season_losses`` onto each FTD row for convenience in
  tooling and reporting (enrichment uses ``franchise.results`` only).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def resolve_mongo_team_id_string(raw: Any) -> str | None:
    """
    Normalize a game/slot team identifier to the canonical ``teams._id`` hex string
    used as ``franchise_team_data.team_id`` (FTD). Accepts ObjectId, 24-char hex, team name, or ``team_id`` slug.
    """
    if raw is None or raw == "":
        return None
    from bson import ObjectId
    from bson.errors import InvalidId

    if isinstance(raw, ObjectId):
        return str(raw)
    s = str(raw).strip()
    if not s:
        return None
    try:
        return str(ObjectId(s))
    except (InvalidId, TypeError):
        pass
    try:
        from BackEnd.db import teams_collection

        doc = teams_collection.find_one(
            {"$or": [{"name": s}, {"team_id": s}, {"code": s}]},
            {"_id": 1},
        )
        if doc and doc.get("_id") is not None:
            return str(doc["_id"])
    except Exception as e:
        logger.warning("resolve_mongo_team_id_string: teams lookup failed for %r: %s", raw, e)
    return None


def natl_rank_from_ftd_document(ftd: dict[str, Any] | None) -> int | None:
    """Return national rank from an FTD document, or None if missing/invalid."""
    if not isinstance(ftd, dict):
        return None
    nr = ftd.get("natl_rank")
    if nr is not None:
        try:
            return int(nr)
        except (TypeError, ValueError):
            pass
    recruits = ftd.get("Recruits")
    if isinstance(recruits, dict):
        nr2 = recruits.get("natl_rank")
        if nr2 is not None:
            try:
                return int(nr2)
            except (TypeError, ValueError):
                pass
    return None


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
        fid = ObjectId(str(franchise_id).strip())
    except (InvalidId, TypeError):
        logger.warning("enrich_franchise_teams_scoreboard_meta: invalid franchise_id=%r", franchise_id)
        return

    oids: list[ObjectId] = []
    id_strs: list[str] = []
    slot_to_canonical: list[tuple[Any, str]] = []
    for raw in (home_team_id, away_team_id):
        if not raw:
            continue
        canon = resolve_mongo_team_id_string(raw)
        if not canon:
            logger.warning("enrich_franchise_teams_scoreboard_meta: could not resolve team_id=%r", raw)
            continue
        slot_to_canonical.append((raw, canon))
        if canon in id_strs:
            continue
        try:
            oids.append(ObjectId(canon))
            id_strs.append(canon)
        except (InvalidId, TypeError):
            logger.warning("enrich_franchise_teams_scoreboard_meta: invalid resolved id=%r", canon)

    if not oids:
        return

    ftd_by_tid: dict[str, dict[str, Any]] = {}
    try:
        for doc in franchise_team_data_collection.find(
            {"franchise_id": fid, "team_id": {"$in": oids}},
            {"team_id": 1, "natl_rank": 1, "Recruits": 1},
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

    def _apply_slot(slot_id: Any, canonical_oid_str: str) -> None:
        entry = teams_row_for_team_id(teams_obj, slot_id)
        if not isinstance(entry, dict):
            return

        ftd = ftd_by_tid.get(canonical_oid_str)
        if ftd:
            nr = natl_rank_from_ftd_document(ftd)
            if nr is not None:
                entry["natl_rank"] = nr

        st = standings.get(canonical_oid_str) or {}
        try:
            w = int(st.get("W", 0) or 0)
            ell = int(st.get("L", 0) or 0)
        except (TypeError, ValueError):
            w, ell = 0, 0
        entry["wins"] = w
        entry["losses"] = ell
        entry["team_wins"] = w
        entry["team_losses"] = ell

    for slot_id, canon in slot_to_canonical:
        _apply_slot(slot_id, canon)


def teams_row_for_team_id(teams: Any, tid: Any) -> dict[str, Any] | None:
    """Return ``teams[tid]`` with tolerant key match (ObjectId vs str)."""
    if not isinstance(teams, dict) or tid is None or tid == "":
        return None
    row = teams.get(tid)
    if row is None:
        sid = str(tid)
        for k, v in teams.items():
            if str(k) == sid and isinstance(v, dict):
                return v
    return row if isinstance(row, dict) else None


def team_scoreboard_meta_for_pair(
    home_display_name: str,
    away_display_name: str,
    home_row: Any,
    away_row: Any,
    home_natl: Any,
    away_natl: Any,
) -> dict[str, dict[str, Any]]:
    """
    Court scoreboard: same keys as ``score`` / box score (display team names).
    Each value: natl_rank, wins, losses (optional team_wins / team_losses mirrors).
    """

    def one(row: Any, natl: Any) -> dict[str, Any]:
        rd = row if isinstance(row, dict) else {}
        return {
            "natl_rank": natl,
            "wins": rd.get("wins"),
            "losses": rd.get("losses"),
            "team_wins": rd.get("team_wins", rd.get("wins")),
            "team_losses": rd.get("team_losses", rd.get("losses")),
        }

    return {
        str(home_display_name): one(home_row, home_natl),
        str(away_display_name): one(away_row, away_natl),
    }


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

    def _shard(tid: Any) -> dict[str, Any] | None:
        row = teams_row_for_team_id(teams, tid)
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


def attach_team_scoreboard_meta_by_name_for_simulate(summary: dict[str, Any], gm: Any) -> None:
    """Set ``team_scoreboard_meta`` on simulate response; keys match ``summary[\"score\"]`` (display names)."""
    if not isinstance(summary, dict) or gm is None:
        return
    teams = summary.get("teams") or {}
    hid = summary.get("home_team_id")
    aid = summary.get("away_team_id")
    rh = teams_row_for_team_id(teams, hid)
    ra = teams_row_for_team_id(teams, aid)
    hn = getattr(gm.home_team, "name", None) or (rh or {}).get("name")
    an = getattr(gm.away_team, "name", None) or (ra or {}).get("name")
    if not hn or not an:
        return
    nh = coalesce_natl_rank_from_team_row(rh or {}, None)
    na = coalesce_natl_rank_from_team_row(ra or {}, None)
    summary["team_scoreboard_meta"] = team_scoreboard_meta_for_pair(hn, an, rh, ra, nh, na)
