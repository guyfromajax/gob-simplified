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
import argparse, os, sys, statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.chdir(REPO)
from dotenv import load_dotenv
load_dotenv(str(REPO / ".env.local"))

# Parse + guard BEFORE importing BackEnd (that import connects to Mongo). The guard
# requires --allow-db's value to appear in the connected MONGO_URI, so the tool can never
# write to a DB you did not explicitly name. Default gob-staging keeps prior behavior;
# pass --allow-db <prod-db-name> (with MONGO_URI pointed at prod) to backfill prod.
_ap = argparse.ArgumentParser(description=__doc__)
_ap.add_argument("--commit", action="store_true", help="write the $set (default: dry-run)")
_ap.add_argument("--allow-db", default="gob-staging",
                 help="DB-name substring that MUST appear in MONGO_URI (safety guard). "
                      "Default gob-staging; pass your prod DB name to run there.")
_args = _ap.parse_args()
if _args.allow_db.lower() not in os.environ.get("MONGO_URI", "").lower():
    print(f"ABORT: MONGO_URI does not contain '{_args.allow_db}' — refusing to write to an "
          f"unnamed DB. Point MONGO_URI at the target and pass --allow-db <its name>.",
          file=sys.stderr)
    sys.exit(1)

from BackEnd.db import players_collection
from BackEnd.utils.player_generation import resolve_potential_factor, POTENTIAL_FACTOR_BAND
from pymongo import UpdateOne


def main():
    args = _args

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

    if not args.commit:
        print("\nDRY-RUN — no write. Re-run with --commit to persist.")
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


if __name__ == "__main__":
    main()
