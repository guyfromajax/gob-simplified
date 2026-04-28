from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
import logging
import re
import time
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
from BackEnd.tournament.bracket_engine import get_round_name
from BackEnd.main import run_simulation
from BackEnd.utils.shared import summarize_game_state
from BackEnd.utils import stat_updater
from BackEnd.utils.team_stats_aggregator import aggregate_team_stats_from_players
from BackEnd.utils.roster_builder import build_roster_players
from BackEnd.utils.command_center_data import build_command_center_base
from bson import ObjectId

from BackEnd.utils.auth import get_current_user
from BackEnd.utils.ownership import verify_tournament_owned_by_user

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


def _team_oid_to_name(oid: str) -> str | None:
    """Resolve team ObjectId string to name. For bracket Oid↔name at API edges."""
    if not oid:
        return None
    try:
        d = teams_collection.find_one({"_id": ObjectId(oid)}, {"name": 1})
        return d.get("name") if d else None
    except Exception:
        return None


def _team_name_to_oid(name: str) -> str | None:
    """Resolve team name to ObjectId string."""
    if not name:
        return None
    d = teams_collection.find_one({"name": name}, {"_id": 1})
    return str(d["_id"]) if d else None


def _resolve_winner_to_oid(winner: str) -> str | None:
    """Winner can be name or ObjectId string. Return ObjectId string."""
    if not winner:
        return None
    if ObjectId.is_valid(winner) and len(winner) == 24:
        return winner
    return _team_name_to_oid(winner)


def _bracket_for_aggregator(bracket: dict) -> dict:
    """Convert bracket to name-based format for team_stats_aggregator. Supports both ObjectId and name keys."""
    out = {}
    for round_key, matchups in (bracket or {}).items():
        if not isinstance(matchups, list):
            continue
        out[round_key] = []
        for m in matchups:
            home = m.get("home_team")
            away = m.get("away_team")
            winner = m.get("winner")
            score = m.get("score") or {}
            def _to_name(v):
                if not v:
                    return None
                if isinstance(v, str) and ObjectId.is_valid(v) and len(v) == 24:
                    return _team_oid_to_name(v)
                return v  # already name
            home_name = _to_name(home)
            away_name = _to_name(away)
            winner_name = _to_name(winner)
            if not home_name or not away_name:
                continue
            out[round_key].append({
                "home_team": home_name,
                "away_team": away_name,
                "winner": winner_name or (home_name if winner == home else away_name),
                "score": score,
            })
    return out


class StartTournamentRequest(BaseModel):
    """Payload for creating a new tournament."""
    user_team_id: str

class TournamentResultRequest(BaseModel):
    tournament_id: str
    game_id: str
    winner: str
    score: dict[str, int] | None = None
    game_document: dict | None = None  # ✅ SS&S: Complete game document from simulate-quarter (eliminates race condition, matches Franchise mode)

class SimulateRequest(BaseModel):
    tournament_id: str


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
    
    tournament_doc = tournaments_collection.find_one({"_id": tid}, {"players": 1, "teams": 1, "bracket": 1})
    if not tournament_doc:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    players = tournament_doc.get("players", {})
    tournament_teams = tournament_doc.get("teams", {})
    bracket = tournament_doc.get("bracket", {})
    
    # Pass name-based bracket for aggregator (bracket may use ObjectId strings)
    bracket_for_agg = _bracket_for_aggregator(bracket)
    output = aggregate_team_stats_from_players(
        players=players,
        team_ids=tournament_teams,
        teams_collection=teams_collection,
        collection_type='tournament',
        logger=logger,
        tournament_bracket=bracket_for_agg if any(bracket_for_agg.values()) else bracket,
    )
    
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

@router.get("/tournament/current")
def get_current_tournament(user: dict = Depends(get_current_user)):
    """
    Return the current user's tournament (active or most recent completed).
    Used by mode-select to show instance and Play Now / New Tournament.
    Returns 404 if the user has no tournament.
    """
    doc = tournaments_collection.find_one(
        {"user_id": user.get("user_id")},
        sort=[("created_at", -1)],
        projection={"_id": 1, "user_team_id": 1, "current_round": 1, "completed": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No tournament found")
    doc["_id"] = str(doc["_id"])
    return jsonable_encoder(doc, custom_encoder={ObjectId: str})


@router.post("/tournament/delete-current")
@router.delete("/tournament/current")
def delete_current_tournament(user: dict = Depends(get_current_user)):
    """
    Delete the current user's tournament (so they can start a new one from mode-select).
    Used when user confirms "New Tournament" in the confirmation modal.
    Cascade-deletes games linked to those tournaments (same as franchise delete).
    Returns 200 with deleted=True if a tournament was deleted, deleted=False if none existed.
    """
    # Cascade: delete games linked to this user's tournaments (match franchise behavior)
    tournament_docs = list(tournaments_collection.find({"user_id": user.get("user_id")}, {"_id": 1}))
    tournament_ids = [str(doc["_id"]) for doc in tournament_docs]
    if tournament_ids:
        games_collection.delete_many({"tournament_id": {"$in": tournament_ids}})
    result = tournaments_collection.delete_many({"user_id": user.get("user_id")})
    deleted = result.deleted_count > 0
    return {"deleted": deleted, "count": result.deleted_count}


def _do_start_tournament(request: StartTournamentRequest, user: dict):
    """Inner logic for start_tournament so it can be run under cProfile when profile=1."""
    all_teams = list(teams_collection.find({}, {"name": 1, "_id": 1}))
    team_names = [t["name"] for t in all_teams]
    if request.user_team_id not in team_names:
        raise HTTPException(status_code=400, detail="Invalid user_team_id")

    existing_tournaments = tournaments_collection.count_documents(
        {"user_id": user.get("user_id"), "completed": False}
    )
    if existing_tournaments >= 1:
        raise HTTPException(
            status_code=400,
            detail="You already have an active tournament. Delete it first to start a new one.",
        )

    team_docs = [{"name": t["name"], "_id": t["_id"]} for t in (all_teams[:8] if len(all_teams) >= 8 else all_teams)]
    if len(team_docs) < 8:
        raise HTTPException(status_code=400, detail="Need at least 8 teams to start a tournament")

    zero_stats = {key: 0 for key in BOX_SCORE_KEYS}
    zero_stats["Outlet_Score_List"] = []
    names_8 = [t["name"] for t in team_docs]
    for tid in names_8:
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
        team_docs=team_docs,
    )
    tournament = manager.create_tournament(user_id=user.get("user_id"))
    tournament["_id"] = str(tournament["_id"])
    return tournament


@router.post("/tournament/start")
@router.post("/start-tournament")  # Backward compatibility; prefer /tournament/start
def start_tournament(
    request: StartTournamentRequest,
    user: dict = Depends(get_current_user),
    profile: bool = False,
):
    if profile:
        from BackEnd.utils.profiling import run_profiled
        _out = [None]
        def _wrapped():
            _out[0] = _do_start_tournament(request, user)
        profile_summary = run_profiled(_wrapped, top_n=60)
        result = _out[0]
        result["profile_summary"] = profile_summary
        return result
    return _do_start_tournament(request, user)

@router.post("/tournament/simulate-round")
@router.post("/simulate-tournament-round")  # Backward compatibility; prefer /tournament/simulate-round
def simulate_round(request: SimulateRequest):
    """Return the user's matchup without simulating computer games.
    
    ✅ TASK 1 FIX: Matches Franchise mode pattern - computer games are simulated
    AFTER the user completes their game (in /tournament/save-result), not before.
    
    If the user game has already been played, a flag is returned."""

    try:
        try:
            tournament_id = ObjectId(request.tournament_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid tournament_id")

        tournament_doc = tournaments_collection.find_one({"_id": tournament_id})
        if not tournament_doc:
            raise HTTPException(status_code=404, detail="Tournament not found")

        round_name = get_round_name(tournament_doc["current_round"])
        matchups = tournament_doc["bracket"].get(round_name, [])

        _, user_team_oid = get_user_team_from_tournament(tournament_doc)
        user_matchup = None
        already_played = False

        for i, matchup in enumerate(matchups):
            h, a = str(matchup.get("home_team", "")), str(matchup.get("away_team", ""))
            if user_team_oid and user_team_oid in (h, a):
                home_name = _team_oid_to_name(h) or h
                away_name = _team_oid_to_name(a) or a
                user_matchup = {"home": home_name, "away": away_name}
                if matchup.get("game_id"):
                    already_played = True
                break

        if already_played:
            return {"already_played": True}
        if user_matchup:
            return user_matchup

        current_round = tournament_doc.get("current_round")
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
        raise HTTPException(status_code=500, detail="Internal server error")


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
    round_key = get_round_name(round_num)

    winner_oid = _resolve_winner_to_oid(request.winner)
    if not winner_oid:
        raise HTTPException(status_code=400, detail="Could not resolve winner to team")

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

    # Step 1: Find and finalize user's game first (matches Franchise mode)
    user_match_index = None
    home_oid = away_oid = None
    user_game_id = None

    for i, match in enumerate(tournament["bracket"][round_key]):
        h, a = str(match.get("home_team", "")), str(match.get("away_team", ""))
        if winner_oid not in (h, a):
            continue
        user_match_index = i
        home_oid = h
        away_oid = a
        gid = (
            ObjectId(request.game_id)
            if ObjectId.is_valid(request.game_id)
            else request.game_id
        )
        logger.info(f"🔍 [SAVE-RESULT] User game - game_id from request: {request.game_id} (type: {type(request.game_id)}), converted gid: {gid} (type: {type(gid)})")
        if request.game_document:
            logger.info(f"✅ [SAVE-RESULT] Using game_document from request (no database lookup needed, matches Franchise pattern)")
            print(f"✅ [SAVE-RESULT] Using game_document from request (no database lookup needed)")
            summary = request.game_document
            quarter = summary.get("quarter", "N/A")
            is_final = summary.get("is_final", False)
            logger.info(f"🔍 [SAVE-RESULT] game_document details: quarter={quarter}, is_final={is_final}, game_id={summary.get('_id') or summary.get('game_id')}")
            print(f"🔍 [SAVE-RESULT] game_document details: quarter={quarter}, is_final={is_final}")
            try:
                game_doc_id = summary.get("_id") or summary.get("game_id")
                if game_doc_id:
                    try:
                        game_doc_oid = ObjectId(game_doc_id) if not isinstance(game_doc_id, ObjectId) else game_doc_id
                    except Exception:
                        game_doc_oid = game_doc_id
                    if "_id" not in summary:
                        summary["_id"] = game_doc_oid
                    elif summary.get("_id") != game_doc_oid:
                        summary["_id"] = game_doc_oid
                    games_collection.replace_one(
                        {"_id": game_doc_oid},
                        summary,
                        upsert=True
                    )
                    logger.info(f"✅ [SAVE-RESULT] Saved game_document to database: {game_doc_oid}")
                    print(f"✅ [SAVE-RESULT] Saved game_document to database: {game_doc_oid}")
                    gid = game_doc_oid
                else:
                    logger.warning(f"⚠️ [SAVE-RESULT] game_document missing _id or game_id, cannot save to database")
            except Exception as e:
                logger.error(f"❌ [SAVE-RESULT] Error saving game_document to database: {e}", exc_info=True)
                print(f"❌ [SAVE-RESULT] Error saving game_document to database: {e}")
        else:
            logger.info(f"🔍 [SAVE-RESULT] game_document not provided, looking up from database...")
            print(f"🔍 [SAVE-RESULT] game_document not provided, looking up from database...")
            summary = None
            summary = games_collection.find_one({"_id": gid}) or {}
            if not summary or not summary.get("_id"):
                logger.warning(f"⚠️ [SAVE-RESULT] Game not found with gid={gid}, trying string format")
                try:
                    summary = games_collection.find_one({"_id": request.game_id}) or {}
                except Exception:
                    pass
            if not summary or not summary.get("_id"):
                logger.warning(f"⚠️ [SAVE-RESULT] Game not found with string format, trying ObjectId conversion")
                try:
                    oid = ObjectId(request.game_id)
                    summary = games_collection.find_one({"_id": oid}) or {}
                    if summary and summary.get("_id"):
                        gid = summary.get("_id")
                        logger.info(f"✅ [SAVE-RESULT] Found game document using ObjectId conversion: {gid}")
                except Exception as e:
                    logger.error(f"❌ [SAVE-RESULT] Error converting game_id to ObjectId: {e}")
            logger.info(f"🔍 [SAVE-RESULT] User game - Final lookup result: Found={bool(summary and summary.get('_id'))}, _id={summary.get('_id') if summary else None}")
            print(f"🔍 [SAVE-RESULT] User game - Final lookup result: Found={bool(summary and summary.get('_id'))}, _id={summary.get('_id') if summary else None}")
            if not summary or not summary.get("_id"):
                logger.error(f"❌ [SAVE-RESULT] Game document not found in games_collection after all attempts. game_id: {request.game_id}, gid: {gid}")
                print(f"❌ [SAVE-RESULT] Game document not found in games_collection after all attempts. game_id: {request.game_id}, gid: {gid}")
        score_map = (
            summary.get("score")
            or summary.get("final_score")
            or request.score
        ) if (summary and isinstance(summary, dict)) else (request.score or {})
        manager.save_game_result(
            round_num, i, request.game_id, winner_oid, score_map
        )
        if summary and summary.get("_id"):
            user_game_id = str(gid)
            logger.info(f"🎯 [SAVE-RESULT] Finalizing user's game FIRST (matches Franchise pattern) - game_id: {user_game_id}")
            print(f"🎯 [SAVE-RESULT] Finalizing user's game FIRST (matches Franchise pattern) - game_id: {user_game_id}")
            stat_updater.finalize_game(
                user_game_id,
                mode="tournament",
                tournament_id=request.tournament_id,
            )
            logger.info(f"✅ [SAVE-RESULT] User game - finalize_game completed for game_id: {user_game_id}")
            print(f"✅ [SAVE-RESULT] User game - finalize_game completed for game_id: {user_game_id}")
        else:
            logger.error(f"❌ [SAVE-RESULT] Skipping finalize_game - game document not found. Stats will not be applied.")
            print(f"❌ [SAVE-RESULT] Skipping finalize_game - game document not found. Stats will not be applied.")
        user_result = {
            "home_team": home_oid,
            "away_team": away_oid,
            "score": score_map or {},
            "winner": winner_oid,
            "round": round_num,
            "match_index": i,
        }
        _log_result(user_result)
        break

    if user_match_index is None:
        raise HTTPException(status_code=400, detail="User matchup not found")

    # ✅ Step 2: THEN simulate and finalize computer games (matches Franchise mode pattern)
    logger.info(f"🎯 [SAVE-RESULT] User's game finalized. Now processing computer games...")
    print(f"🎯 [SAVE-RESULT] User's game finalized. Now processing computer games...")
    
    for i, match in enumerate(manager.tournament["bracket"][round_key]):
        if i == user_match_index:
            continue  # Skip user's game (already finalized)
        
        # Check if this game already exists (from previous simulation)
        if match.get("game_id"):
            gid = (
                ObjectId(match["game_id"])
                if ObjectId.is_valid(match["game_id"])
                else match["game_id"]
            )
            summary = games_collection.find_one({"_id": gid}) or {}
            score_map = summary.get("score") or summary.get("final_score")
            
            wh = str(match.get("winner") or "")
            manager.save_game_result(
                round_num,
                i,
                match["game_id"],
                wh,
                score_map,
            )
            logger.info(f"🔍 [SAVE-RESULT] Finalizing existing computer game {i} - game_id: {str(gid)}")
            stat_updater.finalize_game(
                str(gid),
                mode="tournament",
                tournament_id=request.tournament_id,
            )
            result_doc = {
                "home_team": str(match.get("home_team", "")),
                "away_team": str(match.get("away_team", "")),
                "score": score_map or {},
                "winner": wh,
                "round": round_num,
                "match_index": i,
            }
            _log_result(result_doc)
            continue

        home_name = _team_oid_to_name(match.get("home_team")) or str(match.get("home_team", ""))
        away_name = _team_oid_to_name(match.get("away_team")) or str(match.get("away_team", ""))
        try:
            logger.info(f"🔍 [SAVE-RESULT] Simulating computer game {i} - {home_name} vs {away_name}")
            game = run_simulation(home_name, away_name)
            summary = summarize_game_state(game)
            summary["tournament_id"] = str(request.tournament_id)
            summary["round"] = round_key
            summary["match_index"] = i
            insert_result = games_collection.insert_one(summary)
            game_id = insert_result.inserted_id
            
            # Finalize game immediately after simulation (matches Franchise pattern)
            logger.info(f"🔍 [SAVE-RESULT] Finalizing new computer game {i} - game_id: {str(game_id)}")
            stat_updater.finalize_game(
                str(game_id),
                mode="tournament",
                tournament_id=request.tournament_id,
            )
            print(f"✅ Game document inserted and finalized for round {round_num} match {i}")
        except Exception as e:
            print(
                f"❌ Failed to simulate or insert game for round {round_num} match {i}: {e}"
            )
            continue

        home_oid_s = str(match.get("home_team", ""))
        away_oid_s = str(match.get("away_team", ""))
        score_map = summary.get("score") or summary.get("final_score")
        winner_name = home_name if (score_map.get(home_name) or 0) > (score_map.get(away_name) or 0) else away_name
        winner_oid_s = home_oid_s if winner_name == home_name else away_oid_s
        manager.save_game_result(round_num, i, str(game_id), winner_oid_s, score_map)
        result_doc = {
            "home_team": home_oid_s,
            "away_team": away_oid_s,
            "score": score_map or {},
            "winner": winner_oid_s,
            "round": round_num,
            "match_index": i,
        }
        _log_result(result_doc)

    # Use saved results to advance the bracket to the next round.  This relies
    # solely on the stored results and is safe to re-run (idempotent).
    update_bracket_from_results(tournament_id, tournaments_collection=tournaments_collection)

    return {"status": "success"}


@router.get("/tournament/command-center/data")
def tournament_command_center_data(
    tournament_id: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """
    Return structured command center data for a tournament.
    
    ✅ MIGRATION (Task 4.1): Aligned with Franchise mode pattern.
    Returns structured response matching /franchise/command-center/data format.
    """
    doc = verify_tournament_owned_by_user(tournament_id, user["user_id"])
    tid = doc["_id"]

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
        tournament_teams = doc.get("teams", {})
        tournament_team_obj = tournament_teams.get(user_team_object_id, {})
        if tournament_team_obj:
            team_doc = tournament_team_obj.get("team_attributes", {})
        else:
            team_doc = teams_collection.find_one({"_id": ObjectId(user_team_object_id)}) or {}
    elif user_team_id_name:
        team_doc = teams_collection.find_one({"name": user_team_id_name}) or {}

    # ✅ Phase 5.3: Common keys from shared builder; tournament-only keys merged below
    response = build_command_center_base(user_team_id_name, user_team_object_id, team_doc)
    response["training_completed"] = training_completed
    response["session_type"] = session_type
    response["current_round"] = doc.get("current_round", 1)
    response["completed"] = doc.get("completed", False)
    response["bracket"] = doc.get("bracket", {})
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
            team_doc = teams_collection.find_one({"name": {"$regex": f"^{re.escape(team_name)}$", "$options": "i"}})
        
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
        defenses = ["man", "2-3-zone", "3-2-zone", "1-3-1-zone"]
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


@router.get("/tournament/scouting-report")
def get_tournament_scouting_report(tournament_id: str, team_id: str = None, team_name: str = None):
    """
    Get scouting report for a team in tournament mode, including last game's play usage data.
    
    ✅ SS&S: Prefers team_id (ObjectId) for consistent navigation.
    Falls back to team_name resolution for backward compatibility.
    
    Returns:
    - team_attributes: Team attribute values
    - plays: Array of plays with game_stats from last completed game
    """
    try:
        tid = ObjectId(tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament ID")
    
    # Get tournament document
    tournament_doc = tournaments_collection.find_one({"_id": tid})
    if not tournament_doc:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    # ✅ SS&S: Prefer team_id (ObjectId) if provided, fallback to team_name
    team_doc = None
    if team_id:
        try:
            # Try ObjectId lookup first
            obj_id = ObjectId(team_id)
            team_doc = teams_collection.find_one({"_id": obj_id})
        except Exception:
            # If not a valid ObjectId, try team_id string lookup
            team_doc = teams_collection.find_one({"team_id": team_id})
    
    # Fallback to team_name lookup
    if not team_doc and team_name:
        team_doc = teams_collection.find_one({"name": team_name})
        if not team_doc:
            # Try case-insensitive match
            team_doc = teams_collection.find_one({"name": {"$regex": f"^{re.escape(team_name)}$", "$options": "i"}})
    
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team_object_id = str(team_doc["_id"])
    
    # Get team_id field for querying games (e.g., "XAVIEN")
    team_id_field = team_doc.get("team_id")
    
    # Get team attributes from tournament document
    tournament_teams = tournament_doc.get("teams", {})
    team_obj = tournament_teams.get(team_object_id, {})
    team_attributes = team_obj.get("attributes", {})
    
    # Find last completed game for this team in tournament
    # Match against home_team_id and away_team_id (which are team_id strings like "XAVIEN")
    last_game = games_collection.find_one(
        {
            "tournament_id": str(tournament_id),
            "$or": [
                {"home_team_id": team_id_field},
                {"away_team_id": team_id_field}
            ]
        },
        sort=[("_id", -1)]  # Most recent first
    )
    
    # ✅ SS&S: Use shared utility function to extract plays from game document
    from BackEnd.utils.scouting_utils import extract_plays_from_game_document
    # Get team name for the utility function (it needs it for display)
    team_name_for_utility = team_doc.get("name", team_name or "")
    plays_data = extract_plays_from_game_document(
        last_game,
        team_name_for_utility,
        team_object_id,
        team_id_field
    )

    from BackEnd.utils.scouting_utils import (
        compute_projected_starting_five,
        load_tournament_roster_for_scouting,
    )

    scout_players = load_tournament_roster_for_scouting(tournament_doc, team_doc)
    projected_starting_five = compute_projected_starting_five(scout_players)

    tournament_players = tournament_doc.get("players", {}) or tournament_doc.get("player_stats", {})
    player_season_stats: dict[str, dict] = {}
    for row in projected_starting_five:
        pid = row.get("player_id")
        if pid is None or pid == "":
            continue
        pid_s = str(pid)
        tp = tournament_players.get(pid_s, {}) or {}
        season_raw = tp.get("season") or {}
        player_season_stats[pid_s] = dict(season_raw) if isinstance(season_raw, dict) else {}

    return {
        "team_attributes": team_attributes,
        "plays": plays_data,
        "projected_starting_five": projected_starting_five,
        "player_season_stats": player_season_stats,
    }


@router.get("/tournament/roster")
def get_tournament_roster(tournament_id: str, team_id: str = None, team_name: str = None):
    """
    Get roster with tournament-specific player attributes.
    
    ✅ SS&S: Prefers team_id (ObjectId) for consistent navigation.
    Falls back to team_name resolution for backward compatibility.
    
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
    
    # ✅ SS&S: Prefer team_id (ObjectId) if provided, fallback to team_name
    team_doc = None
    if team_id:
        try:
            # Try ObjectId lookup first
            obj_id = ObjectId(team_id)
            team_doc = teams_collection.find_one({"_id": obj_id})
        except Exception:
            # If not a valid ObjectId, try team_id string lookup
            team_doc = teams_collection.find_one({"team_id": team_id})
    
    # Fallback to team_name lookup
    if not team_doc:
        if not team_name:
            team_name = tournament_doc.get("user_team_id")
        
        if team_name:
            # Strategy 1: Try exact match first
            team_doc = teams_collection.find_one({"name": team_name})
            
            # Strategy 2: If not found, try case-insensitive match
            if not team_doc:
                team_doc = teams_collection.find_one({"name": {"$regex": f"^{re.escape(team_name)}$", "$options": "i"}})
            
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
        raise HTTPException(status_code=404, detail=f"Team not found: {team_id or team_name}")
    
    # ✅ MIGRATION: Use players key instead of player_stats (aligns with Franchise)
    tournament_players = tournament_doc.get("players", {}) or tournament_doc.get("player_stats", {})  # Backward compatibility
    team_player_ids = team_doc.get("player_ids", [])
    
    # ✅ PERFORMANCE: Batch player lookups to fix N+1 query pattern
    # Instead of 12 individual queries, do 1 batch query with $in operator
    # ✅ FIX: Player IDs are UUIDs (strings), not ObjectIds - use directly
    core_players_dict = {str(p["_id"]): p for p in players_collection.find(
        {"_id": {"$in": team_player_ids}},
        {"position_ratings": 1, "height": 1, "weight": 1, "jersey": 1, "year": 1, "attributes": 1,
         "first_name": 1, "last_name": 1}
    )}
    
    # ✅ Phase 5.2: Build player list via shared roster_builder (same shape as franchise roster)
    # Only include players that exist in core; build overrides from tournament.players
    team_name = team_doc.get("name", team_name or "")
    pids_with_core = [pid for pid in team_player_ids if str(pid) in core_players_dict]
    mode_overrides = {}
    for pid in pids_with_core:
        pid_str = str(pid)
        core_player = core_players_dict[pid_str]
        tournament_player_data = tournament_players.get(pid_str, {})
        meta = tournament_player_data.get("meta", {}) if tournament_player_data else {}
        tournament_attributes = tournament_player_data.get("attributes", {}) if tournament_player_data else {}
        core_attributes = core_player.get("attributes", {}) or {}
        merged_attributes = {**core_attributes, **tournament_attributes}
        position_ratings = tournament_player_data.get("position_ratings") if tournament_player_data else None
        if not position_ratings:
            position_ratings = core_player.get("position_ratings", {})
        first = meta.get("first_name") or (tournament_player_data.get("first_name") if tournament_player_data else None) or core_player.get("first_name", "")
        last = meta.get("last_name") or (tournament_player_data.get("last_name") if tournament_player_data else None) or core_player.get("last_name", "")
        mode_overrides[pid_str] = {
            "first_name": first,
            "last_name": last,
            "attributes": merged_attributes,
            "position_ratings": position_ratings,
        }
    players = build_roster_players(pids_with_core, mode_overrides, core_players_dict, team_name)
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
        round_key = get_round_name(round_num)
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
                        "home_team": str(match.get("home_team", "")),
                        "away_team": str(match.get("away_team", "")),
                        "score": score_map or {},
                        "winner": str(match.get("winner", "")),
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

            home_name = _team_oid_to_name(match.get("home_team")) or str(match.get("home_team", ""))
            away_name = _team_oid_to_name(match.get("away_team")) or str(match.get("away_team", ""))
            print(
                f"[sim_remaining] Simulating matchup: {home_name} vs {away_name}"
            )
            game = run_simulation(home_name, away_name)
            summary = summarize_game_state(game)
            summary["tournament_id"] = str(request.tournament_id)
            summary["round"] = round_key
            summary["match_index"] = i
            game_id = games_collection.insert_one(summary).inserted_id
            stat_updater.finalize_game(
                str(game_id),
                mode="tournament",
                tournament_id=request.tournament_id,
            )
            home_oid_s = str(match.get("home_team", ""))
            away_oid_s = str(match.get("away_team", ""))
            score_map = summary.get("score") or summary.get("final_score")
            winner_name = home_name if (score_map.get(home_name) or 0) > (score_map.get(away_name) or 0) else away_name
            winner_oid_s = home_oid_s if winner_name == home_name else away_oid_s
            manager.save_game_result(round_num, i, str(game_id), winner_oid_s, score_map)
            result_doc = {
                "home_team": home_oid_s,
                "away_team": away_oid_s,
                "score": score_map or {},
                "winner": winner_oid_s,
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
def run_tournament_training():
    """Training is not used in Tournament mode; users go directly to gameplay. Kept as stub for backward compatibility."""
    raise HTTPException(status_code=404, detail="Training is not available in Tournament mode")
