"""
One-off / admin repair: fill EOS bracket slots from ``results.{week}`` (and optionally ``games``).

Safe defaults: only updates slots that still have no ``winner``; requires a decisive result row
or an existing ``games`` document. See ``scripts/repair_franchise_eos_bracket_from_results.py``.
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from bson import ObjectId

from BackEnd.db import db as default_db
from BackEnd.tournament import bracket_engine
from BackEnd.tournament import franchise_tournament as ft

logger = logging.getLogger(__name__)


def _pair_set(away_id: Any, home_id: Any) -> frozenset[str]:
    return frozenset({ft._eos_team_id_canonical(away_id), ft._eos_team_id_canonical(home_id)})


def find_results_row_for_pair(
    results_week: List[dict] | None,
    away_id: Any,
    home_id: Any,
) -> Optional[dict]:
    if not results_week:
        return None
    want = _pair_set(away_id, home_id)
    for r in results_week:
        if not isinstance(r, dict):
            continue
        got = _pair_set(r.get("away_id"), r.get("home_id"))
        if got == want:
            return r
    return None


def _row_has_decisive_scores(row: dict) -> bool:
    ah = int(row.get("away_score", 0) or 0)
    hs = int(row.get("home_score", 0) or 0)
    return ah != hs


def build_synthetic_game_doc_from_result_row(
    row: dict,
    away_id: Any,
    home_id: Any,
) -> dict[str, Any]:
    """Shape compatible with ``_sync_eos_bracket_from_existing_game_doc`` (team1 = away, team2 = home)."""
    gid = row.get("game_id")
    oid = gid if gid is not None else ObjectId()
    if isinstance(oid, str) and oid.strip() == "":
        oid = ObjectId()
    return {
        "_id": oid,
        "team1_id": away_id,
        "team2_id": home_id,
        "team1_score": int(row.get("away_score", 0) or 0),
        "team2_score": int(row.get("home_score", 0) or 0),
    }


def find_franchise_game_doc(
    mongo_db,
    *,
    franchise_id_str: str,
    week: int,
    away_id: Any,
    home_id: Any,
) -> Optional[dict]:
    ca = ft._eos_team_id_canonical(away_id)
    ch = ft._eos_team_id_canonical(home_id)
    if not ca or not ch:
        return None
    a_oid = ObjectId(ca) if ObjectId.is_valid(ca) else ca
    h_oid = ObjectId(ch) if ObjectId.is_valid(ch) else ch
    return mongo_db.games.find_one(
        {
            "week": week,
            "franchise_id": franchise_id_str,
            "$or": [
                {"team1_id": a_oid, "team2_id": h_oid},
                {"team1_id": h_oid, "team2_id": a_oid},
            ],
        }
    )


def get_bracket_winner_for_eos_meta(franchise_doc: dict, g: dict) -> Any:
    """Return bracket ``winner`` for this EOS meta row, or ``None`` if missing / OOB."""
    phase = g.get("phase")
    if phase == "conference":
        ct = ft._get_conference_tournament_ct(franchise_doc, int(g["conference"]))
        if not ct:
            return None
        br = ct.get("bracket") or {}
        rn = bracket_engine.get_round_name(int(g["round"]))
        lst = br.get(rn) or []
        i = int(g.get("matchup_index", 0))
        if i < 0 or i >= len(lst):
            return None
        return (lst[i] or {}).get("winner")
    if phase == "region":
        rt = (franchise_doc.get("region_tournaments") or {}).get(g["region"]) or {}
        rnum = int(g["round"])
        if rnum == 1:
            lst = rt.get("round1") or []
            i = int(g.get("matchup_index", 0))
            if 0 <= i < len(lst):
                return (lst[i] or {}).get("winner")
            return None
        if rnum == 2:
            fin = rt.get("final") or []
            if fin:
                return (fin[0] or {}).get("winner")
        return None
    if phase == "national":
        nat = franchise_doc.get("national_tournament") or {}
        br = nat.get("bracket") or {}
        rn = bracket_engine.get_round_name(int(g["round"]))
        lst = br.get(rn) or []
        i = int(g.get("matchup_index", 0))
        if 0 <= i < len(lst):
            return (lst[i] or {}).get("winner")
    return None


def repair_franchise_eos_bracket_from_results(
    franchise_doc: dict,
    *,
    mongo_db: Any = None,
    weeks: Optional[Sequence[int]] = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    For each EOS ``week``, each ``get_eos_week_games(..., include_completed=True)`` slot with no
    bracket ``winner``, apply ``_sync_eos_bracket_from_existing_game_doc`` (which delegates to
    ``record_tournament_game_result``) when ``results.{week}``
    has a decisive row and/or ``games`` has the matchup.

    Mutates ``franchise_doc`` in place when ``dry_run`` is False and persists EOS keys to Mongo.
    When ``dry_run`` is True, operates on a deep copy and does not write.
    """
    from BackEnd.api.franchise_routes import _sync_eos_bracket_from_existing_game_doc

    mongo = mongo_db if mongo_db is not None else default_db
    fid = franchise_doc.get("_id")
    if fid is None:
        raise ValueError("franchise_doc must include _id")
    franchise_id_str = str(fid)

    week_list: Tuple[int, ...] = tuple(weeks) if weeks is not None else ft.EOS_WEEKS

    work_doc = copy.deepcopy(franchise_doc) if dry_run else franchise_doc
    before_eos = {
        "conference_tournaments": copy.deepcopy(work_doc.get("conference_tournaments")),
        "region_tournaments": copy.deepcopy(work_doc.get("region_tournaments")),
        "national_tournament": copy.deepcopy(work_doc.get("national_tournament")),
    }

    applied: List[dict[str, Any]] = []
    skipped: List[dict[str, Any]] = []

    results_root = work_doc.get("results") or {}

    for week in week_list:
        if week not in ft.EOS_WEEKS:
            skipped.append({"week": week, "reason": "not_eos_week"})
            continue
        wk = str(int(week))
        results_week = results_root.get(wk) or results_root.get(week)
        if not results_week:
            skipped.append({"week": week, "reason": "no_results"})
            continue

        meta = ft.get_eos_week_games(work_doc, int(week), include_completed=True)
        for idx, g in enumerate(meta):
            if not isinstance(g, dict) or not g.get("phase"):
                continue
            wcur = get_bracket_winner_for_eos_meta(work_doc, g)
            if wcur:
                continue

            away_id = g.get("away_id")
            home_id = g.get("home_id")
            row = find_results_row_for_pair(results_week, away_id, home_id)
            existing = find_franchise_game_doc(
                mongo,
                franchise_id_str=franchise_id_str,
                week=int(week),
                away_id=away_id,
                home_id=home_id,
            )

            if existing is None and row is None:
                skipped.append({"week": week, "idx": idx, "reason": "no_row_no_game", "g": _g_preview(g)})
                continue
            if existing is None and row is not None and not _row_has_decisive_scores(row):
                skipped.append({"week": week, "idx": idx, "reason": "tie_or_missing_scores", "g": _g_preview(g)})
                continue

            use_existing = existing if existing is not None else build_synthetic_game_doc_from_result_row(row, away_id, home_id)
            _sync_eos_bracket_from_existing_game_doc(
                work_doc,
                existing=use_existing,
                away_id=away_id,
                home_id=home_id,
                g=g,
                week=int(week),
                franchise_id_str=franchise_id_str,
            )
            applied.append(
                {
                    "week": week,
                    "idx": idx,
                    "phase": g.get("phase"),
                    "from_game": existing is not None,
                    "preview": _g_preview(g),
                }
            )

    after_eos = {
        "conference_tournaments": copy.deepcopy(work_doc.get("conference_tournaments")),
        "region_tournaments": copy.deepcopy(work_doc.get("region_tournaments")),
        "national_tournament": copy.deepcopy(work_doc.get("national_tournament")),
    }
    changed = before_eos != after_eos

    update_fields: dict[str, Any] = {}
    if changed:
        if work_doc.get("conference_tournaments") is not None:
            update_fields["conference_tournaments"] = work_doc["conference_tournaments"]
        if work_doc.get("region_tournaments") is not None:
            update_fields["region_tournaments"] = work_doc["region_tournaments"]
        if work_doc.get("national_tournament") is not None:
            update_fields["national_tournament"] = work_doc["national_tournament"]

    if not dry_run and update_fields:
        mongo.franchises.update_one({"_id": fid}, {"$set": update_fields})

    return {
        "franchise_id": franchise_id_str,
        "dry_run": dry_run,
        "changed": changed,
        "applied_count": len(applied),
        "applied": applied,
        "skipped_sample": skipped[:50],
        "skipped_total": len(skipped),
    }


def _g_preview(g: dict) -> str:
    return (
        f"{g.get('phase')} c={g.get('conference')} r={g.get('region')} "
        f"round={g.get('round')} mi={g.get('matchup_index')}"
    )
