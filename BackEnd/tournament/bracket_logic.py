from __future__ import annotations
"""Helpers for manipulating tournament brackets.

This module currently provides a utility to advance the bracket to the next
round based on saved game results.  The function is designed to be idempotent
so repeated invocations (e.g. on page refresh) do not duplicate work or advance
multiple rounds.
"""

from typing import Any
from bson import ObjectId

from BackEnd.db import tournaments_collection as default_tournaments_collection


def update_bracket_from_results(
    tournament_id: str | ObjectId,
    *,
    tournaments_collection=default_tournaments_collection,
) -> dict[str, Any] | None:
    """Advance the bracket using saved results.

    Parameters
    ----------
    tournament_id:
        Identifier for the tournament document.
    tournaments_collection:
        Optional Mongo collection to operate on.  Defaults to the primary
        ``tournaments_collection`` used by the application.

    Returns
    -------
    dict | None
        The updated tournament document if found, otherwise ``None``.

    Notes
    -----
    The round and match indexing scheme is zero based.  ``match_index`` values
    from the saved results determine pairing in the next round: winners from
    match ``0`` and ``1`` advance to match ``0`` in the following round,
    ``2`` and ``3`` advance to match ``1`` and so on.  This provides a stable
    mapping that can be re‑applied without recomputation.
    """

    tid = ObjectId(tournament_id) if not isinstance(tournament_id, ObjectId) else tournament_id
    tournament = tournaments_collection.find_one({"_id": tid})
    if not tournament:
        return None

    current_round: int = tournament.get("current_round", 1)
    round_key = f"round{current_round}" if current_round < 3 else "final"
    bracket = tournament.get("bracket", {})
    matchups = bracket.get(round_key, [])

    # Gather all results for the current round and order them by match index
    results = [r for r in tournament.get("results", []) if r.get("round") == current_round]
    if len(results) < len(matchups):
        # Round not complete – nothing to advance
        return tournament

    results.sort(key=lambda r: r["match_index"])
    winners = [r["winner"] for r in results]

    next_round_num = current_round + 1
    next_key = "final" if next_round_num == 3 else f"round{next_round_num}"

    # If next round already populated, treat as a no‑op (idempotency)
    if bracket.get(next_key):
        return tournament

    next_matchups = []
    for i in range(0, len(winners), 2):
        next_matchups.append(
            {
                "home_team": winners[i],
                "away_team": winners[i + 1],
                "game_id": None,
                "winner": None,
            }
        )

    tournaments_collection.update_one(
        {"_id": tid},
        {"$set": {f"bracket.{next_key}": next_matchups, "current_round": next_round_num}},
    )

    tournament.setdefault("bracket", {})[next_key] = next_matchups
    tournament["current_round"] = next_round_num
    return tournament
