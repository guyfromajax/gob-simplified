"""
Recruit set loading for the recruit image system.

A franchise draws its 300 recruits each season from a pre-built, image-backed
"set" in the shared `recruit_sets` collection instead of generating them fresh —
so each recruit carries a STABLE recruit_id that keys a pre-generated portrait.
Sets are never reused within a franchise (tracked via used_recruit_set_ids on
the franchise doc).

This module is FALLBACK-GUARDED: if no unused set exists, or the collection is
empty, or anything goes wrong, it falls back to the existing dynamic
generate_recruits_list — so behavior is identical to today until sets are loaded.

See _documentation_master/00_Operations/Recruit_Image_System.md.
"""
import random
import logging

logger = logging.getLogger(__name__)

COLLECTION = "recruit_sets"

# The base image library every copy of the game ships with. Dynamic recruits
# (when a user hasn't bought fresh packs) borrow portraits from this set. It is
# the image source regardless of whether the set was ever consumed as a class.
BASE_IMAGE_SET_ID = "set_0001"


# The portrait a dynamic recruit borrows is painted from a KIT asset in R2; an id
# with no kit paints nothing → generic headshot. Filter the borrow pool to ids that
# actually HAVE a kit so a batch of not-yet-arted recruit_ids (e.g. an expanded set
# awaiting portraits) is never handed to a dynamic draw. File-existence, not a flag:
# self-correcting as art uploads, and it catches any future missing/failed asset.
RECRUIT_KIT_PREFIX = "recruits/kit/"
_kit_ids_cache: dict = {"ids": None}  # available-asset set, computed ONCE per process


def _available_kit_ids():
    """Set of recruit_ids that have a kit asset in R2 (portrait-backed). Computed via a
    single R2 LIST, cached for the process. Returns ``None`` when R2 is unavailable /
    unconfigured / errors — the pool then falls back to UNFILTERED (current behaviour)
    rather than emptying, so a missing R2 never breaks recruit generation."""
    if _kit_ids_cache["ids"] is not None:
        return _kit_ids_cache["ids"] or None
    try:
        from BackEnd.services import r2_images
        if not r2_images.is_configured():
            logger.info("[recruit-image-pool] R2 not configured — falling back to has_portrait flag")
            _kit_ids_cache["ids"] = frozenset()
            return None
        keys = r2_images.list_keys(RECRUIT_KIT_PREFIX)
        ids = frozenset(
            k[len(RECRUIT_KIT_PREFIX):-4] for k in keys
            if k.endswith(".png") and not k.endswith(".mask.png")
        )
        _kit_ids_cache["ids"] = ids
        logger.info("[recruit-image-pool] R2 kit assets available: %d", len(ids))
        return ids or None
    except Exception as e:  # noqa: BLE001 — any R2 failure → flag fallback, never break generation
        # An unreachable asset store in production is an error, not a warning: it disables the
        # PRIMARY (R2 file-existence) filter and drops the pool onto the has_portrait fallback.
        logger.error("[recruit-image-pool] R2 kit listing failed (%s) — falling back to has_portrait flag", e)
        _kit_ids_cache["ids"] = frozenset()
        return None


def _base_image_pool(db, set_id=BASE_IMAGE_SET_ID):
    """The recruit_ids of the base image library — the portraits a dynamic recruit can borrow.

    PRIMARY filter: ids whose kit asset actually exists in R2 (self-correcting as art uploads).
    FAIL-SAFE fallback when R2 is unavailable: exclude ids flagged ``has_portrait: false`` (set on
    not-yet-arted recruits), so an R2 outage lands on CORRECT behaviour (portrait-less ids stay out
    of dynamic draws) rather than leaking all of them. Empty (→ generic headshots) if the set isn't
    loaded."""
    try:
        doc = db[COLLECTION].find_one(
            {"set_id": set_id}, {"recruits.recruit_id": 1, "recruits.has_portrait": 1})
        recruits = (doc or {}).get("recruits", [])
        ids = [r.get("recruit_id") for r in recruits if r.get("recruit_id")]
    except Exception as e:  # noqa: BLE001 — image assignment must never break generation
        logger.warning(f"base image pool lookup failed: {e}")
        return []
    available = _available_kit_ids()
    if available is not None:
        before = len(ids)
        ids = [i for i in ids if i in available]
        logger.info("[recruit-image-pool] %d/%d recruit ids have a kit asset (%d portrait-less filtered out)",
                    len(ids), before, before - len(ids))
        return ids
    # R2 down → fail SAFE on the flag rather than passing every id (the leak the filter prevents).
    flagged = {r.get("recruit_id") for r in recruits if r.get("has_portrait") is False}
    if flagged:
        before = len(ids)
        ids = [i for i in ids if i not in flagged]
        logger.error("[recruit-image-pool] R2 unavailable — has_portrait fallback excluded %d flagged, %d remain",
                     before - len(ids), len(ids))
    return ids


def assign_image_ids(recruits, db, base_set_id=BASE_IMAGE_SET_ID):
    """Stamp `image_id` on each recruit — the portrait it wears. Returns recruits.

    - A SET recruit already carries a stable recruit_id that IS its portrait, so
      image_id = recruit_id.
    - A DYNAMIC recruit (no recruit_id/image_id yet) BORROWS a portrait from the
      base image library at random — a shuffled 1:1 mapping so no two recruits in
      the same class share a face (wraps only if the class exceeds the library).
      If the library is unavailable, image_id is left unset → generic headshot.
    """
    borrowers = []
    for r in recruits:
        if r.get("image_id"):
            continue
        if r.get("recruit_id"):
            r["image_id"] = r["recruit_id"]
        else:
            borrowers.append(r)
    if borrowers:
        pool = list(_base_image_pool(db, base_set_id))
        if pool:
            random.shuffle(pool)
            for j, r in enumerate(borrowers):
                r["image_id"] = pool[j % len(pool)]
    return recruits


def load_unused_set_or_generate(db, recruit_manager, used_set_ids, count=400):
    """Return (recruits, used_set_id), each recruit stamped with an image_id.

    Pick a random set from `recruit_sets` whose set_id is not in used_set_ids and
    return its frozen recruit records (each with a stable recruit_id) + the set_id
    used. If none are available — or on ANY error — fall back to dynamic
    generation and return (generated_recruits, None), leaving current behavior
    unchanged. Either way, every returned recruit gets an image_id (its own for
    set recruits; a borrowed base-library portrait for dynamic recruits).
    """
    try:
        used = set(used_set_ids or [])
        available = [d["set_id"] for d in db[COLLECTION].find({}, {"set_id": 1})
                     if d.get("set_id") and d["set_id"] not in used]
        if available:
            pick = random.choice(available)
            doc = db[COLLECTION].find_one({"set_id": pick})
            recruits = (doc or {}).get("recruits") or []
            if recruits:
                logger.info(f"Loaded recruit set {pick} ({len(recruits)} recruits)")
                return assign_image_ids(recruits, db), pick
    except Exception as e:  # noqa: BLE001 — any failure must degrade gracefully
        logger.warning(f"recruit_sets lookup failed; using dynamic generation: {e}")
    return assign_image_ids(recruit_manager.generate_recruits_list(count=count), db), None
