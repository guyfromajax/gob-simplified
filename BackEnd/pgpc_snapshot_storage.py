"""
Prune and package a frozen game snapshot for ``press_conference_sessions``.

Avoids huge fields (e.g. ``turns``, ``text_log``) while preserving inputs the qualifier
and player-slot resolver need.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

_PGPC_GAME_KEYS = frozenset(
    {
        "_id",
        "game_id",
        "quarter",
        "is_final",
        "home_team_id",
        "away_team_id",
        "user_team_side",
        "teams",
        "players",
        "opening_lineup",
        "pgpc_tier_c",
        "score",
    }
)


def prune_game_doc_for_pgpc_snapshot(game_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of only PGPC-relevant top-level keys when present."""
    out: Dict[str, Any] = {}
    for key in _PGPC_GAME_KEYS:
        if key not in game_doc:
            continue
        val = game_doc[key]
        if val is not None:
            out[key] = deepcopy(val)
    gid = game_doc.get("game_id")
    if gid is not None and "game_id" not in out:
        out["game_id"] = deepcopy(gid)
    return out


def build_pgpc_snapshot(
    game_doc: Dict[str, Any], context: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "game": prune_game_doc_for_pgpc_snapshot(game_doc),
        "context": deepcopy(context),
    }


__all__ = ["build_pgpc_snapshot", "prune_game_doc_for_pgpc_snapshot"]
