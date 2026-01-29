from __future__ import annotations
"""Helpers for manipulating tournament brackets.

Advances the bracket using saved results. Uses shared bracket_engine.
Results store winner as ObjectId string; bracket uses ObjectId strings.
"""

from typing import Any
from bson import ObjectId
import logging

from BackEnd.db import tournaments_collection as default_tournaments_collection
from BackEnd.tournament.bracket_engine import advance_bracket, get_round_name


logger = logging.getLogger(__name__)


def update_bracket_from_results(
    tournament_id: str | ObjectId,
    *,
    tournaments_collection=default_tournaments_collection,
) -> dict[str, Any] | None:
    """Advance the bracket using saved results. Idempotent."""

    tid = ObjectId(tournament_id) if not isinstance(tournament_id, ObjectId) else tournament_id
    tournament = tournaments_collection.find_one({"_id": tid})
    if not tournament:
        return None

    current_round = tournament.get("current_round", 1)
    bracket = tournament.get("bracket", {})
    round_key = get_round_name(current_round)
    matchups = bracket.get(round_key, [])

    results = [r for r in tournament.get("results", []) if r.get("round") == current_round]
    results.sort(key=lambda r: r.get("match_index", 0))
    logger.info(
        "Round %s: %d results vs %d matchups",
        current_round,
        len(results),
        len(matchups),
    )

    if len(results) == len(matchups):
        bracket, next_round, completed, champion = advance_bracket(
            bracket,
            current_round,
            winners_from_matchups=False,
            results=results,
        )
    else:
        winners = [m.get("winner") for m in matchups if m.get("winner")]
        if len(winners) != len(matchups):
            return tournament
        bracket, next_round, completed, champion = advance_bracket(
            bracket,
            current_round,
            winners_from_matchups=True,
        )

    update: dict[str, Any] = {
        "bracket": bracket,
        "current_round": next_round,
    }
    if completed and champion is not None:
        update["completed"] = True
        update["champion"] = champion

    tournaments_collection.update_one({"_id": tid}, {"$set": update})
    tournament["bracket"] = bracket
    tournament["current_round"] = next_round
    if completed:
        tournament["completed"] = True
        tournament["champion"] = champion
    return tournament
