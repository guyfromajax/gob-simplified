"""
Franchise mode: persist championship counts on the owning user's document.

Counts are keyed like geek_points_by_team (teams.team_id string, e.g. LANCASTER).
Totals mirror structure: championships_total.<kind>.

Kinds: conf_rs (regular-season #1 seed), conf_t, region, national.
"""
from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId

from BackEnd.db import db, users_collection
from BackEnd.utils.franchise_geek_points import (
    geek_points_team_key_for_franchise_user,
    teams_match_for_franchise,
)

logger = logging.getLogger(__name__)


def _inc_championship(
    *,
    owner_user_id: str | None,
    user_team_id_str: str | None,
    kind: str,
) -> None:
    if kind not in ("conf_rs", "conf_t", "region", "national"):
        return
    if not owner_user_id or not user_team_id_str:
        return
    try:
        oid = ObjectId(owner_user_id)
    except Exception:
        logger.warning("Invalid owner_user_id for championships increment: %s", owner_user_id)
        return

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


def maybe_award_conference_rs_championship(
    *,
    owner_user_id: str | None,
    user_team_id_str: str | None,
    conference_tournaments: dict[str, Any],
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
    _inc_championship(owner_user_id=owner_user_id, user_team_id_str=user_team_id_str, kind="conf_rs")


def maybe_award_franchise_eos_title_championship(
    *,
    owner_user_id: str | None,
    user_team_id_str: str | None,
    winner_team_id: Any,
    week: int,
    eos_game_meta: dict | None,
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
    _inc_championship(owner_user_id=owner_user_id, user_team_id_str=user_team_id_str, kind=kind)
