"""
Delete orphan player docs from gob-staging.players: those whose _id is not
in any team's player_ids (leftover duplicates from the UUID migration).

Requires --yes to perform deletes. Without --yes, reports how many would be deleted.
Run from repo root: python3 scripts/delete_orphan_staging_players.py [--yes]
"""
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
sys.path.insert(0, _root)
os.chdir(_root)

for path in [".env.local", ".env"]:
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from pymongo import MongoClient


def main():
    dry_run = "--yes" not in sys.argv
    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI not set.")
        sys.exit(1)

    client = MongoClient(uri)
    staging = client["gob-staging"]

    # All player_ids that teams reference
    teams = list(staging["teams"].find({}, {"player_ids": 1}))
    referenced = set()
    for t in teams:
        for pid in t.get("player_ids") or []:
            referenced.add(str(pid))

    # Orphans: player _id not in referenced
    players = list(staging["players"].find({}, {"_id": 1}))
    orphan_ids = [p["_id"] for p in players if str(p["_id"]) not in referenced]

    print(f"Player docs referenced by teams: {len(referenced)}")
    print(f"Orphan player docs (not in any team): {len(orphan_ids)}")

    if not orphan_ids:
        print("Nothing to delete.")
        return

    if dry_run:
        print("\nDry run. Run with --yes to delete these orphans.")
        sys.exit(0)

    result = staging["players"].delete_many({"_id": {"$in": orphan_ids}})
    print(f"\nDeleted {result.deleted_count} orphan player doc(s).")
    print("Done.")


if __name__ == "__main__":
    main()
