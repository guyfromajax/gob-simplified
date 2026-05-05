"""
Shared bracket engine for 8-team single-elimination tournaments.

Used by both Tournament mode (standalone) and Franchise EOS (end-of-season).
All team identifiers are ObjectId strings (hex). No DB access; callers persist.

See: _documentation_master/06_GMO_Supporting_Systems/Tournament_Execution_System.md (§9)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ROUND_KEYS = ("round1", "round2", "final")


def get_round_name(round_num: int) -> str:
    """Map round number (1, 2, 3) to bracket key."""
    if round_num == 1:
        return "round1"
    if round_num == 2:
        return "round2"
    if round_num == 3:
        return "final"
    return "round1"


def generate_bracket(seed_order: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build round-1 bracket from ordered seeds (1–8).

    Matchups: 1v8, 4v5, 2v7, 3v6. round2 and final are empty until advance.

    Args:
        seed_order: Ordered list of 8 team ObjectId strings (index 0 = seed 1, …, 7 = seed 8).

    Returns:
        {"round1": [...], "round2": [], "final": []}. Each matchup is
        {home_team, away_team, game_id, winner, score}.

    Raises:
        ValueError: If len(seed_order) < 8.
    """
    if len(seed_order) < 8:
        raise ValueError(
            f"Bracket requires 8 teams; got {len(seed_order)}. "
            "Provide seed_order as ordered list of 8 ObjectId strings."
        )
    # 1v8, 4v5, 2v7, 3v6
    matchups = [
        (seed_order[0], seed_order[7]),
        (seed_order[3], seed_order[4]),
        (seed_order[1], seed_order[6]),
        (seed_order[2], seed_order[5]),
    ]
    round1 = [
        {
            "home_team": home,
            "away_team": away,
            "game_id": None,
            "winner": None,
            "score": {},
        }
        for home, away in matchups
    ]
    return {
        "round1": round1,
        "round2": [],
        "final": [],
    }


def save_game_result(
    bracket: Dict[str, List[Dict[str, Any]]],
    round_num: int,
    matchup_index: int,
    game_id: Any,
    winner_id: str,
    score: Optional[Dict[str, int]] = None,
) -> None:
    """
    Update a single matchup with game result. Mutates bracket in place.

    Args:
        bracket: Bracket dict with round1/round2/final.
        round_num: 1, 2, or 3.
        matchup_index: 0-based index in that round.
        game_id: Game document id (string or ObjectId).
        winner_id: Winning team ObjectId string.
        score: Optional {team_id: points} or similar; stored as-is.
    """
    key = get_round_name(round_num)
    if key not in bracket or matchup_index >= len(bracket[key]):
        logger.warning(
            "bracket_engine.save_game_result: round=%s index=%s missing or OOB",
            key,
            matchup_index,
        )
        return
    m = bracket[key][matchup_index]
    m["game_id"] = game_id
    m["winner"] = winner_id
    if score is not None:
        m["score"] = score


def advance_bracket(
    bracket: Dict[str, List[Dict[str, Any]]],
    current_round: int,
    *,
    winners_from_matchups: bool = True,
    results: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, List[Dict[str, Any]]], int, bool, Optional[str]]:
    """
    Compute next round from current-round winners. Mutates bracket in place.

    Pairing: winners 0+1 → semi 0, 2+3 → semi 1; semi winners → final.

    Args:
        bracket: Bracket with round1/round2/final.
        current_round: 1 (quarters), 2 (semis), or 3 (final).
        winners_from_matchups: If True, derive winners from bracket matchups.
        results: If winners_from_matchups False, list of {round, match_index, winner}
                 for current round. Used for Tournament mode’s results list.

    Returns:
        (bracket, next_round, completed, champion).
        next_round: 1, 2, or 3. If round 3 just finished, completed True and champion set.
    """
    key = get_round_name(current_round)
    matchups = bracket.get(key, [])

    if winners_from_matchups:
        winners = [m.get("winner") for m in matchups if m.get("winner")]
    else:
        if not results:
            winners = []
        else:
            by_round = [r for r in results if r.get("round") == current_round]
            by_round.sort(key=lambda r: r.get("match_index", 0))
            winners = [r["winner"] for r in by_round if "winner" in r]

    completed = False
    champion: Optional[str] = None
    next_round = current_round

    if current_round == 1:
        if len(winners) == 4:
            bracket["round2"] = [
                _matchup(winners[0], winners[1]),
                _matchup(winners[2], winners[3]),
            ]
            next_round = 2
            logger.debug("bracket_engine: advanced to round2 (semis)")
    elif current_round == 2:
        if len(winners) == 2:
            bracket["final"] = [_matchup(winners[0], winners[1])]
            next_round = 3
            logger.debug("bracket_engine: advanced to final")
    elif current_round == 3:
        if len(winners) == 1:
            completed = True
            champion = winners[0]
            logger.debug("bracket_engine: tournament complete, champion=%s", champion)

    return (bracket, next_round, completed, champion)


def _matchup(home_id: str, away_id: str) -> Dict[str, Any]:
    return {
        "home_team": home_id,
        "away_team": away_id,
        "game_id": None,
        "winner": None,
        "score": {},
    }
