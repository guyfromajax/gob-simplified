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

# Bump on every deploy of this file so a game-doc breadcrumb proves the running
# code is current (not stale). Read it from `game.archetype_debug.<q>.build`.
STASH_BUILD = "arch-b2-2026-06-01"


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
    # Diagnosis on Railway can't rely on logs (rate-limited + INFO dropped), so
    # we leave a full per-quarter breadcrumb on the GAME doc. `build` stamps the
    # running code version so we can verify a deploy is fresh, not stale.
    quarter = getattr(body, "quarter", None)
    gid = _to_object_id(game_id)
    dbg = {
        "build": STASH_BUILD,
        "mode": mode,
        "quarter": quarter,
        "full_sim": getattr(body, "full_sim", None),
    }
    try:
        if mode != "franchise":
            dbg["skip"] = "not_franchise"
            return
        if not getattr(body, "franchise_id", None) or not game_id:
            dbg["skip"] = "no_franchise_id_or_game_id"
            return
        if not isinstance(quarter, int) or quarter < 1:
            dbg["skip"] = f"bad_quarter:{quarter!r}"
            return

        # The user's side is authoritative from game_state; fall back to the request.
        gs_side = gm.game_state.get("user_team_side") if (gm is not None and getattr(gm, "game_state", None)) else None
        body_side = getattr(body, "user_team_side", None)
        side = gs_side or body_side
        dbg["gs_side"] = gs_side
        dbg["body_side"] = body_side
        dbg["side"] = side
        if side not in ("home", "away"):
            dbg["skip"] = "no_user_side"
            return

        period_key = str(quarter)

        # Dedup: this period already classified for this game → leave it untouched.
        if games_collection.find_one(
            {"_id": gid, f"archetype_periods.{period_key}": {"$exists": True}},
            {"_id": 1},
        ):
            dbg["skip"] = "already_stashed"
            return

        team = gm.home_team if side == "home" else gm.away_team

        # Preferred source: the entry lineup sent in the request (5 player ids).
        lineup_ids = (body.home_lineup if side == "home" else body.away_lineup) or {}
        starters = []
        for pid in lineup_ids.values():
            if not pid:
                continue
            player = team.get_player_by_id(pid)
            attrs = getattr(player, "attributes", None) if player else None
            if attrs:
                starters.append(attrs)
        dbg["lineup_ids"] = [str(v) for v in lineup_ids.values()]
        dbg["body_n"] = len(starters)

        # Fallback: the team's live lineup object (always populated by the sim).
        # Covers quarters where the client didn't resend the lineup and any
        # home/away orientation mismatch in the request body.
        if len(starters) != 5:
            live = getattr(team, "lineup", None) or {}
            alt = [a for a in (getattr(p, "attributes", None) for p in live.values()) if a]
            dbg["live_n"] = len(alt)
            if len(alt) == 5:
                starters = alt

        if len(starters) != 5:
            dbg["skip"] = "lineup_unresolved"
            return

        archetype = classify_archetype(starters)

        # Atomic conditional set — guards against a concurrent writer for this period.
        games_collection.update_one(
            {"_id": gid, f"archetype_periods.{period_key}": {"$exists": False}},
            {"$set": {f"archetype_periods.{period_key}": archetype}},
        )
        dbg["result"] = archetype
    except Exception as e:
        dbg["error"] = repr(e)
        logger.exception("[archetype] stash_period_archetype failed (non-fatal)")
    finally:
        # Persist the breadcrumb regardless of outcome (rate-limit-proof channel).
        try:
            if game_id is not None:
                qk = str(quarter) if quarter is not None else "x"
                games_collection.update_one(
                    {"_id": gid}, {"$set": {f"archetype_debug.{qk}": dbg}}
                )
        except Exception:
            logger.exception("[archetype] breadcrumb write failed")
