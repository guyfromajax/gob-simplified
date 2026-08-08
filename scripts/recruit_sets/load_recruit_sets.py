#!/usr/bin/env python3
"""
Load built recruit set(s) into the shared `recruit_sets` Mongo collection.

The `recruit_sets` collection is the read-only pool the season-init/rollover
loader draws from (a franchise picks a random unused set). This script upserts a
built set document (set_<id>.json, produced by build_recruit_set.py) into that
collection, keyed by set_id, and ensures the unique index.

Run WHERE MONGO_URI IS SET (your machine / an env with DB access) — same
connection as the game (reuses BackEnd.db). Without MONGO_URI it falls back to
in-memory mongomock, which does NOT persist, so the script refuses unless
--allow-mock.

    # preview, then load one set:
    python3 scripts/recruit_sets/load_recruit_sets.py --set scripts/recruit_sets/set_0001.json --dry-run
    python3 scripts/recruit_sets/load_recruit_sets.py --set scripts/recruit_sets/set_0001.json
    # load every set_*.json in a directory:
    python3 scripts/recruit_sets/load_recruit_sets.py --dir scripts/recruit_sets
    # show what's already loaded:
    python3 scripts/recruit_sets/load_recruit_sets.py --list

See _documentation_master/00_Operations/Recruit_Image_System.md.
"""
import os
import sys
import glob
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

COLL = "recruit_sets"
_CORE_ATTRS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]


def validate(doc):
    recs = doc.get("recruits") or []
    assert doc.get("set_id"), "missing set_id"
    assert len(recs) == doc.get("recruit_count"), \
        f"recruit_count {doc.get('recruit_count')} != {len(recs)} recruits"
    ids = [r.get("recruit_id") for r in recs]
    assert all(ids), "a recruit is missing recruit_id"
    assert len(set(ids)) == len(ids), "duplicate recruit_id within set"
    for r in recs:
        assert r.get("year") in ("JH", "Freshman", "Sophomore", "Junior"), f"bad year {r.get('year')}"
        attrs = r.get("attributes") or {}
        assert all(c in attrs for c in _CORE_ATTRS), f"{r.get('recruit_id')} missing core attributes"


def main():
    ap = argparse.ArgumentParser(description="Load recruit set(s) into the recruit_sets collection.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--set", help="path to one set_<id>.json")
    g.add_argument("--dir", help="directory of set_*.json to load")
    g.add_argument("--list", action="store_true", help="list sets already in the collection")
    ap.add_argument("--dry-run", action="store_true", help="validate + preview, no write")
    ap.add_argument("--allow-mock", action="store_true",
                    help="proceed even without MONGO_URI (writes to ephemeral mongomock — for testing only)")
    ap.add_argument("--force", action="store_true",
                    help="override the revert guard — allow loading a set whose recruit_count is LOWER "
                         "than what's already in the collection (normally refused, since a stale file "
                         "would wipe a larger live set, e.g. reverting the 450 regen back to 300).")
    args = ap.parse_args()

    # Import db FIRST — that is what loads .env/.env.local and sets MONGO_URI.
    # Then decide real-vs-mock from the actual client type, not a raw env read
    # (the env var isn't populated until this import runs).
    from BackEnd.db import db, client  # noqa: E402
    is_mock = "mongomock" in type(client).__module__
    if is_mock and not args.allow_mock and not args.dry_run:
        sys.exit("Not connected to a real MongoDB (got mongomock) — refusing to write. "
                 "Ensure MONGO_URI / .env.local is set, or pass --allow-mock / --dry-run.")
    coll = db[COLL]

    if args.list:
        docs = list(coll.find({}, {"set_id": 1, "recruit_count": 1, "version": 1, "_id": 0}))
        print(f"{len(docs)} set(s) in `{COLL}`:")
        for d in sorted(docs, key=lambda d: d.get("set_id", "")):
            print(f"  {d.get('set_id'):12} v{d.get('version', '?')}  {d.get('recruit_count')} recruits")
        return

    paths = [args.set] if args.set else sorted(glob.glob(os.path.join(args.dir, "set_*.json")))
    paths = [p for p in paths if not p.endswith(".manifest.json")]
    if not paths:
        sys.exit("no set files found")

    if not args.dry_run:
        coll.create_index("set_id", unique=True)

    ok = fail = 0
    for p in paths:
        try:
            doc = json.load(open(p))
            validate(doc)
            # Revert guard: never let a smaller set-file silently overwrite a larger
            # live set (e.g. a stale set_0001.json at 300 clobbering the 450 regen).
            existing = coll.find_one({"set_id": doc["set_id"]}, {"recruit_count": 1})
            existing_count = (existing or {}).get("recruit_count")
            shrinking = existing_count is not None and doc["recruit_count"] < existing_count
            if shrinking and not args.force:
                print(f"[BLOCKED] {os.path.basename(p)}: {doc['set_id']} would shrink "
                      f"{existing_count} -> {doc['recruit_count']} recruits. Refusing (revert guard). "
                      f"Pass --force only if this shrink is intentional.")
                fail += 1
                continue
            if args.dry_run:
                warn = "  ⚠️ SHRINK (allowed via --force)" if shrinking else ""
                print(f"[ok] {os.path.basename(p)}: valid, {doc['recruit_count']} recruits "
                      f"(would upsert {doc['set_id']}){warn}")
            else:
                coll.replace_one({"set_id": doc["set_id"]}, doc, upsert=True)
                note = f" (was {existing_count})" if existing_count is not None else ""
                print(f"[ok] upserted {doc['set_id']} ({doc['recruit_count']} recruits){note}")
            ok += 1
        except Exception as e:
            print(f"[fail] {os.path.basename(p)}: {type(e).__name__}: {str(e)[:160]}")
            fail += 1
    print(f"\n[done] {ok} loaded, {fail} failed"
          + ("  (DRY RUN — nothing written)" if args.dry_run else f" -> `{COLL}`"))
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
