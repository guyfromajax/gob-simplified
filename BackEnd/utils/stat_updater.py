from typing import Any, Dict

from bson import ObjectId

from BackEnd.db import players_collection, tournaments_collection


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

        # Persist the latest season stats to the tournament document if applicable.
        if tournament_id:
            try:
                tid = ObjectId(tournament_id)
            except Exception:
                tid = None
            if tid:
                player_doc = players_collection.find_one(
                    {"_id": pid},
                    {"first_name": 1, "last_name": 1, "team": 1, "stats.season": 1},
                )
                if not player_doc:
                    continue
                season_stats = (
                    player_doc.get("stats", {}).get("season", {}) if isinstance(player_doc, dict) else {}
                )
                player_entry = {
                    "first_name": player_doc.get("first_name", ""),
                    "last_name": player_doc.get("last_name", ""),
                    "team": player_doc.get("team", ""),
                    "stats": season_stats,
                }
                tournaments_collection.update_one(
                    {"_id": tid},
                    {"$set": {f"player_stats.{pid}": player_entry}},
                )
