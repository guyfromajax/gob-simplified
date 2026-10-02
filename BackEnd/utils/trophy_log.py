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
ALL_CONFERENCE_KIND_BY_TEAM = {
    "first_team": "all_conference_1",
    "second_team": "all_conference_2",
}
SEASON_RECORD_KIND = "season_record"
# Once per COACH, so the key carries neither franchise nor season.
MILESTONE_KINDS = (
    "milestone_first_signing_class",
    "milestone_first_bracket",
    "milestone_first_archetype",
)
TROPHY_KINDS = (
    *TITLE_TROPHY_KINDS,
    *ALL_AMERICAN_KIND_BY_TEAM.values(),
    *ALL_CONFERENCE_KIND_BY_TEAM.values(),
    SEASON_RECORD_KIND,
    *MILESTONE_KINDS,
)


def trophy_key(
    franchise_id: Any, season: Any, kind: str, team_id: Any, player_id: Any = None
) -> str:
    if kind in MILESTONE_KINDS:
        return milestone_key(kind)
    parts = [str(franchise_id), str(int(season)), kind, str(team_id)]
    if player_id is not None and str(player_id):
        parts.append(str(player_id))
    return ":".join(parts)


def milestone_key(kind: str) -> str:
    """A milestone is a career first, so its key names neither program nor season."""
    return f"coach:{kind}"


def _storage_key(key: str) -> str:
    # Mongo field names cannot contain "." or start with "$".
    return key.replace(".", "_").replace("$", "_")


def _key_path(key: str) -> str:
    return f"{TROPHY_KEYS_FIELD}.{_storage_key(key)}"


# ``_id: 0`` so the read is the map alone, not the rest of the coach doc.
TROPHY_KEYS_PROJECTION = {TROPHY_KEYS_FIELD: 1, "_id": 0}


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


def _user_picks(franchise_doc: dict, teams: Any, kind_by_team: dict[str, str]) -> list[tuple[str, dict]]:
    """``(kind, pick)`` for USER-team players on the given teams."""
    user_tid = str(franchise_doc.get("user_team_object_id") or "")
    owner = franchise_doc.get("user_id")
    if not user_tid or not owner or not isinstance(teams, dict):
        return []
    picks: list[tuple[str, dict]] = []
    for team_key, kind in kind_by_team.items():
        for pick in teams.get(team_key) or []:
            if not isinstance(pick, dict) or str(pick.get("team_id") or "") != user_tid:
                continue
            if str(pick.get("player_id") or ""):
                picks.append((kind, pick))
    return picks


def _user_all_american_picks(franchise_doc: dict, awards: dict) -> list[tuple[str, dict]]:
    """``(kind, pick)`` for USER-team players on the three All-American teams."""
    return _user_picks(franchise_doc, (awards or {}).get("all_american_teams"), ALL_AMERICAN_KIND_BY_TEAM)


def _user_all_conference_picks(franchise_doc: dict, awards: dict) -> list[tuple[str, dict]]:
    """``(kind, pick)`` for USER-team players on the two All-Conference teams of the
    user's conference (the final, ``all_conference_teams``, keyed by conference)."""
    by_conference = (awards or {}).get("all_conference_teams") or {}
    if not isinstance(by_conference, dict):
        return []
    picks: list[tuple[str, dict]] = []
    for teams in by_conference.values():
        picks.extend(_user_picks(franchise_doc, teams, ALL_CONFERENCE_KIND_BY_TEAM))
    return picks


def expected_all_american_storage_keys(franchise_doc: dict, awards: dict) -> set[str]:
    """``trophy_keys`` map keys for the user-team All-Americans on ``awards``."""
    user_tid = str(franchise_doc.get("user_team_object_id") or "")
    if not user_tid:
        return set()
    fid = str(franchise_doc.get("_id"))
    season = int(franchise_doc.get("current_season", 1) or 1)
    return {
        _storage_key(trophy_key(fid, season, kind, user_tid, str(pick.get("player_id"))))
        for kind, pick in _user_all_american_picks(franchise_doc, awards)
    }


def read_trophy_keys(owner_user_id: Any) -> set[str]:
    """One projected read of ``trophy_keys``. Empty when the coach doc or field is absent."""
    target = _coach_target(owner_user_id)
    if target is None:
        return set()
    coll, doc_id, _local = target
    doc = coll.find_one({"_id": doc_id}, TROPHY_KEYS_PROJECTION) or {}
    raw = doc.get(TROPHY_KEYS_FIELD) or {}
    if not isinstance(raw, dict):
        return set()
    return {str(key) for key in raw}


def record_all_american_trophies(franchise_doc: dict, awards: dict) -> int:
    """One entry per USER-team player on the first/second/third All-American teams."""
    user_tid = str(franchise_doc.get("user_team_object_id") or "")
    owner = franchise_doc.get("user_id")
    picks = _user_all_american_picks(franchise_doc, awards)
    if not user_tid or not owner or not picks:
        return 0
    added = 0
    for kind, pick in picks:
        player_id = str(pick.get("player_id") or "")
        entry = build_trophy_entry(
            franchise_doc,
            kind=kind,
            team_id=user_tid,
            player_id=player_id,
            detail={"player_id": player_id, "player_name": pick.get("name") or ""},
        )
        added += int(append_trophy(owner, entry))
    return added


def expected_all_conference_storage_keys(franchise_doc: dict, awards: dict) -> set[str]:
    user_tid = str(franchise_doc.get("user_team_object_id") or "")
    if not user_tid:
        return set()
    fid = str(franchise_doc.get("_id"))
    season = int(franchise_doc.get("current_season", 1) or 1)
    return {
        _storage_key(trophy_key(fid, season, kind, user_tid, str(pick.get("player_id"))))
        for kind, pick in _user_all_conference_picks(franchise_doc, awards)
    }


def record_all_conference_trophies(franchise_doc: dict, awards: dict) -> int:
    """One entry per USER-team player on the All-Conference first / second team. A
    player on an All-American team too gets both entries."""
    user_tid = str(franchise_doc.get("user_team_object_id") or "")
    owner = franchise_doc.get("user_id")
    picks = _user_all_conference_picks(franchise_doc, awards)
    if not user_tid or not owner or not picks:
        return 0
    added = 0
    for kind, pick in picks:
        player_id = str(pick.get("player_id") or "")
        entry = build_trophy_entry(
            franchise_doc,
            kind=kind,
            team_id=user_tid,
            player_id=player_id,
            detail={"player_id": player_id, "player_name": pick.get("name") or ""},
        )
        added += int(append_trophy(owner, entry))
    return added


def record_all_conference_trophies_if_missing(franchise_doc: dict, awards: dict) -> int:
    """Append user-team All-Conference entries only when a key is missing."""
    owner = franchise_doc.get("user_id")
    if not owner:
        return 0
    expected = expected_all_conference_storage_keys(franchise_doc, awards)
    if not expected:
        return 0
    if expected <= read_trophy_keys(owner):
        return 0
    return record_all_conference_trophies(franchise_doc, awards)


def record_all_american_trophies_if_missing(franchise_doc: dict, awards: dict) -> int:
    """Append user-team All-Americans only when a key is missing.

    One projected ``trophy_keys`` read. When every expected key is already in that
    map the guarded updates are skipped, so a week-35 Office load does not write.
    A save whose awards were stored before the trophy log still catches up: the
    keys are absent, so this records once. The map is the same guard ``append_trophy``
    uses, so a replay cannot duplicate an entry.
    """
    expected = expected_all_american_storage_keys(franchise_doc, awards)
    if not expected:
        return 0
    if expected <= read_trophy_keys(franchise_doc.get("user_id")):
        return 0
    return record_all_american_trophies(franchise_doc, awards)


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
    """The season the review reads, snapshotted off the franchise before the reset.

    Record, conference finish and furthest round come from the stored results and
    brackets; the rest (final national rank, region seed, season Geek Points, best
    players, signed class) from ``career_data``. Any field whose source is not on
    this save is omitted.
    """
    from BackEnd.utils.career_data import season_review_snapshot
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
    try:
        detail.update(season_review_snapshot(franchise_doc, tid))
    except Exception:
        logger.exception(
            "[TROPHY] season review snapshot failed franchise_id=%s", str(franchise_doc.get("_id"))
        )
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


def record_milestone(franchise_doc: dict, kind: str, detail: Optional[dict] = None) -> bool:
    """Append a career-first milestone once per coach, through the same key guard."""
    if kind not in MILESTONE_KINDS:
        return False
    owner = franchise_doc.get("user_id")
    user_tid = franchise_doc.get("user_team_object_id")
    if not owner or not user_tid:
        return False
    entry = build_trophy_entry(franchise_doc, kind=kind, team_id=user_tid, detail=detail)
    return append_trophy(owner, entry)


def record_first_signing_class_milestone(franchise_doc: dict, signed_players: Any) -> bool:
    """First class signed — the user team's non-walk-on signings at week 35."""
    user_tid = str(franchise_doc.get("user_team_object_id") or "")
    signed = [
        player
        for player in (signed_players or [])
        if isinstance(player, dict)
        and not player.get("walk_on")
        and str(player.get("team_id") or "") == user_tid
    ]
    if not signed:
        return False
    return record_milestone(
        franchise_doc, "milestone_first_signing_class", detail={"signed": len(signed)}
    )


def record_first_bracket_milestone(franchise_doc: dict, conference_tournaments: Any) -> bool:
    """First bracket — the user team appears in a conference bracket for the first time."""
    tid = str(franchise_doc.get("user_team_object_id") or "")
    if not tid:
        return False
    for conf in (conference_tournaments or {}).values():
        bracket = (conf or {}).get("bracket") if isinstance(conf, dict) else None
        if not isinstance(bracket, dict):
            continue
        for round_name in ("round1", "round2", "final"):
            if _team_in_round(bracket.get(round_name), tid):
                seed = conference_finish({"conference_tournaments": conference_tournaments}, tid)
                detail = {"seed": seed} if seed is not None else None
                return record_milestone(franchise_doc, "milestone_first_bracket", detail=detail)
    return False


def record_first_archetype_milestone(franchise_doc: dict, archetype: str) -> bool:
    """First archetype — the coach's lead archetype is established for the first time."""
    key = str(archetype or "").strip()
    if not key:
        return False
    return record_milestone(
        franchise_doc, "milestone_first_archetype", detail={"archetype": key}
    )


def title_trophies_for_season(franchise_doc: dict) -> list[dict]:
    """Title trophies already on the coach for this franchise + current season.

    Same source the Trophy Case review filters client-side from coach-career.
    """
    owner = franchise_doc.get("user_id") if isinstance(franchise_doc, dict) else None
    fid = str((franchise_doc or {}).get("_id") or "")
    try:
        season_n = int((franchise_doc or {}).get("current_season") or 1)
    except (TypeError, ValueError):
        season_n = 1
    if not owner or not fid:
        return []
    target = _coach_target(owner)
    if target is None:
        return []
    coll, doc_id, _local = target
    try:
        doc = coll.find_one({"_id": doc_id}, {TROPHIES_FIELD: 1}) or {}
    except Exception:
        logger.exception("[TROPHY] title trophies read failed franchise_id=%s", fid)
        return []
    rows = []
    for trophy in doc.get(TROPHIES_FIELD) or []:
        if not isinstance(trophy, dict):
            continue
        if trophy.get("kind") not in TITLE_TROPHY_KINDS:
            continue
        if str(trophy.get("franchise_id") or "") != fid:
            continue
        try:
            if int(trophy.get("season") or 0) != season_n:
                continue
        except (TypeError, ValueError):
            continue
        rows.append(trophy)
    return trophies_newest_first(rows)


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
