"""
Copy all players from gob.players to gob-staging.players and assign them to the
correct teams in gob-staging (by matching team name). Use when gob has the 96
Conference 1 players and gob-staging needs them.

- Reads from DB 'gob', writes to DB 'gob-staging' (same MONGO_URI).
- For each player, sets team_id to the gob-staging team _id (lookup by player's team name).
- Upserts into gob-staging.players by _id (safe to re-run).
- Updates gob-staging.teams: for each team that has any of these players, sets
  player_ids to the list of those players' _ids.

SAFETY: This script NEVER deletes any documents. It only inserts/updates.
Run from repo root: python3 scripts/copy_gob_players_to_staging.py
"""
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
sys.path.insert(0, _root)
os.chdir(_root)


def _load_env(filepath):
    out = {}
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip('"').strip("'")
    return out


for path in [".env.local", ".env"]:
    for k, v in _load_env(path).items():
        os.environ.setdefault(k, v)

from BackEnd.db import client

SRC_DB = "gob"
DST_DB = "gob-staging"


def main():
    if not client:
        print("❌ MongoDB client not available.")
        sys.exit(1)

    src_players_coll = client[SRC_DB]["players"]
    dst_players_coll = client[DST_DB]["players"]
    dst_teams_coll = client[DST_DB]["teams"]

    # 1) Load all players from gob
    src_players = list(src_players_coll.find({}))
    print(f"[{SRC_DB}] Found {len(src_players)} player(s).")
    if not src_players:
        print("Nothing to copy.")
        sys.exit(0)

    # 2) Build staging team name -> _id
    staging_teams = list(dst_teams_coll.find({}, {"_id": 1, "name": 1}))
    name_to_staging_id = {t["name"]: t["_id"] for t in staging_teams if t.get("name")}
    print(f"[{DST_DB}] Loaded {len(name_to_staging_id)} teams for name lookup.")

    # 3) Prepare docs for staging: set team_id to staging team _id; keep _id for upsert
    team_name_to_player_ids = {}  # staging team name -> [player _id, ...]
    ops = []
    for p in src_players:
        team_name = (p.get("team") or "").strip()
        if not team_name:
            print(f"  ⚠️ Skipping player _id={p['_id']}: no team name.")
            continue
        staging_team_id = name_to_staging_id.get(team_name)
        if not staging_team_id:
            print(f"  ⚠️ No staging team named '{team_name}' for player _id={p['_id']}; skipping.")
            continue
        doc = dict(p)
        doc["team_id"] = staging_team_id
        ops.append(doc)
        team_name_to_player_ids.setdefault(team_name, []).append(p["_id"])

    if not ops:
        print("❌ No players to insert (all skipped).")
        sys.exit(1)

    # 4) Upsert into gob-staging.players (by _id)
    from pymongo import ReplaceOne
    bulk = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in ops]
    result = dst_players_coll.bulk_write(bulk, ordered=False)
    print(f"[{DST_DB}] Players: {result.upserted_count} inserted, {result.modified_count} replaced.")

    # 5) Update staging teams: set player_ids for teams that have any of these players
    updated = 0
    for team_name, player_ids in team_name_to_player_ids.items():
        r = dst_teams_coll.update_one(
            {"name": team_name},
            {"$set": {"player_ids": player_ids}},
        )
        if r.modified_count:
            updated += 1
    print(f"[{DST_DB}] Updated player_ids on {updated} team(s).")
    print("Done.")


if __name__ == "__main__":
    main()
