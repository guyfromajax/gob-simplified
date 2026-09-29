"""Trophy log: append-only itemised career history on the coach.

Online the list lives on the ``users`` doc; the desktop coach (local-desktop-user)
keeps it on the save's ``save_meta`` ``local_coach`` doc. Same helper, same shape::

    {key, season, kind, team_id, team_name, franchise_id, at, detail?}

``key`` = ``franchise_id:season:kind:team_id[:player_id]``. Each append is one guarded
update on ``trophy_keys.<key>`` (a dict path, so the guard works on Mongo and on the
SQLite query engine, which does not traverse arrays). Retries and idempotent replays
never duplicate. Counts (``championships_total`` …) are untouched here.

Entries are the coach's career: they carry franchise_id/team_name and survive the
franchise being deleted. No backfill — seasons finished before this shipped only
have counts.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from bson import ObjectId

from BackEnd.persistence import get_store
from BackEnd.utils.franchise_team_display import resolve_team_name_map

_store = get_store()
users_collection = _store.users_collection
franchises_collection = _store.franchises_collection

logger = logging.getLogger(__name__)

TROPHIES_FIELD = "trophies"
TROPHY_KEYS_FIELD = "trophy_keys"

TITLE_TROPHY_KINDS = ("conf_rs", "conf_t", "region", "national")
ALL_AMERICAN_KIND_BY_TEAM = {
    "first_team": "all_american_1",
    "second_team": "all_american_2",
    "third_team": "all_american_3",
}
SEASON_RECORD_KIND = "season_record"
TROPHY_KINDS = (
    *TITLE_TROPHY_KINDS,
    *ALL_AMERICAN_KIND_BY_TEAM.values(),
    SEASON_RECORD_KIND,
)


def trophy_key(
    franchise_id: Any, season: Any, kind: str, team_id: Any, player_id: Any = None
) -> str:
    parts = [str(franchise_id), str(int(season)), kind, str(team_id)]
    if player_id is not None and str(player_id):
        parts.append(str(player_id))
    return ":".join(parts)


def _key_path(key: str) -> str:
    # Mongo field names cannot contain "." or start with "$".
    return f"{TROPHY_KEYS_FIELD}." + key.replace(".", "_").replace("$", "_")


def _utc(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def team_display_name(franchise_doc: dict, team_id: Any) -> str:
    """Team Builder display name at award time — never the replaced core name."""
    tid = str(team_id or "")
    name = ""
    try:
        name = resolve_team_name_map(franchise_doc, [tid]).get(tid) or ""
    except Exception:
        logger.exception("[TROPHY] display name lookup failed team_id=%s", tid)
    if not name and tid == str(franchise_doc.get("user_team_object_id") or ""):
        name = str(franchise_doc.get("user_team_id") or "")
    return name


def build_trophy_entry(
    franchise_doc: dict,
    *,
    kind: str,
    team_id: Any,
    detail: Optional[dict] = None,
    player_id: Any = None,
    season: Any = None,
    at: Optional[datetime] = None,
) -> dict:
    fid = str(franchise_doc.get("_id"))
    season_n = int(season if season is not None else franchise_doc.get("current_season", 1) or 1)
    tid = str(team_id)
    entry = {
        "key": trophy_key(fid, season_n, kind, tid, player_id),
        "season": season_n,
        "kind": kind,
        "team_id": tid,
        "team_name": team_display_name(franchise_doc, tid),
        "franchise_id": fid,
        "at": at or datetime.now(timezone.utc),
    }
    if detail:
        entry["detail"] = detail
    return entry


def _coach_target(owner_user_id: Any):
    from BackEnd.utils.local_coach import LOCAL_COACH_ID, coach_collection, is_local_owner

    if is_local_owner(owner_user_id):
        return coach_collection(), LOCAL_COACH_ID, True
    try:
        return users_collection, ObjectId(str(owner_user_id)), False
    except Exception:
        logger.warning("[TROPHY] invalid owner_user_id=%r", owner_user_id)
        return None


def append_trophy(owner_user_id: Any, entry: dict) -> bool:
    """Append ``entry`` once per key. Returns True only when this call added it."""
    if not owner_user_id or entry.get("kind") not in TROPHY_KINDS:
        return False
    target = _coach_target(owner_user_id)
    if target is None:
        return False
    coll, doc_id, local = target
    if local:
        # Upsert cannot share the key guard: a guard miss on an existing doc would
        # try to insert a second doc with the same _id.
        coll.update_one({"_id": doc_id}, {"$setOnInsert": {TROPHIES_FIELD: []}}, upsert=True)
    key_path = _key_path(entry["key"])
    result = coll.update_one(
        {"_id": doc_id, key_path: {"$exists": False}},
        {"$set": {key_path: True}, "$push": {TROPHIES_FIELD: entry}},
    )
    return bool(getattr(result, "modified_count", 0))


def _load_franchise(franchise_id: Any) -> Optional[dict]:
    if franchise_id is None:
        return None
    try:
        oid = franchise_id if isinstance(franchise_id, ObjectId) else ObjectId(str(franchise_id))
    except Exception:
        return None
    return franchises_collection.find_one(
        {"_id": oid},
        {
            "user_id": 1,
            "current_season": 1,
            "user_team_id": 1,
            "user_team_object_id": 1,
            "team_builder": 1,
        },
    )


def record_title_trophy(*, owner_user_id: Any, kind: str, franchise_id: Any) -> bool:
    """Title entry for the franchise's user team; called beside the count increment."""
    if kind not in TITLE_TROPHY_KINDS:
        return False
    franchise_doc = _load_franchise(franchise_id)
    if not franchise_doc or not franchise_doc.get("user_team_object_id"):
        return False
    entry = build_trophy_entry(
        franchise_doc, kind=kind, team_id=franchise_doc["user_team_object_id"]
    )
    return append_trophy(owner_user_id, entry)


def record_all_american_trophies(franchise_doc: dict, awards: dict) -> int:
    """One entry per USER-team player on the first/second/third All-American teams."""
    user_tid = str(franchise_doc.get("user_team_object_id") or "")
    owner = franchise_doc.get("user_id")
    teams = (awards or {}).get("all_american_teams") or {}
    if not user_tid or not owner or not isinstance(teams, dict):
        return 0
    added = 0
    for team_key, kind in ALL_AMERICAN_KIND_BY_TEAM.items():
        for pick in teams.get(team_key) or []:
            if not isinstance(pick, dict) or str(pick.get("team_id") or "") != user_tid:
                continue
            player_id = str(pick.get("player_id") or "")
            if not player_id:
                continue
            entry = build_trophy_entry(
                franchise_doc,
                kind=kind,
                team_id=user_tid,
                player_id=player_id,
                detail={"player_id": player_id, "player_name": pick.get("name") or ""},
            )
            added += int(append_trophy(owner, entry))
    return added


def _round_matchups(bracket_round: Any) -> Iterable[dict]:
    if isinstance(bracket_round, list):
        return [m for m in bracket_round if isinstance(m, dict)]
    return []


def _team_in_round(bracket_round: Any, team_id: str) -> bool:
    return any(
        team_id in (str(m.get("away_team") or ""), str(m.get("home_team") or ""))
        for m in _round_matchups(bracket_round)
    )


def furthest_round_reached(franchise_doc: dict, team_id: Any) -> Optional[str]:
    """Deepest stored bracket round holding ``team_id``; None when no brackets exist."""
    tid = str(team_id or "")
    national = (franchise_doc.get("national_tournament") or {}).get("bracket") or {}
    regions = franchise_doc.get("region_tournaments") or {}
    conferences = franchise_doc.get("conference_tournaments") or {}
    if not (national or regions or conferences):
        return None
    for round_name, label in (
        ("final", "national_final"),
        ("round2", "national_semis"),
        ("round1", "national_quarters"),
    ):
        if _team_in_round(national.get(round_name), tid):
            return label
    for region in regions.values():
        if not isinstance(region, dict):
            continue
        if _team_in_round(region.get("final"), tid):
            return "region_final"
    for region in regions.values():
        if isinstance(region, dict) and _team_in_round(region.get("round1"), tid):
            return "region_semis"
    for round_name, label in (
        ("final", "conference_final"),
        ("round2", "conference_semis"),
        ("round1", "conference_quarters"),
    ):
        for conf in conferences.values():
            bracket = (conf or {}).get("bracket") if isinstance(conf, dict) else None
            if bracket and _team_in_round(bracket.get(round_name), tid):
                return label
    return "missed"


def conference_finish(franchise_doc: dict, team_id: Any) -> Optional[int]:
    """Regular-season conference finish = the seed stored on the conference bracket."""
    tid = str(team_id or "")
    for conf in (franchise_doc.get("conference_tournaments") or {}).values():
        seeds = (conf or {}).get("seeds") if isinstance(conf, dict) else None
        if isinstance(seeds, dict) and tid in {str(k) for k in seeds}:
            for k, v in seeds.items():
                if str(k) == tid:
                    try:
                        return int(v)
                    except (TypeError, ValueError):
                        return None
    return None


def season_record_detail(franchise_doc: dict, team_id: Any) -> dict:
    from BackEnd.utils.franchise_standings import calculate_franchise_standings

    tid = str(team_id or "")
    row = calculate_franchise_standings(franchise_doc.get("results") or {}, {tid: {}}).get(tid) or {}
    detail: dict[str, Any] = {
        "wins": int(row.get("W", 0) or 0),
        "losses": int(row.get("L", 0) or 0),
    }
    finish = conference_finish(franchise_doc, tid)
    if finish is not None:
        detail["conf_finish"] = finish
    furthest = furthest_round_reached(franchise_doc, tid)
    if furthest is not None:
        detail["furthest_round"] = furthest
    return detail


def record_season_record_trophy(franchise_doc: dict) -> bool:
    """One season_record per season; call from finish_season BEFORE the reset."""
    user_tid = franchise_doc.get("user_team_object_id")
    owner = franchise_doc.get("user_id")
    if not user_tid or not owner:
        return False
    entry = build_trophy_entry(
        franchise_doc,
        kind=SEASON_RECORD_KIND,
        team_id=user_tid,
        detail=season_record_detail(franchise_doc, user_tid),
    )
    return append_trophy(owner, entry)


def trophies_newest_first(raw: Any) -> list[dict]:
    """Season desc, then ``at`` desc; ``at`` serialised as ISO-8601 UTC."""
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    rows = [dict(t) for t in (raw or []) if isinstance(t, dict)]
    rows.sort(
        key=lambda t: (int(t.get("season", 0) or 0), _utc(t.get("at")) or epoch),
        reverse=True,
    )
    for row in rows:
        at = _utc(row.get("at"))
        row["at"] = at.isoformat().replace("+00:00", "Z") if at else None
    return rows
