"""Commit a finished franchise game to the owning user's account record (Phase 5).

When a franchise game finalizes, increment the human owner's career `record`
(win or loss + derived total_games / win_rate) and fold the per-period archetype
stash (`game.archetype_periods`, written during simulation in Phase 4) into their
`archetypes` counters.

MUST be called exactly once per game, AFTER finalize_game's `applied_games` claim
has succeeded — that claim is the idempotency boundary. This helper does not
re-guard against double-application. Best-effort: it never raises into
finalize_game.

`discount_wins` / `discount_losses` are intentionally left untouched — bulk-sim
discount tracking is deferred (the hook would read `game.get("bulk_sim_used")`).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import ReturnDocument

from BackEnd.db import db, users_collection
from BackEnd.utils.user_tracking import recompute_record_derived

logger = logging.getLogger(__name__)


def _to_oid(value):
    try:
        if isinstance(value, str) and ObjectId.is_valid(value):
            return ObjectId(value)
    except Exception:
        pass
    return value


def _team_score(team_obj, team_name, score_map):
    """Score for a team: prefer the team object's own `score`, else the
    name-keyed score map (mirrors franchise save-result)."""
    if isinstance(team_obj, dict) and team_obj.get("score") is not None:
        return team_obj.get("score")
    return score_map.get(team_name, 0)


def commit_user_game_record(game: dict, franchise_id, home_team_name, away_team_name) -> None:
    try:
        game = game or {}
        side = game.get("user_team_side")
        if side not in ("home", "away"):
            # CPU-vs-CPU franchise game (no human side) — nothing to attribute.
            return

        fdoc = db.franchises.find_one({"_id": _to_oid(franchise_id)}, {"user_id": 1}) or {}
        user_id = fdoc.get("user_id")
        if not user_id:
            logger.warning("[record] franchise %s has no user_id; skipping commit", franchise_id)
            return
        user_oid = _to_oid(user_id)

        teams_obj = game.get("teams") or {}
        home_obj = teams_obj.get(game.get("home_team_id")) or {}
        away_obj = teams_obj.get(game.get("away_team_id")) or {}
        score_map = game.get("score") or game.get("final_score") or {}
        home_score = _team_score(home_obj, home_team_name, score_map)
        away_score = _team_score(away_obj, away_team_name, score_map)

        user_score = home_score if side == "home" else away_score
        opp_score = away_score if side == "home" else home_score
        if user_score == opp_score:
            logger.warning(
                "[record] ambiguous/tied score for game=%s (%s-%s); skipping",
                game.get("_id"), user_score, opp_score,
            )
            return
        user_won = user_score > opp_score

        inc = {
            "record.total_games": 1,
            ("record.wins" if user_won else "record.losses"): 1,
        }
        periods = game.get("archetype_periods") or {}
        for archetype in periods.values():
            field = f"archetypes.{archetype}"
            inc[field] = inc.get(field, 0) + 1
        if periods:
            inc["archetypes.total"] = len(periods)

        updated = users_collection.find_one_and_update(
            {"_id": user_oid},
            {"$inc": inc},
            projection={"record": 1},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            logger.warning("[record] user %s not found; record not committed", user_oid)
            return

        # Recompute derived fields from the post-increment counts so they can't drift.
        rec = recompute_record_derived(updated.get("record", {}))
        users_collection.update_one(
            {"_id": user_oid},
            {"$set": {
                "record.total_games": rec["total_games"],
                "record.win_rate": rec["win_rate"],
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        logger.info(
            "[record] committed game=%s user=%s side=%s won=%s periods=%s",
            game.get("_id"), user_oid, side, user_won, dict(periods),
        )
    except Exception:
        logger.exception("[record] commit_user_game_record failed (non-fatal)")
