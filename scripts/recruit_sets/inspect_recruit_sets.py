"""READ-ONLY inspector for the recruit_sets collection.

Prints, per set: id, version, recruit_count vs actual, field coverage (image-linkage
and the stable Home Region), year distribution, and a few sample recruit_ids — so we
can confirm the as-built state before appending recruits. Writes NOTHING.

Usage (MONGO_URI / .env.local selects the DB, like the other recruit_set scripts):
    python scripts/recruit_sets/inspect_recruit_sets.py
    python scripts/recruit_sets/inspect_recruit_sets.py --set-id set_0001 --samples 5
"""
import argparse
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

CORE_ATTRS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]


def main():
    ap = argparse.ArgumentParser(description="Read-only inspect of recruit_sets.")
    ap.add_argument("--set-id", default=None, help="limit to one set_id (default: all)")
    ap.add_argument("--samples", type=int, default=3, help="how many sample recruits to print")
    args = ap.parse_args()

    from BackEnd.db import db, client
    is_mock = "mongomock" in type(client).__module__
    banner = f"DB: {db.name} | conn: {'MOCK (no MONGO_URI)' if is_mock else 'REAL'}"
    print("=" * len(banner)); print(banner); print("=" * len(banner))

    query = {"set_id": args.set_id} if args.set_id else {}
    sets = list(db.recruit_sets.find(query))
    if not sets:
        print(f"No recruit_sets found{' for ' + args.set_id if args.set_id else ''}.")
        return

    for doc in sets:
        recs = doc.get("recruits") or []
        n = len(recs)
        print(f"\n── set_id={doc.get('set_id')}  version={doc.get('version')}  "
              f"recruit_count={doc.get('recruit_count')}  actual_recruits={n}")
        if doc.get("recruit_count") != n:
            print(f"   ⚠️  recruit_count ({doc.get('recruit_count')}) != actual ({n})")

        # field coverage
        have_rid = sum(1 for r in recs if r.get("recruit_id"))
        have_region = sum(1 for r in recs if r.get("Home Region"))
        have_attrs = sum(1 for r in recs if all(c in (r.get("attributes") or {}) for c in CORE_ATTRS))
        have_pr = sum(1 for r in recs if r.get("position_ratings"))
        print(f"   coverage: recruit_id {have_rid}/{n} | Home Region {have_region}/{n} "
              f"| core attrs {have_attrs}/{n} | position_ratings {have_pr}/{n}")

        # uniqueness
        ids = [r.get("recruit_id") for r in recs if r.get("recruit_id")]
        dupes = [k for k, v in Counter(ids).items() if v > 1]
        print(f"   unique recruit_ids: {len(set(ids))}/{len(ids)}"
              + (f"  ⚠️ DUPLICATES: {dupes[:5]}" if dupes else "  ✓"))

        # distributions
        yr = Counter(r.get("year") for r in recs)
        print("   year: " + " | ".join(f"{k} {yr[k]}" for k in ("JH", "Freshman", "Sophomore", "Junior") if yr.get(k)))
        reg = Counter(r.get("Home Region") for r in recs if r.get("Home Region"))
        if reg:
            print("   region: " + " | ".join(f"{k} {reg[k]}" for k in sorted(reg)))

        # samples
        print(f"   sample recruits (first {args.samples}):")
        for r in recs[:args.samples]:
            print(f"     - {r.get('recruit_id')}  {r.get('name'):<22} "
                  f"{str(r.get('year')):<10} region={r.get('Home Region')}")

    print("\n(read-only — nothing was written)")


if __name__ == "__main__":
    main()
