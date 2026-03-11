"""
Assign UUID _id (and player_id, photo) to the remaining 1440 gob-staging players
that still have 24-char hex ids, so all 1536 use UUIDs and match the id scheme of gob.

- Detects staging players with 24-char hex _id (not already UUID).
- Assigns each a new UUID. Does NOT add them to gob (gob has only 96); when you add
  to gob later you can use these same UUIDs.
- Updates gob-staging.teams: replace hex with new uuid in player_ids.
- Updates gob-staging.franchise_players_data: replace player_id hex -> uuid.
- Replaces each of the 1440 player docs: delete hex doc, insert new doc with uuid.

Requires --yes. Writes only to gob-staging.
Run from repo root: python3 scripts/align_staging_remaining_1440_to_uuid.py --yes
"""
import os
import sys
import uuid as uuid_module

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


def _is_hex_id(val):
    """True if _id looks like 24-char hex (old staging id), not UUID."""
    s = str(val)
    if len(s) != 24:
        return False
    return all(c in "0123456789abcdef" for c in s.lower())


def main():
    if "--yes" not in sys.argv:
        print("Assigns UUIDs to the 1440 staging players that still have hex ids. Requires --yes.")
        sys.exit(1)

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI not set.")
        sys.exit(1)

    client = MongoClient(uri)
    staging = client["gob-staging"]
    staging_players = list(staging["players"].find({}))

    # Only those with 24-char hex _id
    hex_players = [p for p in staging_players if _is_hex_id(p.get("_id"))]
    print(f"[gob-staging] Players: {len(staging_players)} total, {len(hex_players)} with hex _id (to update).")

    if not hex_players:
        print("No hex-id players left. Nothing to do.")
        sys.exit(0)

    # Assign new UUID to each (deterministic order so we can re-run safely: sort by _id)
    hex_players.sort(key=lambda p: str(p.get("_id", "")))
    hex_to_uuid = {}
    for p in hex_players:
        old_id = p.get("_id")
        if old_id is None:
            continue
        old_id_str = str(old_id)
        if old_id_str in hex_to_uuid:
            continue
        hex_to_uuid[old_id_str] = str(uuid_module.uuid4())

    # 1) Update teams: replace hex with uuid in player_ids
    teams = list(staging["teams"].find({}, {"_id": 1, "player_ids": 1}))
    teams_updated = 0
    for t in teams:
        pids = t.get("player_ids") or []
        if not pids:
            continue
        new_pids = [hex_to_uuid.get(str(pid), pid) for pid in pids]
        if new_pids != pids:
            staging["teams"].update_one(
                {"_id": t["_id"]},
                {"$set": {"player_ids": new_pids}},
            )
            teams_updated += 1
    print(f"[gob-staging] Teams: updated player_ids in {teams_updated} team(s).")

    # 2) Update franchise_players_data: player_id hex -> uuid
    fpd_cursor = staging["franchise_players_data"].find({}, {"_id": 1, "player_id": 1})
    fpd_updated = 0
    for d in fpd_cursor:
        pid = d.get("player_id")
        if pid is None:
            continue
        new_pid = hex_to_uuid.get(str(pid))
        if new_pid is not None:
            staging["franchise_players_data"].update_one(
                {"_id": d["_id"]},
                {"$set": {"player_id": new_pid}},
            )
            fpd_updated += 1
    print(f"[gob-staging] FPD: updated player_id in {fpd_updated} doc(s).")

    # 3) Replace each hex player doc: delete old, insert new with uuid
    replaced = 0
    for p in hex_players:
        old_id = p.get("_id")
        if old_id is None:
            continue
        old_id_str = str(old_id)
        uuid_val = hex_to_uuid.get(old_id_str)
        if uuid_val is None:
            continue
        new_doc = dict(p)
        new_doc["_id"] = uuid_val
        new_doc["player_id"] = uuid_val
        new_doc["photo"] = f"/static/images/players/{uuid_val}.png"
        if "team_id" in new_doc and not isinstance(new_doc["team_id"], str):
            new_doc["team_id"] = str(new_doc["team_id"])
        staging["players"].delete_one({"_id": old_id})
        staging["players"].insert_one(new_doc)
        replaced += 1
    print(f"[gob-staging] Players: replaced {replaced} doc(s) with UUID _id/player_id/photo.")
    print("Done.")


if __name__ == "__main__":
    main()
