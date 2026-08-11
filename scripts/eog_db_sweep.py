#!/usr/bin/env python3
"""
Whole-DB sweep — proves the snapshot CAPTURE SET is COMPLETE (not just that captured
collections revert). eog_arm_snapshot.py --verify checks only collections in the
snapshot; if complete_week writes a franchise-scoped doc to a collection NEITHER
write-surface trace found, --verify can't see it. This walks EVERY collection.

For each collection it records total doc count + a checksum over this franchise's
docs (matched by `franchise_id`, or `_id ∈ {franchise_id, owner_user_id}` to cover
the `franchises`/`users` docs). Capture the sweep pre-run and again post-restore:
any collection whose (count, checksum) moved and didn't come back is either
uncaptured or restore-buggy — a hole, regardless of what the traces said.

Usage:
  python scripts/eog_db_sweep.py capture ./sweep_before.json --db gob-staging
  # ... run 1 week, then restore ...
  python scripts/eog_db_sweep.py capture ./sweep_after.json
  python scripts/eog_db_sweep.py compare ./sweep_before.json ./sweep_after.json
"""

from __future__ import annotations

# Pin PYTHONHASHSEED before anything else: unpinned runs are not reproducible and
# have produced false measurement conclusions. See BackEnd/utils/repro.
# Loaded BY PATH so this does not import the BackEnd.utils package, whose __init__
# pulls in stat_updater -> db and would open a Mongo connection twice across the
# re-exec.
import os as _os, sys as _sys, importlib.util as _ilu
_GOB_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _GOB_ROOT)
_spec = _ilu.spec_from_file_location(
    "_gob_repro", _os.path.join(_GOB_ROOT, "BackEnd", "utils", "repro.py"))
_repro = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_repro)
_repro.pin_hash_seed()

import hashlib
import argparse
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TARGET_FRANCHISE_ID = os.environ.get("GOB_MEASUREMENT_FRANCHISE_ID", "6a67882a2b2eb443f8c7789f")


def _abort(msg: str) -> None:
    print(f"❌ ABORT: {msg}", file=sys.stderr)
    sys.exit(1)


def capture(outfile: str, database_name: str) -> int:
    from bson import ObjectId
    from bson.json_util import dumps
    from scripts.db_migration_cli import connect_migration_target

    connection = connect_migration_target(database_name, write=False)
    db = connection.database
    franchises_collection = db["franchises"]

    fid = ObjectId(TARGET_FRANCHISE_ID)
    fdoc = franchises_collection.find_one({"_id": fid}, {"user_id": 1})
    if not fdoc:
        _abort(f"Franchise {TARGET_FRANCHISE_ID} not found.")
    owner = fdoc.get("user_id")
    owner_oid = owner if isinstance(owner, ObjectId) else (ObjectId(owner) if owner else None)
    fq = {"$or": [
        {"franchise_id": {"$in": [str(fid), fid]}},
        {"_id": {"$in": [x for x in (fid, owner_oid) if x is not None]}},
    ]}

    sweep = {}
    for name in sorted(db.list_collection_names()):
        coll = db[name]
        try:
            total = coll.count_documents({})
            docs = list(coll.find(fq))
        except Exception as e:  # noqa: BLE001
            sweep[name] = {"error": str(e)}
            continue
        h = hashlib.sha256()
        for s in sorted(dumps(d, sort_keys=True) for d in docs):
            h.update(s.encode())
        sweep[name] = {"total": total, "fcount": len(docs), "fchecksum": h.hexdigest()}
    Path(outfile).write_text(json.dumps(sweep, indent=0))
    connection.close()
    print(f"✅ Swept {len(sweep)} collections → {outfile} "
          f"(franchise docs across {sum(v.get('fcount',0) for v in sweep.values())} rows)")
    return 0


def compare(a: str, b: str) -> int:
    A = json.loads(Path(a).read_text())
    B = json.loads(Path(b).read_text())
    names = sorted(set(A) | set(B))
    moved = []
    for n in names:
        va, vb = A.get(n), B.get(n)
        if va != vb:
            moved.append((n, va, vb))
    if not moved:
        print(f"✅ SWEEP CLEAN — all {len(names)} collections identical before vs after restore. "
              f"Capture set is COMPLETE (nothing outside it changed and stuck).")
        return 0
    print(f"❌ SWEEP DIRTY — {len(moved)} collection(s) did NOT revert:")
    for n, va, vb in moved:
        print(f"  {n}")
        print(f"     before={va}")
        print(f"     after ={vb}")
    print("\nEach is either uncaptured by eog_arm_snapshot.py's spec, or captured but "
          "not correctly reverted. Add it to the restore set (or fix the restore) before the arms.")
    return 5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("outfile")
    capture_parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("before")
    compare_parser.add_argument("after")
    args = parser.parse_args()
    if args.command == "capture":
        return capture(args.outfile, args.db)
    return compare(args.before, args.after)


if __name__ == "__main__":
    raise SystemExit(main())
