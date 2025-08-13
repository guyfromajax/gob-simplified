#!/usr/bin/env python3
"""Backfill player_stats for tournaments and franchises.

This migration seeds ``player_stats`` and resets ``applied_games`` for every
existing tournament and franchise document.  It queries all players (expected 96)
so each aggregate contains an entry for every player.

Optionally the ``--rebuild`` flag can be used to replay previously applied
game summaries to rebuild the aggregates after seeding.
"""

import argparse
import os
import sys
from pathlib import Path

# Allow ``from BackEnd import ...`` when executed as a script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bson import ObjectId

from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.db import (
    players_collection,
    tournaments_collection,
    games_collection,
    db,
)
from BackEnd.utils.stat_updater import apply_stats_from_summary, finalize_game


def _build_player_template(include_career: bool = False) -> dict[str, dict]:
    """Return a mapping of player id -> zeroed stat structures."""
    zero = {k: 0 for k in BOX_SCORE_KEYS}
    template: dict[str, dict] = {}
    for p in players_collection.find({}, {"first_name": 1, "last_name": 1, "team": 1}):
        pid = str(p.get("_id"))
        entry = {
            "first_name": p.get("first_name", ""),
            "last_name": p.get("last_name", ""),
            "team": p.get("team", ""),
            "season": zero.copy(),
        }
        if include_career:
            entry["career"] = zero.copy()
        template[pid] = entry
    return template


def migrate_tournaments(rebuild: bool) -> None:
    """Seed player_stats and optionally rebuild tournament aggregates."""
    template = _build_player_template()
    for doc in tournaments_collection.find({}):
        tid = doc.get("_id")
        original_games = doc.get("applied_games", [])
        tournaments_collection.update_one(
            {"_id": tid}, {"$set": {"player_stats": template, "applied_games": []}}
        )
        print(f"Updated tournament {tid}")
        if rebuild:
            for gid in original_games:
                game = games_collection.find_one({"_id": gid})
                if not game:
                    try:
                        game = games_collection.find_one({"_id": ObjectId(gid)})
                    except Exception:
                        game = None
                if game:
                    apply_stats_from_summary(game, str(gid), str(tid))


def migrate_franchises(rebuild: bool) -> None:
    """Seed player_stats and optionally rebuild franchise aggregates."""
    template = _build_player_template(include_career=True)
    franchises = db["franchises"]
    for doc in franchises.find({}):
        fid = doc.get("_id")
        original_games = doc.get("applied_games", [])
        franchises.update_one(
            {"_id": fid}, {"$set": {"player_stats": template, "applied_games": []}}
        )
        print(f"Updated franchise {fid}")
        if rebuild:
            for gid in original_games:
                finalize_game(str(gid), mode="franchise", franchise_id=str(fid))


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill player_stats fields")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Replay historical games to rebuild aggregates after seeding",
    )
    args = parser.parse_args()

    migrate_tournaments(args.rebuild)
    migrate_franchises(args.rebuild)
    print("Migration complete")


if __name__ == "__main__":
    main()
