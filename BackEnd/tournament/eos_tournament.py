"""
End-of-Season (EOS) Tournament System for Franchise Mode.

Handles seeding, bracket generation, and tournament progression for weeks 15-17.
"""
from typing import Dict, List, Tuple, Any, Optional
from bson import ObjectId
import random
import logging

logger = logging.getLogger(__name__)


def calculate_standings(
    franchise_doc: Dict[str, Any],
    teams_collection,
    team_ids: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Calculate regular season standings for all teams in the franchise.

    Args:
        franchise_doc: Franchise document
        teams_collection: MongoDB teams collection
        team_ids: Optional list of team IDs (ObjectId or str). When provided (e.g. from FTD),
                  used instead of franchise_teams. Required after FTD migration since
                  franchise_teams is empty.

    Returns:
        List of team standings sorted by: Wins (desc), PF-PA delta (desc), Random
    """
    # Prefer explicit team_ids (from FTD) when provided; else fall back to franchise_teams
    if team_ids is not None:
        team_ids = [ObjectId(tid) if not isinstance(tid, ObjectId) else tid for tid in team_ids]
    else:
        franchise_teams = franchise_doc.get("franchise_teams", {})
        team_ids = [ObjectId(tid) for tid in franchise_teams.keys()]
    
    # Get team records from teams collection
    teams = list(teams_collection.find(
        {"_id": {"$in": team_ids}},
        {"name": 1, "record": 1, "PF": 1, "PA": 1, "_id": 1}
    ))
    
    standings = []
    for team in teams:
        rec = team.get("record", {"W": 0, "L": 0})
        wins = rec.get("W", 0)
        losses = rec.get("L", 0)
        pf = team.get("PF", 0)
        pa = team.get("PA", 0)
        differential = pf - pa
        
        standings.append({
            "team_id": str(team["_id"]),
            "name": team.get("name", ""),
            "wins": wins,
            "losses": losses,
            "pf": pf,
            "pa": pa,
            "differential": differential,
            "tiebreaker_random": random.random()  # For final tiebreaker
        })
    
    # Sort by: Wins (desc), PF-PA delta (desc), Random
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


def generate_bracket(seeds: Dict[str, int], teams_collection) -> Dict[str, List[Dict[str, Any]]]:
    """
    Generate tournament bracket structure for 8 teams.

    Args:
        seeds: Dictionary mapping team_id to seed (1-8)
        teams_collection: MongoDB teams collection (for team names)

    Returns:
        Bracket structure: {round1: [...], round2: [], final: []}

    Raises:
        ValueError: If seeds has fewer than 8 teams (e.g. empty after FTD migration).
    """
    if len(seeds) < 8:
        raise ValueError(
            f"EOS bracket requires 8 teams; got {len(seeds)}. "
            "Ensure team IDs are provided from FTD when franchise_teams is empty."
        )
    # Get team names for bracket display
    team_ids = [ObjectId(tid) for tid in seeds.keys()]
    teams = {str(t["_id"]): t.get("name", "") for t in teams_collection.find(
        {"_id": {"$in": team_ids}},
        {"name": 1, "_id": 1}
    )}
    
    # Sort teams by seed
    sorted_teams = sorted(seeds.items(), key=lambda x: x[1])
    
    # Round 1 matchups: 1v8, 4v5, 2v7, 3v6
    matchups = [
        (sorted_teams[0][0], sorted_teams[7][0]),  # Seed 1 vs Seed 8
        (sorted_teams[3][0], sorted_teams[4][0]),  # Seed 4 vs Seed 5
        (sorted_teams[1][0], sorted_teams[6][0]),  # Seed 2 vs Seed 7
        (sorted_teams[2][0], sorted_teams[5][0]),  # Seed 3 vs Seed 6
    ]
    
    round1 = []
    for home_id, away_id in matchups:
        round1.append({
            "home_team": home_id,
            "away_team": away_id,
            "game_id": None,
            "winner": None,
            "score": {},
        })
    
    return {
        "round1": round1,
        "round2": [],
        "final": []
    }


def initialize_eos_tournament(
    franchise_doc: Dict[str, Any],
    teams_collection,
    team_ids: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Initialize EOS Tournament after week 14 completion.

    Args:
        franchise_doc: Franchise document
        teams_collection: MongoDB teams collection
        team_ids: Optional list of team IDs for standings (e.g. from franchise_team_data).
                  When provided, used instead of franchise_doc.franchise_teams. Required
                  after FTD migration since franchise_teams is empty.

    Returns:
        Tournament state dictionary to be saved to franchise document
    """
    # Calculate standings (use team_ids from FTD when franchise_teams is empty)
    standings = calculate_standings(franchise_doc, teams_collection, team_ids=team_ids)
    
    # Generate seeds (top 8 teams)
    seeds = generate_seeds(standings)
    
    # Generate bracket
    bracket = generate_bracket(seeds, teams_collection)
    
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
    
    Args:
        franchise_doc: Franchise document with eos_tournament
        teams_collection: MongoDB teams collection
        
    Returns:
        Updated tournament state
    """
    eos_tournament = franchise_doc.get("eos_tournament", {})
    current_round = eos_tournament.get("current_round", 1)
    bracket = eos_tournament.get("bracket", {})
    
    if current_round == 1:
        # Check if all Round 1 games are complete
        round1 = bracket.get("round1", [])
        winners = [m.get("winner") for m in round1 if m.get("winner")]
        
        if len(winners) == 4:
            # Advance to Round 2 (Semifinals)
            round2 = [
                {
                    "home_team": winners[0],
                    "away_team": winners[1],
                    "game_id": None,
                    "winner": None,
                    "score": {},
                },
                {
                    "home_team": winners[2],
                    "away_team": winners[3],
                    "game_id": None,
                    "winner": None,
                    "score": {},
                },
            ]
            bracket["round2"] = round2
            eos_tournament["current_round"] = 2
            eos_tournament["bracket"] = bracket
            logger.info(f"✅ [EOS TOURNAMENT] Advanced to Round 2 (Semifinals)")
    
    elif current_round == 2:
        # Check if all Round 2 games are complete
        round2 = bracket.get("round2", [])
        winners = [m.get("winner") for m in round2 if m.get("winner")]
        
        if len(winners) == 2:
            # Advance to Final
            final = [
                {
                    "home_team": winners[0],
                    "away_team": winners[1],
                    "game_id": None,
                    "winner": None,
                    "score": {},
                }
            ]
            bracket["final"] = final
            eos_tournament["current_round"] = 3
            eos_tournament["bracket"] = bracket
            logger.info(f"✅ [EOS TOURNAMENT] Advanced to Final (Championship)")
    
    elif current_round == 3:
        # Check if Final is complete
        final = bracket.get("final", [])
        if final and final[0].get("winner"):
            eos_tournament["completed"] = True
            eos_tournament["champion"] = final[0]["winner"]
            logger.info(f"✅ [EOS TOURNAMENT] Tournament complete! Champion: {final[0]['winner']}")
    
    return eos_tournament


def get_round_name(round_num: int) -> str:
    """Get round name from round number."""
    if round_num == 1:
        return "round1"
    elif round_num == 2:
        return "round2"
    elif round_num == 3:
        return "final"
    else:
        return "round1"


def save_tournament_game_result(
    franchise_doc: Dict[str, Any],
    round_num: int,
    matchup_index: int,
    game_id: str,
    winner_id: str,
    score: Dict[str, int] | None = None
) -> None:
    """
    Save tournament game result to bracket.
    
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
    round_name = get_round_name(round_num)
    
    if round_name not in bracket:
        logger.error(f"❌ [EOS TOURNAMENT] Round {round_name} not found in bracket")
        return
    
    matchups = bracket[round_name]
    if matchup_index >= len(matchups):
        logger.error(f"❌ [EOS TOURNAMENT] Matchup index {matchup_index} out of range for {round_name}")
        return
    
    match = matchups[matchup_index]
    match["game_id"] = game_id
    match["winner"] = winner_id
    if score:
        match["score"] = score
    
    # Add to results array
    result_entry = {
        "round": round_num,
        "match_index": matchup_index,
        "winner": winner_id,
        "game_id": game_id,
        "score": score or {}
    }
    
    results = eos_tournament.get("results", [])
    # Remove existing result for this matchup if present
    results = [r for r in results if not (r.get("round") == round_num and r.get("match_index") == matchup_index)]
    results.append(result_entry)
    eos_tournament["results"] = results
    
    logger.info(f"✅ [EOS TOURNAMENT] Saved result: Round {round_num}, Matchup {matchup_index}, Winner: {winner_id}")

