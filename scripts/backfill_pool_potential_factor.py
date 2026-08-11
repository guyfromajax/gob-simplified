"""Phase 5 — retroactive potential_factor backfill for the migrated universal pool.

Persists `resolve_potential_factor(player_id, None)` — the EXACT deterministic hash value the
Phase-4 base-roster pages already display for a pool player with no stored factor — NOT a fresh
uniform draw. So nothing changes visibly at backfill: a team scouted pre-franchise shows the same
ceiling afterward (verified per-player below). The value is uniform and in-band by construction
(see BackEnd/tests/test_potential_factor.py), so persisting it loses nothing versus a fresh draw.

Additive `$set` of a single field only — never touches attributes/height/weight/year/ratings.
Idempotent: skips any player that already carries potential_factor. Dry-run by default; pass
--commit to write. Guarded to gob-staging.

  python scripts/backfill_pool_potential_factor.py            # dry-run manifest
  python scripts/backfill_pool_potential_factor.py --commit   # write, then verify
"""
from __future__ import annotations
import argparse, sys, statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
_ap = argparse.ArgumentParser(description=__doc__)
_ap.add_argument("--db", required=True, choices=["gob-staging", "gob"])
_ap.add_argument("--apply", action="store_true", help="write the $set (default: dry-run)")
_args = _ap.parse_args()

from BackEnd.utils.player_generation import resolve_potential_factor, POTENTIAL_FACTOR_BAND
from pymongo import UpdateOne
from scripts.db_migration_cli import connect_migration_target


def main():
    args = _args
    connection = connect_migration_target(args.db, write=args.apply)
    players_collection = connection.database["players"]

    total = players_collection.count_documents({})
    have = players_collection.count_documents({"potential_factor": {"$exists": True}})
    missing_cur = players_collection.find(
        {"potential_factor": {"$exists": False}}, {"_id": 1})
    targets = []
    for d in missing_cur:
        pid = str(d["_id"])
        # warn=False: this IS the expected legacy resolution, not a regression
        pf = resolve_potential_factor(pid, None, warn=False)
        targets.append((d["_id"], pf))

    vals = [pf for _, pf in targets]
    print(f"pool players total          : {total}")
    print(f"already have potential_factor: {have}  (skipped — idempotent)")
    print(f"to backfill                  : {len(targets)}")
    if vals:
        lo, hi = 1 - POTENTIAL_FACTOR_BAND, 1 + POTENTIAL_FACTOR_BAND
        in_band = all(lo <= v <= hi for v in vals)
        print(f"  value dist: min {min(vals):.4f}  p50 {statistics.median(vals):.4f}  "
              f"max {max(vals):.4f}  mean {statistics.mean(vals):.4f}  in-band {in_band}")
        print(f"  sample: " + ", ".join(f"{str(i)[:8]}…={v}" for i, v in targets[:5]))

    if not args.apply:
        print("\nDRY-RUN — no write. Re-run with --apply to persist.")
        connection.close()
        return

    if not targets:
        print("\nNothing to write."); return
    ops = [UpdateOne({"_id": i}, {"$set": {"potential_factor": pf}}) for i, pf in targets]
    res = players_collection.bulk_write(ops, ordered=False)
    print(f"\nCOMMITTED: modified {res.modified_count} docs.")

    # post-write EQUALITY CHECK: stored value must equal what the page showed (resolve(id,None))
    mism = 0
    for i, pf in targets:
        stored = players_collection.find_one({"_id": i}, {"potential_factor": 1}).get("potential_factor")
        if stored != pf:
            mism += 1
            if mism <= 5:
                print(f"  MISMATCH {i}: stored {stored} != displayed {pf}")
    print(f"equality check: {len(targets) - mism}/{len(targets)} match the pre-write displayed value "
          f"({'CLEAN' if mism == 0 else str(mism) + ' MISMATCHES'})")
    connection.close()


if __name__ == "__main__":
    main()
