#!/usr/bin/env python3
"""
Read-only: verify Training Squad / walk-on roster invariants for a franchise.

For each team in a franchise it reports active (players), training squad, total,
walk-on count, and class-year spread, and flags violations of the invariants:
  - total roster <= 15
  - active (players) <= 12
  - active + training_squad have no overlap
Useful after: season-1 init (expect 15/team, 3 walk-ons, TS empty),
after Training Camp (expect 12 active + 3 TS), and after a season turn.

Usage (from repo root):
  PYTHONPATH=. venv/bin/python scripts/inspect_franchise_roster_counts.py <franchise_id> [db]
  PYTHONPATH=. venv/bin/python scripts/inspect_franchise_roster_counts.py --list [db]

db defaults to gob-staging.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from bson import ObjectId
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target
MAX_ROSTER = 15
ACTIVE_CAP = 12


def _ids(values) -> list[str]:
    return [str(v) for v in (values or []) if v]


def list_franchises(db) -> None:
    docs = list(db["franchises"].find({}, {"week": 1, "user_id": 1}).limit(25))
    print(f"Recent franchises in [{db.name}]:")
    for d in docs:
        print(f"  {d['_id']}  week={d.get('week')}  user_id={d.get('user_id')}")
    if not docs:
        print("  (none)")


def inspect(db, franchise_id: str) -> int:
    try:
        fid_obj = ObjectId(franchise_id)
    except Exception:
        fid_obj = franchise_id

    fdoc = db["franchises"].find_one({"_id": fid_obj}, {"week": 1}) or {}
    week = fdoc.get("week")
    ftd_docs = list(db["franchise_team_data"].find(
        {"franchise_id": fid_obj},
        {"team_id": 1, "players": 1, "training_squad_players": 1},
    ))
    if not ftd_docs:
        print(f"No franchise_team_data for franchise_id={franchise_id} in [{db.name}].")
        return 1

    # FPD year/archetype lookup for every roster + TS id.
    all_ids = []
    for d in ftd_docs:
        all_ids += _ids(d.get("players")) + _ids(d.get("training_squad_players"))
    fpd = {
        doc["player_id"]: doc
        for doc in db["franchise_players_data"].find(
            {"franchise_id": str(fid_obj), "player_id": {"$in": all_ids}},
            {"player_id": 1, "meta.year": 1, "meta.archetype": 1},
        )
    }

    def year_of(pid: str) -> str:
        return str((((fpd.get(pid) or {}).get("meta") or {}).get("year") or "?")).lower()

    def is_walkon(pid: str) -> bool:
        return (((fpd.get(pid) or {}).get("meta") or {}).get("archetype")) == "Walk On"

    print(f"Franchise {franchise_id}  (week={week})  in [{db.name}] — {len(ftd_docs)} teams\n")
    print(f"{'team_id':26} {'active':>6} {'TS':>3} {'total':>5} {'walkon':>6}  flags")
    violations = 0
    totals = Counter()
    for d in sorted(ftd_docs, key=lambda x: str(x.get("team_id"))):
        active = _ids(d.get("players"))
        ts = _ids(d.get("training_squad_players"))
        total = len(set(active) | set(ts))
        walkons = sum(1 for pid in active + ts if is_walkon(pid))

        flags = []
        if total > MAX_ROSTER:
            flags.append(f"TOTAL>{MAX_ROSTER}")
        if len(active) > ACTIVE_CAP:
            flags.append(f"ACTIVE>{ACTIVE_CAP}")
        if set(active) & set(ts):
            flags.append("OVERLAP")
        if flags:
            violations += 1
        totals["active"] += len(active)
        totals["ts"] += len(ts)
        totals["walkon"] += walkons

        print(f"{str(d.get('team_id')):26} {len(active):>6} {len(ts):>3} {total:>5} {walkons:>6}  {','.join(flags)}")

    print(
        f"\nTotals: active={totals['active']}  TS={totals['ts']}  walk-ons={totals['walkon']}"
        f"  | teams with violations: {violations}/{len(ftd_docs)}"
    )
    # Sample one team's year spread for a quick sanity read.
    sample = ftd_docs[0]
    spread = Counter(year_of(pid) for pid in _ids(sample.get("players")) + _ids(sample.get("training_squad_players")))
    print(f"Sample team {sample.get('team_id')} year spread: {dict(spread)}")
    return 0 if violations == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("franchise_id", nargs="?")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=False)
    try:
        if args.list or not args.franchise_id:
            list_franchises(connection.database)
            return 0
        return inspect(connection.database, args.franchise_id)
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
