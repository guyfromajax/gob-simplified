"""
Franchise mode: award geek_points on the owning user's document when their team wins or loses.

Point ranges are documented in _documentation_master/02_User_Account_Systems/Geek_Points_System.md
"""
from __future__ import annotations

import logging
import random
from typing import Any

from bson import ObjectId

from BackEnd.persistence import get_store
_store = get_store()
db = _store.db
users_collection = _store.users_collection
from BackEnd.tournament import franchise_tournament as ft

logger = logging.getLogger(__name__)

SEASON_GP_FIELD = "season_gp"


def season_gp_key(franchise_id: Any, season: Any) -> str | None:
    """``<franchise_id>:<season>`` map key, or None without both parts.

    A dict path like ``trophy_keys``: the SQLite query engine does not traverse
    arrays, and Mongo field names cannot hold ``.`` or start with ``$``.
    """
    fid = str(franchise_id or "").strip()
    if not fid:
        return None
    try:
        season_n = int(season)
    except (TypeError, ValueError):
        return None
    return f"{fid}:{season_n}".replace(".", "_").replace("$", "_")


def season_gp_path(franchise_id: Any, season: Any) -> str | None:
    key = season_gp_key(franchise_id, season)
    return None if key is None else f"{SEASON_GP_FIELD}.{key}"


def _franchise_season_for_award(
    owner_user_id: Any,
    user_team_id_str: str | None,
    week: int,
) -> tuple[Any, Any]:
    """Franchise id + season for a caller that could not pass them.

    Only the CPU-week sim block reaches this: it awards the user's GP from inside
    ``_complete_week_finish_cpu_and_persist``, which this change does not touch.
    One projected read on the owner's franchises; ``week`` separates two saves
    that coach the same team. Ambiguous → career GP still increments, the season
    bucket is skipped.
    """
    if not owner_user_id or not user_team_id_str:
        return None, None
    docs = list(
        db.franchises.find(
            {"user_id": str(owner_user_id), "user_team_object_id": str(user_team_id_str)},
            {"current_season": 1, "week": 1},
        )
    )
    if len(docs) > 1:
        docs = [d for d in docs if int(d.get("week", 0) or 0) == int(week)]
    if len(docs) != 1:
        if docs:
            logger.warning(
                "[GP] season bucket skipped; %s franchises match owner=%s team=%s",
                len(docs), owner_user_id, user_team_id_str,
            )
        return None, None
    return docs[0].get("_id"), docs[0].get("current_season")


def apply_geek_points_delta(
    *,
    owner_user_id: str | None,
    user_team_id_str: str | None,
    delta: int,
    franchise_id: Any = None,
    season: Any = None,
    week: int | None = None,
) -> None:
    """Add ``delta`` to the coach's career total, team bucket and season bucket.

    One ``$inc`` on one doc: the online ``users`` doc, or the save's ``local_coach``
    doc for the desktop principal (same rule and same fields, so Home Base reads
    one shape). The delta is computed once by the caller and written once here.
    """
    if delta <= 0 or not owner_user_id or not user_team_id_str:
        return
    from BackEnd.utils.local_coach import LOCAL_COACH_ID, coach_collection, is_local_owner

    local = is_local_owner(owner_user_id)
    doc_id: Any = LOCAL_COACH_ID
    if not local:
        try:
            doc_id = ObjectId(str(owner_user_id))
        except Exception:
            logger.warning("Invalid owner_user_id for geek_points increment: %s", owner_user_id)
            return

    team_key = geek_points_team_key_for_franchise_user(user_team_id_str)
    inc_fields: dict[str, int] = {"geek_points": delta}
    if team_key:
        # Dot path creates geek_points_by_team and the sub-key on first $inc (lazy).
        inc_fields[f"geek_points_by_team.{team_key}"] = delta
    else:
        logger.warning(
            "geek_points_by_team not incremented; could not resolve team key (user_team_id_str=%r)",
            user_team_id_str,
        )
    if franchise_id is None or season is None:
        franchise_id, season = _franchise_season_for_award(
            owner_user_id, user_team_id_str, int(week or 0)
        )
    path = season_gp_path(franchise_id, season)
    if path:
        inc_fields[path] = delta
    if local:
        # The desktop coach doc is created on its first award.
        coach_collection().update_one({"_id": doc_id}, {"$inc": inc_fields}, upsert=True)
    else:
        users_collection.update_one({"_id": doc_id}, {"$inc": inc_fields})


def _resolve_to_object_id_str(team_ref: Any) -> str | None:
    if team_ref is None:
        return None
    s = str(team_ref).strip()
    if not s:
        return None
    if ObjectId.is_valid(s):
        try:
            return str(ObjectId(s))
        except Exception:
            pass
    doc = db.teams.find_one(
        {"$or": [{"team_id": s}, {"name": s}, {"code": s}]},
        {"_id": 1},
    )
    if doc:
        return str(doc["_id"])
    return None


def geek_points_team_key_for_franchise_user(user_team_object_id_str: str | None) -> str | None:
    """
    Canonical key for users.geek_points_by_team (teams.team_id, e.g. LANCASTER).
    Falls back to str(ObjectId) if team_id is missing on the team document.
    """
    if not user_team_object_id_str:
        return None
    try:
        oid = ObjectId(str(user_team_object_id_str).strip())
    except Exception:
        return None
    doc = db.teams.find_one({"_id": oid}, {"team_id": 1})
    if not doc:
        return None
    tid = doc.get("team_id")
    if isinstance(tid, str) and tid.strip():
        return tid.strip()
    return str(oid)


def teams_match_for_franchise(team_a: Any, team_b: Any) -> bool:
    if team_a is None or team_b is None:
        return False
    if str(team_a) == str(team_b):
        return True
    oid_a = _resolve_to_object_id_str(team_a)
    oid_b = _resolve_to_object_id_str(team_b)
    return bool(oid_a and oid_b and oid_a == oid_b)


def gm_team_matches_ref(gm_team: Any, team_ref: Any) -> bool:
    """True if ``team_ref`` (ObjectId, slug, core name, or display name) identifies ``gm_team``.

    ``TeamManager.name`` is always core; ``display_name`` may be the overlay.
    Used for playbook / team-pick helpers — not the simulate-quarter matchup gate.
    """
    if gm_team is None or team_ref is None:
        return False
    ref = str(team_ref)
    if str(getattr(gm_team, "name", None) or "") == ref:
        return True
    if str(getattr(gm_team, "display_name", None) or "") == ref:
        return True
    return teams_match_for_franchise(team_ref, getattr(gm_team, "team_id", None))


def franchise_win_geek_points_delta(
    week: int,
    eos_game: dict | None,
    *,
    bulk_sim_used: bool = False,
) -> int:
    """Return random GP delta for a qualifying win, or 0 if no rule applies."""
    if week <= ft.REGULAR_SEASON_WEEKS:
        return random.randint(5, 12) if bulk_sim_used else random.randint(13, 20)

    if not eos_game:
        return 0

    phase = eos_game.get("phase")
    rnd = int(eos_game.get("round") or 0)

    if phase == "conference":
        if rnd in (1, 2):
            return apply_bulk_sim_geek_points_policy(
                random.randint(15, 20),
                bulk_sim_used=bulk_sim_used,
            )
        if rnd == 3:
            return apply_bulk_sim_geek_points_policy(
                random.randint(25, 35),
                bulk_sim_used=bulk_sim_used,
            )
    elif phase == "region":
        return apply_bulk_sim_geek_points_policy(
            random.randint(40, 50),
            bulk_sim_used=bulk_sim_used,
        )
    elif phase == "national":
        if rnd in (1, 2):
            return apply_bulk_sim_geek_points_policy(
                random.randint(50, 75),
                bulk_sim_used=bulk_sim_used,
            )
        if rnd == 3:
            return apply_bulk_sim_geek_points_policy(
                random.randint(125, 175),
                bulk_sim_used=bulk_sim_used,
            )

    return 0


def franchise_loss_geek_points_delta(
    week: int,
    eos_game: dict | None,
    *,
    bulk_sim_used: bool = False,
) -> int:
    """Random GP for a franchise game loss (user's team played and did not win)."""
    if week <= ft.REGULAR_SEASON_WEEKS:
        return random.randint(1, 2) if bulk_sim_used else random.randint(3, 4)
    if eos_game:
        return apply_bulk_sim_geek_points_policy(
            random.randint(1, 2),
            bulk_sim_used=bulk_sim_used,
        )
    return 0


def apply_bulk_sim_geek_points_policy(delta: int, *, bulk_sim_used: bool = False) -> int:
    """Apply EOS gameplay-mode GP policy to a final base delta.

    Bulk-sim games keep the existing base award. Games without Sim Full Game /
    Sim Rest of Game receive a 2x award.
    """
    if delta <= 0:
        return 0
    return delta if bulk_sim_used else delta * 2


def maybe_award_franchise_loss_geek_points(
    *,
    owner_user_id: str | None,
    user_team_id_str: str | None,
    winner_team_id: Any,
    participant_team_ids: tuple[Any, ...] | list[Any] | None,
    week: int,
    eos_game_meta: dict | None = None,
    bulk_sim_used: bool = False,
    franchise_id: Any = None,
    season: Any = None,
) -> None:
    """Increment geek_points when the user's franchise team loses a game they participated in."""
    if not owner_user_id or not user_team_id_str:
        return
    if not participant_team_ids:
        return
    if teams_match_for_franchise(winner_team_id, user_team_id_str):
        return
    played = any(teams_match_for_franchise(p, user_team_id_str) for p in participant_team_ids)
    if not played:
        return

    delta = franchise_loss_geek_points_delta(
        week,
        eos_game_meta,
        bulk_sim_used=bulk_sim_used,
    )
    apply_geek_points_delta(
        owner_user_id=owner_user_id,
        user_team_id_str=user_team_id_str,
        delta=delta,
        franchise_id=franchise_id,
        season=season,
        week=week,
    )


def maybe_award_franchise_win_geek_points(
    *,
    owner_user_id: str | None,
    user_team_id_str: str | None,
    winner_team_id: Any,
    week: int,
    eos_game_meta: dict | None,
    bulk_sim_used: bool = False,
    franchise_id: Any = None,
    season: Any = None,
) -> None:
    if not owner_user_id or not user_team_id_str:
        return
    if not teams_match_for_franchise(winner_team_id, user_team_id_str):
        return

    delta = franchise_win_geek_points_delta(
        week,
        eos_game_meta,
        bulk_sim_used=bulk_sim_used,
    )
    apply_geek_points_delta(
        owner_user_id=owner_user_id,
        user_team_id_str=user_team_id_str,
        delta=delta,
        franchise_id=franchise_id,
        season=season,
        week=week,
    )
