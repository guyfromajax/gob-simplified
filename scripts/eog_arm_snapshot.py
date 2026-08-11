#!/usr/bin/env python3
"""
Snapshot / restore the measurement franchise's week-1 state so the 5-seed
distributional arms (and the poison-stash pass) can each start from the SAME
state. scripts/eog_measurement_season.py ADVANCES the franchise, so re-running it
gives later weeks, not independent arms — restore between runs.

Every write in a franchise week is franchise-scoped EXCEPT three cross-scope docs
(the owner `users` account, and the global `community_highlights` /
`around_the_league` feed docs). All are single docs on the isolated staging DB,
so this captures them too for a clean restore. Restore only ever touches THIS
franchise's docs, its owner's user doc, and (optionally) the two global feed docs.

Usage:
  export MONGO_URI='mongodb+srv://.../gob-staging'
  python scripts/eog_arm_snapshot.py --snapshot ./wk1_baseline           # once, at week 1
  python scripts/eog_arm_snapshot.py --restore  ./wk1_baseline           # before each arm
  # add --include-feeds to also snapshot/restore the two GLOBAL feed docs
  # (skip on a shared DB — they'd clobber other users' feed entries; cosmetic only)

5-seed arm loop:
  python scripts/eog_arm_snapshot.py --snapshot ./wk1_baseline
  for i in 1 2 3 4 5; do
    python scripts/eog_arm_snapshot.py --restore ./wk1_baseline
    GOB_EOG_BAND_LOG_FILE="$(pwd)/arm_$i.jsonl" scripts/run_eog_measurement.sh
  done
"""
from __future__ import annotations

import argparse
import atexit
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TARGET_FRANCHISE_ID = os.environ.get("GOB_MEASUREMENT_FRANCHISE_ID", "6a67882a2b2eb443f8c7789f")
EXPECTED_USER_TEAM = os.environ.get("GOB_MEASUREMENT_TEAM", "South Lancaster")
FEED_DOC_ID = "global_feed"      # community_highlights
BOARD_DOC_ID = "global_board"    # around_the_league


def _abort(msg: str) -> None:
    print(f"❌ ABORT: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--snapshot", metavar="DIR", help="Capture franchise state to DIR.")
    g.add_argument("--restore", metavar="DIR", help="Restore franchise state from DIR.")
    g.add_argument("--verify", metavar="DIR", help="Compare CURRENT captured-collection "
                   "state to snapshot DIR (determinism-free restore check; run after a "
                   "run+restore). Exit 0 = reverted cleanly; exit 5 = mismatches.")
    ap.add_argument("--include-feeds", action="store_true",
                    help="Also snapshot/restore the two GLOBAL feed docs (isolated DB only).")
    ap.add_argument("--yes", action="store_true",
                    help="Required with --restore because restore replaces staging data.")
    args = ap.parse_args()

    from bson import ObjectId
    from bson.json_util import dumps, loads
    from BackEnd.script_db import STAGING_DB, connect_script_database

    if args.restore and not args.yes:
        _abort("--restore requires --yes")
    connection = connect_script_database(
        target=STAGING_DB,
        access="write" if args.restore else "read",
        destructive=bool(args.restore),
        pristine_env=dict(os.environ),
        repo_root=_REPO,
    )
    atexit.register(connection.close)
    db = connection.database
    franchises_collection = db["franchises"]
    franchise_team_data_collection = db["franchise_team_data"]
    franchise_players_data_collection = db["franchise_players_data"]
    franchise_recruits_data_collection = db["franchise_recruits_data"]
    games_collection = db["games"]
    users_collection = db["users"]
    community_highlights_collection = db["community_highlights"]
    around_the_league_collection = db["around_the_league"]

    fid = ObjectId(TARGET_FRANCHISE_ID)
    sfid = str(fid)
    fdoc = franchises_collection.find_one({"_id": fid})
    if not fdoc:
        _abort(f"Franchise {TARGET_FRANCHISE_ID} not found in this DB.")
    if fdoc.get("user_team_id") != EXPECTED_USER_TEAM:
        _abort(f"Franchise user team is {fdoc.get('user_team_id')!r}, expected {EXPECTED_USER_TEAM!r}.")
    owner_oid = fdoc.get("user_id")
    owner_query = {"_id": ObjectId(owner_oid)} if owner_oid and not isinstance(owner_oid, ObjectId) else {"_id": owner_oid}

    # (name, collection, query) — franchise-scoped + owner user; feeds appended below.
    specs = [
        ("franchises", franchises_collection, {"_id": fid}),
        ("franchise_team_data", franchise_team_data_collection, {"franchise_id": fid}),
        ("franchise_players_data", franchise_players_data_collection, {"franchise_id": sfid}),
        ("franchise_recruits_data", franchise_recruits_data_collection, {"franchise_id": sfid}),
        ("games", games_collection, {"franchise_id": sfid}),
        ("users", users_collection, owner_query),
    ]
    if args.include_feeds:
        specs += [
            ("community_highlights", community_highlights_collection, {"_id": FEED_DOC_ID}),
            ("around_the_league", around_the_league_collection, {"_id": BOARD_DOC_ID}),
        ]

    if args.snapshot:
        d = Path(args.snapshot)
        d.mkdir(parents=True, exist_ok=True)
        print(f"✅ Guards passed. Snapshotting franchise {TARGET_FRANCHISE_ID} → {d}")
        for name, coll, query in specs:
            docs = list(coll.find(query))
            (d / f"{name}.json").write_text(dumps(docs))
            print(f"  {name:<24} {len(docs):>5} docs")
        print("Snapshot complete. Restore before each arm.")
        return 0

    if args.verify:
        # Determinism-free restore check: current captured-collection state vs snapshot.
        d = Path(args.verify)
        if not d.exists():
            _abort(f"snapshot dir not found: {d}")
        print(f"✅ Guards passed. Verifying franchise {TARGET_FRANCHISE_ID} vs snapshot {d}")
        total_mismatch = 0
        for name, coll, query in specs:
            snap = {doc["_id"]: dumps(doc, sort_keys=True) for doc in loads((d / f"{name}.json").read_text())}
            cur = {doc["_id"]: dumps(doc, sort_keys=True) for doc in coll.find(query)}
            changed = [k for k in snap if k in cur and snap[k] != cur[k]]
            missing = [k for k in snap if k not in cur]     # snapshot doc gone
            extra = [k for k in cur if k not in snap]        # un-reverted insert
            n = len(changed) + len(missing) + len(extra)
            total_mismatch += n
            flag = "" if n == 0 else f"  ⚠️ changed={len(changed)} missing={len(missing)} extra={len(extra)}"
            print(f"  {name:<24} {len(cur):>5} docs{flag}")
            for k in (changed[:3]):
                print(f"      CHANGED _id={k}")
        if total_mismatch == 0:
            print("\n✅ VERIFY CLEAN — restore reverted every captured collection to the snapshot.")
            return 0
        print(f"\n❌ VERIFY FAILED — {total_mismatch} doc(s) not reverted. Restore has a hole "
              f"in the captured collections (or the run wrote something restore didn't undo).")
        return 5

    # --restore
    d = Path(args.restore)
    if not d.exists():
        _abort(f"snapshot dir not found: {d}")
    print(f"✅ Guards passed. Restoring franchise {TARGET_FRANCHISE_ID} ← {d}")
    for name, coll, query in specs:
        snap = loads((d / f"{name}.json").read_text())
        if name == "games":
            # Games are CREATED during a run → delete every franchise game not in the
            # baseline set, leaving pre-existing docs (usually none at week 1).
            baseline_ids = {doc["_id"] for doc in snap}
            res = coll.delete_many({"franchise_id": sfid, "_id": {"$nin": list(baseline_ids)}})
            print(f"  {name:<24} deleted {res.deleted_count} arm-created game docs")
            continue
        if name in ("franchises", "users") or name in ("community_highlights", "around_the_league"):
            # Single-doc collections → overwrite in place.
            for doc in snap:
                coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)
            print(f"  {name:<24} overwrote {len(snap)} doc(s)")
            continue
        # FTD / FPD / FR: finalize can INSERT new docs, so delete-then-insert to avoid leaks.
        coll.delete_many(query)
        if snap:
            coll.insert_many(snap)
        print(f"  {name:<24} restored {len(snap)} docs (delete_many + insert_many)")
    print("Restore complete. Franchise is back at the snapshot state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
