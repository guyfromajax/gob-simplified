"""
Lazy recruit-image paint endpoints — generate-on-miss.

Player/recruit portraits are painted the first time they're actually needed and
cached in R2 forever after. The frontend requests the normal CDN image URL; on a
404 it calls one of these endpoints, which paints the master from the recruit's
KIT (already in R2) and uploads it, then the frontend retries the CDN URL.

Two masters:
  - WHITE display master (recruits/white/<image_id>.png)  — un-signed recruits.
  - UNIFORMED master (players/master/<player_id>.png)      — signed players.

Everything degrades gracefully: unconfigured R2, missing kit, walk-on with no
portrait, etc. all return a status the frontend treats as "use the generic
headshot" — never a 500. No AI: the paint is a deterministic recolor.
"""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from BackEnd.db import db, franchise_players_data_collection
from BackEnd.services import recruit_image, r2_images
from BackEnd.utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

WEEK_35_RECRUITING_RESULTS_FIELD = "week_35_recruiting_results"


class EnsurePlayerImageRequest(BaseModel):
    franchise_id: str
    player_id: str


class EnsureRecruitImageRequest(BaseModel):
    image_id: str


def _maybe_objid(value):
    try:
        from bson import ObjectId
        return ObjectId(value)
    except Exception:
        return None


def _resolve_signed(franchise_id: str, player_id: str):
    """(image_id, team_id) for a signed player, or (None, None). Rostered players
    resolve from FPD.meta; a just-signed player (week 36, pre-rollover) resolves
    from the franchise's week_35 signed_players."""
    fpd = franchise_players_data_collection.find_one(
        {"franchise_id": str(franchise_id), "player_id": str(player_id)}, {"meta": 1})
    meta = (fpd or {}).get("meta") or {}
    if meta.get("image_id"):
        return meta.get("image_id"), meta.get("team_id")

    fdoc = None
    for qid in (_maybe_objid(franchise_id), str(franchise_id)):
        if qid is None:
            continue
        fdoc = db.franchises.find_one({"_id": qid}, {f"{WEEK_35_RECRUITING_RESULTS_FIELD}.signed_players": 1})
        if fdoc:
            break
    signed = ((fdoc or {}).get(WEEK_35_RECRUITING_RESULTS_FIELD) or {}).get("signed_players") or []
    for s in signed:
        if str(s.get("player_id")) == str(player_id):
            return s.get("image_id"), s.get("team_id")
    return None, None


def delete_signed_masters_for_franchise(franchise_id) -> int:
    """Best-effort GC of a deleted franchise's signed-recruit uniform masters in R2.

    Only removes players/master/<player_id>.png for THIS franchise's signed
    recruits — identified by their FPD doc carrying meta.image_id. That is safe on
    two counts: (1) a signed player's player_id is a fresh per-franchise uuid, so a
    key can never belong to another franchise; (2) original/universal players have
    no image_id, so their shared masters are never touched. The shared uniform
    cache (recruits/uniform-cache/...) is also left intact. Never raises — a portrait
    GC failure must not block the franchise delete. Returns count removed.

    Call BEFORE deleting the franchise's FPD docs (it reads them to find the keys).
    """
    if not r2_images.is_configured():
        return 0
    deleted = 0
    try:
        cursor = franchise_players_data_collection.find(
            {"franchise_id": str(franchise_id), "meta.image_id": {"$exists": True, "$ne": None}},
            {"player_id": 1},
        )
        for doc in cursor:
            pid = doc.get("player_id")
            if not pid:
                continue
            try:
                if r2_images.delete(f"players/master/{pid}.png"):
                    deleted += 1
            except Exception:
                logger.exception("[IMG-GC] delete failed franchise_id=%s player_id=%s",
                                 str(franchise_id), pid)
    except Exception:
        logger.exception("[IMG-GC] scan failed franchise_id=%s", str(franchise_id))
    if deleted:
        logger.info("[IMG-GC] removed %s signed masters franchise_id=%s", deleted, str(franchise_id))
    return deleted


@router.post("/player-image/ensure")
def ensure_player_image(req: EnsurePlayerImageRequest, user: dict = Depends(get_current_user)):
    """Paint a signed player's uniformed master into R2 if it's missing."""
    if not r2_images.is_configured():
        return {"status": "unconfigured"}
    master_key = f"players/master/{req.player_id}.png"
    try:
        if r2_images.exists(master_key):
            return {"status": "exists"}
        image_id, team_id = _resolve_signed(req.franchise_id, req.player_id)
        if not image_id:
            return {"status": "generic"}          # walk-on / dynamic with no library
        kit_keys = None
        try:
            from BackEnd.utils.team_builder_portraits import resolve_kit_keys

            kit_keys = resolve_kit_keys(image_id)
        except Exception:
            kit_keys = None
        if kit_keys:
            kit_key, mask_key = kit_keys
        else:
            kit_key = f"recruits/kit/{image_id}.png"
            mask_key = f"recruits/kit/{image_id}.mask.png"
        if not (r2_images.exists(kit_key) and r2_images.exists(mask_key)):
            return {"status": "no_kit"}
        team = db.teams.find_one({"_id": _maybe_objid(team_id)}) if team_id else None
        if not team:
            return {"status": "no_team"}
        from BackEnd.utils.franchise_team_display import resolve_team_display

        disp = resolve_team_display(req.franchise_id, team_id, core_doc=team)
        master = recruit_image.make_signed_master(
            r2_images.get(kit_key), r2_images.get(mask_key),
            disp.get("primary_color") or team.get("primary_color", "#000000"),
            disp.get("secondary_color") or team.get("secondary_color", "#ffffff"),
            disp.get("mascot") if disp.get("mascot") is not None else team.get("mascot", ""),
        )
        r2_images.put(master_key, master)
        franchise_players_data_collection.update_one(
            {"franchise_id": str(req.franchise_id), "player_id": str(req.player_id)},
            {"$set": {"meta.image_painted": True}})
        return {"status": "painted"}
    except Exception as e:  # noqa: BLE001 — never 500 a portrait; fall back to generic
        logger.exception("paint failed for player %s", req.player_id)
        return {"status": "error", "detail": str(e)[:200]}


@router.post("/recruit-image/ensure")
def ensure_recruit_image(req: EnsureRecruitImageRequest, user: dict = Depends(get_current_user)):
    """Paint an un-signed recruit's finished WHITE display master into R2 if missing."""
    if not r2_images.is_configured():
        return {"status": "unconfigured"}
    white_key = f"recruits/white/{req.image_id}.png"
    try:
        if r2_images.exists(white_key):
            return {"status": "exists"}
        kit_keys = None
        try:
            from BackEnd.utils.team_builder_portraits import resolve_kit_keys

            kit_keys = resolve_kit_keys(req.image_id)
        except Exception:
            kit_keys = None
        kit_key = kit_keys[0] if kit_keys else f"recruits/kit/{req.image_id}.png"
        if not r2_images.exists(kit_key):
            return {"status": "no_kit"}
        r2_images.put(white_key, recruit_image.make_white_master(r2_images.get(kit_key)))
        return {"status": "painted"}
    except Exception as e:  # noqa: BLE001
        logger.exception("white paint failed for image %s", req.image_id)
        return {"status": "error", "detail": str(e)[:200]}
