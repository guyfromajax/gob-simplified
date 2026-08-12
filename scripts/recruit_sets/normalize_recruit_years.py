"""Normalize recruit `year` from abbreviations (JH/FR/SO/JR) to full names
(JH/Freshman/Sophomore/Junior) — the recruit-set contract (SCHEMA + loader
validator + season-rollover advancer all expect full names).

The 300->450 regen wrote abbreviated years into the DB + canonical set, which
(a) fails load_recruit_sets.validate() and (b) breaks season rollover: advance_year
only maps full names, so a signed FR/SO/JR recruit gets stuck (never advances /
graduates). This maps them back to full names everywhere they're stored.

Two targets, both idempotent (already-full years are left untouched; a run that
changes nothing writes nothing):
  --db            normalize the recruit_sets collection (dry-run unless --commit; prints the DB)
  --files a.json  normalize local set/export JSON files in place (needs --commit to write)

Usage:
    python scripts/recruit_sets/normalize_recruit_years.py --db                         # dry-run staging via .env.local
    MONGO_URI="<uri>" python scripts/recruit_sets/normalize_recruit_years.py --db --commit
    python scripts/recruit_sets/normalize_recruit_years.py --files scripts/recruit_sets/set_0001.json --commit
"""
import argparse
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

# Abbrev (or already-full) -> canonical full name. SR included defensively though
# recruit sets never contain seniors.
YEAR_FULL = {
    "JH": "JH", "FR": "Freshman", "SO": "Sophomore", "JR": "Junior", "SR": "Senior",
    "Freshman": "Freshman", "Sophomore": "Sophomore", "Junior": "Junior", "Senior": "Senior",
}


def normalize_recruits(recruits):
    """Map each recruit's year to its full name in place. Returns (changed, before, after)."""
    before = Counter(r.get("year") for r in recruits)
    changed = 0
    for r in recruits:
        y = r.get("year")
        full = YEAR_FULL.get(y)
        if full and full != y:
            r["year"] = full
            changed += 1
        elif full is None and y is not None:
            print(f"  ⚠️ unrecognized year {y!r} on {r.get('recruit_id')} — left as-is")
    after = Counter(r.get("year") for r in recruits)
    return changed, before, after


def _report(label, changed, before, after):
    print(f"  {label}: normalized {changed}")
    print(f"    before: {dict(before)}")
    print(f"    after:  {dict(after)}")


def run_files(paths, commit):
    for p in paths:
        doc = json.load(open(p))
        recs = doc.get("recruits") or []
        if not recs:
            print(f"  {os.path.basename(p)}: no recruits[] — skipped")
            continue
        changed, before, after = normalize_recruits(recs)
        _report(os.path.basename(p), changed, before, after)
        if changed and commit:
            json.dump(doc, open(p, "w"), indent=2)
            print(f"    ✔ wrote {p}")
        elif changed:
            print("    DRY-RUN — not written (pass --commit)")


def run_db(db, set_id, commit):
    banner = f"DB: {db.name}"
    print("=" * len(banner)); print(banner); print("=" * len(banner))
    query = {"set_id": set_id} if set_id else {}
    sets = list(db.recruit_sets.find(query))
    if not sets:
        print("  no recruit_sets found"); return
    for doc in sets:
        recs = doc.get("recruits") or []
        changed, before, after = normalize_recruits(recs)
        _report(doc.get("set_id"), changed, before, after)
        if changed and commit:
            db.recruit_sets.update_one({"_id": doc["_id"]}, {"$set": {"recruits": recs}})
            print(f"    ✔ updated {doc.get('set_id')} in {db.name}")
        elif changed:
            print("    DRY-RUN — nothing written (pass --commit)")


def main():
    ap = argparse.ArgumentParser(description="Normalize recruit years abbrev -> full names.")
    ap.add_argument("--db", choices=["gob-staging", "gob"], help="normalize this recruit_sets collection")
    ap.add_argument("--set-id", default=None, help="limit --db to one set_id")
    ap.add_argument("--files", nargs="+", help="normalize local set/export JSON files in place")
    ap.add_argument("--apply", action="store_true", help="actually write (default: dry-run)")
    args = ap.parse_args()
    if not args.db and not args.files:
        ap.error("pass --db and/or --files")
    if args.files:
        print("── files ──")
        run_files(args.files, args.apply)
    if args.db:
        print("── database ──")
        from scripts.db_migration_cli import connect_migration_target
        connection = connect_migration_target(args.db, write=args.apply)
        run_db(connection.database, args.set_id, args.apply)
        connection.close()


if __name__ == "__main__":
    main()
