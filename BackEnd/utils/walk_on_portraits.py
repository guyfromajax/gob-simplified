"""Walk-on portrait pool — 71 kits under portrait-kits/walk_on_portraits/.

Source art is the retired set_0001 mover archive, remapped to collision-free
``image_id``s (see BackEnd/data/walk_on_portraits_manifest.json). Assign at camp
cuts when a Walk On survives onto the active 12; paint via ensure_player_image.

Season 1 uses this pool only. Season 2+ unions it with recruit ``set_0001`` kit ids
(see ``pick_roster_maker_image_id``).
"""
from __future__ import annotations

import json
import logging
import random
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

logger = logging.getLogger(__name__)

_REPO_DATA = Path(__file__).resolve().parents[1] / "data" / "walk_on_portraits_manifest.json"
WALK_ON_KIT_PREFIX = "portrait-kits/walk_on_portraits"
FRANCHISE_USED_FIELD = "walk_on_image_ids_used"


@lru_cache(maxsize=1)
def load_walk_on_portrait_manifest() -> dict[str, Any]:
    raw = json.loads(_REPO_DATA.read_text(encoding="utf-8"))
    return raw


@lru_cache(maxsize=1)
def walk_on_image_ids() -> tuple[str, ...]:
    portraits = load_walk_on_portrait_manifest().get("portraits") or []
    return tuple(str(p["image_id"]) for p in portraits if p.get("image_id"))


@lru_cache(maxsize=1)
def walk_on_image_id_set() -> frozenset[str]:
    return frozenset(walk_on_image_ids())


def walk_on_kit_prefix() -> str:
    return str(load_walk_on_portrait_manifest().get("kit_prefix") or WALK_ON_KIT_PREFIX)


def pick_walk_on_image_id(
    used: Iterable[str] | None,
    rng: Optional[random.Random] = None,
) -> str | None:
    """Pick an unused walk-on portrait id; wrap to full pool when exhausted."""
    return pick_roster_maker_image_id(used, season=1, rng=rng)


def pick_roster_maker_image_id(
    used: Iterable[str] | None,
    *,
    season: int = 1,
    recruit_pool: Sequence[str] | None = None,
    rng: Optional[random.Random] = None,
) -> str | None:
    """Pick a portrait id for a Walk On making the active 12.

    Season 1: walk-on pool only.
    Season 2+: walk-on pool ∪ recruit set_0001 kit ids (``recruit_pool``).
    League-wide de-dupe via ``used`` (``franchises.walk_on_image_ids_used``); wraps when
    the applicable pool is exhausted.
    """
    walk_ids = list(walk_on_image_ids())
    if int(season or 1) <= 1:
        pool = walk_ids
    else:
        extra = [str(x) for x in (recruit_pool or []) if x]
        seen: set[str] = set()
        pool = []
        for iid in walk_ids + extra:
            if iid in seen:
                continue
            seen.add(iid)
            pool.append(iid)
    if not pool:
        return None
    used_set = {str(x) for x in (used or []) if x}
    available = [i for i in pool if i not in used_set]
    chooser = rng.choice if rng is not None else random.choice
    return chooser(available or pool)


def is_walk_on_fpd(doc: dict[str, Any] | None) -> bool:
    if not doc:
        return False
    meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
    arch = str(meta.get("archetype") or doc.get("archetype") or "").strip().lower()
    # Normalize common separators so "Walk On" / "Walk-On" / "walk_on" all match.
    arch = arch.replace("-", " ").replace("_", " ")
    arch = " ".join(arch.split())
    return arch == "walk on"
