"""
Freeze each recruit's Home Region into the recruit_sets collection.

Home Region used to be re-rolled per franchise at FRD-load time (random.choice
over regions A–H), so the SAME set recruit could appear in a different region in
every franchise. This bakes a region ONCE into each recruit record in
`recruit_sets`, making it part of the recruit's stable identity. The loader then
reads the frozen value instead of re-rolling (see franchise_manager /
finish_season). Lean stays random (derived from the now-stable region) and jersey
stays random at signing — only Home Region becomes fixed.

The bake uses the exact same draw the loader used: a per-recruit uniform
random.choice over the eight regions "ABCDEFGH" (the fixed key set from
FranchiseManager._build_region_team_map). Running it is "do one more random
region assignment, then persist it".

SAFE BY DEFAULT:
  * Dry-run unless --commit is passed (so you always see the plan first).
  * Prints which database it is connected to — confirm staging vs prod before
    committing.
  * Idempotent: a recruit that already has a Home Region is left untouched, so
    re-running never re-randomizes a frozen value (unless --force is given).

Usage (MONGO_URI selects the database, exactly like load_recruit_sets.py):
    MONGO_URI="<staging-uri>" python scripts/recruit_sets/bake_home_region.py            # dry-run
    MONGO_URI="<staging-uri>" python scripts/recruit_sets/bake_home_region.py --commit    # write
    MONGO_URI="<prod-uri>"    python scripts/recruit_sets/bake_home_region.py --commit    # write prod
"""
import argparse
import os
import random
import sys

# Put the repo root on sys.path so `BackEnd` imports resolve when run as a script
# (mirrors load_recruit_sets.py).
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

# Fixed region key set — identical to FranchiseManager._build_region_team_map(),
# which pre-seeds {r: [] for r in "ABCDEFGH"} and whose .keys() is what the loader
# passed to random.choice. Independent of team data, so the bake matches the loader
# draw exactly.
REGION_KEYS = list("ABCDEFGH")


def region_for(recruit_id, region_keys):
    """The stable region for a recruit_id. Seeded by recruit_id — identical to the
    baker (build_recruit_set.build_one) — so the SAME recruit resolves to the SAME
    region everywhere this runs: the repo set file, staging, and prod all agree,
    regardless of when the script is run. Recruits with no recruit_id fall back to
    an unseeded draw (should not happen for set recruits)."""
    rng = random.Random(f"region|{recruit_id}") if recruit_id else random
    return rng.choice(region_keys)


def assign_regions(recruits, region_keys, force=False):
    """Stamp Home Region on each recruit in place. Returns (baked, skipped).

    baked   = recruits that received a region.
    skipped = recruits left as-is because they already had one (idempotent);
              always 0 when force=True.
    """
    baked = skipped = 0
    for r in recruits:
        if r.get("Home Region") and not force:
            skipped += 1
            continue
        r["Home Region"] = region_for(r.get("recruit_id"), region_keys)
        baked += 1
    return baked, skipped


def main():
    parser = argparse.ArgumentParser(description="Freeze Home Region into recruit_sets.")
    parser.add_argument("--commit", action="store_true",
                        help="Actually write. Without this the script only reports the plan (dry-run).")
    parser.add_argument("--force", action="store_true",
                        help="Re-randomize recruits that ALREADY have a Home Region. "
                             "Destroys frozen values — only for a deliberate re-bake.")
    parser.add_argument("--set-id", default=None,
                        help="Limit to a single set_id (default: all sets in the collection).")
    args = parser.parse_args()

    # Import after arg parsing so --help works without a DB. BackEnd.db reads
    # MONGO_URI (or falls back to mongomock) exactly like the loader.
    from BackEnd.db import db, client

    is_mock = "mongomock" in type(client).__module__
    banner = f"DB: {db.name} | conn: {'MOCK (no MONGO_URI)' if is_mock else 'REAL'}"
    print("=" * len(banner))
    print(banner)
    print("=" * len(banner))
    if is_mock:
        print("⚠️  Connected to mongomock — MONGO_URI is not set. Nothing real will be written.",
              file=sys.stderr)

    query = {"set_id": args.set_id} if args.set_id else {}
    sets = list(db.recruit_sets.find(query))
    if not sets:
        print(f"No recruit_sets found{' for set_id=' + args.set_id if args.set_id else ''}.")
        return

    total_baked = total_skipped = total_written = 0
    for set_doc in sets:
        set_id = set_doc.get("set_id", "<no set_id>")
        recruits = set_doc.get("recruits") or []
        baked, skipped = assign_regions(recruits, REGION_KEYS, force=args.force)
        total_baked += baked
        total_skipped += skipped
        action = "would bake" if not args.commit else "baked"
        print(f"  {set_id}: {action} {baked}, left {skipped} already-frozen "
              f"({len(recruits)} recruits total)")
        if args.commit and baked:
            new_version = int(set_doc.get("version", 1) or 1) + 1
            db.recruit_sets.update_one(
                {"_id": set_doc["_id"]},
                {"$set": {"recruits": recruits, "version": new_version}},
            )
            total_written += 1
            print(f"    ✔ wrote {set_id} (version -> {new_version})")

    print("-" * 40)
    print(f"Sets: {len(sets)} | recruits baked: {total_baked} | already-frozen: {total_skipped}")
    if args.commit:
        print(f"Committed: {total_written} set doc(s) updated.")
    else:
        print("DRY-RUN — nothing written. Re-run with --commit to persist.")


if __name__ == "__main__":
    main()
