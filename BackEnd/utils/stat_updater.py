from typing import Any, Dict

from bson import ObjectId
from pymongo import ReturnDocument

from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.db import db, players_collection, tournaments_collection, games_collection


def init_franchise_player_stats(franchise_id: str | ObjectId, roster: list[dict]) -> None:
    """Seed a franchise document with zeroed player stat containers.

    Args:
        franchise_id: The ``_id`` of the franchise document to update. Can be
            a ``str`` or :class:`~bson.objectid.ObjectId`.
        roster: Iterable of player documents. Each entry should contain at
            least ``_id``, ``first_name``, ``last_name`` and ``team`` fields.

    The function populates ``players.<player_id>`` with ``meta``, ``season`` and
    ``career`` blocks. All stat fields start at zero. Player documents in the
    ``players`` collection are left untouched.
    """

    try:
        fid = ObjectId(franchise_id)
    except Exception:
        fid = franchise_id

    zero_stats = {k: 0 for k in BOX_SCORE_KEYS}
    update: Dict[str, Any] = {}

    for player in roster:
        pid = str(player.get("_id"))
        if not pid:
            continue
        meta = {
            "first_name": player.get("first_name", ""),
            "last_name": player.get("last_name", ""),
            "team": player.get("team", ""),
        }
        update[f"players.{pid}"] = {
            "meta": meta,
            "season": zero_stats.copy(),
            "career": zero_stats.copy(),
        }

    if update:
        db.franchises.update_one({"_id": fid}, {"$set": update})


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
        raw_pid = p.get("playerId")
        query_pid = ObjectId(raw_pid) if ObjectId.is_valid(raw_pid) else raw_pid
        team_side = p.get("team")
        pos = p.get("pos")
        team_name = team_map.get(team_side)
        if not raw_pid or not team_name:
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
            {"_id": query_pid, "stats.applied_games": {"$ne": token}},
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
                    {"_id": query_pid},
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
                    "season": season_stats,
                }
                tournaments_collection.update_one(
                    {"_id": tid},
                    {"$set": {f"player_stats.{str(query_pid)}": player_entry}},
                )


def recompute_tournament_leaders(tournament_id: str, limit: int = 10) -> Dict[str, Any]:
    """Rebuild cached leaderboards for a tournament.

    Returns the computed leaderboards dict.  If the tournament is not found,
    an empty dict is returned.  Results are written back to the tournament
    document under the ``leaderboards`` field.
    """
    try:
        tid = ObjectId(tournament_id)
    except Exception:
        return {}

    tourney = tournaments_collection.find_one({"_id": tid})
    if not tourney:
        return {}

    teams: set[str] = set()
    for round_matches in tourney.get("bracket", {}).values():
        for match in round_matches:
            teams.add(match.get("home_team"))
            teams.add(match.get("away_team"))
    teams.discard(None)

    players: list[Dict[str, Any]] = []
    for pid, pdata in tourney.get("player_stats", {}).items():
        if pdata.get("team") not in teams:
            continue
        players.append(
            {
                "player_id": str(pid),
                "first_name": pdata.get("first_name", ""),
                "last_name": pdata.get("last_name", ""),
                "team_name": pdata.get("team", ""),
                "stats": pdata.get("season", {}),
            }
        )

    categories = [
        ("PTS", "MIN"),
        ("REB", "MIN"),
        ("AST", "MIN"),
        ("STL", "MIN"),
        ("BLK", "MIN"),
        ("TPM", "TPA"),
        ("FG%", "FGA"),
        ("FT%", "FTA"),
    ]

    def stat_val(stats: Dict[str, Any], key: str) -> float:
        if key == "FG%":
            makes = stats.get("FGM", 0)
            attempts = stats.get("FGA", 0)
            return (makes / attempts * 100) if attempts else 0.0
        if key == "FT%":
            makes = stats.get("FTM", 0)
            attempts = stats.get("FTA", 0)
            return (makes / attempts * 100) if attempts else 0.0
        if key == "TPM":
            return stats.get("3PTM", 0)
        if key == "TPA":
            return stats.get("3PTA", 0)
        return stats.get(key, 0)

    leaderboards: Dict[str, list] = {}
    for stat, tie_key in categories:
        entries = []
        for p in players:
            season = p.get("stats", {})
            value = stat_val(season, stat)
            tie_val = stat_val(season, tie_key) if tie_key else 0
            if stat == "FG%" and season.get("FGA", 0) == 0:
                continue
            if stat == "FT%" and season.get("FTA", 0) == 0:
                continue
            if stat == "TPM":
                attempts = season.get("3PTA", season.get("TPA", 0))
                if attempts == 0:
                    continue
            entries.append(
                {
                    "player_id": p["player_id"],
                    "first_name": p.get("first_name", ""),
                    "last_name": p.get("last_name", ""),
                    "team_name": p.get("team_name", ""),
                    "value": value,
                    "_tie": tie_val,
                }
            )
        entries.sort(
            key=lambda x: (
                -x["value"],
                -x["_tie"],
                f"{x['first_name']} {x['last_name']}",
            )
        )
        top = []
        for idx, e in enumerate(entries[:limit], start=1):
            top.append(
                {
                    "rank": idx,
                    "player_id": e["player_id"],
                    "first_name": e["first_name"],
                    "last_name": e["last_name"],
                    "team_name": e["team_name"],
                    "value": e["value"],
                }
            )
        leaderboards[stat] = top

    tournaments_collection.update_one(
        {"_id": tid}, {"$set": {"leaderboards": leaderboards}}
    )
    return leaderboards


def rollup_game_to_franchise(franchise_id: str | ObjectId, game_id: str | ObjectId) -> None:
    """Aggregate a game's stats into a franchise document.

    The update is idempotent per ``game_id`` thanks to the ``processed_games``
    guard.  Per-player season and career totals are incremented, per-game
    averages and shooting percentages are recomputed, and ``game_id`` is
    appended to ``processed_games``.
    """

    try:
        fid = ObjectId(franchise_id)
    except Exception:
        fid = franchise_id

    game = games_collection.find_one({"_id": game_id})
    if not game and isinstance(game_id, str):
        try:
            game = games_collection.find_one({"_id": ObjectId(game_id)})
        except Exception:
            game = None
    if not game:
        return

    players = game.get("players", [])
    box_score = game.get("box_score", {})
    team_map = {"home": game.get("home_team"), "away": game.get("away_team")}

    inc_doc: Dict[str, Any] = {}
    set_doc: Dict[str, Any] = {}

    for p in players:
        pid = str(p.get("playerId"))
        team_side = p.get("team")
        pos = p.get("pos")
        team_name = team_map.get(team_side)
        if not pid or not team_name:
            continue
        stat_block = box_score.get(team_name, {}).get(pos, p.get("stats", {}))
        for stat, val in stat_block.items():
            if stat == "name" or not isinstance(val, (int, float)):
                continue
            inc_doc[f"player_stats.{pid}.season.{stat}"] = inc_doc.get(
                f"player_stats.{pid}.season.{stat}", 0
            ) + val
            inc_doc[f"player_stats.{pid}.career.{stat}"] = inc_doc.get(
                f"player_stats.{pid}.career.{stat}", 0
            ) + val
        inc_doc[f"player_stats.{pid}.season.GP"] = inc_doc.get(
            f"player_stats.{pid}.season.GP", 0
        ) + 1
        inc_doc[f"player_stats.{pid}.career.GP"] = inc_doc.get(
            f"player_stats.{pid}.career.GP", 0
        ) + 1

        meta = players_collection.find_one(
            {"_id": pid}, {"first_name": 1, "last_name": 1, "team": 1}
        )
        if meta:
            set_doc[f"player_stats.{pid}.first_name"] = meta.get("first_name", "")
            set_doc[f"player_stats.{pid}.last_name"] = meta.get("last_name", "")
            set_doc[f"player_stats.{pid}.team"] = meta.get("team", "")

    if not inc_doc:
        return

    update_doc: Dict[str, Any] = {
        "$inc": inc_doc,
        "$addToSet": {"processed_games": game_id},
    }
    if set_doc:
        update_doc["$set"] = set_doc

    result = db.franchises.find_one_and_update(
        {"_id": fid, "processed_games": {"$ne": game_id}},
        update_doc,
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        return

    avg_doc: Dict[str, Any] = {}
    for p in players:
        pid = str(p.get("playerId"))
        pdata = result.get("player_stats", {}).get(pid, {})
        season_totals = pdata.get("season", {})
        gp = season_totals.get("GP", 0)
        averages: Dict[str, Any] = {}
        if gp:
            for stat in BOX_SCORE_KEYS:
                averages[stat] = season_totals.get(stat, 0) / gp
            averages["FG%"] = (
                season_totals.get("FGM", 0) / season_totals.get("FGA", 0) * 100
                if season_totals.get("FGA", 0)
                else 0.0
            )
            averages["FT%"] = (
                season_totals.get("FTM", 0) / season_totals.get("FTA", 0) * 100
                if season_totals.get("FTA", 0)
                else 0.0
            )
        else:
            for stat in BOX_SCORE_KEYS:
                averages[stat] = 0
            averages["FG%"] = 0.0
            averages["FT%"] = 0.0
        avg_doc[f"player_stats.{pid}.averages"] = averages

    if avg_doc:
        db.franchises.update_one({"_id": fid}, {"$set": avg_doc})


def finalize_game(
    game_id: str,
    *,
    mode: str | None = None,
    tournament_id: str | None = None,
    franchise_id: str | None = None,
) -> None:
    """Persist finished game stats into aggregate documents for supported modes.

    Scrimmage games (or calls with ``mode`` omitted) should not write any
    aggregate data.  They rely solely on :func:`update_game_stats` for per-turn
    box score updates.  Passing ``mode="scrimmage"`` therefore causes an early
    return so future modes don't unintentionally create aggregates.
    """
    if mode in (None, "scrimmage"):
        # Explicitly skip aggregation for scrimmages and unspecified modes.
        return
    if mode == "tournament" and tournament_id:
        try:
            tid = ObjectId(tournament_id)
        except Exception:
            return

        result = tournaments_collection.update_one(
            {"_id": tid, "applied_games": {"$ne": game_id}},
            {"$addToSet": {"applied_games": game_id}},
        )

        if result.modified_count == 0:
            return

        try:
            gid = ObjectId(game_id)
        except Exception:
            gid = game_id

        game = games_collection.find_one({"_id": gid}) or {}
        apply_stats_from_summary(game, game_id, tournament_id)
        recompute_tournament_leaders(tournament_id)

        return

    if mode == "franchise" and franchise_id:
        try:
            fid = ObjectId(franchise_id)
        except Exception:
            return

        game = games_collection.find_one({"_id": game_id})
        if not game and isinstance(game_id, str):
            try:
                game = games_collection.find_one({"_id": ObjectId(game_id)})
            except Exception:
                game = None
        if not game:
            return

        players = game.get("players", [])
        box_score = game.get("box_score", {})
        team_map = {"home": game.get("home_team"), "away": game.get("away_team")}

        inc_doc: Dict[str, Any] = {}
        for p in players:
            pid = p.get("playerId")
            team_side = p.get("team")
            pos = p.get("pos")
            team_name = team_map.get(team_side)
            if not pid or not team_name:
                continue
            stat_block = box_score.get(team_name, {}).get(pos, p.get("stats", {}))
            for stat, val in stat_block.items():
                if stat == "name" or not isinstance(val, (int, float)):
                    continue
                inc_doc[f"players.{pid}.season.{stat}"] = inc_doc.get(
                    f"players.{pid}.season.{stat}", 0
                ) + val
                inc_doc[f"players.{pid}.career.{stat}"] = inc_doc.get(
                    f"players.{pid}.career.{stat}", 0
                ) + val

        update: Dict[str, Any] = {"$addToSet": {"applied_games": game_id}}
        if inc_doc:
            update["$inc"] = inc_doc

        result = db.franchises.update_one(
            {"_id": fid, "applied_games": {"$ne": game_id}},
            update,
        )
        if result.modified_count == 0:
            return

        apply_stats_from_summary(game, game_id)

        return

    return

def update_game_stats(game_id: str | None, deltas: Dict[str, Any], score: Dict[str, Any]) -> None:
    """Apply per-turn stat deltas to the ongoing game's document."""
    if not game_id or not deltas:
        return
    for pid, pdata in deltas.items():
        stats = pdata.get("stats", {})
        if not stats:
            continue
        inc_doc = {f"players.$.stats.{stat}": amt for stat, amt in stats.items()}
        set_doc: Dict[str, Any] = {}
        team_name = pdata.get("team")
        if team_name and team_name in score:
            set_doc[f"score.{team_name}"] = score[team_name]
        update_doc: Dict[str, Any] = {"$inc": inc_doc}
        if set_doc:
            update_doc["$set"] = set_doc
        games_collection.update_one(
            {"_id": game_id, "players.playerId": pid},
            update_doc,
        )
