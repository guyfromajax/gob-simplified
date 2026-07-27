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
  export MONGO_URI='mongodb+srv://.../gob-staging'
  python scripts/eog_db_sweep.py capture ./sweep_before.json
  # ... run 1 week, then restore ...
  python scripts/eog_db_sweep.py capture ./sweep_after.json
  python scripts/eog_db_sweep.py compare ./sweep_before.json ./sweep_after.json
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TARGET_FRANCHISE_ID = os.environ.get("GOB_MEASUREMENT_FRANCHISE_ID", "6a67882a2b2eb443f8c7789f")
EXPECTED_DB_MARKER = "gob-staging"


def _abort(msg: str) -> None:
    print(f"❌ ABORT: {msg}", file=sys.stderr)
    sys.exit(1)


def capture(outfile: str) -> int:
    if EXPECTED_DB_MARKER not in os.environ.get("MONGO_URI", "").lower():
        _abort(f"MONGO_URI does not point at '{EXPECTED_DB_MARKER}'.")
    from bson import ObjectId
    from bson.json_util import dumps
    from BackEnd.db import db, franchises_collection

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
    if len(sys.argv) < 2 or sys.argv[1] not in ("capture", "compare"):
        print(__doc__)
        return 2
    if sys.argv[1] == "capture":
        if len(sys.argv) != 3:
            _abort("capture needs an output file")
        return capture(sys.argv[2])
    if len(sys.argv) != 4:
        _abort("compare needs two files")
    return compare(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    raise SystemExit(main())
