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

from fastapi import APIRouter, BackgroundTasks, Depends
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


class WarmTeamsRequest(BaseModel):
    """Teams may be identified by ObjectId string OR by name.

    The Set Lineup screen holds the user's team_id but only the opponent's display
    name, so accepting either avoids a lookup round trip on the client.
    """
    franchise_id: str
    teams: list[str]


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


def collect_franchise_master_keys(franchise_id) -> list[str]:
    """Return the R2 master keys owned by one franchise, for GC on delete.

    A key qualifies when its FPD doc carries ``meta.image_id`` — that covers signed
    recruits AND walk-ons promoted onto an active roster (see
    BackEnd/utils/walk_on_roster_identity.py, which stamps meta.image_id league-wide
    per franchise and paints players/master/<player_id>.png for each). Safe to delete
    because a signed/walk-on player_id is a fresh per-franchise uuid, so a key can
    never belong to another franchise; original/universal players carry no image_id,
    so their shared masters are never touched. The shared uniform archive
    (uniforms/..., recruits/uniform-cache/...) is left intact.

    MUST be called BEFORE the franchise's FPD docs are deleted — it reads them to
    find the keys. Never raises; returns [] on any scan failure, and short-circuits
    when R2 is unconfigured so no franchise delete pays for a pointless scan.
    """
    if not r2_images.is_configured():
        return []
    try:
        cursor = franchise_players_data_collection.find(
            {"franchise_id": str(franchise_id), "meta.image_id": {"$exists": True, "$ne": None}},
            {"player_id": 1},
        )
        return [
            f"players/master/{doc['player_id']}.png"
            for doc in cursor
            if doc.get("player_id")
        ]
    except Exception:
        logger.exception("[IMG-GC] scan failed franchise_id=%s", str(franchise_id))
        return []


def delete_master_keys(keys, franchise_id=None) -> int:
    """Batch-delete master keys collected by :func:`collect_franchise_master_keys`.

    One DeleteObjects round trip per 1000 keys instead of two per player — a
    league-wide franchise can carry hundreds of walk-on masters, and the old
    per-key head+delete loop is what made franchise delete run for minutes.
    Never raises: portrait GC must not block or fail a franchise delete.
    """
    if not keys or not r2_images.is_configured():
        return 0
    try:
        removed = r2_images.delete_many(keys)
    except Exception:
        logger.exception("[IMG-GC] batch delete failed franchise_id=%s", str(franchise_id))
        return 0
    if removed:
        logger.info("[IMG-GC] removed %s masters franchise_id=%s", removed, str(franchise_id))
    return removed


def delete_signed_masters_for_franchise(franchise_id) -> int:
    """Synchronous collect + batch-delete of one franchise's masters. Returns count.

    Kept for callers that wipe inline (admin reset). The franchise-delete route
    splits the two halves instead so the DB cascade is not held up by R2.
    """
    if not r2_images.is_configured():
        return 0
    return delete_master_keys(collect_franchise_master_keys(franchise_id), franchise_id)


@router.post("/player-image/ensure")
def ensure_player_image(req: EnsurePlayerImageRequest, user: dict = Depends(get_current_user)):
    """Ensure a signed player's uniformed portrait exists, via the shared archive.

    The painted artifact lives at ``uniforms/<image_id>__<color_key>.png`` and is
    shared by every franchise whose player wears that portrait in those colours —
    see _documentation_master/projects/Uniform_Archive_Brief.md. The legacy
    ``players/master/<player_id>.png`` key is MIRRORED from it with a server-side
    copy so existing read paths keep resolving while payloads are threaded with
    uniform_key. The mirror is migration scaffolding, not the artifact; once every
    surface reads uniform_key it can be dropped and the duplicates GC'd.
    """
    from BackEnd.utils import uniform_archive

    if not r2_images.is_configured():
        return {"status": "unconfigured"}
    master_key = f"players/master/{req.player_id}.png"
    try:
        image_id, team_id = _resolve_signed(req.franchise_id, req.player_id)
        if not image_id:
            return {"status": "generic"}          # walk-on / dynamic with no library
        team = db.teams.find_one({"_id": _maybe_objid(team_id)}) if team_id else None
        if not team:
            return {"status": "no_team"}
        from BackEnd.utils.franchise_team_display import resolve_team_display

        disp = resolve_team_display(req.franchise_id, team_id, core_doc=team)
        primary = disp.get("primary_color") or team.get("primary_color", "#000000")
        secondary = disp.get("secondary_color") or team.get("secondary_color", "#ffffff")
        mascot = disp.get("mascot") if disp.get("mascot") is not None else team.get("mascot", "")

        result = uniform_archive.ensure_uniform(
            image_id=image_id, primary=primary, secondary=secondary, mascot=mascot,
        )
        if result["status"] in ("no_image_id", "no_kit"):
            return {"status": "no_kit" if result["status"] == "no_kit" else "generic"}
        if result["status"] == "error":
            return {"status": "error", "detail": result.get("detail")}

        # Persist the pointer. This is what lets payloads resolve the archive
        # directly and skip the 404 -> ensure -> retry round trip entirely.
        franchise_players_data_collection.update_one(
            {"franchise_id": str(req.franchise_id), "player_id": str(req.player_id)},
            {"$set": {"meta.uniform_key": result["uniform_key"], "meta.image_painted": True}})

        # Mirror to the legacy key for surfaces not yet threaded. Server-side copy:
        # no download, no repaint.
        if not r2_images.exists(master_key):
            r2_images.copy(result["object_key"], master_key)

        return {"status": result["status"], "uniform_key": result["uniform_key"]}
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


# ---------------------------------------------------------------------------------
# Pre-game warm
# ---------------------------------------------------------------------------------

# Bounded so a cold franchise cannot spike RSS. Each paint holds ~48 MB of numpy
# arrays for a 12 MP canvas, and this service runs MALLOC_ARENA_MAX=2 after an
# allocator-retention incident. Raise only with a measurement.
WARM_CONCURRENCY = 2

# Above this, something systemic is wrong (asset zone down, kits missing) and
# grinding through hundreds of paints on a user-facing request helps nobody.
WARM_MAX_PLAYERS = 60


def _resolve_team_doc(team_ref: str):
    """Resolve a team by ObjectId string, raw _id, team_id slug, or display name."""
    ref = str(team_ref or "").strip()
    if not ref:
        return None
    try:
        from bson import ObjectId

        doc = db.teams.find_one({"_id": ObjectId(ref)})
        if doc:
            return doc
    except Exception:
        pass
    return (
        db.teams.find_one({"_id": ref})
        or db.teams.find_one({"team_id": ref})
        or db.teams.find_one({"name": ref})
    )


def warm_teams_now(franchise_id: str, team_refs: list[str]) -> dict:
    """Paint any unpainted archive entries for these teams' rosters.

    Idempotent and cheap in the steady state: a player already carrying
    ``meta.uniform_key`` is skipped without touching R2, so once the backfill has
    run this is one indexed query and no paints. It exists as a safety net, not as
    the primary mechanism — see Uniform_Archive_Brief.md.
    """
    from concurrent.futures import ThreadPoolExecutor

    from BackEnd.db import franchise_team_data_collection
    from BackEnd.utils import uniform_archive
    from BackEnd.utils.franchise_team_display import resolve_team_display

    summary = {"considered": 0, "skipped_stamped": 0, "painted": 0, "exists": 0, "failed": 0}
    if not r2_images.is_configured():
        summary["status"] = "unconfigured"
        return summary

    jobs = []
    for ref in team_refs or []:
        core = _resolve_team_doc(ref)
        if not core:
            continue
        team_oid = core.get("_id")
        ftd = franchise_team_data_collection.find_one(
            {"franchise_id": _maybe_objid(franchise_id), "team_id": team_oid}, {"players": 1}
        ) or franchise_team_data_collection.find_one(
            {"franchise_id": str(franchise_id), "team_id": team_oid}, {"players": 1}
        ) or {}
        pids = [str(p) for p in (ftd.get("players") or []) if p]
        if not pids:
            continue
        try:
            disp = resolve_team_display(franchise_id, team_oid, core_doc=core) or {}
        except Exception:
            disp = {}
        primary = disp.get("primary_color") or core.get("primary_color")
        secondary = disp.get("secondary_color") or core.get("secondary_color")
        mascot = disp.get("mascot") if disp.get("mascot") is not None else core.get("mascot", "")

        for fpd in franchise_players_data_collection.find(
            {"franchise_id": str(franchise_id), "player_id": {"$in": pids},
             "meta.image_id": {"$nin": [None, ""]}},
            {"player_id": 1, "meta": 1},
        ):
            meta = fpd.get("meta") or {}
            summary["considered"] += 1
            if meta.get("uniform_key"):
                summary["skipped_stamped"] += 1
                continue
            jobs.append({
                "player_id": str(fpd.get("player_id")),
                "image_id": meta.get("image_id"),
                "primary": primary, "secondary": secondary, "mascot": mascot,
            })

    if not jobs:
        summary["status"] = "nothing_to_do"
        return summary
    if len(jobs) > WARM_MAX_PLAYERS:
        logger.warning("[WARM] capping %s jobs at %s franchise=%s",
                       len(jobs), WARM_MAX_PLAYERS, franchise_id)
        jobs = jobs[:WARM_MAX_PLAYERS]

    def _one(job):
        res = uniform_archive.ensure_uniform(
            image_id=job["image_id"], primary=job["primary"],
            secondary=job["secondary"], mascot=job["mascot"],
        )
        if res["status"] in ("exists", "painted"):
            franchise_players_data_collection.update_one(
                {"franchise_id": str(franchise_id), "player_id": job["player_id"]},
                {"$set": {"meta.uniform_key": res["uniform_key"], "meta.image_painted": True}},
            )
        return res["status"]

    with ThreadPoolExecutor(max_workers=WARM_CONCURRENCY) as pool:
        for status in pool.map(_one, jobs):
            if status in summary:
                summary[status] += 1
            else:
                summary["failed"] += 1

    summary["status"] = "ok"
    logger.info("[WARM] franchise=%s teams=%s %s", franchise_id, team_refs, summary)
    return summary


@router.post("/player-image/warm-teams")
def warm_teams(
    req: WarmTeamsRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Kick off a pre-game warm and return IMMEDIATELY.

    Called when the user enters Set Lineup. Painting overlaps the time they spend on
    that screen, so nothing blocks and no load screen is needed. If the user is
    faster than the paint, the game still starts — the sprite preloader's self-heal
    covers the stragglers.
    """
    background_tasks.add_task(warm_teams_now, req.franchise_id, req.teams)
    return {"status": "queued", "teams": len(req.teams or [])}
