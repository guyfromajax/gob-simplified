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
    args = ap.parse_args()

    if not os.environ.get("MONGO_URI") and not args.allow_mock and not args.dry_run:
        sys.exit("MONGO_URI not set — refusing to write to ephemeral mongomock. "
                 "Set MONGO_URI, or pass --allow-mock / --dry-run.")

    from BackEnd.db import db  # noqa: E402
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
            if args.dry_run:
                print(f"[ok] {os.path.basename(p)}: valid, {doc['recruit_count']} recruits (would upsert {doc['set_id']})")
            else:
                coll.replace_one({"set_id": doc["set_id"]}, doc, upsert=True)
                print(f"[ok] upserted {doc['set_id']} ({doc['recruit_count']} recruits)")
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
