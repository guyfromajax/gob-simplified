"""Commit a finished franchise game to the owning user's account record (Phase 5).

When a franchise game finalizes, increment the human owner's career `record`
(win or loss + derived total_games / win_rate) and fold the per-period archetype
stash (`game.archetype_periods`, written during simulation in Phase 4) into their
`archetypes` counters.

MUST be called exactly once per game, AFTER finalize_game's `applied_games` claim
has succeeded — that claim is the idempotency boundary. This helper does not
re-guard against double-application. Best-effort: it never raises into
finalize_game.

`discount_wins` / `discount_losses` increment when `game.bulk_sim_used` is true.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import ReturnDocument

from BackEnd.db import db, users_collection
from BackEnd.utils.user_tracking import compute_lead_archetype, recompute_record_derived

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
        if game.get("bulk_sim_used") is True:
            inc["record.discount_wins" if user_won else "record.discount_losses"] = 1
        periods = game.get("archetype_periods") or {}
        if not periods:
            # Fallback: archetype_periods can be clobbered before finalize, but the
            # per-quarter result also rides the durable `archetype_hook` breadcrumb.
            hook = game.get("archetype_hook") or {}
            for q, h in hook.items():
                res = (h.get("dbg") or {}).get("result") if isinstance(h, dict) else None
                if res:
                    periods[q] = res
        for archetype in periods.values():
            field = f"archetypes.{archetype}"
            inc[field] = inc.get(field, 0) + 1
        if periods:
            inc["archetypes.total"] = len(periods)

        updated = users_collection.find_one_and_update(
            {"_id": user_oid},
            {"$inc": inc},
            projection={"record": 1, "archetypes": 1},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            logger.warning("[record] user %s not found; record not committed", user_oid)
            return

        # Recompute derived fields from the post-increment counts so they can't drift,
        # and refresh the denormalized lead_archetype (tie-break: most recently
        # incremented this game — periods in chronological quarter order).
        rec = recompute_record_derived(updated.get("record", {}))
        # period keys are quarter strings ("1".."5"); order chronologically, but
        # tolerate any stray non-digit key without raising.
        recent_keys = [periods[q] for q in sorted(periods, key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k)))]
        lead = compute_lead_archetype(updated.get("archetypes", {}), recent_keys=recent_keys)
        users_collection.update_one(
            {"_id": user_oid},
            {"$set": {
                "record.total_games": rec["total_games"],
                "record.win_rate": rec["win_rate"],
                "lead_archetype": lead,
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        logger.info(
            "[record] committed game=%s user=%s side=%s won=%s periods=%s",
            game.get("_id"), user_oid, side, user_won, dict(periods),
        )
    except Exception:
        logger.exception("[record] commit_user_game_record failed (non-fatal)")
