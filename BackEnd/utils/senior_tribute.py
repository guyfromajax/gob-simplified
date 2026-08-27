"""Senior Tribute snapshot — graduating active-roster seniors for the FCC reveal.

Built BEFORE finish_season drops those FPDs. Training-squad, practice-squad, and
already-cut players are out. Titles are whatever is already on each FPD (future-forward;
no backfill).
"""
from __future__ import annotations

from typing import Any

from bson import ObjectId

from BackEnd.db import franchise_players_data_collection, franchise_team_data_collection
from BackEnd.utils.franchise_championships import normalize_titles
from BackEnd.utils.scouting_utils import _season_def_pct_whole, _season_total_rebounds


def _is_graduating_year(year_value: Any) -> bool:
    return str(year_value or "").strip().lower() in {"senior", "graduate"}


def _stat_int(block: dict[str, Any], key: str) -> int:
    try:
        return int(block.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _stat_float(block: dict[str, Any], key: str) -> float:
    try:
        return float(block.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _per_game(total: float, games: int) -> float:
    if games <= 0:
        return 0.0
    return round(total / games, 1)


def _best_rt(position_ratings: Any) -> float:
    if not isinstance(position_ratings, dict):
        return -1.0
    best = -1.0
    for value in position_ratings.values():
        try:
            rating = float(value)
        except (TypeError, ValueError):
            continue
        if rating > best:
            best = rating
    return best


def _player_name(meta: dict[str, Any]) -> str:
    first = str(meta.get("first_name") or "").strip()
    last = str(meta.get("last_name") or "").strip()
    return " ".join(part for part in (first, last) if part) or "--"


def _career_rebounds(career: dict[str, Any]) -> float:
    reb = _stat_float(career, "REB")
    if reb:
        return reb
    return _season_total_rebounds(career)


def build_senior_tribute_payload(
    *,
    franchise_id: Any,
    user_team_object_id: str | None,
    current_season: Any = 1,
) -> dict[str, Any]:
    """Active-roster graduating seniors, RT descending, with career rates + titles."""
    try:
        season = int(current_season or 1)
    except (TypeError, ValueError):
        season = 1
    empty = {"season": max(1, season), "players": []}
    if not franchise_id or not user_team_object_id:
        return empty
    try:
        fid = ObjectId(str(franchise_id))
        team_oid = ObjectId(str(user_team_object_id).strip())
    except Exception:
        return empty

    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": team_oid},
        {"players": 1},
    ) or {}
    roster_ids = [str(pid) for pid in (ftd_doc.get("players") or []) if pid]
    if not roster_ids:
        return empty

    fpd_docs = list(
        franchise_players_data_collection.find(
            {"franchise_id": str(fid), "player_id": {"$in": roster_ids}},
            {"player_id": 1, "meta": 1, "career": 1, "position_ratings": 1, "titles": 1},
        )
    )
    fpd_by_id = {str(doc.get("player_id")): doc for doc in fpd_docs if doc.get("player_id")}

    players: list[dict[str, Any]] = []
    for player_id in roster_ids:
        fpd = fpd_by_id.get(player_id)
        if not fpd:
            continue
        meta = fpd.get("meta") or {}
        if not _is_graduating_year(meta.get("year")):
            continue
        career = fpd.get("career") if isinstance(fpd.get("career"), dict) else {}
        games = _stat_int(career, "GP")
        titles = normalize_titles(fpd.get("titles"))
        players.append(
            {
                "player_id": player_id,
                "name": _player_name(meta),
                "rt": _best_rt(fpd.get("position_ratings")),
                "ppg": _per_game(_stat_float(career, "PTS"), games),
                "rpg": _per_game(_career_rebounds(career), games),
                "apg": _per_game(_stat_float(career, "AST"), games),
                "def_pct": _season_def_pct_whole(career),
                "titles": titles,
            }
        )

    players.sort(key=lambda row: (-float(row.get("rt") or -1), str(row.get("name") or "")))
    for row in players:
        try:
            row["rt"] = int(round(float(row["rt"])))
        except (TypeError, ValueError):
            row["rt"] = 0
    return {"season": max(1, season), "players": players}
