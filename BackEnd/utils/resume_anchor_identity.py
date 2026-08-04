"""Resume-anchor identity: franchise_id / mode must survive snapshot restore.

summarize_game_state never emits top-level ``franchise_id`` or ``mode``. Historical
``resume_anchor.snapshot`` blobs therefore omit them. Replacing the root game doc
with the snapshot wholesale made ``franchise_id_for_roster`` resolve to None and
rebuilt GameManager from core ``players_collection`` — wrong for every franchise,
not only Team Builder.

Contract:
- Merge: game state from the snapshot; identity from the root document (history).
- Stamp: write identity into new snapshots so anchors are self-sufficient (future).
- Guard: mode=franchise with no franchise_id must fail closed, never load core.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def body_get(body: Any, key: str, default: Any = None) -> Any:
    if isinstance(body, dict):
        return body.get(key, default)
    return getattr(body, key, default)


def resolve_resume_identity_fields(
    body: Any = None,
    identity_source: dict | None = None,
    gm: Any = None,
) -> tuple[str | None, str | None, str | None]:
    """Return ``(mode, franchise_id, tournament_id)`` from root / body / live GM."""
    src = identity_source if isinstance(identity_source, dict) else {}
    mode = src.get("mode") or body_get(body, "mode", None)
    franchise_id = src.get("franchise_id") or body_get(body, "franchise_id", None)
    tournament_id = src.get("tournament_id") or body_get(body, "tournament_id", None)
    if gm is not None:
        if not franchise_id:
            franchise_id = getattr(getattr(gm, "home_team", None), "franchise_id", None) or getattr(
                getattr(gm, "away_team", None), "franchise_id", None
            )
        if not mode:
            mode = getattr(getattr(gm, "home_team", None), "mode", None) or getattr(
                getattr(gm, "away_team", None), "mode", None
            )
    if franchise_id is not None and franchise_id != "":
        franchise_id = str(franchise_id)
    else:
        franchise_id = None
    if tournament_id is not None and tournament_id != "":
        tournament_id = str(tournament_id)
    else:
        tournament_id = None
    if mode is not None and mode != "":
        mode = str(mode)
    else:
        mode = None
    return mode, franchise_id, tournament_id


def stamp_resume_identity_on_snapshot(
    snapshot: dict,
    body: Any = None,
    identity_source: dict | None = None,
    gm: Any = None,
) -> dict:
    """Write mode / franchise_id / tournament_id onto a resume snapshot in place."""
    if not isinstance(snapshot, dict):
        return snapshot
    mode, franchise_id, tournament_id = resolve_resume_identity_fields(
        body=body, identity_source=identity_source, gm=gm
    )
    if not mode:
        mode = snapshot.get("mode")
    if not franchise_id:
        franchise_id = snapshot.get("franchise_id")
    if not tournament_id:
        tournament_id = snapshot.get("tournament_id")
    if mode:
        snapshot["mode"] = mode
    if franchise_id:
        snapshot["franchise_id"] = str(franchise_id)
    if tournament_id:
        snapshot["tournament_id"] = str(tournament_id)
    return snapshot


def merge_resume_anchor_snapshot(root_doc: dict | None, snapshot: dict | None) -> dict:
    """Take game state from the anchor; keep identity context from the root doc."""
    root = root_doc if isinstance(root_doc, dict) else {}
    snap = snapshot if isinstance(snapshot, dict) else {}
    merged = deepcopy(snap)
    for key in ("franchise_id", "mode", "tournament_id", "user_team_side"):
        root_val = root.get(key)
        if root_val is not None and root_val != "":
            merged[key] = root_val
    if root.get("_id") is not None:
        merged["_id"] = root.get("_id")
    return merged


def resolve_franchise_id_for_roster(
    saved: dict | None,
    body: Any = None,
) -> tuple[str, str | None]:
    """Return ``(mode, franchise_id_for_roster)``.

    Raises ``ValueError`` when mode is franchise but franchise_id is missing —
    callers must not fall open to core rosters.
    """
    saved = saved if isinstance(saved, dict) else {}
    saved_mode = saved.get("mode") or body_get(body, "mode", None) or "single"
    saved_mode = str(saved_mode)
    saved_franchise_id = saved.get("franchise_id") or (
        body_get(body, "franchise_id", None) if saved_mode == "franchise" else None
    )
    if saved_franchise_id is not None and saved_franchise_id != "":
        saved_franchise_id = str(saved_franchise_id)
    else:
        saved_franchise_id = None
    if saved_mode == "franchise" and not saved_franchise_id:
        raise ValueError(
            "Resume rebuild refused: mode=franchise but franchise_id is missing "
            "after resume-anchor merge. Refusing to load core rosters."
        )
    franchise_id_for_roster = saved_franchise_id if saved_mode == "franchise" else None
    return saved_mode, franchise_id_for_roster
