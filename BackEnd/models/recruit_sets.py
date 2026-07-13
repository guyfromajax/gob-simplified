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


def load_unused_set_or_generate(db, recruit_manager, used_set_ids, count=300):
    """Return (recruits, used_set_id).

    Pick a random set from `recruit_sets` whose set_id is not in used_set_ids and
    return its frozen recruit records (each with a stable recruit_id) + the set_id
    used. If none are available — or on ANY error — fall back to dynamic
    generation and return (generated_recruits, None), leaving current behavior
    unchanged.
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
                return recruits, pick
    except Exception as e:  # noqa: BLE001 — any failure must degrade gracefully
        logger.warning(f"recruit_sets lookup failed; using dynamic generation: {e}")
    return recruit_manager.generate_recruits_list(count=count), None
