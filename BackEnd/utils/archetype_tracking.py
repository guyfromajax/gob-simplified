"""Per-period coaching-archetype stash for franchise games (Phase 4).

When a franchise quarter is simulated, classify the user's 5 active starters and
record the resulting archetype on the GAME document under `archetype_periods`,
keyed by quarter number. This is the "classify as you go" half of the design;
`finalize_game` folds these into the user's account record at game completion
(Phase 5).

Keying per (game_id, quarter) makes it idempotent: refreshes, timeout / foul-out
resumes, and "already simulated" replays never double-count, and an abandoned
game (never finalized) simply never commits its stash.

This is best-effort telemetry — it must NEVER raise into the gameplay path.
"""

from __future__ import annotations

import logging

from bson import ObjectId

from BackEnd.utils.coaching_archetype import classify_archetype

logger = logging.getLogger(__name__)


def _to_object_id(game_id):
    try:
        if isinstance(game_id, str) and ObjectId.is_valid(game_id):
            return ObjectId(game_id)
    except Exception:
        pass
    return game_id


def stash_period_archetype(*, gm, body, mode, game_id, games_collection) -> None:
    """Classify + stash the user's archetype for the quarter just simulated.

    Franchise mode only. Reads the ENTRY lineup from `body.<side>_lineup` (so
    mid-quarter substitutions don't change the classification) and the players'
    `anchor_` base attributes. No-op if the period was already stashed.
    """
    try:
        if mode != "franchise":
            return
        if not getattr(body, "franchise_id", None) or not game_id:
            return
        quarter = getattr(body, "quarter", None)
        if not isinstance(quarter, int) or quarter < 1:
            return

        # The user's side is authoritative from game_state; fall back to the request.
        side = None
        if gm is not None and getattr(gm, "game_state", None):
            side = gm.game_state.get("user_team_side")
        side = side or getattr(body, "user_team_side", None)
        if side not in ("home", "away"):
            return

        period_key = str(quarter)
        gid = _to_object_id(game_id)

        # Dedup: this period already classified for this game → leave it untouched.
        if games_collection.find_one(
            {"_id": gid, f"archetype_periods.{period_key}": {"$exists": True}},
            {"_id": 1},
        ):
            return

        team = gm.home_team if side == "home" else gm.away_team
        lineup_ids = (body.home_lineup if side == "home" else body.away_lineup) or {}
        starters = []
        for pid in lineup_ids.values():
            if not pid:
                continue
            player = team.get_player_by_id(pid)
            attrs = getattr(player, "attributes", None) if player else None
            if attrs:
                starters.append(attrs)

        if len(starters) != 5:
            logger.warning(
                "[archetype] skip stash game=%s q=%s side=%s: resolved %d/5 starters",
                game_id, period_key, side, len(starters),
            )
            return

        archetype = classify_archetype(starters)

        # Atomic conditional set — guards against a concurrent writer for this period.
        games_collection.update_one(
            {"_id": gid, f"archetype_periods.{period_key}": {"$exists": False}},
            {"$set": {f"archetype_periods.{period_key}": archetype}},
        )
        logger.info(
            "[archetype] stashed game=%s q=%s side=%s -> %s",
            game_id, period_key, side, archetype,
        )
    except Exception:
        logger.exception("[archetype] stash_period_archetype failed (non-fatal)")
