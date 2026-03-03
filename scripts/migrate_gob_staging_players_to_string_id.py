"""
Migrate gob-staging.players so document shape matches gob (production):
- _id: ObjectId -> string (24-char hex, str(existing ObjectId))
- Add player_id: string (same as _id)
- Set photo: "/static/images/players/{_id}.png"

Also updates:
- teams.player_ids: each element ObjectId -> string

Does not update FTD or FPD (franchise_team_data, franchise_players_data).

MongoDB does not allow updating _id in place, so we insert new docs (string _id)
then delete old docs (ObjectId _id).

SAFETY: Run only against gob-staging. Requires --yes.
Usage (from repo root):
  MONGO_URI="..." MONGO_DB_NAME=gob-staging python3 scripts/migrate_gob_staging_players_to_string_id.py --yes
"""
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
sys.path.insert(0, _root)
os.chdir(_root)

# Load env
for path in [".env.local", ".env"]:
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from pymongo import MongoClient
from bson import ObjectId

def main():
    if "--yes" not in sys.argv:
        print("This script migrates player _id from ObjectId to string and updates teams/FPD.")
        print("Run with --yes to confirm. Target DB should be gob-staging (MONGO_DB_NAME).")
        sys.exit(1)

    uri = os.environ.get("MONGO_URI")
    db_name = os.environ.get("MONGO_DB_NAME", "gob")
    if not uri:
        print("MONGO_URI not set.")
        sys.exit(1)
    if db_name != "gob-staging":
        print(f"MONGO_DB_NAME is '{db_name}'. This script is intended for gob-staging.")
        print("Set MONGO_DB_NAME=gob-staging and re-run.")
        sys.exit(1)

    client = MongoClient(uri)
    db = client[db_name]
    players_coll = db["players"]
    teams_coll = db["teams"]

    # 1) Update teams: player_ids ObjectId -> string
    teams = list(teams_coll.find({}, {"_id": 1, "player_ids": 1}))
    for t in teams:
        pids = t.get("player_ids") or []
        if not pids:
            continue
        new_pids = [str(pid) for pid in pids]
        if new_pids == pids:
            continue
        teams_coll.update_one(
            {"_id": t["_id"]},
            {"$set": {"player_ids": new_pids}},
        )
    print(f"[{db_name}] Updated player_ids (to string) on {len(teams)} team(s).")

    # 2) Replace each player doc: new _id (string), player_id, photo
    players = list(players_coll.find({}))
    print(f"[{db_name}] Found {len(players)} player(s). Migrating _id to string and setting player_id/photo.")
    inserted = 0
    deleted = 0
    for doc in players:
        old_id = doc["_id"]
        if isinstance(old_id, str):
            # Already string (e.g. re-run); ensure player_id and photo
            players_coll.update_one(
                {"_id": old_id},
                {
                    "$set": {
                        "player_id": old_id,
                        "photo": f"/static/images/players/{old_id}.png",
                    }
                },
            )
            continue
        # ObjectId -> string
        new_id = str(old_id)
        new_doc = dict(doc)
        new_doc["_id"] = new_id
        new_doc["player_id"] = new_id
        new_doc["photo"] = f"/static/images/players/{new_id}.png"
        # team_id: convert to string if ObjectId so JSON serialization is consistent
        if "team_id" in new_doc and isinstance(new_doc["team_id"], ObjectId):
            new_doc["team_id"] = str(new_doc["team_id"])
        # Remove the old doc then insert new (avoid duplicate _id key during insert)
        players_coll.delete_one({"_id": old_id})
        players_coll.insert_one(new_doc)
        inserted += 1
        deleted += 1
    print(f"[{db_name}] Players: {deleted} replaced (ObjectId -> string), document shape now matches gob.")
    print("Done.")


if __name__ == "__main__":
    main()
