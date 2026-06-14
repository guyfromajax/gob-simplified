"""Practice Squad player stat rollup into FPD/FRD ps_season_stats."""

from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId

from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.db import (
    franchise_players_data_collection,
    franchise_recruits_data_collection,
    games_collection,
)

logger = logging.getLogger(__name__)

_PS_STAT_KEYS = [k for k in BOX_SCORE_KEYS if k != "MIN"]


def _load_game_doc(game_id: str) -> dict | None:
    """Load a game doc; PS games store _id as a string, not ObjectId."""
    gid = str(game_id)
    game = games_collection.find_one({"_id": gid})
    if game:
        return game
    try:
        game = games_collection.find_one({"_id": ObjectId(gid)})
    except Exception:
        game = None
    return game


def _collect_ps_game_ids(ps_state: dict, franchise_id: str) -> list[str]:
    """All completed PS game ids for a franchise (applied_games + schedule/brackets)."""
    seen: set[str] = set()
    ordered: list[str] = []

    def add(gid: Any) -> None:
        if not gid:
            return
        s = str(gid)
        if s not in seen:
            seen.add(s)
            ordered.append(s)

    for gid in ps_state.get("applied_games") or []:
        add(gid)

    for week_games in (ps_state.get("schedule") or {}).values():
        for g in week_games or []:
            if isinstance(g, dict) and g.get("status") == "completed":
                add(g.get("game_id"))

    for tstate in (ps_state.get("tournaments") or {}).values():
        bracket = (tstate or {}).get("bracket") or {}
        for round_key in ("round1", "round2", "final"):
            for m in bracket.get(round_key) or []:
                if isinstance(m, dict) and m.get("game_id"):
                    add(m["game_id"])

    champ = ps_state.get("championship") or {}
    if isinstance(champ, dict) and champ.get("game_id"):
        add(champ["game_id"])

    fid = str(franchise_id)
    for doc in games_collection.find(
        {"franchise_id": fid, "mode": "practice_squad"},
        {"_id": 1, "week": 1},
    ).sort("week", 1):
        add(doc.get("_id"))

    return ordered


def _extract_box_score_players(game: dict) -> list[tuple[str, dict, str | None]]:
    """Return (player_id, stats_row, team_id) tuples from a game doc."""
    rows: list[tuple[str, dict, str | None]] = []
    box = game.get("box_score") or {}
    if not box:
        teams = game.get("teams") or {}
        for tid, tdata in teams.items():
            bs = (tdata or {}).get("box_score") or {}
            for _pos, row in bs.items():
                if isinstance(row, dict) and row.get("playerId"):
                    rows.append((str(row["playerId"]), row, str(tid)))
        return rows
    for tid, team_box in box.items():
        if not isinstance(team_box, dict):
            continue
        for _pos, row in team_box.items():
            if isinstance(row, dict) and row.get("playerId"):
                rows.append((str(row["playerId"]), row, str(tid)))
    return rows


def apply_ps_game_stats(
    game_id: str,
    franchise_id: str,
    *,
    player_sources: dict[str, str] | None = None,
) -> bool:
    """
    Roll box score into ps_season_stats on FPD/FRD. Idempotent via caller tracking applied_games.
    player_sources maps player_id -> 'fpd'|'frd'.
    """
    game = _load_game_doc(game_id)
    if not game:
        logger.warning("apply_ps_game_stats: game %s not found", game_id)
        return False

    player_sources = player_sources or {}
    fid = str(franchise_id)

    for player_id, row, _team_id in _extract_box_score_players(game):
        source = player_sources.get(player_id)
        if not source:
            # Infer from collections
            if franchise_players_data_collection.find_one(
                {"franchise_id": fid, "player_id": player_id}, {"player_id": 1}
            ):
                source = "fpd"
            elif franchise_recruits_data_collection.find_one(
                {"franchise_id": fid, "recruit_id": player_id}, {"recruit_id": 1}
            ):
                source = "frd"
            else:
                continue

        inc: dict[str, int] = {}
        for key in _PS_STAT_KEYS:
            if key not in row:
                continue
            try:
                val = int(row.get(key) or 0)
            except (TypeError, ValueError):
                continue
            if val:
                inc[f"ps_season_stats.{key}"] = val

        min_val = row.get("MIN")
        if min_val is not None:
            try:
                mins = int(min_val)
                if mins > 300:
                    mins = mins // 60
                if mins:
                    inc["ps_season_stats.MIN"] = mins
            except (TypeError, ValueError):
                pass

        if inc:
            inc["ps_season_stats.GP"] = 1

        if not inc:
            continue

        if source == "fpd":
            franchise_players_data_collection.update_one(
                {"franchise_id": fid, "player_id": player_id},
                {"$inc": inc},
            )
        else:
            franchise_recruits_data_collection.update_one(
                {"franchise_id": fid, "recruit_id": player_id},
                {"$inc": inc},
            )

    return True


def backfill_ps_season_stats(franchise_id: str, ps_state: dict) -> int:
    """
    Rebuild ps_season_stats from all saved PS games (one-time repair after _id lookup bug).
    Clears existing ps_season_stats first to avoid double-counting.
    Returns number of games processed.
    """
    from BackEnd.practice_squad.manager import _player_sources_from_ps_state

    fid = str(franchise_id)
    game_ids = _collect_ps_game_ids(ps_state, fid)
    if not game_ids:
        return 0

    clear_ps_season_stats_for_franchise(fid)
    sources = _player_sources_from_ps_state(ps_state)
    applied = 0
    for gid in game_ids:
        if apply_ps_game_stats(gid, fid, player_sources=sources):
            applied += 1
    logger.info(
        "backfill_ps_season_stats: franchise=%s games=%s applied=%s",
        fid,
        len(game_ids),
        applied,
    )
    return applied


def ensure_ps_season_stats_backfilled(
    franchise_id: str,
    ps_state: dict,
) -> dict[str, Any]:
    """Run one-time backfill when ps_season_stats_backfilled flag is missing."""
    state = dict(ps_state)
    if state.get("ps_season_stats_backfilled"):
        return state
    if not state.get("initialized"):
        return state
    backfill_ps_season_stats(franchise_id, state)
    state["ps_season_stats_backfilled"] = True
    return state


def clear_ps_season_stats_for_franchise(franchise_id: str) -> None:
    fid = str(franchise_id)
    franchise_players_data_collection.update_many(
        {"franchise_id": fid, "ps_season_stats": {"$exists": True}},
        {"$unset": {"ps_season_stats": ""}},
    )
    franchise_recruits_data_collection.update_many(
        {"franchise_id": fid, "ps_season_stats": {"$exists": True}},
        {"$unset": {"ps_season_stats": ""}},
    )
