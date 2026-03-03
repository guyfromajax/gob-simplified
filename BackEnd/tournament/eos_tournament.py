"""
End-of-Season (EOS) Tournament System for Franchise Mode.

Handles seeding, bracket generation, and tournament progression for weeks 15-17.
Uses shared bracket_engine for bracket init, advance, and save-result.
"""
from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional

from bson import ObjectId

from BackEnd.tournament import bracket_engine
from BackEnd.utils.franchise_standings import calculate_franchise_standings

logger = logging.getLogger(__name__)


def calculate_standings(
    franchise_doc: Dict[str, Any],
    teams_collection,
    team_ids: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Calculate regular season standings for all teams in the franchise.

    Uses franchise.results as the source of truth (same as Franchise standings tab).
    team_ids must be provided from franchise_team_data (FTD); franchise_teams is no longer used.

    Returns:
        List of team standings sorted by: Wins (desc), PF-PA delta (desc), Random
    """
    if team_ids is None:
        raise ValueError(
            "team_ids is required. Provide team IDs from franchise_team_data (FTD); "
            "franchise_teams is no longer used."
        )
    team_ids = [ObjectId(tid) if not isinstance(tid, ObjectId) else tid for tid in team_ids]
    franchise_results = franchise_doc.get("results", {})
    team_ids_map = {str(tid): {} for tid in team_ids}
    standings_data = calculate_franchise_standings(franchise_results, team_ids_map)

    # Fetch team names
    teams = list(teams_collection.find(
        {"_id": {"$in": team_ids}},
        {"name": 1, "_id": 1}
    ))
    name_by_id = {str(t["_id"]): t.get("name", "") for t in teams}

    standings = []
    for tid in team_ids:
        tid_str = str(tid)
        data = standings_data.get(tid_str, {"W": 0, "L": 0, "PF": 0, "PA": 0})
        wins = data.get("W", 0)
        losses = data.get("L", 0)
        pf = data.get("PF", 0)
        pa = data.get("PA", 0)
        differential = pf - pa
        standings.append({
            "team_id": tid_str,
            "name": name_by_id.get(tid_str, ""),
            "wins": wins,
            "losses": losses,
            "pf": pf,
            "pa": pa,
            "differential": differential,
            "tiebreaker_random": random.random(),
        })

    standings.sort(key=lambda x: (x["wins"], x["differential"], x["tiebreaker_random"]), reverse=True)
    return standings


def generate_seeds(standings: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Generate seeds 1-8 from sorted standings.
    
    Args:
        standings: List of team standings (already sorted)
        
    Returns:
        Dictionary mapping team_id to seed number (1-8)
    """
    seeds = {}
    for i, team in enumerate(standings[:8]):  # Top 8 teams
        seeds[team["team_id"]] = i + 1
    
    return seeds


def initialize_eos_tournament(
    franchise_doc: Dict[str, Any],
    teams_collection,
    team_ids: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Initialize EOS Tournament after regular season (week 26) completion.

    Args:
        franchise_doc: Franchise document
        teams_collection: MongoDB teams collection
        team_ids: List of team IDs for standings (from franchise_team_data). Required.

    Returns:
        Tournament state dictionary to be saved to franchise document
    """
    standings = calculate_standings(franchise_doc, teams_collection, team_ids=team_ids)

    # Generate seeds (top 8 teams)
    seeds = generate_seeds(standings)
    if len(seeds) < 8:
        raise ValueError(
            f"EOS bracket requires 8 teams; got {len(seeds)}. "
            "Ensure team IDs are provided from franchise_team_data (FTD)."
        )
    seed_order = [tid for tid, _ in sorted(seeds.items(), key=lambda x: x[1])]
    bracket = bracket_engine.generate_bracket(seed_order)
    
    # Create tournament state
    tournament_state = {
        "bracket": bracket,
        "current_round": 1,
        "completed": False,
        "champion": None,
        "seeds": seeds,
        "results": []
    }
    
    logger.info(f"✅ [EOS TOURNAMENT] Initialized tournament with seeds: {seeds}")
    
    return tournament_state


def advance_tournament_round(franchise_doc: Dict[str, Any], teams_collection) -> Dict[str, Any]:
    """
    Advance tournament to next round based on completed matchups.
    Uses shared bracket_engine.advance_bracket (winners from matchups).
    
    Args:
        franchise_doc: Franchise document with eos_tournament
        teams_collection: MongoDB teams collection (unused; kept for API compatibility)
        
    Returns:
        Updated tournament state
    """
    eos_tournament = franchise_doc.get("eos_tournament", {})
    current_round = eos_tournament.get("current_round", 1)
    bracket = eos_tournament.get("bracket", {})
    
    updated, next_round, completed, champion = bracket_engine.advance_bracket(
        bracket, current_round, winners_from_matchups=True
    )
    eos_tournament["bracket"] = updated
    eos_tournament["current_round"] = next_round
    if completed and champion is not None:
        eos_tournament["completed"] = True
        eos_tournament["champion"] = champion
        logger.info("✅ [EOS TOURNAMENT] Tournament complete! Champion: %s", champion)
    elif next_round > current_round:
        if next_round == 2:
            logger.info("✅ [EOS TOURNAMENT] Advanced to Round 2 (Semifinals)")
        elif next_round == 3:
            logger.info("✅ [EOS TOURNAMENT] Advanced to Final (Championship)")
    
    return eos_tournament


def save_tournament_game_result(
    franchise_doc: Dict[str, Any],
    round_num: int,
    matchup_index: int,
    game_id: str,
    winner_id: str,
    score: Dict[str, int] | None = None,
) -> None:
    """
    Save tournament game result to bracket.
    Uses shared bracket_engine.save_game_result; also appends to eos_tournament.results.
    
    Args:
        franchise_doc: Franchise document
        round_num: Round number (1, 2, or 3)
        matchup_index: Index of matchup in round (0-based)
        game_id: Game document ID
        winner_id: Winning team ObjectId (string)
        score: Optional score dictionary
    """
    eos_tournament = franchise_doc.get("eos_tournament", {})
    bracket = eos_tournament.get("bracket", {})
    bracket_engine.save_game_result(bracket, round_num, matchup_index, game_id, winner_id, score)

    result_entry = {
        "round": round_num,
        "match_index": matchup_index,
        "winner": winner_id,
        "game_id": game_id,
        "score": score or {},
    }
    results = eos_tournament.get("results", [])
    results = [r for r in results if not (r.get("round") == round_num and r.get("match_index") == matchup_index)]
    results.append(result_entry)
    eos_tournament["results"] = results

    logger.info("✅ [EOS TOURNAMENT] Saved result: Round %s, Matchup %s, Winner: %s", round_num, matchup_index, winner_id)

