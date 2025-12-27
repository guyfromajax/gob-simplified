from typing import Any, Dict

from bson import ObjectId
from pymongo import ReturnDocument

from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.db import db, players_collection, tournaments_collection, games_collection, teams_collection


def _clean_stat_block(stats: Dict[str, Any]) -> Dict[str, float]:
    """Return only numeric, non-negative stat entries.

    Any field that is not a number or is negative is discarded. The ``name``
    field, sometimes present in box score rows, is also ignored.
    """

    clean: Dict[str, float] = {}
    for stat, val in stats.items():
        if stat == "name":
            continue
        if isinstance(val, (int, float)) and val >= 0:
            clean[stat] = val
    return clean


def _per_game_block(totals: Dict[str, Any]) -> Dict[str, float]:
    """Return per-game averages for a totals block."""

    gp = totals.get("GP", 0)
    if not gp:
        return {stat: 0 for stat in BOX_SCORE_KEYS}
    return {stat: totals.get(stat, 0) / gp for stat in BOX_SCORE_KEYS}


def _pct_block(totals: Dict[str, Any]) -> Dict[str, float]:
    """Return shooting percentage metrics for a totals block."""

    fga = totals.get("FGA", 0)
    fgm = totals.get("FGM", 0)
    tpa = totals.get("3PTA", 0)
    tpm = totals.get("3PTM", 0)
    fta = totals.get("FTA", 0)
    ftm = totals.get("FTM", 0)
    pts = totals.get("PTS", 0)
    fg_pct = (fgm / fga * 100) if fga else 0.0
    fg3_pct = (tpm / tpa * 100) if tpa else 0.0
    ft_pct = (ftm / fta * 100) if fta else 0.0
    ts_den = 2 * (fga + 0.44 * fta)
    ts_pct = (pts / ts_den * 100) if ts_den else 0.0
    efg_pct = ((fgm + 0.5 * tpm) / fga * 100) if fga else 0.0
    return {"FG%": fg_pct, "3PT%": fg3_pct, "FT%": ft_pct, "TS%": ts_pct, "eFG%": efg_pct}


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
    zero_stats["Outlet_Score_List"] = []  # Outlet_Score_List is an array, not an integer
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
        tid = player.get("team_id")
        if tid is not None:
            meta["team_id"] = str(tid)
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

    # Get box_score from top level or build from team objects
    box_score = summary.get("box_score", {})
    if not box_score:
        # Build box_score from team objects (new structure)
        home_team_obj = summary.get("home_team", {})
        away_team_obj = summary.get("away_team", {})
        if home_team_obj and isinstance(home_team_obj, dict):
            home_team_name = home_team_obj.get("name")
            if home_team_name and "box_score" in home_team_obj:
                box_score[home_team_name] = home_team_obj.get("box_score", {})
        if away_team_obj and isinstance(away_team_obj, dict):
            away_team_name = away_team_obj.get("name")
            if away_team_name and "box_score" in away_team_obj:
                box_score[away_team_name] = away_team_obj.get("box_score", {})
    
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
        team_obj = team_map.get(team_side)
        if not raw_pid or not team_obj:
            continue
        
        # Extract team name from team object (handle both dict and string for backward compatibility)
        if isinstance(team_obj, dict):
            team_name = team_obj.get("name")
        else:
            team_name = team_obj  # Backward compatibility: if it's already a string
        
        if not team_name:
            continue
        stat_block = box_score.get(team_name, {}).get(pos, {})
        inc_fields: Dict[str, Any] = {}
        set_fields: Dict[str, Any] = {}
        for stat, val in _clean_stat_block(stat_block).items():
            # ✅ MIN special handling: Convert seconds to minutes (integer division)
            # Game MIN is tracked in seconds, but season/career MIN should be in minutes
            if stat == "MIN":
                val = val // 60  # Convert seconds to minutes (integer division)
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
    averages and shooting percentages are recomputed within the ``season`` and
    ``career`` blocks, and ``game_id`` is appended to ``processed_games``.
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
        for stat, val in _clean_stat_block(stat_block).items():
            # ✅ MIN special handling: Convert seconds to minutes (integer division)
            # Game MIN is tracked in seconds, but season/career MIN should be in minutes
            if stat == "MIN":
                val = val // 60  # Convert seconds to minutes (integer division)
            # ✅ SS&S: Write to players object (single source of truth), not player_stats
            inc_doc[f"players.{pid}.season.{stat}"] = inc_doc.get(
                f"players.{pid}.season.{stat}", 0
            ) + val
            inc_doc[f"players.{pid}.career.{stat}"] = inc_doc.get(
                f"players.{pid}.career.{stat}", 0
            ) + val
        inc_doc[f"players.{pid}.season.GP"] = inc_doc.get(
            f"players.{pid}.season.GP", 0
        ) + 1
        inc_doc[f"players.{pid}.career.GP"] = inc_doc.get(
            f"players.{pid}.career.GP", 0
        ) + 1

        # ✅ SS&S: Set meta in players object if not already present
        meta = players_collection.find_one(
            {"_id": pid}, {"first_name": 1, "last_name": 1, "team": 1, "team_id": 1}
        )
        if meta:
            # Only set meta if it doesn't already exist (preserve existing meta)
            set_doc[f"players.{pid}.meta.first_name"] = meta.get("first_name", "")
            set_doc[f"players.{pid}.meta.last_name"] = meta.get("last_name", "")
            set_doc[f"players.{pid}.meta.team"] = meta.get("team", "")
            if meta.get("team_id"):
                set_doc[f"players.{pid}.meta.team_id"] = str(meta.get("team_id"))

    if not inc_doc:
        return

    # ✅ SS&S: Use applied_games (not processed_games) for consistency with finalize_game()
    update_doc: Dict[str, Any] = {
        "$inc": inc_doc,
        "$addToSet": {"applied_games": game_id},
    }
    if set_doc:
        update_doc["$set"] = set_doc

    # ✅ SS&S: Use applied_games (not processed_games) for consistency with finalize_game()
    result = db.franchises.find_one_and_update(
        {"_id": fid, "applied_games": {"$ne": game_id}},
        update_doc,
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        return

    # ✅ SS&S: Calculate per_game and percentages from players object (not player_stats)
    stats_doc: Dict[str, Any] = {}
    for p in players:
        pid = str(p.get("playerId"))
        pdata = result.get("players", {}).get(pid, {})
        season_totals = pdata.get("season", {})
        career_totals = pdata.get("career", {})
        # Store per_game and percentages in players object for easy access
        stats_doc[f"players.{pid}.season.per_game"] = _per_game_block(season_totals)
        stats_doc[f"players.{pid}.career.per_game"] = _per_game_block(career_totals)
        stats_doc[f"players.{pid}.season.percentages"] = _pct_block(season_totals)
        stats_doc[f"players.{pid}.career.percentages"] = _pct_block(career_totals)

    if stats_doc:
        db.franchises.update_one({"_id": fid}, {"$set": stats_doc})


def _update_defensive_playcall_season_stats(game: Dict[str, Any]) -> None:
    """Update defensive playcall season_stats from game_stats for both teams.
    
    Extracts scouting data from the game document and copies all game_stats
    values to season_stats for each defensive playcall (Man, 2-3 Zone, etc.).
    This is called at the end of games in tournament and franchise modes.
    """
    teams_obj = game.get("teams", {})
    if not teams_obj:
        return
    
    for team_id, team_data in teams_obj.items():
        scouting = team_data.get("scouting", {})
        defense_data = scouting.get("defense", {})
        
        if not defense_data:
            continue
        
        # Build $inc operations for all defensive playcall season_stats
        inc_doc: Dict[str, Any] = {}
        
        for playcall_name, playcall_data in defense_data.items():
            game_stats = playcall_data.get("game_stats", {})
            if not game_stats:
                continue
            
            # Base stats: used, success
            if "used" in game_stats:
                inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.used"] = game_stats["used"]
            if "success" in game_stats:
                inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.success"] = game_stats["success"]
            
            # Granular stats: vs_motion, vs_set, vs_inside, vs_attack, vs_outside
            for vs_key in ["vs_motion", "vs_set", "vs_inside", "vs_attack", "vs_outside"]:
                vs_data = game_stats.get(vs_key, {})
                if isinstance(vs_data, dict):
                    if "attempts" in vs_data:
                        inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.{vs_key}.attempts"] = vs_data["attempts"]
                    if "success" in vs_data:
                        inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.{vs_key}.success"] = vs_data["success"]
            
            # Combination stats: vs_motion_inside, vs_motion_attack, etc.
            for combo_key in ["vs_motion_inside", "vs_motion_attack", "vs_motion_outside",
                             "vs_set_inside", "vs_set_attack", "vs_set_outside"]:
                combo_data = game_stats.get(combo_key, {})
                if isinstance(combo_data, dict):
                    if "attempts" in combo_data:
                        inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.{combo_key}.attempts"] = combo_data["attempts"]
                    if "success" in combo_data:
                        inc_doc[f"scouting_data.defense.{playcall_name}.season_stats.{combo_key}.success"] = combo_data["success"]
        
        # Update the team document if we have any stats to increment
        if inc_doc:
            # Find team by team_id (which is stored in the teams object key)
            # team_id is typically a string matching the team_id field in teams collection
            result = teams_collection.update_one(
                {"team_id": team_id},
                {"$inc": inc_doc}
            )
            
            # If team_id lookup failed, try finding by name as fallback
            if result.matched_count == 0:
                # Get team name from game document
                home_team_id = game.get("home_team_id")
                away_team_id = game.get("away_team_id")
                home_team_data = game.get("home_team", {})
                away_team_data = game.get("away_team", {})
                home_team_name = home_team_data.get("name") if isinstance(home_team_data, dict) else game.get("home_team", "")
                away_team_name = away_team_data.get("name") if isinstance(away_team_data, dict) else game.get("away_team", "")
                
                team_name = None
                if team_id == home_team_id:
                    team_name = home_team_name
                elif team_id == away_team_id:
                    team_name = away_team_name
                
                if team_name:
                    teams_collection.update_one(
                        {"name": team_name},
                        {"$inc": inc_doc}
                    )


def backfill_franchise_player_stats(franchise_id: str | ObjectId) -> None:
    """Migrate a franchise document from legacy ``players`` schema.

    Existing ``players`` entries are converted to the ``player_stats`` structure
    used by :func:`rollup_game_to_franchise`.  ``applied_games`` is renamed to
    ``processed_games`` and per-game/percentage helpers are generated for both
    season and career totals.
    """

    try:
        fid = ObjectId(franchise_id)
    except Exception:
        fid = franchise_id

    doc = db.franchises.find_one({"_id": fid})
    if not doc:
        return

    player_stats: Dict[str, Any] = {}
    for pid, pdata in (doc.get("players") or {}).items():
        meta = pdata.get("meta", {})
        season_totals = _clean_stat_block(pdata.get("season", {}))
        career_totals = _clean_stat_block(pdata.get("career", {}))
        player_stats[pid] = {
            "first_name": meta.get("first_name", ""),
            "last_name": meta.get("last_name", ""),
            "team": meta.get("team", ""),
            "season": {
                **season_totals,
                "per_game": _per_game_block(season_totals),
                "percentages": _pct_block(season_totals),
            },
            "career": {
                **career_totals,
                "per_game": _per_game_block(career_totals),
                "percentages": _pct_block(career_totals),
            },
        }

    processed_games = [str(g) for g in doc.get("applied_games", []) if g]

    db.franchises.update_one(
        {"_id": fid},
        {
            "$set": {
                "player_stats": player_stats,
                "processed_games": processed_games,
            },
            "$unset": {"players": "", "applied_games": ""},
        },
    )


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
        
        # Update defensive playcall season_stats from game_stats
        _update_defensive_playcall_season_stats(game)

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
            for stat, val in _clean_stat_block(stat_block).items():
                # ✅ MIN special handling: Convert seconds to minutes (integer division)
                # Game MIN is tracked in seconds, but season/career MIN should be in minutes
                if stat == "MIN":
                    val = val // 60  # Convert seconds to minutes (integer division)
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
        
        # Update defensive playcall season_stats from game_stats
        _update_defensive_playcall_season_stats(game)

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
