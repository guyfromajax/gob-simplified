"""Walk-on portrait pool — 71 kits under portrait-kits/walk_on_portraits/.

Source art is the retired set_0001 mover archive, remapped to collision-free
``image_id``s (see BackEnd/data/walk_on_portraits_manifest.json). Assign at camp
cuts when a Walk On survives onto the active 12; paint via ensure_player_image.
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
    pool = list(walk_on_image_ids())
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
    arch = str(meta.get("archetype") or doc.get("archetype") or "").strip()
    return arch == "Walk On"
