from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
import logging
from typing import Optional
from BackEnd.db import (
    tournaments_collection,
    teams_collection,
    games_collection,
    players_collection,
)
from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.tournament.bracket_logic import update_bracket_from_results
from BackEnd.main import run_simulation
from BackEnd.utils.shared import summarize_game_state
from BackEnd.utils import stat_updater
from bson import ObjectId

router = APIRouter()
logger = logging.getLogger(__name__)


def get_user_team_from_tournament(tournament_doc: dict) -> tuple[str | None, str | None]:
    """
    Get user team identifiers from tournament document with backward compatibility.
    
    ✅ MIGRATION (February 2025): Created to align with Franchise mode pattern.
    Uses tournament document's user_team_object_id as authoritative source.
    Includes backward compatibility for old tournaments missing user_team_object_id.
    
    Returns:
        tuple: (user_team_id: team name, user_team_object_id: ObjectId string)
    """
    # Try tournament document first (new approach)
    user_team_id = tournament_doc.get("user_team_id")
    user_team_object_id = tournament_doc.get("user_team_object_id")
    
    if user_team_id and user_team_object_id:
        return (user_team_id, user_team_object_id)
    
    # ✅ BACKWARD COMPATIBILITY: If user_team_object_id is missing, resolve from user_team_id
    # This handles old tournaments created before the migration
    if user_team_id and not user_team_object_id:
        team_doc = teams_collection.find_one({"name": user_team_id})
        if team_doc:
            return (user_team_id, str(team_doc["_id"]))
    
    # If not found, return None values
    return (None, None)


class StartTournamentRequest(BaseModel):
    """Payload for creating a new tournament."""
    user_team_id: str

class TournamentResultRequest(BaseModel):
    tournament_id: str
    game_id: str
    winner: str
    score: dict[str, int] | None = None

class SimulateRequest(BaseModel):
    tournament_id: str

class TournamentTrainingRequest(BaseModel):
    tournament_id: str
    team_id: Optional[str] = None
    training_data: dict  # Contains player_drills, team_drills, general, coaching_focus


@router.get("/tournament/team-stats")
def tournament_team_stats(tournament_id: str):
    """Get team stats by aggregating player stats from tournament document.
    
    ✅ SS&S: Aggregates from tournament.players object (tournament-specific stats),
    not from universal players_collection.
    """
    try:
        tid = ObjectId(tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament_id")
    
    tournament_doc = tournaments_collection.find_one({"_id": tid}, {"players": 1, "teams": 1})
    if not tournament_doc:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    players = tournament_doc.get("players", {})
    tournament_teams = tournament_doc.get("teams", {})
    
    # Get all team IDs from tournament_teams
    team_stats_map: dict[str, dict[str, int]] = {}
    
    # Initialize team stats for all teams in tournament
    for team_id in tournament_teams.keys():
        team_id_str = str(team_id)
        team_stats_map[team_id_str] = {
            "PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0,
            "FGM": 0, "FGA": 0, "TPM": 0, "TPA": 0, "FTM": 0, "FTA": 0,
            "DREB": 0, "OREB": 0, "TREB": 0,
            "TO": 0, "F": 0,
            "DEF_A": 0, "DEF_S": 0, "SCR_A": 0, "SCR_S": 0
        }
    
    # Aggregate stats from players object
    players_with_stats = 0
    players_without_team_id = 0
    players_without_stats = 0
    for pid, pdata in players.items():
        meta = pdata.get("meta", {})
        team_id = meta.get("team_id")
        if not team_id:
            players_without_team_id += 1
            continue
        
        team_id_str = str(team_id)
        season_stats = pdata.get("season", {})
        if not season_stats:
            players_without_stats += 1
            continue
        
        if team_id_str not in team_stats_map:
            team_stats_map[team_id_str] = {
                "PTS": 0, "REB": 0, "AST": 0, "STL": 0, "BLK": 0,
                "FGM": 0, "FGA": 0, "TPM": 0, "TPA": 0, "FTM": 0, "FTA": 0,
                "DREB": 0, "OREB": 0, "TREB": 0,
                "TO": 0, "F": 0,
                "DEF_A": 0, "DEF_S": 0, "SCR_A": 0, "SCR_S": 0
            }
        
        players_with_stats += 1
        # Sum all stats for this team (map 3PTM to TPM for output)
        for stat, val in season_stats.items():
            if isinstance(val, (int, float)):
                output_stat = stat
                if stat == "3PTM":
                    output_stat = "TPM"
                elif stat == "3PTA":
                    output_stat = "TPA"
                
                if output_stat in team_stats_map[team_id_str]:
                    team_stats_map[team_id_str][output_stat] += val
    
    # Get PF/PA from standings (teams collection)
    standings_data = {}
    teams_list = list(teams_collection.find({}, {"name": 1, "PF": 1, "PA": 1, "_id": 1}))
    for t in teams_list:
        team_id_str = str(t["_id"])
        standings_data[team_id_str] = {
            "PF": t.get("PF", 0),
            "PA": t.get("PA", 0)
        }
    
    # Convert to output format with team names
    output = []
    for team_id_str, stats in team_stats_map.items():
        try:
            team_doc = teams_collection.find_one({"_id": ObjectId(team_id_str)}, {"name": 1})
            team_name = team_doc.get("name", team_id_str) if team_doc else team_id_str
        except Exception:
            team_name = team_id_str
        
        # Add PF/PA from standings
        if team_id_str in standings_data:
            stats["PF"] = standings_data[team_id_str]["PF"]
            stats["PA"] = standings_data[team_id_str]["PA"]
        else:
            stats["PF"] = 0
            stats["PA"] = 0
        
        # Calculate TREB from DREB + OREB
        stats["TREB"] = stats.get("DREB", 0) + stats.get("OREB", 0)
        
        output.append({"team": team_name, "stats": stats})
    
    # Log for debugging
    print(f"🔍 [TOURNAMENT_TEAM_STATS] Processed {players_with_stats} players with stats, {players_without_team_id} without team_id, {players_without_stats} without stats")
    
    return {"teams": output}


@router.get("/tournament/leaders")
def get_tournament_leaders(tournament_id: str, recompute: bool = False):
    """Return top leaders for key stats within a tournament.

    Leaderboards are cached on the tournament document. Pass ``recompute=true``
    to rebuild them on demand."""
    try:
        tid = ObjectId(tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament_id")

    tourney = tournaments_collection.find_one({"_id": tid})
    if not tourney:
        raise HTTPException(status_code=404, detail="Tournament not found")

    if recompute or "leaderboards" not in tourney:
        leaderboards = stat_updater.recompute_tournament_leaders(str(tid))
    else:
        leaderboards = tourney.get("leaderboards", {})

    return leaderboards

@router.post("/start-tournament")
def start_tournament(request: StartTournamentRequest):
    team_docs = list(teams_collection.find({}, {"name": 1}))
    team_ids = [team["name"] for team in team_docs]

    if request.user_team_id not in team_ids:
        raise HTTPException(status_code=400, detail="Invalid user_team_id")

    # Reset all player stats for teams in this tournament
    zero_stats = {key: 0 for key in BOX_SCORE_KEYS}
    zero_stats["Outlet_Score_List"] = []  # Outlet_Score_List is an array, not an integer
    for tid in team_ids:
        players_collection.update_many(
            {"team": tid},
            {
                "$set": {
                    "stats.game": zero_stats,
                    "stats.season": zero_stats,
                    "stats.career": zero_stats,
                    "stats.applied_games": [],
                }
            },
        )

    manager = TournamentManager(
        user_team_id=request.user_team_id,
        tournaments_collection=tournaments_collection,
        team_ids=team_ids,
    )
    tournament = manager.create_tournament()
    tournament["_id"] = str(tournament["_id"])
    return tournament

@router.post("/simulate-tournament-round")
def simulate_round(request: SimulateRequest):
    """Simulate all non-user games for the current round and return the user's
    matchup. If the user game has already been played, a flag is returned."""

    try:
        try:
            tournament_id = ObjectId(request.tournament_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid tournament_id")

        tournament_doc = tournaments_collection.find_one({"_id": tournament_id})
        if not tournament_doc:
            raise HTTPException(status_code=404, detail="Tournament not found")

        manager = TournamentManager(tournaments_collection=tournaments_collection)
        manager.tournament = tournament_doc
        manager.tournament_id = tournament_id

        round_name = f"round{tournament_doc['current_round']}"
        matchups = tournament_doc["bracket"].get(round_name, [])

        user_team_id = tournament_doc.get("user_team_id")
        user_matchup = None
        already_played = False

        for i, matchup in enumerate(matchups):
            if user_team_id in [matchup["home_team"], matchup["away_team"]]:
                user_matchup = {"home": matchup["home_team"], "away": matchup["away_team"]}
                if matchup.get("game_id"):
                    already_played = True
                continue  # skip sim for user game

            # Skip games already simulated
            if matchup.get("game_id"):
                continue

            print(f"🔍 About to run simulation: {matchup['home_team']} vs {matchup['away_team']}")
            game = run_simulation(matchup["home_team"], matchup["away_team"])
            print(f"🔍 Simulation completed, game type: {type(game)}")
            summary = summarize_game_state(game)
            print(f"🔍 Summary created, type: {type(summary)}")
            game_id = games_collection.insert_one(summary).inserted_id
            logger.info(f"✅ [SIMULATE-ROUND] Game document inserted for round {tournament_doc['current_round']} match {i}, game_id: {game_id} (type: {type(game_id)}), _id in summary: {summary.get('_id')}")
            #add a print statement here to show team name and score for each team after the game is simulated
            print(f"Home team: {matchup['home_team']} - Score: {summary['score'][matchup['home_team']]}")
            print(f"Away team: {matchup['away_team']} - Score: {summary['score'][matchup['away_team']]}")
            winner = (
                matchup["home_team"]
                if summary["score"][matchup["home_team"]] > summary["score"][matchup["away_team"]]
                else matchup["away_team"]
            )
            manager.save_game_result(round_name, i, str(game_id), winner)
            logger.info(f"🔍 [SIMULATE-ROUND] About to finalize game stats for game_id: {str(game_id)} (type: {type(str(game_id))}), tournament_id: {request.tournament_id}")
            stat_updater.finalize_game(
                str(game_id), mode="tournament", tournament_id=request.tournament_id
            )
            logger.info(f"✅ [SIMULATE-ROUND] Game stats finalized successfully for game_id: {str(game_id)}")
            result_doc = {
                "home_team": matchup["home_team"],
                "away_team": matchup["away_team"],
                "score": summary.get("score", {}),
                "winner": winner,
                "round": tournament_doc["current_round"],
                "match_index": i,
            }
            tournaments_collection.update_one(
                {"_id": tournament_id}, {"$push": {"results": result_doc}}
            )

        # Reload tournament to check if round is complete
        updated_doc = tournaments_collection.find_one({"_id": tournament_id})
        if updated_doc:
            all_done = all(m.get("winner") for m in updated_doc["bracket"].get(round_name, []))
            if all_done:
                manager.tournament = updated_doc
                manager.advance_round()

        # Sync bracket state with stored results
        update_bracket_from_results(
            tournament_id, tournaments_collection=tournaments_collection
        )

        if already_played:
            return {"already_played": True}
        if user_matchup:
            return user_matchup

        current_round = (
            manager.tournament.get("current_round")
            if getattr(manager, "tournament", None)
            else None
        )
        logger.error(
            "User matchup not found: tournament_id=%s current_round=%s user_team_id=%s",
            str(tournament_id),
            current_round,
            user_team_id,
        )
        raise HTTPException(status_code=409, detail="User matchup not found")

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print("🚨 Error in simulate_round:", str(e))
        print("🚨 Full traceback:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tournament/save-result")
def save_result(request: TournamentResultRequest):
    """Save the user's game result, simulate remaining games in the round and
    persist all results to the tournament document.

    Each result entry includes home/away team, score, winner, round number and
    match index. A log message is printed for each database write indicating
    success or failure.
    """

    from bson import ObjectId

    tournament_id = ObjectId(request.tournament_id)
    tournament = tournaments_collection.find_one({"_id": tournament_id})

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    round_num = tournament["current_round"]
    round_key = "final" if round_num == 3 else f"round{round_num}"

    manager = TournamentManager(tournaments_collection=tournaments_collection)
    manager.tournament = tournament
    manager.tournament_id = tournament_id

    def _log_result(result_doc):
        exists = tournaments_collection.find_one(
            {
                "_id": tournament_id,
                "results": {
                    "$elemMatch": {
                        "round": result_doc["round"],
                        "match_index": result_doc["match_index"],
                    }
                },
            }
        )
        if exists:
            return
        try:
            update_result = tournaments_collection.update_one(
                {"_id": tournament_id}, {"$push": {"results": result_doc}}
            )
            if update_result.modified_count == 1:
                print(
                    f"✅ Saved result for round {result_doc['round']} match {result_doc['match_index']}"
                )
            else:
                print(
                    f"⚠️ No document updated for round {result_doc['round']} match {result_doc['match_index']}"
                )
        except Exception as e:
            print(
                f"❌ Failed to save result for round {result_doc['round']} match {result_doc['match_index']}: {e}"
            )

    # Save user's game result
    user_match_index = None
    home_team = away_team = None
    for i, match in enumerate(tournament["bracket"][round_key]):
        if request.winner in [match["home_team"], match["away_team"]]:
            user_match_index = i
            home_team = match["home_team"]
            away_team = match["away_team"]
            gid = (
                ObjectId(request.game_id)
                if ObjectId.is_valid(request.game_id)
                else request.game_id
            )
            logger.info(f"🔍 [SAVE-RESULT] User game - game_id from request: {request.game_id} (type: {type(request.game_id)}), converted gid: {gid} (type: {type(gid)})")
            summary = games_collection.find_one({"_id": gid}) or {}
            logger.info(f"🔍 [SAVE-RESULT] User game - Found game document: {bool(summary)}, has _id: {bool(summary.get('_id'))}, _id value: {summary.get('_id')}")
            if not summary or not summary.get("_id"):
                logger.error(f"❌ [SAVE-RESULT] User game - Game document not found in games_collection for game_id: {request.game_id}, gid: {gid}")
                logger.error(f"❌ [SAVE-RESULT] Attempting to find game by string ID: {str(request.game_id)}")
                # Try finding by string ID as fallback
                try:
                    summary = games_collection.find_one({"_id": ObjectId(request.game_id)}) or {}
                    if summary and summary.get("_id"):
                        logger.info(f"✅ [SAVE-RESULT] Found game document using ObjectId conversion")
                        gid = summary.get("_id")
                    else:
                        logger.error(f"❌ [SAVE-RESULT] Game document still not found after ObjectId conversion. Cannot proceed with stat finalization.")
                        # Continue without finalize_game - stats will be lost but game result will be saved
                except Exception as e:
                    logger.error(f"❌ [SAVE-RESULT] Error converting game_id to ObjectId: {e}")
            score_map = (
                summary.get("score")
                or summary.get("final_score")
                or request.score
            )
            manager.save_game_result(
                round_key, i, request.game_id, request.winner, score_map
            )
            # Only call finalize_game if we found the game document
            if summary and summary.get("_id"):
                logger.info(f"🔍 [SAVE-RESULT] User game - About to call finalize_game with game_id: {str(gid)} (type: {type(gid)}), tournament_id: {request.tournament_id}")
                stat_updater.finalize_game(
                    str(gid),  # ✅ FIX: Ensure game_id is always a string
                    mode="tournament",
                    tournament_id=request.tournament_id,
                )
                logger.info(f"✅ [SAVE-RESULT] User game - finalize_game completed for game_id: {str(gid)}")
            else:
                logger.error(f"❌ [SAVE-RESULT] Skipping finalize_game - game document not found. Stats will not be applied.")
            user_result = {
                "home_team": home_team,
                "away_team": away_team,
                "score": score_map or {},
                "winner": request.winner,
                "round": round_num,
                "match_index": i,
            }
            _log_result(user_result)
            break

    if user_match_index is None:
        raise HTTPException(status_code=400, detail="User matchup not found")

    # Ensure all match results are recorded
    for i, match in enumerate(manager.tournament["bracket"][round_key]):
        if i == user_match_index:
            continue
        if match.get("game_id"):
            gid = (
                ObjectId(match["game_id"])
                if ObjectId.is_valid(match["game_id"])
                else match["game_id"]
            )
            summary = games_collection.find_one({"_id": gid}) or {}
            score_map = summary.get("score") or summary.get("final_score")
            manager.save_game_result(
                round_key,
                i,
                match["game_id"],
                match["winner"],
                score_map,
            )
            stat_updater.finalize_game(
                gid,
                mode="tournament",
                tournament_id=request.tournament_id,
            )
            result_doc = {
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                "score": score_map or {},
                "winner": match["winner"],
                "round": round_num,
                "match_index": i,
            }
            _log_result(result_doc)
            continue

        try:
            game = run_simulation(match["home_team"], match["away_team"])
            summary = summarize_game_state(game)
            summary["tournament_id"] = str(request.tournament_id)
            summary["round"] = round_key
            summary["match_index"] = i
            insert_result = games_collection.insert_one(summary)
            game_id = insert_result.inserted_id
            stat_updater.finalize_game(
                str(game_id),
                mode="tournament",
                tournament_id=request.tournament_id,
            )
            print(f"✅ Game document inserted for round {round_num} match {i}")
        except Exception as e:
            print(
                f"❌ Failed to simulate or insert game for round {round_num} match {i}: {e}"
            )
            continue

        home = match["home_team"]
        away = match["away_team"]
        score_map = summary.get("score") or summary.get("final_score")
        winner = home if score_map[home] > score_map[away] else away
        manager.save_game_result(round_key, i, str(game_id), winner, score_map)

        result_doc = {
            "home_team": home,
            "away_team": away,
            "score": score_map or {},
            "winner": winner,
            "round": round_num,
            "match_index": i,
        }
        _log_result(result_doc)

    # Use saved results to advance the bracket to the next round.  This relies
    # solely on the stored results and is safe to re-run (idempotent).
    update_bracket_from_results(tournament_id, tournaments_collection=tournaments_collection)

    return {"status": "success"}


@router.get("/tournament/command-center/data")
def tournament_command_center_data(tournament_id: str = Query(...)):
    """
    Return structured command center data for a tournament.
    
    ✅ MIGRATION (Task 4.1): Aligned with Franchise mode pattern.
    Returns structured response matching /franchise/command-center/data format.
    """
    try:
        tid = ObjectId(tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament_id")
    
    doc = tournaments_collection.find_one({"_id": tid})
    if not doc:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    # Get user team identifiers from tournament document
    user_team_id_name, user_team_object_id = get_user_team_from_tournament(doc)
    
    # Get training status
    training_status = doc.get("training_status", {})
    training_completed = training_status.get("training_completed", False)
    session_type = training_status.get("session_type", "pre-tournament")
    current_round = training_status.get("round", doc.get("current_round", 1))
    
    # Get team stats from tournament teams object or universal teams collection
    team_doc = {}
    if user_team_object_id:
        # Try tournament-specific team object first
        tournament_teams = doc.get("teams", {})
        tournament_team_obj = tournament_teams.get(user_team_object_id, {})
        if tournament_team_obj:
            team_doc = tournament_team_obj.get("team_attributes", {})
        else:
            # Fallback to universal team doc
            team_doc = teams_collection.find_one({"_id": ObjectId(user_team_object_id)}) or {}
    elif user_team_id_name:
        # Fallback: resolve by team name
        team_doc = teams_collection.find_one({"name": user_team_id_name}) or {}
    
    response = {
        "team": user_team_id_name,
        "team_id": user_team_object_id,  # ✅ SS&S: Include ObjectId for consistent navigation
        "team_chemistry": team_doc.get("team_chemistry", 0),
        "offense": team_doc.get("offense", "-"),
        "defense": team_doc.get("defense", "-"),
        "athleticism": team_doc.get("athleticism", "-"),
        "training_completed": training_completed,
        "session_type": session_type,
        "current_round": doc.get("current_round", 1),
        "completed": doc.get("completed", False),
        "bracket": doc.get("bracket", {}),
    }
    
    return response


@router.get("/tournament/state")
def tournament_state(tournament_id: str = Query(...)):
    """Return the current bracket state for a tournament.
    
    ⚠️ DEPRECATED: Use /tournament/command-center/data for structured response.
    This endpoint is kept for backward compatibility and returns the full tournament document.
    """
    try:
        tid = ObjectId(tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament_id")
    doc = tournaments_collection.find_one({"_id": tid})
    if not doc:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    # Add user team chemistry if user_team_id is present
    user_team_id = doc.get("user_team_id")
    if user_team_id:
        team_doc = teams_collection.find_one({"name": user_team_id}) or {}
        doc["team_chemistry"] = team_doc.get("team_chemistry", 0)
        doc["offense"] = team_doc.get("offense", "-")
        doc["defense"] = team_doc.get("defense", "-")
        doc["athleticism"] = team_doc.get("athleticism", "-")
        # ✅ SS&S: Include team_id (ObjectId) for consistent navigation
        if team_doc.get("_id"):
            doc["user_team_object_id"] = str(team_doc["_id"])
    
    return jsonable_encoder(doc, custom_encoder={ObjectId: str})


@router.get("/tournament/team-data")
def get_tournament_team_data(tournament_id: str, team_id: str = None, team_name: str = None):
    """
    Get team data (attributes, plays, scouting_data) from tournament teams.
    
    ✅ SS&S: Prefers team_id (ObjectId) for consistent navigation.
    Falls back to team_name resolution for backward compatibility.
    """
    try:
        tid = ObjectId(tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament ID")
    
    # Get tournament document
    tournament_doc = tournaments_collection.find_one({"_id": tid})
    if not tournament_doc:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    # ✅ SS&S: Prefer team_id (ObjectId) if provided
    if team_id:
        try:
            # Validate it's a valid ObjectId
            ObjectId(team_id)
            actual_team_id = team_id
        except Exception:
            # If not a valid ObjectId, try to resolve as team name
            team_doc = teams_collection.find_one({"name": team_id})
            if not team_doc:
                raise HTTPException(status_code=404, detail=f"Team not found: {team_id}")
            actual_team_id = str(team_doc["_id"])
    elif team_name:
        # Fallback to team_name resolution for backward compatibility
        # Try multiple strategies to handle both formatted and unformatted team names
        team_doc = None
        
        # Strategy 1: Try exact match first
        team_doc = teams_collection.find_one({"name": team_name})
        
        # Strategy 2: If not found, try case-insensitive match
        if not team_doc:
            team_doc = teams_collection.find_one({"name": {"$regex": f"^{team_name}$", "$options": "i"}})
        
        # Strategy 3: If still not found, try normalized name (replace dashes with spaces, title case)
        if not team_doc:
            normalized_name = team_name.replace("-", " ").title()
            team_doc = teams_collection.find_one({"name": normalized_name})
        
        # Strategy 4: Fallback to tournament's user_team_id
        if not team_doc:
            fallback_team_name = tournament_doc.get("user_team_id")
            if fallback_team_name and fallback_team_name != team_name:
                team_doc = teams_collection.find_one({"name": fallback_team_name})
        
        if not team_doc:
            raise HTTPException(status_code=404, detail=f"Team not found: {team_name}")
        
        actual_team_id = str(team_doc["_id"])
    else:
        # Get team name from tournament if not provided
        team_name = tournament_doc.get("user_team_id")
        if not team_name:
            raise HTTPException(status_code=404, detail="Team not found")
        team_doc = teams_collection.find_one({"name": team_name})
        if not team_doc:
            raise HTTPException(status_code=404, detail="Team not found")
        actual_team_id = str(team_doc["_id"])
    
    # Get team object from tournament teams
    tournament_teams = tournament_doc.get("teams", {})
    team_obj = tournament_teams.get(actual_team_id, {})
    
    if not team_obj:
        raise HTTPException(status_code=404, detail=f"Team data not found in tournament for team_id: {actual_team_id}")
    
    # Extract team attributes
    team_attributes = {}
    attr_keys = ['shot_threshold', 'discipline', 'fight', 'rebound_modifier', 
                 'momentum_score', 'offensive_efficiency', 'team_chemistry', 'defensive_efficiency',
                 'fb_efficiency', 'pt_efficiency', 'fb_opp_modifier', 'pt_opp_modifier']
    for key in attr_keys:
        if key in team_obj:
            team_attributes[key] = team_obj[key]
        else:
            team_attributes[key] = 0  # Default to 0 if not present
    
    # Get plays data
    plays_data = team_obj.get("plays", {})
    
    # Get scouting data - initialize defense structure if missing (with randomized values for tournament)
    scouting_data = team_obj.get("scouting_data", {})
    if not scouting_data.get("defense"):
        # Initialize with randomized values using populate_scouting_data (for tournament mode)
        from BackEnd.api.gameplan_routes import populate_scouting_data
        scouting_data = populate_scouting_data(mode="tournament")
        # Save initialized scouting_data back to tournament document
        tournaments_collection.update_one(
            {"_id": tid},
            {"$set": {f"teams.{actual_team_id}.scouting_data": scouting_data}}
        )
    else:
        # Ensure each defense has effectiveness value (fallback to 0 if missing)
        defenses = ["Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone"]
        for def_name in defenses:
            if def_name not in scouting_data["defense"]:
                scouting_data["defense"][def_name] = {"effectiveness": 0, "momentum": 0, "cloaking": 0}
            elif "effectiveness" not in scouting_data["defense"][def_name]:
                scouting_data["defense"][def_name]["effectiveness"] = 0
    
    return {
        "team_attributes": team_attributes,
        "plays_data": plays_data,
        "scouting_data": scouting_data
    }


@router.get("/tournament/roster")
def get_tournament_roster(tournament_id: str, team_name: str = None):
    """
    Get roster with tournament-specific player attributes.
    
    Similar to /franchise/roster, this endpoint merges tournament-specific attributes
    (EM, CH, MO) with base attributes from the universal collection. Future training
    support will allow tournament documents to store evolved attributes like franchise mode.
    """
    try:
        tid = ObjectId(tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament ID")
    
    # Get tournament document
    tournament_doc = tournaments_collection.find_one({"_id": tid})
    if not tournament_doc:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    # Get team name from tournament if not provided
    if not team_name:
        team_name = tournament_doc.get("user_team_id")
    
    if not team_name:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get team document - try multiple strategies to handle both formatted and unformatted team names
    team_doc = None
    
    # Strategy 1: Try exact match first
    team_doc = teams_collection.find_one({"name": team_name})
    
    # Strategy 2: If not found, try case-insensitive match
    if not team_doc:
        team_doc = teams_collection.find_one({"name": {"$regex": f"^{team_name}$", "$options": "i"}})
    
    # Strategy 3: If still not found, try normalized name (replace dashes with spaces, title case)
    if not team_doc:
        normalized_name = team_name.replace("-", " ").title()
        team_doc = teams_collection.find_one({"name": normalized_name})
    
    # Strategy 4: Fallback to tournament's user_team_id
    if not team_doc:
        fallback_team_name = tournament_doc.get("user_team_id")
        if fallback_team_name and fallback_team_name != team_name:
            team_doc = teams_collection.find_one({"name": fallback_team_name})
    
    if not team_doc:
        raise HTTPException(status_code=404, detail=f"Team not found: {team_name}")
    
    # ✅ MIGRATION: Use players key instead of player_stats (aligns with Franchise)
    tournament_players = tournament_doc.get("players", {}) or tournament_doc.get("player_stats", {})  # Backward compatibility
    team_player_ids = team_doc.get("player_ids", [])
    
    # Build player list with tournament-specific attributes
    players = []
    for pid in team_player_ids:
        pid_str = str(pid)
        tournament_player_data = tournament_players.get(pid_str, {})
        if not tournament_player_data:
            continue
        
        # Get tournament-specific attributes (currently EM, CH, MO only)
        # Future: will include all evolved attributes when training is added
        tournament_attributes = tournament_player_data.get("attributes", {})
        
        # Get additional data from core collection
        core_player = players_collection.find_one({"_id": pid}, {
            "position_ratings": 1, "height": 1, "weight": 1, "jersey": 1, "year": 1, "attributes": 1,
            "first_name": 1, "last_name": 1
        })
        
        if not core_player:
            continue
        
        # Get position ratings from tournament (with backward compatibility to core)
        position_ratings = tournament_player_data.get("position_ratings")
        if not position_ratings:
            position_ratings = core_player.get("position_ratings", {})
        
        # Merge core attributes with tournament attributes (tournament overrides core)
        core_attributes = core_player.get("attributes", {}) if core_player else {}
        merged_attributes = {**core_attributes, **tournament_attributes}
        
        # Create anchor_ prefixed attributes (like Player class does)
        for attr_key in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]:
            if attr_key in merged_attributes:
                merged_attributes[f"anchor_{attr_key}"] = merged_attributes[attr_key]
        
        # Use tournament player data for name (with meta wrapper), fallback to core
        # Backward compatibility: check meta wrapper first, then root level, then core
        meta = tournament_player_data.get("meta", {})
        first = meta.get("first_name") or tournament_player_data.get("first_name") or core_player.get("first_name", "")
        last = meta.get("last_name") or tournament_player_data.get("last_name") or core_player.get("last_name", "")
        
        player = {
            "_id": pid_str,
            "first_name": first,
            "last_name": last,
            "name": f"{first} {last}".strip(),
            "team": team_name,
            "attributes": merged_attributes,
            "position_ratings": position_ratings,
            "height": core_player.get("height"),
            "weight": core_player.get("weight"),
            "jersey": core_player.get("jersey", 0),
            "year": core_player.get("year")
        }
        players.append(player)
    
    return {"players": players}


@router.post("/tournament/sim-remaining")
def sim_remaining(request: SimulateRequest):
    """Simulate all remaining games until the bracket is complete.

    The endpoint is idempotent; already simulated games are skipped and existing
    results are preserved.  The updated tournament document is returned."""

    try:
        # Debug: show which tournament is being simulated
        print(f"[sim_remaining] Incoming tournament_id={request.tournament_id}")
        tid = ObjectId(request.tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament_id")

    tournament = tournaments_collection.find_one({"_id": tid})
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    manager = TournamentManager(tournaments_collection=tournaments_collection)
    manager.tournament_id = tid

    def _log_result(result_doc):
        exists = tournaments_collection.find_one(
            {
                "_id": tid,
                "results": {
                    "$elemMatch": {
                        "round": result_doc["round"],
                        "match_index": result_doc["match_index"],
                    }
                },
            }
        )
        if not exists:
            tournaments_collection.update_one(
                {"_id": tid}, {"$push": {"results": result_doc}}
            )

    while True:
        tournament = tournaments_collection.find_one({"_id": tid})
        if not tournament or tournament.get("completed"):
            break

        round_num = tournament.get("current_round", 1)
        round_key = "final" if round_num == 3 else f"round{round_num}"
        print(f"[sim_remaining] Processing round {round_num} ({round_key})")
        matchups = tournament.get("bracket", {}).get(round_key, [])
        manager.tournament = tournament

        for i, match in enumerate(matchups):
            # Skip if a result for this matchup already exists
            exists_result = tournaments_collection.find_one(
                {
                    "_id": tid,
                    "results": {
                        "$elemMatch": {"round": round_num, "match_index": i}
                    },
                }
            )

            if match.get("game_id"):
                if not exists_result:
                    summary = games_collection.find_one({"_id": ObjectId(match["game_id"])}) or {}
                    stat_updater.finalize_game(
                        match["game_id"],
                        mode="tournament",
                        tournament_id=request.tournament_id,
                    )
                    score_map = summary.get("score") or summary.get("final_score")
                    result_doc = {
                        "home_team": match["home_team"],
                        "away_team": match["away_team"],
                        "score": score_map or {},
                        "winner": match.get("winner"),
                        "round": round_num,
                        "match_index": i,
                    }
                    _log_result(result_doc)
                else:
                    print(
                        f"[sim_remaining] Skipping round {round_num} match {i} - already has game and result"
                    )
                continue

            if exists_result:
                print(
                    f"[sim_remaining] Skipping round {round_num} match {i} - result already recorded"
                )
                continue

            print(
                f"[sim_remaining] Simulating matchup: {match['home_team']} vs {match['away_team']}"
            )
            game = run_simulation(match["home_team"], match["away_team"])
            summary = summarize_game_state(game)
            game_id = games_collection.insert_one(summary).inserted_id
            stat_updater.finalize_game(
                str(game_id),
                mode="tournament",
                tournament_id=request.tournament_id,
            )
            home = match["home_team"]
            away = match["away_team"]
            winner = home if summary["score"][home] > summary["score"][away] else away
            score_map = summary.get("score") or summary.get("final_score")
            manager.save_game_result(round_key, i, str(game_id), winner, score_map)
            result_doc = {
                "home_team": home,
                "away_team": away,
                "score": score_map or {},
                "winner": winner,
                "round": round_num,
                "match_index": i,
            }
            _log_result(result_doc)

        update_bracket_from_results(tid, tournaments_collection=tournaments_collection)
        print(f"[sim_remaining] Bracket updated after round {round_num}")

    final_doc = tournaments_collection.find_one({"_id": tid})
    if not final_doc:
        raise HTTPException(status_code=404, detail="Tournament not found")

    # Ensure the document is fully JSON serializable before returning so the
    # API does not raise a 500 error when encoding ``ObjectId`` instances.
    return jsonable_encoder(final_doc, custom_encoder={ObjectId: str})


@router.post("/tournament/run-training")
def run_tournament_training(req: TournamentTrainingRequest):
    """
    Run training for a tournament team using tournament-specific player/team attributes.
    Updates only the tournament document, not the core collections.
    """
    from datetime import datetime
    from BackEnd.models.training_execution_v2 import execute_training
    from BackEnd.utils.position_ratings import compute_position_ratings
    
    try:
        tournament_id = ObjectId(req.tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament ID format")

    # Load tournament document
    tournament_doc = tournaments_collection.find_one({"_id": tournament_id})
    if not tournament_doc:
        raise HTTPException(status_code=404, detail="Tournament not found")

    # Get training status and check for duplicate submission
    training_status = tournament_doc.get("training_status", {})
    current_round = tournament_doc.get("current_round", 1)
    if training_status.get("training_completed", False) and training_status.get("round") == current_round:
        # Training already completed for this round, redirect to report
        # SS&S: Only pass navigation params - backend will determine round from state
        return {
            "status": "already_completed",
            "round": current_round,
            "redirect": f"/static/training-report.html?mode=tournament&tournament_id={req.tournament_id}&team_id={req.team_id}"
        }

    # ✅ MIGRATION: Use tournament document's user_team_object_id as source of truth
    # This ensures we're always using the correct team, even if URL params are wrong
    user_team_id_name, user_team_object_id = get_user_team_from_tournament(tournament_doc)
    if not user_team_id_name or not user_team_object_id:
        raise HTTPException(status_code=404, detail="User team not found in tournament document")
    
    # Use tournament document's user_team_object_id as authoritative team_id
    team_id = user_team_object_id
    team_name = user_team_id_name  # ✅ FIX: Use team name from tournament document
    
    # Log if URL team_id doesn't match (for debugging)
    if req.team_id and req.team_id != team_id:
        logger.warning(f"⚠️ [TOURNAMENT TRAINING] URL team_id ({req.team_id}) doesn't match tournament document user_team_object_id ({team_id}). Using tournament document value.")
    
    # Get team document for player_ids lookup
    team_doc = teams_collection.find_one({"_id": ObjectId(team_id)})
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")

    # ✅ MIGRATION: Use players key instead of player_stats (aligns with Franchise)
    tournament_players = tournament_doc.get("players", {}) or tournament_doc.get("player_stats", {})  # Backward compatibility
    team_player_ids = team_doc.get("player_ids", [])
    
    # Build player list with tournament-specific attributes
    players_for_training = []
    for pid in team_player_ids:
        pid_str = str(pid)
        tournament_player_data = tournament_players.get(pid_str, {})
        if not tournament_player_data:
            continue
        
        # Get core player data for additional fields and attributes
        core_player = players_collection.find_one({"_id": pid}, {
            "first_name": 1, "last_name": 1, "height": 1, "attributes": 1
        })
        if not core_player:
            try:
                core_player = players_collection.find_one({"_id": ObjectId(pid)}, {
                    "first_name": 1, "last_name": 1, "height": 1, "attributes": 1
                })
            except:
                pass
        
        # Get tournament-specific attributes
        tournament_attributes = tournament_player_data.get("attributes", {})
        
        # For backward compatibility: if tournament only has EM, CH, MO (old format),
        # merge with core attributes. New tournaments will have all attributes stored.
        standard_attrs = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
        has_all_attrs = all(attr in tournament_attributes for attr in standard_attrs)
        
        if not has_all_attrs and core_player:
            # Merge core attributes with tournament attributes (tournament overrides core)
            core_attributes = core_player.get("attributes", {}) if core_player else {}
            tournament_attributes = {**core_attributes, **tournament_attributes}
            logger.info(f"📊 [TOURNAMENT TRAINING] Merged core attributes for player {pid_str} (backward compatibility)")
        
        # Get player metadata (with meta wrapper support and backward compatibility)
        meta = tournament_player_data.get("meta", {})
        first_name = meta.get("first_name") or tournament_player_data.get("first_name") or (core_player.get("first_name", "") if core_player else "")
        last_name = meta.get("last_name") or tournament_player_data.get("last_name") or (core_player.get("last_name", "") if core_player else "")
        
        # Get position ratings from tournament (with backward compatibility to core)
        position_ratings = tournament_player_data.get("position_ratings")
        if not position_ratings and core_player:
            position_ratings = core_player.get("position_ratings", {})
        
        # Build player dict for training
        player = {
            "_id": pid_str,
            "first_name": first_name,
            "last_name": last_name,
            "team": team_name,
            "attributes": tournament_attributes,
            "position_ratings": position_ratings or {}
        }
        players_for_training.append(player)

    if not players_for_training:
        raise HTTPException(status_code=404, detail="No players found for training")

    # Get team data from tournament document
    tournament_teams = tournament_doc.get("teams", {})
    team_data = tournament_teams.get(team_id, {})
    
    # Get team attributes from tournament document (if stored) or initialize
    # For now, tournament doesn't store team attributes separately, so we'll initialize them
    # In the future, tournament could store team attributes similar to franchise
    from BackEnd.models.team_manager import TeamManager
    team_stats = team_data.get("team_attributes", TeamManager.init_team_attributes(mode="tournament"))
    if not isinstance(team_stats, dict):
        team_stats = TeamManager.init_team_attributes(mode="tournament")

    # Extract training data
    training_data = req.training_data
    allocations = {
        "player_drills": training_data.get("player_drills", {}),
        "team_drills": training_data.get("team_drills", {}),
        "general": training_data.get("general", {})
    }
    coaching_focus = training_data.get("coaching_focus")

    # Execute training
    # ✅ Get plays, game plan settings, and playbook settings for training
    # These are the LATEST settings saved from Game Plan and Playbooks screens
    # When playbook_training_mode == "current-playbooks", these settings will be used
    plays_data = team_data.get("plays", {})
    playcall_settings = team_data.get("playcall_settings", {})
    strategy_settings = team_data.get("strategy_settings", {})
    playbook_settings = team_data.get("playbook_settings", {})
    scouting_data = team_data.get("scouting_data", {})
    
    # Initialize plays_data if empty (first time training for this team)
    if not plays_data:
        logger.warning(f"📚 [API] plays_data is empty, populating from universal plays collection")
        from BackEnd.api.gameplan_routes import populate_team_plays
        plays_data = populate_team_plays(mode="tournament")
        # Save to database
        tournaments_collection.update_one(
            {"_id": tournament_id},
            {"$set": {f"teams.{team_id}.plays": plays_data}}
        )
    
    # Initialize scouting_data if empty or missing defense structure
    if not scouting_data or "defense" not in scouting_data:
        logger.warning(f"📚 [API] scouting_data is empty or missing defense structure, initializing")
        from BackEnd.models.team_manager import TeamManager
        # Get team name for initialization
        team_doc = teams_collection.find_one({"_id": ObjectId(team_id)})
        team_name = team_doc.get("name", team_id) if team_doc else team_id
        # Create a temporary TeamManager to use its initialization method
        temp_team = TeamManager(name=team_name, mode="tournament")
        scouting_data = temp_team.scouting_data
        # Save to database
        tournaments_collection.update_one(
            {"_id": tournament_id},
            {"$set": {f"teams.{team_id}.scouting_data": scouting_data}}
        )
    
    updated_players, updated_team, updated_plays, updated_scouting_data, training_report = execute_training(
        players_for_training,
        team_stats,
        allocations,
        coaching_focus,
        plays_data=plays_data,
        playcall_settings=playcall_settings,
        strategy_settings=strategy_settings,
        playbook_settings=playbook_settings,
        scouting_data=scouting_data,
        playbook_training_mode=training_data.get("playbook_training_mode", "current-playbooks")
    )
    
    # Recalculate position ratings for each player after training
    position_ratings_updates = {}
    for player in updated_players:
        pid = player["_id"]
        # Get player's height
        core_player = players_collection.find_one({"_id": pid}, {"height": 1})
        if not core_player:
            try:
                core_player = players_collection.find_one({"_id": ObjectId(pid)}, {"height": 1})
            except:
                pass
        height = core_player.get("height") if core_player else None
        
        # Build player dict for position ratings calculation
        player_for_ratings = {
            "attributes": player.get("attributes", {}),
            "height": height,
            "name": f"{player.get('first_name', '')} {player.get('last_name', '')}"
        }
        
        # Compute new position ratings
        new_ratings = compute_position_ratings(player_for_ratings)
        position_ratings_updates[pid] = new_ratings

    # Use training report data for player and team changes
    # Support both old field names (player_changes, team_changes) and new standardized names (player_logs, team_log)
    player_logs = training_report.get("player_logs") or training_report.get("player_changes", {})
    team_log = training_report.get("team_log") or training_report.get("team_changes", {})

    # Update tournament document with new attribute values and position ratings
    tournament_update = {}
    
    # Update plays data
    if updated_plays:
        tournament_update[f"teams.{team_id}.plays"] = updated_plays
    
    # Update scouting_data (defenses)
    if updated_scouting_data:
        tournament_update[f"teams.{team_id}.scouting_data"] = updated_scouting_data
    
    for player in updated_players:
        pid = player["_id"]
        attrs = player.get("attributes", {})
        
        # ✅ MIGRATION: Use players key instead of player_stats (aligns with Franchise)
        # Save ALL attributes (like franchise mode) - not just modified ones
        # This ensures all attributes are stored in the tournament document
        for attr in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ", "CH", "EM", "MO"]:
            anchor_key = f"anchor_{attr}"
            # Save anchor_ value if it exists (post-training value)
            if anchor_key in attrs:
                tournament_update[f"players.{pid}.attributes.{anchor_key}"] = attrs[anchor_key]
            # Always save base attribute value (even if no anchor_ exists)
            if attr in attrs:
                tournament_update[f"players.{pid}.attributes.{attr}"] = attrs[attr]
        
        # NG doesn't have an anchor_key, save it directly if it exists
        if "NG" in attrs:
            tournament_update[f"players.{pid}.attributes.NG"] = attrs["NG"]
        
        # Update position ratings for this player (if tournament stores them)
        if pid in position_ratings_updates:
            tournament_update[f"players.{pid}.position_ratings"] = position_ratings_updates[pid]

    # Mark training as completed and update status
    # Get session_type from training data (defaults to "in-season" if not provided)
    session_type = training_data.get("session_type", "in-season")
    
    tournament_update["training_status.training_completed"] = True
    tournament_update["training_status.round"] = current_round
    tournament_update["training_status.last_training_date"] = datetime.now().strftime("%Y-%m-%d")
    tournament_update["training_status.session_type"] = session_type
    
    # Store training report data
    training_report_data = {
        "round": current_round,
        "player_logs": player_logs,  # Standardized name (was player_changes)
        "team_log": team_log,  # Standardized name (was team_changes)
        "session_type": session_type,
        "coaching_focus": training_report.get("coaching_focus", {}),
        "training_notes": training_report.get("training_notes", []),
        "plays_data": training_report.get("plays_data", {}),
        "scouting_data": training_report.get("scouting_data", {}),
        "plays_effectiveness_changes": training_report.get("plays_effectiveness_changes", {}),
        "defenses_effectiveness_changes": training_report.get("defenses_effectiveness_changes", {}),
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    
    # Store training report in teams.{team_id}.training_reports.{round} (per-round storage, matches Franchise pattern)
    tournament_update[f"teams.{team_id}.training_reports.{current_round}"] = training_report_data
    
    # Also save latest training for quick access
    tournament_update["latest_training"] = training_report_data

    # Save to tournament document
    tournaments_collection.update_one({"_id": tournament_id}, {"$set": tournament_update})
    
    return {
        "status": "success",
        "round": current_round,
        "player_changes": player_logs,
        "team_changes": team_log,
        "coaching_focus": training_report.get("coaching_focus", {}),
        # SS&S: Only pass navigation params (tournament_id, mode, team_id) - backend will determine round from state
        "redirect": f"/static/training-report.html?mode=tournament&tournament_id={req.tournament_id}&team_id={team_name}"
    }
