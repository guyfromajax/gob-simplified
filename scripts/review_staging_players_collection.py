"""
Read-only review of gob-staging.players to explain extra docs (e.g. 1995 vs expected 1536).

Reports:
- Total player docs, expected (128 * 12)
- Unique player_ids referenced in teams.player_ids
- Orphans: player docs whose _id is not in any team's player_ids
- Duplicates: same (first_name, last_name, team) with different _ids (hex vs uuid pairs)
- _id type counts: 24-char hex vs UUID

Run from repo root: python3 scripts/review_staging_players_collection.py
"""
import os
import sys
from collections import defaultdict

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
    s = str(val)
    if len(s) != 24:
        return False
    return all(c in "0123456789abcdef" for c in s.lower())


def main():
    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI not set.")
        sys.exit(1)

    client = MongoClient(uri)
    staging = client["gob-staging"]
    players = list(staging["players"].find({}))
    teams = list(staging["teams"].find({}, {"_id": 1, "name": 1, "player_ids": 1}))

    total = len(players)
    expected = 128 * 12
    print(f"=== gob-staging.players ===\n")
    print(f"Total player docs:     {total}")
    print(f"Expected (128*12):     {expected}")
    print(f"Difference:            {total - expected} extra\n")

    # All player_ids referenced by teams
    all_pids = []
    for t in teams:
        pids = t.get("player_ids") or []
        all_pids.extend(str(pid) for pid in pids)
    unique_in_teams = set(all_pids)
    print(f"Unique player_ids in teams.player_ids: {len(unique_in_teams)}")
    print(f"Total roster slots (sum of len(player_ids)): {len(all_pids)}\n")

    # Orphans: player _id not in any team
    player_ids_set = {str(p.get("_id")) for p in players if p.get("_id") is not None}
    orphans = player_ids_set - unique_in_teams
    print(f"Orphans (player _id not in any team's player_ids): {len(orphans)}")
    if orphans and len(orphans) <= 20:
        for o in sorted(orphans):
            print(f"  - {o}")
    elif orphans:
        print(f"  (first 20) {sorted(orphans)[:20]}")
    print()

    # Referenced in teams but no player doc
    missing_docs = unique_in_teams - player_ids_set
    print(f"Referenced in teams but no player doc: {len(missing_docs)}")
    if missing_docs and len(missing_docs) <= 10:
        for m in sorted(missing_docs):
            print(f"  - {m}")
    elif missing_docs:
        print(f"  (first 10) {sorted(missing_docs)[:10]}")
    print()

    # _id type: hex vs uuid
    hex_count = sum(1 for p in players if _is_hex_id(p.get("_id")))
    uuid_count = sum(1 for p in players if p.get("_id") and not _is_hex_id(str(p.get("_id"))))
    print(f"_id type: 24-char hex: {hex_count}, UUID (or other): {uuid_count}\n")

    # Duplicates: same (first_name, last_name, team), multiple _ids
    by_key = defaultdict(list)
    for p in players:
        fn = (p.get("first_name") or "").strip()
        ln = (p.get("last_name") or "").strip()
        team = (p.get("team") or "").strip()
        key = (fn.lower(), ln.lower(), team.lower())
        by_key[key].append((str(p.get("_id")), _is_hex_id(p.get("_id"))))

    dupes = {k: v for k, v in by_key.items() if len(v) > 1}
    total_dupe_docs = sum(len(v) for v in dupes.values())
    print(f"Duplicate (first_name, last_name, team) keys: {len(dupes)}")
    print(f"Total docs in those groups: {total_dupe_docs} (so {total_dupe_docs - len(dupes)} extra docs)\n")

    if dupes:
        print("Sample duplicate groups (name, team -> list of _ids, hex?):")
        for i, (key, ids) in enumerate(sorted(dupes.items(), key=lambda x: -len(x[1]))[:15]):
            fn, ln, team = key
            print(f"  {fn} {ln} @ {team}: {len(ids)} docs -> {[(id_, 'hex' if h else 'uuid') for id_, h in ids[:5]]}{'...' if len(ids) > 5 else ''}")

    print("\nDone.")


if __name__ == "__main__":
    main()
