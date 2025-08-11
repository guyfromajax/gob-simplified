from typing import Any, Dict

from BackEnd.db import players_collection


def apply_stats_from_summary(summary: Dict[str, Any], game_id: str, tournament_id: str | None = None) -> None:
    """Accumulate each player's game stats into season and career totals.

    This function is idempotent per (tournament_id, game_id) pair.  If the
    combination has already been applied for a player, no changes will occur.
    After applying, the player's game stats are reset to zero.
    """
    token = f"{tournament_id}:{game_id}" if tournament_id else str(game_id)

    box_score = summary.get("box_score", {})
    players = summary.get("players", [])
    team_map = {
        "home": summary.get("home_team"),
        "away": summary.get("away_team"),
    }

    for p in players:
        pid = p.get("playerId")
        team_side = p.get("team")
        pos = p.get("pos")
        team_name = team_map.get(team_side)
        if not pid or not team_name:
            continue
        stat_block = box_score.get(team_name, {}).get(pos, {})
        inc_fields: Dict[str, Any] = {}
        set_fields: Dict[str, Any] = {}
        for stat, val in stat_block.items():
            if stat == "name":
                continue
            if isinstance(val, (int, float)):
                inc_fields[f"stats.season.{stat}"] = val
                inc_fields[f"stats.career.{stat}"] = val
                set_fields[f"stats.game.{stat}"] = 0
        if not inc_fields and not set_fields:
            continue
        update_doc: Dict[str, Any] = {"$addToSet": {"stats.applied_games": token}}
        if inc_fields:
            update_doc["$inc"] = inc_fields
        if set_fields:
            update_doc["$set"] = set_fields
        players_collection.update_one(
            {"_id": pid, "stats.applied_games": {"$ne": token}},
            update_doc,
        )
