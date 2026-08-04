"""Team Builder portrait pool, fitted assignment, and picker catalog (§6.5 / §6.5a).

Pool = recruit_set_0001 ∪ builder_set_0001. Recruit assignment stays set_0001 alone.

Assignment reuses scripts/classify_player_archetypes.py + player_ethnicity.py.
Relaxation: hold frame → skin within race family → definition → frame last.
Never a uniform random pick across the whole pool.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts"
_SETS = _SCRIPTS / "recruit_sets"

FRAMES = ("Slight", "Lean", "Normal", "Broad", "Doughy")
DEFINITIONS = ("Cut", "Toned", "Soft")
FRAME_NEIGHBORS: dict[str, tuple[str, ...]] = {
    "Slight": ("Lean", "Normal"),
    "Lean": ("Slight", "Normal"),
    "Normal": ("Lean", "Broad", "Slight"),
    "Broad": ("Normal", "Doughy", "Lean"),
    "Doughy": ("Broad", "Normal"),
}

SKIN_FAMILY: dict[str, str] = {
    "black-normal": "black",
    "black-light": "black",
    "black-dark": "black",
    "white-normal": "white",
    "white-tan": "white",
    "white-pale": "white",
    "asian": "other",
    "hispanic": "other",
    "ambiguous": "other",
}
FAMILY_SKINS: dict[str, tuple[str, ...]] = {
    "black": ("black-normal", "black-light", "black-dark"),
    "white": ("white-normal", "white-tan", "white-pale"),
    "other": ("asian", "hispanic", "ambiguous"),
}

RECRUIT_SET_LOGICAL = "recruit_set_0001"
RECRUIT_SET_DISK = "set_0001"
BUILDER_SET_ID = "builder_set_0001"
RECRUIT_KIT_PREFIX = "recruits/kit"
BUILDER_KIT_PREFIX = f"portrait-kits/{BUILDER_SET_ID}"


def _ensure_scripts_path() -> None:
    scripts = str(_SCRIPTS)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


def skin_family(skin: str | None) -> str:
    return SKIN_FAMILY.get(str(skin or ""), "other")


def skins_in_family(skin: str | None) -> tuple[str, ...]:
    return FAMILY_SKINS.get(skin_family(skin), FAMILY_SKINS["other"])


@lru_cache(maxsize=1)
def load_tb_portrait_pool() -> tuple[dict[str, Any], ...]:
    """Game-facing TB pool: filtered recruit manifest ∪ builder published."""
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    recruit_path = _SETS / f"{RECRUIT_SET_DISK}.manifest.json"
    recruit_doc = json.loads(recruit_path.read_text(encoding="utf-8"))
    for raw in recruit_doc.get("entries") or []:
        image_id = str(raw.get("recruit_id") or raw.get("image_id") or "").strip()
        if not image_id or image_id in seen:
            continue
        build = raw.get("build") or {}
        portrait = raw.get("portrait") or {}
        frame = str(build.get("frame") or "").strip()
        definition = str(build.get("definition") or "").strip()
        skin = str(portrait.get("skin") or "").strip()
        if not (frame and definition and skin):
            continue
        seen.add(image_id)
        entries.append(
            {
                "image_id": image_id,
                "set_id": RECRUIT_SET_LOGICAL,
                "kit_prefix": RECRUIT_KIT_PREFIX,
                "frame": frame,
                "definition": definition,
                "skin": skin,
            }
        )

    builder_path = _SETS / f"{BUILDER_SET_ID}.published.json"
    builder_doc = json.loads(builder_path.read_text(encoding="utf-8"))
    prefix = str(builder_doc.get("r2_prefix") or f"{BUILDER_KIT_PREFIX}/").rstrip("/")
    for raw in builder_doc.get("entries") or []:
        image_id = str(raw.get("image_id") or "").strip()
        if not image_id or image_id in seen:
            continue
        build = raw.get("build") or {}
        portrait = raw.get("portrait") or {}
        frame = str(build.get("frame") or "").strip()
        definition = str(build.get("definition") or "").strip()
        skin = str(portrait.get("skin") or "").strip()
        if not (frame and definition and skin):
            continue
        seen.add(image_id)
        entries.append(
            {
                "image_id": image_id,
                "set_id": BUILDER_SET_ID,
                "kit_prefix": prefix,
                "frame": frame,
                "definition": definition,
                "skin": skin,
            }
        )

    if len(entries) != 450:
        logger.warning(
            "[TB-PORTRAIT] pool size %s (expected 450) recruit+builder",
            len(entries),
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def _pool_by_id() -> dict[str, dict[str, Any]]:
    return {e["image_id"]: e for e in load_tb_portrait_pool()}


def resolve_kit_keys(image_id: str | None) -> tuple[str, str] | None:
    """Return (kit_png_key, mask_png_key) for a TB/recruit image_id, or None."""
    iid = str(image_id or "").strip()
    if not iid:
        return None
    entry = _pool_by_id().get(iid)
    if entry:
        prefix = entry["kit_prefix"]
        return f"{prefix}/{iid}.png", f"{prefix}/{iid}.mask.png"
    # Recruit-only kits may be known to the game without being in the TB pool
    # cache yet — fall back to the legacy recruit path.
    return f"{RECRUIT_KIT_PREFIX}/{iid}.png", f"{RECRUIT_KIT_PREFIX}/{iid}.mask.png"


def classify_team_builder_player(player: Mapping[str, Any]) -> dict[str, Any] | None:
    """
    Classify a wizard/editor player with the same axes as base-league portraits.

    Requires height, weight, ST, AG, and best-position RT (computed when missing).
    Seed for ethnicity / definition re-roll is player_id (_id).
    """
    _ensure_scripts_path()
    from classify_player_archetypes import classify  # noqa: WPS433 — scripts path

    height = player.get("height_in")
    if height is None:
        height = player.get("height")
    weight = player.get("weight_lb")
    if weight is None:
        weight = player.get("weight")
    try:
        height_i = int(height) if height is not None else None
        weight_i = int(weight) if weight is not None else None
    except (TypeError, ValueError):
        return None

    meta = player.get("meta") if isinstance(player.get("meta"), Mapping) else {}
    first = str(
        player.get("first_name") or meta.get("first_name") or ""
    ).strip()
    last = str(player.get("last_name") or meta.get("last_name") or "").strip()
    pid = str(
        player.get("player_id")
        or player.get("_id")
        or meta.get("player_id")
        or ""
    ).strip()
    if not pid:
        return None

    # §10.3b — weight is not previewed on the client. When the wizard omits it
    # (height edited → "Set at creation"), derive here for frame classification only.
    if height_i and not weight_i:
        from BackEnd.utils.player_generation import weight_from_height

        weight_i = weight_from_height(height_i, player_id=pid)
    if not height_i or not weight_i:
        return None

    attrs = player.get("attributes") or player.get("attrs") or {}
    st = attrs.get("ST") if isinstance(attrs, Mapping) else None
    ag = attrs.get("AG") if isinstance(attrs, Mapping) else None
    rt = player.get("rt")
    if rt is None:
        rt = _best_position_rt(player, attrs)

    payload = {
        "_id": pid,
        "height_in": height_i,
        "weight_lb": weight_i,
        "st": int(st) if st is not None else None,
        "ag": int(ag) if ag is not None else None,
        "rt": int(rt) if rt is not None else None,
        "first_name": first,
        "last_name": last,
        "year": player.get("class_year") or player.get("year") or meta.get("year"),
        "team": (meta.get("team") if meta else None) or player.get("team"),
    }
    result = classify(payload)
    if not result:
        return None
    definition = result.get("definition")
    if definition in (None, "", "n/a"):
        definition = "Toned"
    return {
        "frame": result.get("frame"),
        "definition": definition,
        "skin": result.get("skin"),
        "race": result.get("race"),
        "archetype": result.get("archetype"),
        "player_id": pid,
    }


def _best_position_rt(player: Mapping[str, Any], attrs: Mapping[str, Any]) -> int | None:
    ratings = player.get("position_ratings")
    if isinstance(ratings, Mapping) and ratings:
        vals = [int(v) for v in ratings.values() if isinstance(v, (int, float))]
        if vals:
            return max(vals)
    try:
        from BackEnd.utils.position_ratings import compute_position_ratings

        meta = player.get("meta") if isinstance(player.get("meta"), Mapping) else {}
        computed = compute_position_ratings(
            {
                "attributes": dict(attrs or {}),
                "height": player.get("height_in") or player.get("height") or meta.get("height"),
                "name": f"{player.get('first_name') or ''} {player.get('last_name') or ''}".strip(),
            }
        )
        vals = [int(v) for v in (computed or {}).values() if isinstance(v, (int, float))]
        return max(vals) if vals else None
    except Exception:
        logger.exception("[TB-PORTRAIT] position rating fallback failed")
        return None


def _stable_pick(candidates: Sequence[Mapping[str, Any]], seed: str) -> dict[str, Any]:
    """Deterministic pick among equally ranked candidates — never uniform over the pool."""
    if len(candidates) == 1:
        return dict(candidates[0])
    ranked = sorted(
        candidates,
        key=lambda e: (
            int(hashlib.md5(f"{seed}|{e['image_id']}".encode()).hexdigest(), 16),
            e["image_id"],
        ),
    )
    return dict(ranked[0])


def _match_stages(target: Mapping[str, Any]):
    """Yield (stage_name, predicate) in §6.5 relaxation order."""
    frame = target.get("frame")
    definition = target.get("definition") or "Toned"
    skin = target.get("skin")
    family = set(skins_in_family(skin))
    neighbors = FRAME_NEIGHBORS.get(str(frame), ())

    def pred(**kwargs):
        def _inner(e: Mapping[str, Any]) -> bool:
            for key, val in kwargs.items():
                if key == "skin_in":
                    if e.get("skin") not in val:
                        return False
                elif key == "frame_in":
                    if e.get("frame") not in val:
                        return False
                elif e.get(key) != val:
                    return False
            return True

        return _inner

    # Hold frame. Relax skin within race family first, then definition, frame last.
    yield ("exact", pred(frame=frame, definition=definition, skin=skin))
    yield ("frame_def_family", pred(frame=frame, definition=definition, skin_in=family))
    yield ("frame_skin", pred(frame=frame, skin=skin))
    yield ("frame_family", pred(frame=frame, skin_in=family))
    yield ("frame_only", pred(frame=frame))
    yield (
        "neighbor_exact",
        pred(frame_in=neighbors, definition=definition, skin=skin),
    )
    yield (
        "neighbor_family",
        pred(frame_in=neighbors, definition=definition, skin_in=family),
    )
    yield ("neighbor_only", pred(frame_in=neighbors))
    yield ("def_skin", pred(definition=definition, skin=skin))
    yield ("def_family", pred(definition=definition, skin_in=family))
    yield ("skin_only", pred(skin=skin))
    yield ("family_only", pred(skin_in=family))
    yield ("any", lambda _e: True)


def assign_fitted_image(
    target: Mapping[str, Any],
    *,
    used_ids: set[str] | None = None,
    exclude_ids: set[str] | None = None,
    pool: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Assign one kit for a classified target.

    Within each relaxation stage: prefer unused ids; if the stage has matches
    but all are used, take a used match (quality over uniqueness). Never jump
    to a worse stage while a better stage still has candidates.
    """
    pool = list(pool if pool is not None else load_tb_portrait_pool())
    used = set(used_ids or ())
    exclude = set(exclude_ids or ())
    seed = str(target.get("player_id") or target.get("_id") or "")
    if not seed:
        raise ValueError("portrait_assign_missing_player_id")

    for stage_name, predicate in _match_stages(target):
        matches = [e for e in pool if predicate(e) and e["image_id"] not in exclude]
        if not matches:
            continue
        unused = [e for e in matches if e["image_id"] not in used]
        chosen_pool = unused if unused else matches
        pick = _stable_pick(chosen_pool, f"{seed}|{stage_name}")
        return {
            "image_id": pick["image_id"],
            "set_id": pick["set_id"],
            "kit_prefix": pick["kit_prefix"],
            "frame": pick["frame"],
            "definition": pick["definition"],
            "skin": pick["skin"],
            "match_stage": stage_name,
            "exact_match": stage_name == "exact",
            "duplicate_allowed": not unused and bool(matches),
            "target": {
                "frame": target.get("frame"),
                "definition": target.get("definition"),
                "skin": target.get("skin"),
                "race": target.get("race"),
            },
        }
    raise ValueError("portrait_pool_empty")


def assign_roster_portraits(
    players: Sequence[Mapping[str, Any]],
    *,
    preserve: Mapping[int, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Auto-assign all roster slots. Optional preserve map keeps picker overrides
    or prior auto picks when the classification target is unchanged.
    """
    preserved = preserve or {}
    used: set[str] = set()
    out: list[dict[str, Any]] = []

    # Reserve preserved image_ids first so auto-fill skips them when possible.
    for idx, prev in preserved.items():
        iid = str((prev or {}).get("image_id") or "").strip()
        if iid and 0 <= int(idx) < len(players):
            used.add(iid)

    for i, player in enumerate(players):
        prev = preserved.get(i) or preserved.get(str(i)) or {}
        pid = str(
            player.get("player_id")
            or (prev.get("player_id") if prev else "")
            or ""
        ).strip() or str(uuid.uuid4())
        row = dict(player)
        row["player_id"] = pid
        target = classify_team_builder_player(row)
        if not target:
            raise ValueError(f"portrait_classify_failed:{i}")

        prev_image = str(prev.get("image_id") or "").strip()
        prev_source = str(prev.get("source") or "auto")
        prev_target = prev.get("target") or {}
        same_target = (
            prev_image
            and prev_target.get("frame") == target.get("frame")
            and prev_target.get("definition") == target.get("definition")
            and prev_target.get("skin") == target.get("skin")
        )
        if same_target and prev_image in _pool_by_id():
            entry = _pool_by_id()[prev_image]
            assignment = {
                "slot": i,
                "player_id": pid,
                "image_id": prev_image,
                "set_id": entry["set_id"],
                "kit_prefix": entry["kit_prefix"],
                "frame": entry["frame"],
                "definition": entry["definition"],
                "skin": entry["skin"],
                "match_stage": prev.get("match_stage") or "preserved",
                "exact_match": bool(prev.get("exact_match")),
                "source": prev_source,
                "target": {
                    "frame": target.get("frame"),
                    "definition": target.get("definition"),
                    "skin": target.get("skin"),
                    "race": target.get("race"),
                },
            }
            out.append(assignment)
            used.add(prev_image)
            continue

        # Picker override with different target still wins until user re-rolls.
        if prev_source == "picker" and prev_image in _pool_by_id():
            entry = _pool_by_id()[prev_image]
            assignment = {
                "slot": i,
                "player_id": pid,
                "image_id": prev_image,
                "set_id": entry["set_id"],
                "kit_prefix": entry["kit_prefix"],
                "frame": entry["frame"],
                "definition": entry["definition"],
                "skin": entry["skin"],
                "match_stage": "picker",
                "exact_match": (
                    entry["frame"] == target.get("frame")
                    and entry["definition"] == target.get("definition")
                    and entry["skin"] == target.get("skin")
                ),
                "source": "picker",
                "target": {
                    "frame": target.get("frame"),
                    "definition": target.get("definition"),
                    "skin": target.get("skin"),
                    "race": target.get("race"),
                },
            }
            out.append(assignment)
            used.add(prev_image)
            continue

        fitted = assign_fitted_image(target, used_ids=used)
        used.add(fitted["image_id"])
        out.append(
            {
                "slot": i,
                "player_id": pid,
                "source": "auto",
                **fitted,
            }
        )
    return out


def reroll_slot_portrait(
    players: Sequence[Mapping[str, Any]],
    *,
    slot: int,
    current_assignments: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Re-roll one slot, skipping its current image_id and preferring unused ids."""
    if slot < 0 or slot >= len(players):
        raise ValueError(f"portrait_slot_invalid:{slot}")
    used = {
        str(a.get("image_id"))
        for i, a in enumerate(current_assignments)
        if i != slot and a.get("image_id")
    }
    current_id = ""
    if slot < len(current_assignments):
        current_id = str(current_assignments[slot].get("image_id") or "")
    prev = current_assignments[slot] if slot < len(current_assignments) else {}
    pid = str(
        players[slot].get("player_id")
        or prev.get("player_id")
        or ""
    ).strip() or str(uuid.uuid4())
    row = dict(players[slot])
    row["player_id"] = pid
    target = classify_team_builder_player(row)
    if not target:
        raise ValueError(f"portrait_classify_failed:{slot}")
    # Salt the pick seed so consecutive re-rolls advance through candidates.
    # Classification axes stay tied to the real player_id above.
    reroll_n = int(prev.get("reroll_count") or 0) + 1
    pick_target = dict(target)
    pick_target["player_id"] = f"{pid}|reroll|{reroll_n}"
    fitted = assign_fitted_image(
        pick_target,
        used_ids=used,
        exclude_ids={current_id} if current_id else None,
    )
    return {
        "slot": slot,
        "player_id": pid,
        "source": "auto",
        "reroll_count": reroll_n,
        **fitted,
        "target": {
            "frame": target.get("frame"),
            "definition": target.get("definition"),
            "skin": target.get("skin"),
            "race": target.get("race"),
        },
    }


def pick_slot_portrait(
    *,
    slot: int,
    image_id: str,
    player_id: str,
    players: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    entry = _pool_by_id().get(str(image_id).strip())
    if not entry:
        raise ValueError("portrait_image_unknown")
    row = dict(players[slot])
    row["player_id"] = str(player_id).strip() or str(uuid.uuid4())
    target = classify_team_builder_player(row) or {}
    return {
        "slot": slot,
        "player_id": row["player_id"],
        "image_id": entry["image_id"],
        "set_id": entry["set_id"],
        "kit_prefix": entry["kit_prefix"],
        "frame": entry["frame"],
        "definition": entry["definition"],
        "skin": entry["skin"],
        "match_stage": "picker",
        "exact_match": (
            entry["frame"] == target.get("frame")
            and entry["definition"] == target.get("definition")
            and entry["skin"] == target.get("skin")
        ),
        "source": "picker",
        "target": {
            "frame": target.get("frame"),
            "definition": target.get("definition"),
            "skin": target.get("skin"),
            "race": target.get("race"),
        },
    }


def catalog_for_picker(
    *,
    skin: str | None = None,
    frame: str | None = None,
    definition: str | None = None,
) -> dict[str, Any]:
    """Picker catalog with pre-filter counts (visible before a filter is applied)."""
    pool = list(load_tb_portrait_pool())
    skin_counts: dict[str, int] = {}
    frame_counts: dict[str, int] = {}
    def_counts: dict[str, int] = {}
    for e in pool:
        skin_counts[e["skin"]] = skin_counts.get(e["skin"], 0) + 1
        frame_counts[e["frame"]] = frame_counts.get(e["frame"], 0) + 1
        def_counts[e["definition"]] = def_counts.get(e["definition"], 0) + 1

    filtered = pool
    if skin:
        filtered = [e for e in filtered if e["skin"] == skin]
    if frame:
        filtered = [e for e in filtered if e["frame"] == frame]
    if definition:
        filtered = [e for e in filtered if e["definition"] == definition]

    return {
        "total": len(pool),
        "filtered_count": len(filtered),
        "filters": {"skin": skin, "frame": frame, "definition": definition},
        "counts": {
            "skin": skin_counts,
            "frame": frame_counts,
            "definition": def_counts,
        },
        "entries": [
            {
                "image_id": e["image_id"],
                "set_id": e["set_id"],
                "frame": e["frame"],
                "definition": e["definition"],
                "skin": e["skin"],
            }
            for e in filtered
        ],
        "empty_reason": (
            None
            if filtered
            else "No portraits match these filters. Clear a filter or pick another combination."
        ),
    }


def get_or_create_wizard_portraits(
    db: Any,
    *,
    user_id: str,
    replaced_object_id: str,
    draft_id: str,
    players: Sequence[Mapping[str, Any]],
    force_reassign: bool = False,
    force_reassign_slots: Sequence[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Idempotent portrait map keyed on (user_id, draft_id, replaced_object_id).

    Seed strategy: mint player_id on first assignment and persist with image_id.
    Apply must reuse these player_ids so the wizard portrait is the shipped one.
    """
    from datetime import datetime

    user_key = str(user_id or "").strip()
    slot_key = str(replaced_object_id or "").strip()
    draft_key = str(draft_id or "").strip()
    if not user_key or not slot_key or not draft_key:
        raise ValueError("wizard_portraits_key_incomplete")
    if len(players) != 15:
        raise ValueError(f"portrait_roster_size_invalid:{len(players)}")

    col = db["team_builder_wizard_drafts"]
    query = {
        "user_id": user_key,
        "draft_id": draft_key,
        "replaced_object_id": slot_key,
    }
    existing = col.find_one(query, {"portraits": 1}) or {}
    stored = existing.get("portraits") if not force_reassign else None
    reassign_set = {
        int(i) for i in (force_reassign_slots or []) if isinstance(i, (int, float)) or str(i).isdigit()
    }
    preserve: dict[int, dict[str, Any]] = {}
    if isinstance(stored, list) and len(stored) == 15:
        for i, row in enumerate(stored):
            if not isinstance(row, Mapping):
                continue
            pid = str(row.get("player_id") or "").strip()
            if i in reassign_set:
                # Drop image so classification re-runs; keep player_id for §6.5 / §10.3b.
                if pid:
                    preserve[i] = {"player_id": pid, "source": "auto"}
                continue
            if row.get("image_id") and pid:
                preserve[i] = dict(row)

    assignments = assign_roster_portraits(players, preserve=preserve)
    col.update_one(
        query,
        {
            "$set": {
                **query,
                "portraits": assignments,
                "updated_at": datetime.utcnow(),
            },
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )
    again = col.find_one(query, {"portraits": 1}) or {}
    final = again.get("portraits")
    if isinstance(final, list) and len(final) == 15:
        return final
    return assignments


def update_wizard_portrait_slot(
    db: Any,
    *,
    user_id: str,
    replaced_object_id: str,
    draft_id: str,
    assignment: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Persist a single-slot re-roll or picker override onto the draft."""
    from datetime import datetime

    query = {
        "user_id": str(user_id).strip(),
        "draft_id": str(draft_id).strip(),
        "replaced_object_id": str(replaced_object_id).strip(),
    }
    col = db["team_builder_wizard_drafts"]
    doc = col.find_one(query, {"portraits": 1}) or {}
    portraits = list(doc.get("portraits") or [])
    slot = int(assignment["slot"])
    while len(portraits) < 15:
        portraits.append({})
    portraits[slot] = dict(assignment)
    col.update_one(
        query,
        {
            "$set": {
                **query,
                "portraits": portraits,
                "updated_at": datetime.utcnow(),
            },
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )
    return portraits


def measure_exact_match_rate(
    league_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Measure exact (frame×definition×skin) coverage of the TB pool vs league rows.

    Default: scripts/players_archetypes.csv when present.
    """
    pool = load_tb_portrait_pool()
    cells: dict[tuple[str, str, str], int] = {}
    for e in pool:
        key = (e["frame"], e["definition"], e["skin"])
        cells[key] = cells.get(key, 0) + 1

    if league_rows is None:
        csv_path = _SCRIPTS / "players_archetypes.csv"
        if not csv_path.exists():
            return {"error": "players_archetypes.csv missing", "pool_size": len(pool)}
        import csv

        league_rows = []
        with csv_path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                league_rows.append(row)

    total = 0
    exact = 0
    for row in league_rows:
        frame = str(row.get("frame") or "").strip()
        definition = str(row.get("definition") or "").strip()
        if definition in ("", "n/a"):
            definition = "Toned"
        skin = str(row.get("skin") or "").strip()
        if not (frame and definition and skin):
            continue
        total += 1
        if cells.get((frame, definition, skin), 0) > 0:
            exact += 1
    rate = (exact / total) if total else 0.0
    return {
        "pool_size": len(pool),
        "league_players": total,
        "exact_match_count": exact,
        "exact_match_rate": round(rate, 4),
        "exact_match_pct": round(rate * 100, 1),
    }


__all__ = [
    "assign_fitted_image",
    "assign_roster_portraits",
    "catalog_for_picker",
    "classify_team_builder_player",
    "get_or_create_wizard_portraits",
    "load_tb_portrait_pool",
    "measure_exact_match_rate",
    "pick_slot_portrait",
    "reroll_slot_portrait",
    "resolve_kit_keys",
    "update_wizard_portrait_slot",
]
