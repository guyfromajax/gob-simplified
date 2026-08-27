"""
Franchise mode: persist championship counts on the owning user's document
and, going forward, on each active-roster FPD for the user team.

User totals are keyed like geek_points_by_team (teams.team_id string, e.g. LANCASTER).
Totals mirror structure: championships_total.<kind>.

Player titles live on franchise_players_data.titles.<kind> and are incremented
only for the user team's active roster at the moment of the award. No backfill.

Kinds: conf_rs (regular-season #1 seed), conf_t, region, national.
"""
from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId

from BackEnd.db import (
    db,
    franchise_players_data_collection,
    franchise_team_data_collection,
    users_collection,
)
from BackEnd.utils.franchise_geek_points import (
    geek_points_team_key_for_franchise_user,
    teams_match_for_franchise,
)

logger = logging.getLogger(__name__)

TITLE_KINDS = ("conf_rs", "conf_t", "region", "national")


def empty_titles() -> dict[str, int]:
    return {kind: 0 for kind in TITLE_KINDS}


def normalize_titles(raw: Any) -> dict[str, int]:
    src = raw if isinstance(raw, dict) else {}
    out = empty_titles()
    for kind in TITLE_KINDS:
        try:
            out[kind] = max(0, int(src.get(kind, 0) or 0))
        except (TypeError, ValueError):
            out[kind] = 0
    return out


def _inc_player_titles(
    *,
    franchise_id: Any,
    user_team_id_str: str | None,
    kind: str,
) -> None:
    """$inc titles.<kind> on the user team's active-roster FPDs. No-op without ids."""
    if kind not in TITLE_KINDS or not franchise_id or not user_team_id_str:
        return
    try:
        fid = ObjectId(str(franchise_id))
        team_oid = ObjectId(str(user_team_id_str).strip())
    except Exception:
        return
    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": team_oid},
        {"players": 1},
    ) or {}
    player_ids = [str(pid) for pid in (ftd_doc.get("players") or []) if pid]
    if not player_ids:
        return
    franchise_players_data_collection.update_many(
        {"franchise_id": str(fid), "player_id": {"$in": player_ids}},
        {"$inc": {f"titles.{kind}": 1}},
    )


def _inc_championship(
    *,
    owner_user_id: str | None,
    user_team_id_str: str | None,
    kind: str,
    franchise_id: Any = None,
) -> None:
    if kind not in TITLE_KINDS:
        return
    if owner_user_id and user_team_id_str:
        try:
            oid = ObjectId(owner_user_id)
        except Exception:
            logger.warning("Invalid owner_user_id for championships increment: %s", owner_user_id)
            oid = None
        if oid is not None:
            team_key = geek_points_team_key_for_franchise_user(user_team_id_str)
            inc_fields: dict[str, int] = {f"championships_total.{kind}": 1}
            if team_key:
                inc_fields[f"championships_by_team.{team_key}.{kind}"] = 1
            else:
                logger.warning(
                    "championships_by_team not incremented; could not resolve team key (user_team_id_str=%r)",
                    user_team_id_str,
                )
            users_collection.update_one({"_id": oid}, {"$inc": inc_fields})
    _inc_player_titles(
        franchise_id=franchise_id,
        user_team_id_str=user_team_id_str,
        kind=kind,
    )


def maybe_award_conference_rs_championship(
    *,
    owner_user_id: str | None,
    user_team_id_str: str | None,
    conference_tournaments: dict[str, Any],
    franchise_id: Any = None,
) -> None:
    """
    Award conf_rs when brackets are built from week 1–26 standings (user's team is #1 seed).
    Call once when initializing conference_tournaments after week 26.
    """
    if not owner_user_id or not user_team_id_str:
        return
    try:
        user_oid = ObjectId(str(user_team_id_str).strip())
    except Exception:
        return
    team_doc = db.teams.find_one({"_id": user_oid}, {"conference": 1})
    if not team_doc:
        return
    conf = team_doc.get("conference")
    if conf is None or not (1 <= int(conf) <= 16):
        return
    ct = conference_tournaments.get(str(int(conf))) or conference_tournaments.get(conf)
    if not isinstance(ct, dict):
        return
    seeds = ct.get("seeds") or {}
    if not isinstance(seeds, dict):
        return
    uid_str = str(user_oid)
    seed = seeds.get(uid_str)
    if seed is None:
        seed = seeds.get(user_team_id_str)
    if seed is None:
        for k, v in seeds.items():
            if teams_match_for_franchise(k, user_team_id_str) and isinstance(v, int):
                seed = v
                break
    if seed != 1:
        return
    _inc_championship(
        owner_user_id=owner_user_id,
        user_team_id_str=user_team_id_str,
        kind="conf_rs",
        franchise_id=franchise_id,
    )


def maybe_award_franchise_eos_title_championship(
    *,
    owner_user_id: str | None,
    user_team_id_str: str | None,
    winner_team_id: Any,
    week: int,
    eos_game_meta: dict | None,
    franchise_id: Any = None,
) -> None:
    """Award conf_t, region, or national when the user's team wins the corresponding final."""
    if not eos_game_meta:
        return
    if not teams_match_for_franchise(winner_team_id, user_team_id_str):
        return
    phase = eos_game_meta.get("phase")
    rnd = int(eos_game_meta.get("round") or 0)
    kind: str | None = None
    if phase == "conference" and rnd == 3:
        kind = "conf_t"
    elif phase == "region" and rnd == 2:
        kind = "region"
    elif phase == "national" and rnd == 3:
        kind = "national"
    if not kind:
        return
    _inc_championship(
        owner_user_id=owner_user_id,
        user_team_id_str=user_team_id_str,
        kind=kind,
        franchise_id=franchise_id,
    )
