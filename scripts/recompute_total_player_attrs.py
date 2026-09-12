#!/usr/bin/env python3
"""Recompute teams.total_player_attrs from live rosters; dry-run by default.

WHY
---
``teams.total_player_attrs`` is a DERIVED CACHE — the sum of
``core_total_player_attrs`` (SC SH ID OD PS BH RB ST AG IQ ND FT) over a team's
rostered players. Nothing recomputes it when player attributes change, so it drifted
out of date at the attribute recalibration and has stayed wrong since.

Measured on gob-staging 2026-09-11: all 128 teams disagree with their live rosters,
mean absolute error 540, max 1633, in BOTH directions. Because the error is not a
constant scale factor, the RANKING it implies is wrong, not merely the magnitudes --
all 16 conferences re-order when recomputed. It feeds FTE v3 opponent ranking and
``franchise_rank_prestige`` / Team Builder league context, so a stale value silently
mis-ranks opponents and prestige.

This script only recomputes the cache from the players it already points at. It adds
no players, removes none, and touches no other field.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db_migration_cli import connect_migration_target
from BackEnd.utils.franchise_rank_prestige import core_total_player_attrs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", choices=("gob-staging", "gob"), required=True)
    parser.add_argument("--apply", action="store_true", help="write; omit for dry run")
    parser.add_argument("--limit", type=int, default=0, help="only show N rows in the plan")
    args = parser.parse_args()

    connection = connect_migration_target(args.db, write=args.apply)
    teams = connection.database["teams"]
    players = connection.database["players"]

    planned: list[tuple[str, int, int]] = []
    missing_players = 0

    for team in teams.find({}, {"name": 1, "player_ids": 1, "total_player_attrs": 1}):
        ids = list(team.get("player_ids") or [])
        docs = list(players.find({"_id": {"$in": ids}}, {"attributes": 1}))
        if len(docs) != len(ids):
            missing_players += len(ids) - len(docs)
        live = sum(core_total_player_attrs(d.get("attributes")) for d in docs)
        stored = int(team.get("total_player_attrs") or 0)
        if live != stored:
            planned.append((team["_id"], stored, live))

    total = teams.count_documents({})
    print(f"[PLAN] {args.db}.teams total={total} needing_update={len(planned)}")
    if missing_players:
        # Not fatal, but it means a roster references players that no longer exist;
        # the recomputed total legitimately drops. Surfaced so it is never silent.
        print(f"[WARN] {missing_players} referenced player_ids had no players doc")

    shown = planned if not args.limit else planned[: args.limit]
    for _id, stored, live in shown:
        print(f"   {str(_id)[:24]:<26} {stored:>7} -> {live:>7}  ({live - stored:+})")
    if args.limit and len(planned) > args.limit:
        print(f"   ... and {len(planned) - args.limit} more")

    if not args.apply:
        print("[DRY RUN] No data changed.")
        connection.close()
        return 0

    modified = 0
    for _id, _stored, live in planned:
        result = teams.update_one({"_id": _id}, {"$set": {"total_player_attrs": int(live)}})
        modified += result.modified_count
    print(f"[DONE] matched={len(planned)} modified={modified}")

    remaining = 0
    for team in teams.find({}, {"player_ids": 1, "total_player_attrs": 1}):
        docs = players.find({"_id": {"$in": list(team.get("player_ids") or [])}}, {"attributes": 1})
        if sum(core_total_player_attrs(d.get("attributes")) for d in docs) != int(
            team.get("total_player_attrs") or 0
        ):
            remaining += 1
    print(f"[VERIFY] teams still disagreeing after write: {remaining}")

    connection.close()
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
