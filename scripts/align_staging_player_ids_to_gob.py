"""
Align gob-staging.players _id (and player_id, photo) to match gob.players for the same 96 players,
so the same image files (UUID-named) work for both DBs.

- Reads from gob.players to get UUID _ids (96 players).
- Matches gob-staging.players by (first_name, last_name, team) to build hex_id -> uuid mapping.
- Updates gob-staging.teams: replace any player_ids that are in the mapping (hex -> uuid).
- Updates gob-staging.franchise_players_data: replace player_id hex -> uuid when in mapping.
- Replaces each matched gob-staging player doc: delete doc with hex _id, insert new doc with
  _id=uuid, player_id=uuid, photo=/static/images/players/{uuid}.png (rest of fields copied).

Requires --yes. Uses MONGO_URI; reads from 'gob', writes to 'gob-staging'.
Run from repo root: MONGO_DB_NAME=gob-staging python3 scripts/align_staging_player_ids_to_gob.py --yes
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from BackEnd.script_db import connect_script_database


def _key(p):
    """Normalize for matching: (first_name, last_name, team) lowercased and stripped."""
    fn = (p.get("first_name") or "").strip().lower()
    ln = (p.get("last_name") or "").strip().lower()
    team = (p.get("team") or "").strip().lower()
    return (fn, ln, team)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write staging changes; default is dry-run")
    args = parser.parse_args()
    pristine_env = dict(os.environ)
    production_connection = connect_script_database(
        target="gob", access="read", pristine_env=pristine_env, repo_root=ROOT
    )
    staging_connection = connect_script_database(
        target="gob-staging",
        access="write" if args.apply else "read",
        pristine_env=pristine_env,
        repo_root=ROOT,
        force_local_staging=True,
    )
    gob = production_connection.database
    staging = staging_connection.database
    gob_players = list(gob["players"].find({}))
    staging_players = list(staging["players"].find({}))

    # Map: (first_name, last_name, team) -> gob player _id (UUID string)
    gob_by_key = {}
    for p in gob_players:
        k = _key(p)
        if k in gob_by_key:
            continue  # first wins
        uid = p.get("_id")
        if uid is not None:
            gob_by_key[k] = str(uid)

    # Build hex_id -> uuid for staging players that match gob
    hex_to_uuid = {}
    for p in staging_players:
        k = _key(p)
        uuid_val = gob_by_key.get(k)
        if uuid_val is None:
            continue
        old_id = p.get("_id")
        if old_id is not None:
            hex_to_uuid[str(old_id)] = uuid_val

    print(f"[gob] Players: {len(gob_players)}")
    print(f"[gob-staging] Players: {len(staging_players)}")
    print(f"[align] Matched (hex -> uuid): {len(hex_to_uuid)}")

    if not hex_to_uuid:
        print("No matches. Check first_name, last_name, team alignment between DBs.")
        production_connection.close()
        staging_connection.close()
        return

    if not args.apply:
        print(f"DRY RUN: would align {len(hex_to_uuid)} players and dependent staging references.")
        production_connection.close()
        staging_connection.close()
        return

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

    # 3) Replace matched player docs: delete hex doc, insert uuid doc
    replaced = 0
    for p in staging_players:
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
    print(f"[gob-staging] Players: replaced {replaced} doc(s) with gob UUID _id/player_id/photo.")
    print("Done.")
    production_connection.close()
    staging_connection.close()


if __name__ == "__main__":
    main()
